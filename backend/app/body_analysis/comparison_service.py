from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from numbers import Real
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.body_analysis.comparison_enums import BodyProgressState
from app.body_analysis.comparison_models import BodyProgressComparison
from app.body_analysis.comparison_schemas import (
    BodyProgressAreaComparison,
    BodyProgressComparisonContext,
    BodyProgressItemProvenance,
    BodyProgressMeasurementDelta,
    BodyProgressPersistentPriority,
    BodyProgressProvenance,
    BodyProgressVisualTransition,
    ComparisonInputQuality,
    NormalizedBodyProgressComparison,
    NormalizedBodyProgressComparisonV2,
    UserReportedMeasurementChange,
)
from app.body_analysis.enums import BodyAnalysisClassification, BodyAnalysisStatus, BodyArea
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion
from app.body_analysis.schemas import BodyAnalysisFinding, NormalizedBodyAnalysis
from app.body_photos.enums import BodyPhotoSessionState
from app.body_photos.models import BodyPhoto, BodyPhotoSession
from app.profile.models import BodyMeasurement
from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleFeedback


class BodyProgressComparisonNotFoundError(LookupError):
    pass


class BodyProgressComparisonPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    minimum_change_confidence: float = Field(default=0.6, ge=0, le=1)


@dataclass(frozen=True)
class _ResultInput:
    session: BodyPhotoSession
    analysis: BodyAnalysis
    version: BodyAnalysisResultVersion
    normalized: NormalizedBodyAnalysis
    quality: ComparisonInputQuality
    measurement_evidence: _MeasurementEvidence | None


@dataclass(frozen=True)
class _MeasurementEvidence:
    source: Literal["body_analysis_input_snapshot", "cycle_measurement"]
    reference_id: UUID
    recorded_at: datetime
    values: dict[str, float | None]
    reason_code: Literal["exact_analysis_input_snapshot", "exact_cycle_measurement"]


_CLASSIFICATION_RANK = {
    BodyAnalysisClassification.CLEAR_LAG: 0,
    BodyAnalysisClassification.MILD_LAG: 1,
    BodyAnalysisClassification.NEUTRAL: 2,
    BodyAnalysisClassification.STRENGTH: 3,
}


