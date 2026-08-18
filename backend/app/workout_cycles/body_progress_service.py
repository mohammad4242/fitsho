from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.body_analysis.comparison_enums import BodyProgressState
from app.body_analysis.comparison_schemas import NormalizedBodyProgressComparison
from app.body_analysis.comparison_service import BodyProgressComparisonService
from app.body_analysis.enums import BodyAnalysisStatus, BodyArea
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion
from app.body_photos.enums import BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
from app.profile.models import BodyMeasurement
from app.workout_cycles.body_progress_models import WorkoutCycleBodyProgressComparison
from app.workout_cycles.body_progress_schemas import (
    BodyMeasurementMetricDelta,
    CycleBodyAnalysisComparison,
    CycleBodyMeasurementComparison,
    CycleBodyProgressComparisonResult,
    CycleBodyProgressProvenance,
)
from app.workout_cycles.models import WorkoutCycle
from app.workout_cycles.service import get_cycle_for_user


class WorkoutCycleBodyProgressComparisonNotFoundError(LookupError):
    pass


class _AnalysisSource(NamedTuple):
    session: BodyPhotoSession
    analysis: BodyAnalysis
    version: BodyAnalysisResultVersion


_MEASUREMENT_FIELDS = (
    "weight_kg",
    "shoulder_circumference_cm",
    "waist_circumference_cm",
    "hip_circumference_cm",
)


def compare_cycle_body_progress(
    db: Session,
    *,
    user_id: UUID,
    cycle_id: UUID,
) -> WorkoutCycleBodyProgressComparison:
    cycle = get_cycle_for_user(db, cycle_id=cycle_id, user_id=user_id)
    if cycle is None:
        raise WorkoutCycleBodyProgressComparisonNotFoundError

    start_measurement = _start_measurement(db, cycle)
    end_measurement = _end_measurement(db, cycle)
    start_analysis = _start_analysis(db, cycle)
    end_analysis = _end_analysis(db, cycle)
    result = _build_result(
        db,
        cycle,
        start_measurement=start_measurement,
        end_measurement=end_measurement,
        start_analysis=start_analysis,
        end_analysis=end_analysis,
    )

    comparison = db.scalar(
        select(WorkoutCycleBodyProgressComparison)
        .where(
            WorkoutCycleBodyProgressComparison.cycle_id == cycle.id,
            WorkoutCycleBodyProgressComparison.user_id == user_id,
        )
        .with_for_update()
    )
    if comparison is None:
        comparison = WorkoutCycleBodyProgressComparison(
            user_id=user_id,
            cycle_id=cycle.id,
        )
        db.add(comparison)

    comparison.start_measurement_id = start_measurement.id if start_measurement else None
    comparison.end_measurement_id = end_measurement.id if end_measurement else None
    comparison.start_session_id = start_analysis.session.id if start_analysis else None
    comparison.end_session_id = end_analysis.session.id if end_analysis else None
    comparison.start_analysis_id = start_analysis.analysis.id if start_analysis else None
    comparison.end_analysis_id = end_analysis.analysis.id if end_analysis else None
    comparison.start_result_version_id = start_analysis.version.id if start_analysis else None
    comparison.end_result_version_id = end_analysis.version.id if end_analysis else None
    comparison.schema_version = "1.0"
    comparison.comparison_result = result.model_dump(mode="json")
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return comparison


def _start_measurement(db: Session, cycle: WorkoutCycle) -> BodyMeasurement | None:
    return db.scalar(
        select(BodyMeasurement)
        .where(
            BodyMeasurement.user_id == cycle.user_id,
            BodyMeasurement.measured_at <= cycle.started_at,
        )
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
        .limit(1)
    )


def _end_measurement(db: Session, cycle: WorkoutCycle) -> BodyMeasurement | None:
    return db.scalar(
        select(BodyMeasurement)
        .where(
            BodyMeasurement.user_id == cycle.user_id,
            BodyMeasurement.cycle_id == cycle.id,
        )
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
        .limit(1)
    )


def _start_analysis(db: Session, cycle: WorkoutCycle) -> _AnalysisSource | None:
    sessions = db.scalars(
        select(BodyPhotoSession)
        .where(
            BodyPhotoSession.user_id == cycle.user_id,
            BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
            BodyPhotoSession.created_at <= cycle.started_at,
        )
        .order_by(BodyPhotoSession.created_at.desc(), BodyPhotoSession.id.desc())
    ).all()
    for session in sessions:
        source = _latest_analysis(db, session)
        if source is not None:
            return source
    return None


def _end_analysis(db: Session, cycle: WorkoutCycle) -> _AnalysisSource | None:
    sessions = db.scalars(
        select(BodyPhotoSession)
        .where(
            BodyPhotoSession.user_id == cycle.user_id,
            BodyPhotoSession.cycle_id == cycle.id,
            BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
        )
        .order_by(BodyPhotoSession.created_at.desc(), BodyPhotoSession.id.desc())
    ).all()
    for session in sessions:
        source = _latest_analysis(db, session)
        if source is not None:
            return source
    return None


