from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exercises.models import ExerciseAlternative
from app.workout_cycles.enums import (
    WorkoutCycleStatus,
    WorkoutExercisePreferenceType,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
    WorkoutExerciseSafetySignalType,
)
from app.workout_cycles.models import (
    WorkoutCycle,
    WorkoutCycleFeedback,
    WorkoutExercisePreference,
    WorkoutExerciseReplacement,
    WorkoutExerciseSafetySignal,
)
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan, WorkoutPlanExercise
from app.workouts.repository import get_plan_for_user

SUPPORTED_CYCLE_DURATIONS = frozenset({4, 6, 8})


class WorkoutCycleNotFoundError(Exception):
    pass


class WorkoutCycleAlreadyCompletedError(Exception):
    pass


class WorkoutCyclePlanInactiveError(Exception):
    pass


class WorkoutExerciseReplacementNoActiveCycleError(Exception):
    pass


class WorkoutExerciseReplacementPlanExerciseNotFoundError(Exception):
    pass


class WorkoutExerciseReplacementSelfError(Exception):
    pass


class WorkoutExerciseReplacementAlternativeNotAllowedError(Exception):
    pass


def calculate_current_week(
    started_at: datetime,
    duration_weeks: int,
    *,
    now: datetime | None = None,
) -> int:
    if duration_weeks < 1:
        raise ValueError("Workout cycle duration must be at least one week")

    current_at = datetime.now(UTC) if now is None else now
    started_at_utc = _as_utc(started_at)
    current_at_utc = _as_utc(current_at)
    elapsed_days = max(0, (current_at_utc - started_at_utc).days)
    return min(duration_weeks, elapsed_days // 7 + 1)


def record_exercise_replacement(
    db: Session,
    *,
    user_id: UUID,
    workout_plan_exercise_id: UUID,
    replacement_exercise_id: UUID,
    reason: WorkoutExerciseReplacementReason,
    scope: WorkoutExerciseReplacementScope,
) -> WorkoutExerciseReplacement:
    cycle = get_current_active_cycle_for_user(db, user_id=user_id)
    if cycle is None:
        raise WorkoutExerciseReplacementNoActiveCycleError

    plan = get_plan_for_user(db, plan_id=cycle.workout_plan_id, user_id=user_id)
    if plan is None or plan.status is not WorkoutPlanStatus.ACTIVE:
        raise WorkoutExerciseReplacementPlanExerciseNotFoundError

    prescribed = next(
        (
            item
            for day in plan.days
            for item in day.exercises
            if item.id == workout_plan_exercise_id
        ),
        None,
    )
    if prescribed is None:
        raise WorkoutExerciseReplacementPlanExerciseNotFoundError

    if replacement_exercise_id == prescribed.exercise_id:
        raise WorkoutExerciseReplacementSelfError
    if replacement_exercise_id not in _allowed_replacement_ids(prescribed):
        raise WorkoutExerciseReplacementAlternativeNotAllowedError

    replacement = WorkoutExerciseReplacement(
        user_id=user_id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        original_exercise_id=prescribed.exercise_id,
        replacement_exercise_id=replacement_exercise_id,
        reason=reason,
        scope=scope,
        week_number=calculate_current_week(cycle.started_at, cycle.duration_weeks),
    )
    db.add(replacement)
    try:
        db.flush()
        _persist_replacement_meaning(db, replacement)
        db.commit()
        db.refresh(replacement)
    except SQLAlchemyError:
        db.rollback()
        raise
    return replacement


def _persist_replacement_meaning(
    db: Session,
    replacement: WorkoutExerciseReplacement,
) -> None:
    if replacement.reason is WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT:
        _ensure_safety_signal(db, replacement)
        return

    if replacement.scope is not WorkoutExerciseReplacementScope.PERSISTENT:
        return

    preference_type = {
        WorkoutExerciseReplacementReason.EQUIPMENT_UNAVAILABLE: (
            WorkoutExercisePreferenceType.EQUIPMENT_UNAVAILABLE
        ),
        WorkoutExerciseReplacementReason.UNCOMFORTABLE: WorkoutExercisePreferenceType.UNCOMFORTABLE,
        WorkoutExerciseReplacementReason.DISLIKE: WorkoutExercisePreferenceType.DISLIKE,
    }.get(replacement.reason)
    if preference_type is not None:
        _ensure_exercise_preference(db, replacement, preference_type)


def _ensure_exercise_preference(
    db: Session,
    replacement: WorkoutExerciseReplacement,
    preference_type: WorkoutExercisePreferenceType,
) -> None:
    existing = db.scalar(
        select(WorkoutExercisePreference).where(
            WorkoutExercisePreference.user_id == replacement.user_id,
            WorkoutExercisePreference.exercise_id == replacement.original_exercise_id,
            WorkoutExercisePreference.preference_type == preference_type,
        )
    )
    if existing is not None:
        return

    preference = WorkoutExercisePreference(
        user_id=replacement.user_id,
        exercise_id=replacement.original_exercise_id,
        preference_type=preference_type,
        source_replacement_id=replacement.id,
    )
    try:
        with db.begin_nested():
            db.add(preference)
            db.flush()
    except IntegrityError:
        if db.scalar(
            select(WorkoutExercisePreference).where(
                WorkoutExercisePreference.user_id == replacement.user_id,
                WorkoutExercisePreference.exercise_id == replacement.original_exercise_id,
                WorkoutExercisePreference.preference_type == preference_type,
            )
        ) is None:
            raise


def _ensure_safety_signal(
    db: Session,
    replacement: WorkoutExerciseReplacement,
) -> None:
    existing = db.scalar(
        select(WorkoutExerciseSafetySignal).where(
            WorkoutExerciseSafetySignal.user_id == replacement.user_id,
            WorkoutExerciseSafetySignal.cycle_id == replacement.cycle_id,
            WorkoutExerciseSafetySignal.workout_plan_exercise_id
            == replacement.workout_plan_exercise_id,
            WorkoutExerciseSafetySignal.replacement_exercise_id
            == replacement.replacement_exercise_id,
            WorkoutExerciseSafetySignal.week_number == replacement.week_number,
            WorkoutExerciseSafetySignal.signal_type
            == WorkoutExerciseSafetySignalType.PAIN_OR_DISCOMFORT,
        )
    )
    if existing is not None:
        return

    signal = WorkoutExerciseSafetySignal(
        user_id=replacement.user_id,
        cycle_id=replacement.cycle_id,
        workout_plan_exercise_id=replacement.workout_plan_exercise_id,
        original_exercise_id=replacement.original_exercise_id,
        replacement_exercise_id=replacement.replacement_exercise_id,
        signal_type=WorkoutExerciseSafetySignalType.PAIN_OR_DISCOMFORT,
        week_number=replacement.week_number,
        source_replacement_id=replacement.id,
    )
    try:
        with db.begin_nested():
            db.add(signal)
            db.flush()
    except IntegrityError:
        if db.scalar(
            select(WorkoutExerciseSafetySignal).where(
                WorkoutExerciseSafetySignal.user_id == replacement.user_id,
                WorkoutExerciseSafetySignal.cycle_id == replacement.cycle_id,
                WorkoutExerciseSafetySignal.workout_plan_exercise_id
                == replacement.workout_plan_exercise_id,
                WorkoutExerciseSafetySignal.replacement_exercise_id
                == replacement.replacement_exercise_id,
                WorkoutExerciseSafetySignal.week_number == replacement.week_number,
                WorkoutExerciseSafetySignal.signal_type
                == WorkoutExerciseSafetySignalType.PAIN_OR_DISCOMFORT,
            )
        ) is None:
            raise


def start_cycle(
    db: Session,
    *,
    user_id: UUID,
    workout_plan_id: UUID,
) -> WorkoutCycle:
    existing = db.scalar(
        select(WorkoutCycle).where(
            WorkoutCycle.workout_plan_id == workout_plan_id,
            WorkoutCycle.user_id == user_id,
        )
    )
    if existing is not None:
        return existing

    plan = db.scalar(
        select(WorkoutPlan).where(
            WorkoutPlan.id == workout_plan_id,
            WorkoutPlan.user_id == user_id,
        )
    )
    if plan is None:
        raise WorkoutCycleNotFoundError
    if plan.status is not WorkoutPlanStatus.ACTIVE:
        raise WorkoutCyclePlanInactiveError

    duration_weeks = _plan_duration_weeks(plan)
    cycle = WorkoutCycle(
        user_id=user_id,
        workout_plan_id=plan.id,
        duration_weeks=duration_weeks,
    )
    try:
        with db.begin_nested():
            db.add(cycle)
            db.flush()
    except IntegrityError:
        concurrent_cycle = db.scalar(
            select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == workout_plan_id)
        )
        if concurrent_cycle is not None:
            return concurrent_cycle
        raise
    return cycle


