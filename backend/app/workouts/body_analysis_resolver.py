from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.body_analysis.enums import BodyAnalysisClassification, BodyAnalysisStatus, TrainingEmphasis
from app.body_analysis.models import BodyAnalysis
from app.body_analysis.service import (
    BodyAnalysisNotFoundError,
    BodyAnalysisService,
    EffectiveBodyAnalysisResult,
)
from app.body_photos.enums import BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.schemas import BodyAnalysisInfluence, BodyAnalysisPriority


class BodyAnalysisInfluenceResolver(Protocol):
    def resolve(self, user_id: UUID) -> BodyAnalysisInfluence | None: ...


_MUSCLE_BY_EMPHASIS: dict[TrainingEmphasis, MuscleGroup] = {
    TrainingEmphasis.LATERAL_DELTOID: MuscleGroup.SHOULDERS,
    TrainingEmphasis.REAR_DELTOID: MuscleGroup.SHOULDERS,
    TrainingEmphasis.CHEST: MuscleGroup.CHEST,
    TrainingEmphasis.UPPER_CHEST: MuscleGroup.CHEST,
    TrainingEmphasis.BACK_WIDTH: MuscleGroup.BACK,
    TrainingEmphasis.BACK_THICKNESS: MuscleGroup.BACK,
    TrainingEmphasis.BICEPS: MuscleGroup.BICEPS,
    TrainingEmphasis.TRICEPS: MuscleGroup.TRICEPS,
    TrainingEmphasis.FOREARMS: MuscleGroup.FOREARMS,
    TrainingEmphasis.WAIST_MIDSECTION: MuscleGroup.ABS,
    TrainingEmphasis.GLUTES: MuscleGroup.GLUTES,
    TrainingEmphasis.QUADS: MuscleGroup.QUADRICEPS,
    TrainingEmphasis.HAMSTRINGS: MuscleGroup.HAMSTRINGS,
    TrainingEmphasis.CALVES: MuscleGroup.CALVES,
}


class WorkoutBodyAnalysisResolver:
    """Resolves the newest usable result at the workout service boundary."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._analysis_service = BodyAnalysisService(db)

    def resolve(self, user_id: UUID) -> BodyAnalysisInfluence | None:
        analyses = self._db.scalars(
            select(BodyAnalysis)
            .join(BodyPhotoSession, BodyPhotoSession.id == BodyAnalysis.session_id)
            .where(
                BodyPhotoSession.user_id == user_id,
                BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
                BodyAnalysis.status.in_(
                    [BodyAnalysisStatus.REVIEW_PENDING, BodyAnalysisStatus.COMPLETED]
                ),
            )
            .order_by(BodyAnalysis.completed_at.desc().nullslast(), BodyAnalysis.revision.desc())
        ).all()
        visited_sessions: set[UUID] = set()
        for analysis in analyses:
            if analysis.session_id in visited_sessions:
                continue
            visited_sessions.add(analysis.session_id)
            try:
                effective = self._analysis_service.effective_result(
                    analysis.session_id, user_id
                )
            except BodyAnalysisNotFoundError:
                continue
            effective_analysis = self._db.get(BodyAnalysis, effective.analysis_id)
            if effective_analysis is None:
                continue
            return to_body_analysis_influence(
                effective,
                analysis_revision=effective_analysis.revision,
            )
        return None


def to_body_analysis_influence(
    result: EffectiveBodyAnalysisResult,
    *,
    analysis_revision: int,
) -> BodyAnalysisInfluence:
    priorities: dict[MuscleGroup, BodyAnalysisPriority] = {}
    for finding in result.normalized_result.findings:
        if finding.classification not in {
            BodyAnalysisClassification.MILD_LAG,
            BodyAnalysisClassification.CLEAR_LAG,
        }:
            continue
        for emphasis in finding.suggested_training_emphasis:
            muscle = _MUSCLE_BY_EMPHASIS.get(emphasis)
            if muscle is None or finding.severity is None:
                continue
            candidate = BodyAnalysisPriority(
                muscle=muscle,
                classification=finding.classification.value,
                confidence=finding.confidence,
                severity=finding.severity,
                emphasis=(emphasis.value,),
            )
            previous = priorities.get(muscle)
            if previous is None:
                priorities[muscle] = candidate
                continue
            stronger = max(
                (previous, candidate),
                key=lambda item: (
                    item.classification == "clear_lag",
                    item.severity,
                    item.confidence,
                ),
            )
            priorities[muscle] = stronger.model_copy(
                update={
                    "emphasis": tuple(
                        sorted(set(previous.emphasis).union(candidate.emphasis))
                    )
                }
            )
    provenance = result.provenance
    return BodyAnalysisInfluence(
        analysis_id=result.analysis_id,
        result_version_id=result.result_version_id,
        analysis_revision=analysis_revision,
        schema_version=result.normalized_result.schema_version,
        source="ai_provisional" if provenance == "ai_only" else provenance,
        overall_confidence=result.normalized_result.overall_confidence,
        priorities=tuple(
            priorities[muscle] for muscle in sorted(priorities, key=lambda item: item.value)
        ),
    )