def _latest_analysis(db: Session, session: BodyPhotoSession) -> _AnalysisSource | None:
    analyses = db.scalars(
        select(BodyAnalysis)
        .where(
            BodyAnalysis.session_id == session.id,
            BodyAnalysis.status.in_(
                (BodyAnalysisStatus.REVIEW_PENDING, BodyAnalysisStatus.COMPLETED)
            ),
        )
        .order_by(BodyAnalysis.revision.desc(), BodyAnalysis.id.desc())
    ).all()
    for analysis in analyses:
        version = db.scalar(
            select(BodyAnalysisResultVersion)
            .where(BodyAnalysisResultVersion.analysis_id == analysis.id)
            .order_by(BodyAnalysisResultVersion.version.desc(), BodyAnalysisResultVersion.id.desc())
            .limit(1)
        )
        if version is not None:
            return _AnalysisSource(session=session, analysis=analysis, version=version)
    return None


def _build_result(
    db: Session,
    cycle: WorkoutCycle,
    *,
    start_measurement: BodyMeasurement | None,
    end_measurement: BodyMeasurement | None,
    start_analysis: _AnalysisSource | None,
    end_analysis: _AnalysisSource | None,
) -> CycleBodyProgressComparisonResult:
    missing_data: list[str] = []
    if start_measurement is None:
        missing_data.append("start_measurement")
    if end_measurement is None:
        missing_data.append("end_measurement")
    if start_analysis is None:
        missing_data.append("start_analysis")
    if end_analysis is None:
        missing_data.append("end_analysis")

    measurement_status = _status(start_measurement is not None, end_measurement is not None)
    metrics = {
        field: _metric_delta(
            getattr(start_measurement, field) if start_measurement else None,
            getattr(end_measurement, field) if end_measurement else None,
        )
        for field in _MEASUREMENT_FIELDS
    }
    measurement = CycleBodyMeasurementComparison(
        status=measurement_status,
        start_measurement_id=start_measurement.id if start_measurement else None,
        end_measurement_id=end_measurement.id if end_measurement else None,
        start_measured_at=start_measurement.measured_at if start_measurement else None,
        end_measured_at=end_measurement.measured_at if end_measurement else None,
        metrics=metrics,
    )

    analysis_comparison = _analysis_comparison(
        db,
        cycle.user_id,
        start_analysis=start_analysis,
        end_analysis=end_analysis,
    )
    body_analysis = CycleBodyAnalysisComparison(
        status=_status(start_analysis is not None, end_analysis is not None),
        start_session_id=start_analysis.session.id if start_analysis else None,
        end_session_id=end_analysis.session.id if end_analysis else None,
        start_analysis_id=start_analysis.analysis.id if start_analysis else None,
        end_analysis_id=end_analysis.analysis.id if end_analysis else None,
        start_result_version_id=start_analysis.version.id if start_analysis else None,
        end_result_version_id=end_analysis.version.id if end_analysis else None,
        start_created_at=start_analysis.session.created_at if start_analysis else None,
        end_created_at=end_analysis.session.created_at if end_analysis else None,
        comparison=analysis_comparison,
        improved_areas=_areas_for_state(analysis_comparison, BodyProgressState.IMPROVED),
        unchanged_areas=_areas_for_state(analysis_comparison, BodyProgressState.UNCHANGED),
        lagging_areas=_areas_for_state(
            analysis_comparison, BodyProgressState.DECLINED_OR_LESS_BALANCED
        ),
    )
    return CycleBodyProgressComparisonResult(
        measurement=measurement,
        body_analysis=body_analysis,
        missing_data=missing_data,
        provenance=CycleBodyProgressProvenance(
            cycle_id=cycle.id,
            cycle_started_at=cycle.started_at,
            cycle_completed_at=cycle.completed_at,
        ),
    )


def _analysis_comparison(
    db: Session,
    user_id: UUID,
    *,
    start_analysis: _AnalysisSource | None,
    end_analysis: _AnalysisSource | None,
) -> NormalizedBodyProgressComparison | None:
    if start_analysis is None or end_analysis is None:
        return None
    return BodyProgressComparisonService(db).compare_result_versions(
        start_analysis.version.id,
        end_analysis.version.id,
        user_id,
    )


def _areas_for_state(
    comparison: NormalizedBodyProgressComparison | None,
    state: BodyProgressState,
) -> list[BodyArea]:
    if comparison is None:
        return []
    return [area.body_area for area in comparison.areas if area.state is state]


def _metric_delta(start: Decimal | None, end: Decimal | None) -> BodyMeasurementMetricDelta:
    start_value = float(start) if start is not None else None
    end_value = float(end) if end is not None else None
    delta = (
        round(end_value - start_value, 4)
        if start_value is not None and end_value is not None
        else None
    )
    return BodyMeasurementMetricDelta(start=start_value, end=end_value, delta=delta)


def _status(has_start: bool, has_end: bool) -> str:
    if has_start and has_end:
        return "complete"
    if has_start:
        return "missing_end"
    if has_end:
        return "missing_start"
    return "missing_both"