def get_cycle_for_user(
    db: Session,
    *,
    cycle_id: UUID,
    user_id: UUID,
) -> WorkoutCycle | None:
    return db.scalar(
        select(WorkoutCycle).where(
            WorkoutCycle.id == cycle_id,
            WorkoutCycle.user_id == user_id,
        )
    )


def get_current_active_cycle_for_user(
    db: Session,
    *,
    user_id: UUID,
) -> WorkoutCycle | None:
    return db.scalar(
        select(WorkoutCycle)
        .where(
            WorkoutCycle.user_id == user_id,
            WorkoutCycle.status == WorkoutCycleStatus.ACTIVE,
        )
        .order_by(WorkoutCycle.started_at.desc())
    )


def complete_cycle(
    db: Session,
    *,
    cycle_id: UUID,
    user_id: UUID,
    feedback: CompletionFeedbackInput | None = None,
) -> WorkoutCycle:
    cycle = db.scalar(
        select(WorkoutCycle)
        .where(
            WorkoutCycle.id == cycle_id,
            WorkoutCycle.user_id == user_id,
        )
        .with_for_update()
    )
    if cycle is None:
        raise WorkoutCycleNotFoundError
    if cycle.status is WorkoutCycleStatus.COMPLETED:
        raise WorkoutCycleAlreadyCompletedError

    if feedback is not None:
        cycle.completion_feedback = WorkoutCycleFeedback(
            adherence_percent=feedback.adherence_percent,
            performance_changes=feedback.performance_changes,
            pain_or_limitation_feedback=feedback.pain_or_limitation_feedback,
            measurements=dict(feedback.measurements),
        )
    cycle.status = WorkoutCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(UTC)
    db.flush()
    return cycle


def _plan_duration_weeks(plan: WorkoutPlan) -> int:
    raw_duration = plan.profile_snapshot.get("plan_duration_weeks")
    if isinstance(raw_duration, bool) or not isinstance(raw_duration, int):
        raise ValueError("Workout cycle duration must be 4, 6, or 8 weeks")
    if raw_duration not in SUPPORTED_CYCLE_DURATIONS:
        raise ValueError("Workout cycle duration must be 4, 6, or 8 weeks")
    return raw_duration


def _allowed_replacement_ids(item: WorkoutPlanExercise) -> set[UUID]:
    substitution_ids = item.substitution_exercise_ids
    if substitution_ids:
        allowed: set[UUID] = set()
        for value in substitution_ids:
            try:
                allowed.add(UUID(value))
            except (TypeError, ValueError):
                continue
        return allowed

    return {
        alternative.alternative_exercise_id
        for alternative in item.exercise.alternatives
        if isinstance(alternative, ExerciseAlternative)
        and alternative.alternative_exercise.is_active
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Workout cycle dates must be timezone-aware")
    return value.astimezone(UTC)