class BodyProgressComparisonService:
    """Build deterministic progress records without reading or comparing image pixels."""

    def __init__(
        self,
        db: Session,
        policy: BodyProgressComparisonPolicy | None = None,
    ) -> None:
        self._db = db
        self._policy = policy or BodyProgressComparisonPolicy()

    def create_for_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> BodyProgressComparison | None:
        session = self._owner_session(session_id, user_id)
        current = self._latest_eligible_result(session, user_id)
        if current is None:
            return None
        return self.create_for_result(current.version.id, user_id)

    def create_for_result(
        self,
        current_result_version_id: UUID,
        user_id: UUID,
    ) -> BodyProgressComparison | None:
        current = self._result_input(current_result_version_id, user_id)
        # Serialize comparison versions for a session and make repeat job delivery safe.
        self._owner_session(current.session.id, user_id, lock=True)
        existing = self._db.scalar(
            select(BodyProgressComparison).where(
                BodyProgressComparison.current_result_version_id == current_result_version_id,
                BodyProgressComparison.user_id == user_id,
            )
        )
        if existing is not None:
            return existing
        previous = self._previous_eligible_result(current.session, user_id)
        if previous is None:
            return None

        previous_feedback = self._feedback_at(user_id, previous.session.created_at)
        current_feedback = self._feedback_at(user_id, current.session.created_at)
        context = self._context(previous_feedback, current_feedback)
        normalized = self._comparison_for_results(previous, current)
        next_version = (
            int(
                self._db.scalar(
                    select(
                        func.coalesce(func.max(BodyProgressComparison.comparison_version), 0)
                    ).where(BodyProgressComparison.current_session_id == current.session.id)
                )
                or 0
            )
            + 1
        )
        comparison = BodyProgressComparison(
            user_id=user_id,
            previous_session_id=previous.session.id,
            current_session_id=current.session.id,
            previous_result_version_id=previous.version.id,
            current_result_version_id=current.version.id,
            previous_feedback_id=previous_feedback.id if previous_feedback else None,
            current_feedback_id=current_feedback.id if current_feedback else None,
            comparison_version=next_version,
            schema_version=normalized.schema_version,
            normalized_result=normalized.model_dump(mode="json"),
            quality_snapshot={
                "previous": previous.quality.model_dump(mode="json"),
                "current": current.quality.model_dump(mode="json"),
            },
            context_snapshot=context.model_dump(mode="json"),
        )
        self._db.add(comparison)
        try:
            self._db.commit()
            self._db.refresh(comparison)
        except IntegrityError:
            self._db.rollback()
            existing = self._db.scalar(
                select(BodyProgressComparison).where(
                    BodyProgressComparison.current_result_version_id == current_result_version_id,
                    BodyProgressComparison.user_id == user_id,
                )
            )
            if existing is None:
                raise
            return existing
        return comparison

    def compare_result_versions(
        self,
        previous_result_version_id: UUID,
        current_result_version_id: UUID,
        user_id: UUID,
    ) -> NormalizedBodyProgressComparison | NormalizedBodyProgressComparisonV2:
        """Reuse the normalized analysis comparison for an explicit start/end pair."""
        previous = self._result_input(previous_result_version_id, user_id)
        current = self._result_input(current_result_version_id, user_id)
        return self._comparison_for_results(previous, current)

    def _owner_session(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        lock: bool = False,
    ) -> BodyPhotoSession:
        statement = select(BodyPhotoSession).where(
            BodyPhotoSession.id == session_id,
            BodyPhotoSession.user_id == user_id,
            BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
        )
        if lock:
            statement = statement.with_for_update()
        session = self._db.scalar(statement)
        if session is None:
            raise BodyProgressComparisonNotFoundError
        return session

    def _result_input(self, version_id: UUID, user_id: UUID) -> _ResultInput:
        version = self._db.get(BodyAnalysisResultVersion, version_id)
        if version is None:
            raise BodyProgressComparisonNotFoundError
        analysis = self._db.get(BodyAnalysis, version.analysis_id)
        if analysis is None or analysis.status not in {
            BodyAnalysisStatus.REVIEW_PENDING,
            BodyAnalysisStatus.COMPLETED,
        }:
            raise BodyProgressComparisonNotFoundError
        session = self._owner_session(analysis.session_id, user_id)
        return _ResultInput(
            session=session,
            analysis=analysis,
            version=version,
            normalized=NormalizedBodyAnalysis.model_validate(version.normalized_result),
            quality=self._quality(session.id, version.overall_confidence),
            measurement_evidence=self._measurement_evidence(analysis, user_id),
        )

    def _latest_eligible_result(
        self,
        session: BodyPhotoSession,
        user_id: UUID,
    ) -> _ResultInput | None:
        analyses = self._db.scalars(
            select(BodyAnalysis)
            .where(
                BodyAnalysis.session_id == session.id,
                BodyAnalysis.status.in_(
                    [BodyAnalysisStatus.REVIEW_PENDING, BodyAnalysisStatus.COMPLETED]
                ),
            )
            .order_by(BodyAnalysis.revision.desc())
        ).all()
        for analysis in analyses:
            version = self._db.scalar(
                select(BodyAnalysisResultVersion)
                .where(BodyAnalysisResultVersion.analysis_id == analysis.id)
                .order_by(BodyAnalysisResultVersion.version.desc())
                .limit(1)
            )
            if version is not None:
                return _ResultInput(
                    session=session,
                    analysis=analysis,
                    version=version,
                    normalized=NormalizedBodyAnalysis.model_validate(version.normalized_result),
                    quality=self._quality(session.id, version.overall_confidence),
                    measurement_evidence=self._measurement_evidence(analysis, user_id),
                )
        return None

    def _previous_eligible_result(
        self,
        current_session: BodyPhotoSession,
        user_id: UUID,
    ) -> _ResultInput | None:
        candidates = self._db.scalars(
            select(BodyPhotoSession)
            .where(
                BodyPhotoSession.user_id == user_id,
                BodyPhotoSession.id != current_session.id,
                BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
                or_(
                    BodyPhotoSession.created_at < current_session.created_at,
                    and_(
                        BodyPhotoSession.created_at == current_session.created_at,
                        BodyPhotoSession.id < current_session.id,
                    ),
                ),
            )
            .order_by(BodyPhotoSession.created_at.desc(), BodyPhotoSession.id.desc())
        ).all()
        for session in candidates:
            result = self._latest_eligible_result(session, user_id)
            if result is not None:
                return result
        return None

    def _measurement_evidence(
        self,
        analysis: BodyAnalysis,
        user_id: UUID,
    ) -> _MeasurementEvidence | None:
        if analysis.schema_version == "4.0":
            raw_result = analysis.raw_result
            raw_snapshot = (
                raw_result.get("input_snapshot") if isinstance(raw_result, dict) else None
            )
            if not isinstance(raw_snapshot, dict):
                return None
            try:
                from app.body_analysis.service import BodyAnalysisInputSnapshot

                snapshot = BodyAnalysisInputSnapshot.model_validate(raw_snapshot)
            except (TypeError, ValueError):
                return None
            return _MeasurementEvidence(
                source="body_analysis_input_snapshot",
                reference_id=snapshot.measurement_id,
                recorded_at=snapshot.measurement_measured_at,
                values={
                    "weight_kg": snapshot.weight_kg,
                    "shoulder_circumference_cm": snapshot.shoulder_circumference_cm,
                    "waist_circumference_cm": snapshot.waist_circumference_cm,
                    "hip_circumference_cm": snapshot.hip_circumference_cm,
                },
                reason_code="exact_analysis_input_snapshot",
            )

        if analysis.cycle_id is None:
            return None
        measurement = self._db.scalar(
            select(BodyMeasurement)
            .where(
                BodyMeasurement.user_id == user_id,
                BodyMeasurement.cycle_id == analysis.cycle_id,
            )
            .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
            .limit(1)
        )
        if measurement is None:
            return None
        return _MeasurementEvidence(
            source="cycle_measurement",
            reference_id=measurement.id,
            recorded_at=measurement.measured_at,
            values={
                "weight_kg": self._measurement_value(measurement.weight_kg),
                "shoulder_circumference_cm": self._measurement_value(
                    measurement.shoulder_circumference_cm
                ),
                "waist_circumference_cm": self._measurement_value(
                    measurement.waist_circumference_cm
                ),
                "hip_circumference_cm": self._measurement_value(
                    measurement.hip_circumference_cm
                ),
            },
            reason_code="exact_cycle_measurement",
        )

    @staticmethod
    def _measurement_value(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            return None
        return round(float(value), 2)

    def _comparison_for_results(
        self,
        previous: _ResultInput,
        current: _ResultInput,
    ) -> NormalizedBodyProgressComparison | NormalizedBodyProgressComparisonV2:
        if current.analysis.schema_version == "4.0":
            return self._compare_v2(previous, current)
        return self._compare(previous, current)

    def _compare_v2(
        self,
        previous: _ResultInput,
        current: _ResultInput,
    ) -> NormalizedBodyProgressComparisonV2:
        previous_by_area = {finding.body_area: finding for finding in previous.normalized.findings}
        current_by_area = {finding.body_area: finding for finding in current.normalized.findings}
        visual_transitions = tuple(
            self._compare_visual_v2(
                area,
                previous_by_area.get(area),
                current_by_area.get(area),
                previous,
                current,
            )
            for area in BodyArea
        )
        measurement_deltas = tuple(
            self._measurement_delta(
                measurement,
                unit,
                previous.measurement_evidence,
                current.measurement_evidence,
            )
            for measurement, unit in (
                ("weight_kg", "kg"),
                ("shoulder_circumference_cm", "cm"),
                ("waist_circumference_cm", "cm"),
                ("hip_circumference_cm", "cm"),
            )
        )
        confident = [
            item.change_confidence
            for item in visual_transitions
            if item.state is not BodyProgressState.UNCERTAIN
        ]
        return NormalizedBodyProgressComparisonV2(
            overall_confidence=round(sum(confident) / len(confident), 4)
            if confident
            else 0.0,
            previous_session_id=previous.session.id,
            current_session_id=current.session.id,
            previous_result_version_id=previous.version.id,
            current_result_version_id=current.version.id,
            previous_session_date=previous.session.created_at,
            current_session_date=current.session.created_at,
            interval_days=(
                current.session.created_at.date() - previous.session.created_at.date()
            ).days,
            measurement_deltas=measurement_deltas,
            visual_transitions=visual_transitions,
            persistent_priorities=self._persistent_priorities(previous, current),
        )

    def _measurement_delta(
        self,
        measurement: str,
        unit: str,
        previous: _MeasurementEvidence | None,
        current: _MeasurementEvidence | None,
    ) -> BodyProgressMeasurementDelta:
        previous_value = previous.values.get(measurement) if previous else None
        current_value = current.values.get(measurement) if current else None
        exact = previous_value is not None and current_value is not None
        delta: float | None = None
        if previous_value is not None and current_value is not None:
            delta = round(current_value - previous_value, 2)
        return BodyProgressMeasurementDelta(
            measurement=measurement,
            unit=unit,
            previous=previous_value,
            current=current_value,
            delta=delta,
            availability="exact" if exact else "unavailable",
            provenance=BodyProgressItemProvenance(
                previous=self._measurement_provenance(previous),
                current=self._measurement_provenance(current),
            ),
        )

    @staticmethod
    def _measurement_provenance(
        evidence: _MeasurementEvidence | None,
    ) -> BodyProgressProvenance:
        if evidence is None:
            return BodyProgressProvenance(
                source="unavailable",
                reason_code="measurement_unavailable_for_legacy_scan",
            )
        return BodyProgressProvenance(
            source=evidence.source,
            reference_id=evidence.reference_id,
            recorded_at=evidence.recorded_at,
            reason_code=evidence.reason_code,
        )

    @staticmethod
    def _normalized_provenance(result: _ResultInput) -> BodyProgressProvenance:
        return BodyProgressProvenance(
            source="normalized_result",
            reference_id=result.version.id,
            recorded_at=result.version.created_at,
            reason_code="effective_normalized_result",
        )

    def _compare_visual_v2(
        self,
        area: BodyArea,
        previous_finding: BodyAnalysisFinding | None,
        current_finding: BodyAnalysisFinding | None,
        previous: _ResultInput,
        current: _ResultInput,
    ) -> BodyProgressVisualTransition:
        comparison = self._compare_area(
            area,
            previous_finding,
            current_finding,
            previous.quality,
            current.quality,
        )
        reasons: list[str] = []
        if previous_finding is None:
            reasons.append("missing_previous_observation")
        if current_finding is None:
            reasons.append("missing_current_observation")
        if previous_finding is not None and current_finding is not None:
            if previous_finding.classification == current_finding.classification:
                reasons.append("classification_unchanged")
            else:
                reasons.append("classification_changed")
        if (
            not previous.quality.all_standardized_views_present
            or not current.quality.all_standardized_views_present
        ):
            reasons.append("incomplete_standardized_views")
        if (
            previous_finding is not None
            and current_finding is not None
            and not comparison.supporting_views
        ):
            reasons.append("no_common_supporting_view")
        if comparison.change_confidence < self._policy.minimum_change_confidence:
            reasons.append("low_confidence")
        if (
            previous.version.source.value != "ai"
            or current.version.source.value != "ai"
        ):
            reasons.append("specialist_corrected_result")
        return BodyProgressVisualTransition(
            body_area=area,
            state=comparison.state,
            previous_classification=comparison.previous_classification,
            current_classification=comparison.current_classification,
            change_confidence=comparison.change_confidence,
            supporting_views=comparison.supporting_views,
            reason_codes=tuple(dict.fromkeys(reasons)),
            provenance=BodyProgressItemProvenance(
                previous=self._normalized_provenance(previous),
                current=self._normalized_provenance(current),
            ),
        )

    @staticmethod
    def _persistent_priorities(
        previous: _ResultInput,
        current: _ResultInput,
    ) -> tuple[BodyProgressPersistentPriority, ...]:
        previous_priorities = set(previous.normalized.summary.priority_areas)
        current_priorities = set(current.normalized.summary.priority_areas)
        return tuple(
            BodyProgressPersistentPriority(
                body_area=area,
                provenance=BodyProgressItemProvenance(
                    previous=BodyProgressComparisonService._normalized_provenance(previous),
                    current=BodyProgressComparisonService._normalized_provenance(current),
                ),
            )
            for area in BodyArea
            if area in previous_priorities and area in current_priorities
        )

    def _quality(self, session_id: UUID, analysis_confidence: float) -> ComparisonInputQuality:
        photos = self._db.scalars(select(BodyPhoto).where(BodyPhoto.session_id == session_id)).all()
        return ComparisonInputQuality(
            analysis_confidence=analysis_confidence,
            all_standardized_views_present=len(photos) == 3,
        )

    def _compare(
        self,
        previous: _ResultInput,
        current: _ResultInput,
    ) -> NormalizedBodyProgressComparison:
        previous_by_area = {finding.body_area: finding for finding in previous.normalized.findings}
        current_by_area = {finding.body_area: finding for finding in current.normalized.findings}
        areas = tuple(
            self._compare_area(
                area,
                previous_by_area.get(area),
                current_by_area.get(area),
                previous.quality,
                current.quality,
            )
            for area in BodyArea
        )
        confident = [
            area.change_confidence
            for area in areas
            if area.state is not BodyProgressState.UNCERTAIN
        ]
        overall_confidence = round(sum(confident) / len(confident), 4) if confident else 0.0
        counts = {state: sum(area.state is state for area in areas) for state in BodyProgressState}
        summary = (
            f"Visible comparison: {counts[BodyProgressState.IMPROVED]} improved, "
            f"{counts[BodyProgressState.UNCHANGED]} unchanged, "
            f"{counts[BodyProgressState.DECLINED_OR_LESS_BALANCED]} relatively less balanced, "
            f"and {counts[BodyProgressState.UNCERTAIN]} uncertain areas."
        )
        return NormalizedBodyProgressComparison(
            schema_version="1.0",
            overall_confidence=overall_confidence,
            previous_session_id=previous.session.id,
            current_session_id=current.session.id,
            previous_result_version_id=previous.version.id,
            current_result_version_id=current.version.id,
            areas=areas,
            summary=summary,
        )

    def _compare_area(
        self,
        area: BodyArea,
        previous: BodyAnalysisFinding | None,
        current: BodyAnalysisFinding | None,
        previous_quality: ComparisonInputQuality,
        current_quality: ComparisonInputQuality,
    ) -> BodyProgressAreaComparison:
        limitations = {
            limitation.value
            for finding in (previous, current)
            if finding is not None
            for limitation in finding.limitations
        }
        if previous is None:
            limitations.add("missing_previous_finding")
        if current is None:
            limitations.add("missing_current_finding")
        if (
            not previous_quality.all_standardized_views_present
            or not current_quality.all_standardized_views_present
        ):
            limitations.add("incomplete_standardized_views")

        supporting_views = tuple(
            sorted(
                set(previous.supporting_views if previous else ())
                & set(current.supporting_views if current else ()),
                key=lambda view: view.value,
            )
        )
        if previous is not None and current is not None and not supporting_views:
            limitations.add("no_common_supporting_view")

        confidence = self._change_confidence(
            previous,
            current,
            previous_quality,
            current_quality,
        )
        previous_classification = previous.classification if previous else None
        current_classification = current.classification if current else None
        state = BodyProgressState.UNCERTAIN
        if (
            previous is not None
            and current is not None
            and previous.classification is not BodyAnalysisClassification.UNCERTAIN
            and current.classification is not BodyAnalysisClassification.UNCERTAIN
            and confidence >= self._policy.minimum_change_confidence
            and supporting_views
        ):
            previous_rank = _CLASSIFICATION_RANK[previous.classification]
            current_rank = _CLASSIFICATION_RANK[current.classification]
            if current_rank > previous_rank:
                state = BodyProgressState.IMPROVED
            elif current_rank < previous_rank:
                state = BodyProgressState.DECLINED_OR_LESS_BALANCED
            else:
                state = BodyProgressState.UNCHANGED
        else:
            if confidence < self._policy.minimum_change_confidence:
                limitations.add("low_confidence")

        return BodyProgressAreaComparison(
            body_area=area,
            state=state,
            previous_classification=previous_classification,
            current_classification=current_classification,
            change_confidence=confidence,
            supporting_views=supporting_views,
            explanation=self._explanation(area, state),
            limitations=tuple(sorted(limitations)),
        )

    @staticmethod
    def _change_confidence(
        previous: BodyAnalysisFinding | None,
        current: BodyAnalysisFinding | None,
        previous_quality: ComparisonInputQuality,
        current_quality: ComparisonInputQuality,
    ) -> float:
        if previous is None or current is None:
            return 0.0
        confidence_values = [
            previous.confidence,
            current.confidence,
            previous_quality.analysis_confidence,
            current_quality.analysis_confidence,
        ]
        if not (
            previous_quality.all_standardized_views_present
            and current_quality.all_standardized_views_present
        ):
            return 0.0
        return round(min(confidence_values), 4)

    @staticmethod
    def _explanation(area: BodyArea, state: BodyProgressState) -> str:
        label = area.value.replace("_", " ")
        if state is BodyProgressState.IMPROVED:
            return (
                f"Visible {label} development or balance appears improved compared with "
                "the previous standardized session."
            )
        if state is BodyProgressState.UNCHANGED:
            return (
                f"Visible {label} development or balance appears broadly unchanged compared "
                "with the previous standardized session."
            )
        if state is BodyProgressState.DECLINED_OR_LESS_BALANCED:
            return (
                f"Visible {label} development or balance appears relatively less balanced "
                "than in the previous standardized session."
            )
        return f"A reliable visible comparison for {label} is not available."

    def _feedback_at(
        self,
        user_id: UUID,
        at: datetime,
    ) -> WorkoutCycleFeedback | None:
        return self._db.scalar(
            select(WorkoutCycleFeedback)
            .join(WorkoutCycle, WorkoutCycle.id == WorkoutCycleFeedback.cycle_id)
            .where(
                WorkoutCycle.user_id == user_id,
                WorkoutCycle.status == WorkoutCycleStatus.COMPLETED,
                WorkoutCycle.completed_at.is_not(None),
                WorkoutCycle.completed_at <= at,
            )
            .order_by(WorkoutCycle.completed_at.desc(), WorkoutCycleFeedback.id.desc())
            .limit(1)
        )

    @staticmethod
    def _context(
        previous: WorkoutCycleFeedback | None,
        current: WorkoutCycleFeedback | None,
    ) -> BodyProgressComparisonContext:
        previous_measurements = (
            BodyProgressComparisonService._numeric_measurements(previous.measurements)
            if previous
            else {}
        )
        current_measurements = (
            BodyProgressComparisonService._numeric_measurements(current.measurements)
            if current
            else {}
        )
        changes = {
            key: UserReportedMeasurementChange(
                previous=previous_measurements[key],
                current=current_measurements[key],
                delta=round(current_measurements[key] - previous_measurements[key], 4),
            )
            for key in sorted(previous_measurements.keys() & current_measurements.keys())
        }
        return BodyProgressComparisonContext(
            previous_feedback_id=previous.id if previous else None,
            current_feedback_id=current.id if current else None,
            previous_adherence_percent=previous.adherence_percent if previous else None,
            current_adherence_percent=current.adherence_percent if current else None,
            previous_performance_feedback_available=bool(previous and previous.performance_changes),
            current_performance_feedback_available=bool(current and current.performance_changes),
            current_pain_or_limitation_feedback_available=bool(
                current and current.pain_or_limitation_feedback
            ),
            user_reported_measurement_changes=changes,
        )

    @staticmethod
    def _numeric_measurements(measurements: dict[str, object]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for key, value in measurements.items():
            if isinstance(value, bool) or not isinstance(value, Real):
                continue
            number = float(value)
            if math.isfinite(number):
                normalized[key] = number
        return normalized
