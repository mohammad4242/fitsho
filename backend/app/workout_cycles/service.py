from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.exercises.models import ExerciseAlternative
from app.workout_cycles.body_progress_schemas import (
    WorkoutCycleBodyProgressComparisonResponse,
    WorkoutCycleFeedbackBodyProgressContext,
)
from app.workout_cycles.enums import (
    WorkoutCycleExerciseFeedbackSuggestionKind,
    WorkoutCycleExerciseFeedbackType,
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExercisePreferenceType,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
    WorkoutExerciseSafetySignalType,
)
from app.workout_cycles.models import (
    WorkoutCycle,
    WorkoutCycleExerciseFeedback,
    WorkoutCycleFeedback,
    WorkoutCycleWeeklyCheckIn,
    WorkoutCycleWeeklyCheckInPainLimitation,
    WorkoutExercisePreference,
    WorkoutExerciseReplacement,
    WorkoutExerciseSafetySignal,
)
from app.workout_cycles.schemas import (
    CompletionFeedbackInput,
    WorkoutCycleExerciseFeedbackPersistentStateResponse,
    WorkoutCycleExerciseFeedbackReplacementSummaryResponse,
    WorkoutCycleExerciseFeedbackSuggestionResponse,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise
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


class WorkoutCycleExerciseFeedbackPlanExerciseNotFoundError(Exception):
    pass


class WorkoutCycleExerciseFeedbackDuplicateError(Exception):
    pass


class WorkoutCycleWeeklyCheckInCycleNotFoundError(Exception):
    pass


class WorkoutCycleWeeklyCheckInNoActiveCycleError(Exception):
    pass


class WorkoutCycleWeeklyCheckInNotFoundError(Exception):
    pass


class WorkoutCycleWeeklyCheckInWeekOutOfRangeError(ValueError):
    pass


class WorkoutCycleWeeklyCheckInSessionsOutOfRangeError(ValueError):
    pass


class WorkoutCycleWeeklyCheckInPainExerciseRequiredError(ValueError):
    pass


class WorkoutCycleWeeklyCheckInPainExerciseNotFoundError(Exception):
    pass


class WorkoutCycleWeeklyCheckInPainFollowUpNotAllowedError(ValueError):
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


def create_weekly_check_in(
    db: Session,
    *,
    user_id: UUID,
    cycle_id: UUID,
    week_number: int,
    sessions_completed: int,
    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty,
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery,
    has_pain_or_limitation: bool,
    note_optional: str | None = None,
    pain_workout_plan_exercise_id: UUID | None = None,
    pain_note_optional: str | None = None,
) -> WorkoutCycleWeeklyCheckIn:
    cycle = get_cycle_for_user(db, cycle_id=cycle_id, user_id=user_id)
    if cycle is None or cycle.workout_plan.user_id != user_id:
        raise WorkoutCycleWeeklyCheckInCycleNotFoundError
    _validate_weekly_check_in_payload(
        cycle,
        week_number=week_number,
        sessions_completed=sessions_completed,
        has_pain_or_limitation=has_pain_or_limitation,
        pain_workout_plan_exercise_id=pain_workout_plan_exercise_id,
        pain_note_optional=pain_note_optional,
    )

    check_in = WorkoutCycleWeeklyCheckIn(
        user_id=user_id,
        cycle_id=cycle.id,
        week_number=week_number,
        sessions_completed=sessions_completed,
        perceived_difficulty=perceived_difficulty,
        recovery_rating=recovery_rating,
        has_pain_or_limitation=has_pain_or_limitation,
        note_optional=note_optional,
    )
    _set_pain_follow_up(
        check_in,
        user_id=user_id,
        cycle_id=cycle.id,
        has_pain_or_limitation=has_pain_or_limitation,
        pain_workout_plan_exercise_id=pain_workout_plan_exercise_id,
        pain_note_optional=pain_note_optional,
        db=db,
    )
    db.add(check_in)
    try:
        db.flush()
        db.commit()
        db.refresh(check_in)
    except SQLAlchemyError:
        db.rollback()
        raise
    return check_in


def get_weekly_check_in_for_cycle_week(
    db: Session,
    *,
    cycle_id: UUID,
    week_number: int,
) -> WorkoutCycleWeeklyCheckIn | None:
    return db.scalar(
        select(WorkoutCycleWeeklyCheckIn).where(
            WorkoutCycleWeeklyCheckIn.cycle_id == cycle_id,
            WorkoutCycleWeeklyCheckIn.week_number == week_number,
        )
    )


def get_current_weekly_check_in(
    db: Session,
    *,
    user_id: UUID,
) -> WorkoutCycleWeeklyCheckIn:
    cycle = get_current_active_cycle_for_user(db, user_id=user_id)
    if cycle is None:
        raise WorkoutCycleWeeklyCheckInNoActiveCycleError
    week_number = calculate_current_week(cycle.started_at, cycle.duration_weeks)
    check_in = get_weekly_check_in_for_cycle_week(
        db,
        cycle_id=cycle.id,
        week_number=week_number,
    )
    if check_in is None:
        raise WorkoutCycleWeeklyCheckInNotFoundError
    return check_in


def upsert_current_weekly_check_in(
    db: Session,
    *,
    user_id: UUID,
    sessions_completed: int,
    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty,
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery,
    has_pain_or_limitation: bool,
    note_optional: str | None = None,
    pain_workout_plan_exercise_id: UUID | None = None,
    pain_note_optional: str | None = None,
) -> WorkoutCycleWeeklyCheckIn:
    cycle = get_current_active_cycle_for_user(db, user_id=user_id)
    if cycle is None:
        raise WorkoutCycleWeeklyCheckInNoActiveCycleError
    week_number = calculate_current_week(cycle.started_at, cycle.duration_weeks)
    _validate_weekly_check_in_payload(
        cycle,
        week_number=week_number,
        sessions_completed=sessions_completed,
        has_pain_or_limitation=has_pain_or_limitation,
        pain_workout_plan_exercise_id=pain_workout_plan_exercise_id,
        pain_note_optional=pain_note_optional,
    )

    check_in = db.scalar(
        select(WorkoutCycleWeeklyCheckIn)
        .where(
            WorkoutCycleWeeklyCheckIn.cycle_id == cycle.id,
            WorkoutCycleWeeklyCheckIn.week_number == week_number,
        )
        .with_for_update()
    )
    if check_in is None:
        check_in = WorkoutCycleWeeklyCheckIn(
            user_id=user_id,
            cycle_id=cycle.id,
            week_number=week_number,
            sessions_completed=sessions_completed,
            perceived_difficulty=perceived_difficulty,
            recovery_rating=recovery_rating,
            has_pain_or_limitation=has_pain_or_limitation,
            note_optional=note_optional,
        )
        db.add(check_in)
    else:
        check_in.sessions_completed = sessions_completed
        check_in.perceived_difficulty = perceived_difficulty
        check_in.recovery_rating = recovery_rating
        check_in.has_pain_or_limitation = has_pain_or_limitation
        check_in.note_optional = note_optional
        check_in.submitted_at = datetime.now(UTC)

    _set_pain_follow_up(
        check_in,
        user_id=user_id,
        cycle_id=cycle.id,
        has_pain_or_limitation=has_pain_or_limitation,
        pain_workout_plan_exercise_id=pain_workout_plan_exercise_id,
        pain_note_optional=pain_note_optional,
        db=db,
    )
    try:
        db.flush()
        db.commit()
        db.refresh(check_in)
    except SQLAlchemyError:
        db.rollback()
        raise
    return check_in


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


def record_workout_cycle_exercise_feedback(
    db: Session,
    *,
    user_id: UUID,
    cycle_id: UUID,
    workout_plan_exercise_id: UUID,
    feedback_type: WorkoutCycleExerciseFeedbackType,
    persistent: bool,
    note_optional: str | None = None,
) -> WorkoutCycleExerciseFeedback:
    cycle = get_cycle_for_user(db, cycle_id=cycle_id, user_id=user_id)
    if cycle is None:
        raise WorkoutCycleExerciseFeedbackPlanExerciseNotFoundError

    prescribed = db.scalar(
        select(WorkoutPlanExercise)
        .join(WorkoutDay, WorkoutDay.id == WorkoutPlanExercise.workout_day_id)
        .where(
            WorkoutPlanExercise.id == workout_plan_exercise_id,
            WorkoutDay.workout_plan_id == cycle.workout_plan_id,
        )
    )
    if prescribed is None:
        raise WorkoutCycleExerciseFeedbackPlanExerciseNotFoundError
    if note_optional is not None and len(note_optional) > 1000:
        raise ValueError("Exercise feedback note must be at most 1000 characters")

    existing = db.scalar(
        select(WorkoutCycleExerciseFeedback).where(
            WorkoutCycleExerciseFeedback.cycle_id == cycle.id,
            WorkoutCycleExerciseFeedback.workout_plan_exercise_id == prescribed.id,
            WorkoutCycleExerciseFeedback.feedback_type == feedback_type,
        )
    )
    if existing is not None:
        raise WorkoutCycleExerciseFeedbackDuplicateError

    feedback = WorkoutCycleExerciseFeedback(
        user_id=user_id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        exercise_id=prescribed.exercise_id,
        feedback_type=feedback_type,
        persistent=persistent,
        note_optional=note_optional,
    )
    db.add(feedback)
    try:
        db.flush()
        db.commit()
        db.refresh(feedback)
    except SQLAlchemyError:
        db.rollback()
        raise
    return feedback


def get_cycle_exercise_feedback_suggestions(
    db: Session,
    *,
    user_id: UUID,
    cycle_id: UUID,
) -> list[WorkoutCycleExerciseFeedbackSuggestionResponse]:
    cycle = get_cycle_for_user(db, cycle_id=cycle_id, user_id=user_id)
    if cycle is None:
        raise WorkoutCycleNotFoundError

    replacements = list(
        db.scalars(
            select(WorkoutExerciseReplacement)
            .options(
                joinedload(WorkoutExerciseReplacement.original_exercise),
                joinedload(WorkoutExerciseReplacement.replacement_exercise),
            )
            .where(
                WorkoutExerciseReplacement.user_id == user_id,
                WorkoutExerciseReplacement.cycle_id == cycle.id,
            )
            .order_by(
                WorkoutExerciseReplacement.workout_plan_exercise_id,
                WorkoutExerciseReplacement.created_at,
                WorkoutExerciseReplacement.id,
            )
        ).all()
    )
    if not replacements:
        return []

    original_exercise_ids = {replacement.original_exercise_id for replacement in replacements}
    preferences = list(
        db.scalars(
            select(WorkoutExercisePreference).where(
                WorkoutExercisePreference.user_id == user_id,
                WorkoutExercisePreference.exercise_id.in_(original_exercise_ids),
            )
        ).all()
    )
    safety_signals = list(
        db.scalars(
            select(WorkoutExerciseSafetySignal).where(
                WorkoutExerciseSafetySignal.user_id == user_id,
                WorkoutExerciseSafetySignal.cycle_id == cycle.id,
                WorkoutExerciseSafetySignal.original_exercise_id.in_(original_exercise_ids),
            )
        ).all()
    )

    preferences_by_exercise: dict[UUID, list[WorkoutExercisePreference]] = {}
    for preference in preferences:
        preferences_by_exercise.setdefault(preference.exercise_id, []).append(preference)
    safety_by_exercise: dict[UUID, list[WorkoutExerciseSafetySignal]] = {}
    for signal in safety_signals:
        safety_by_exercise.setdefault(signal.original_exercise_id, []).append(signal)

    grouped: dict[UUID, list[WorkoutExerciseReplacement]] = {}
    for replacement in replacements:
        if _replacement_suggestion_kind(replacement) is not None:
            grouped.setdefault(replacement.workout_plan_exercise_id, []).append(replacement)

    suggestions: list[WorkoutCycleExerciseFeedbackSuggestionResponse] = []
    for prescribed_replacements in grouped.values():
        by_kind: dict[
            WorkoutCycleExerciseFeedbackSuggestionKind,
            list[WorkoutExerciseReplacement],
        ] = {}
        for replacement in prescribed_replacements:
            kind = _replacement_suggestion_kind(replacement)
            if kind is not None:
                by_kind.setdefault(kind, []).append(replacement)

        first = prescribed_replacements[0]
        persistent_state = WorkoutCycleExerciseFeedbackPersistentStateResponse(
            preference_types=sorted(
                (preference.preference_type for preference in preferences_by_exercise.get(
                    first.original_exercise_id, []
                )),
                key=lambda preference_type: preference_type.value,
            ),
            safety_signal_types=sorted(
                (
                    signal.signal_type
                    for signal in safety_by_exercise.get(first.original_exercise_id, [])
                ),
                key=lambda signal_type: signal_type.value,
            ),
        )
        for kind, kind_replacements in by_kind.items():
            suggestions.append(
                _build_replacement_suggestion(
                    kind=kind,
                    replacements=kind_replacements,
                    persistent_state=persistent_state,
                )
            )

    return suggestions


def _replacement_suggestion_kind(
    replacement: WorkoutExerciseReplacement,
) -> WorkoutCycleExerciseFeedbackSuggestionKind | None:
    if replacement.reason is WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT:
        return WorkoutCycleExerciseFeedbackSuggestionKind.SAFETY
    if replacement.scope is not WorkoutExerciseReplacementScope.PERSISTENT:
        return None
    if replacement.reason in {
        WorkoutExerciseReplacementReason.UNCOMFORTABLE,
        WorkoutExerciseReplacementReason.DISLIKE,
    }:
        return WorkoutCycleExerciseFeedbackSuggestionKind.NEGATIVE_EXERCISE_PREFERENCE
    if replacement.reason is WorkoutExerciseReplacementReason.EQUIPMENT_UNAVAILABLE:
        return WorkoutCycleExerciseFeedbackSuggestionKind.EQUIPMENT_CONTEXT
    return None


def _build_replacement_suggestion(
    *,
    kind: WorkoutCycleExerciseFeedbackSuggestionKind,
    replacements: list[WorkoutExerciseReplacement],
    persistent_state: WorkoutCycleExerciseFeedbackPersistentStateResponse,
) -> WorkoutCycleExerciseFeedbackSuggestionResponse:
    first = replacements[0]
    by_replacement_exercise: dict[UUID, list[WorkoutExerciseReplacement]] = {}
    for replacement in replacements:
        by_replacement_exercise.setdefault(replacement.replacement_exercise_id, []).append(
            replacement
        )

    replacement_summaries = [
        WorkoutCycleExerciseFeedbackReplacementSummaryResponse(
            replacement_exercise_id=rows[0].replacement_exercise_id,
            replacement_name_en=rows[0].replacement_exercise.name_en,
            replacement_name_fa=rows[0].replacement_exercise.name_fa,
            replacement_count=len(rows),
            replacement_ids=[row.id for row in rows],
            reasons=_unique_enum_values(row.reason for row in rows),
            scopes=_unique_enum_values(row.scope for row in rows),
            week_numbers=_unique_int_values(row.week_number for row in rows),
        )
        for rows in by_replacement_exercise.values()
    ]
    return WorkoutCycleExerciseFeedbackSuggestionResponse(
        suggestion_kind=kind,
        workout_plan_exercise_id=first.workout_plan_exercise_id,
        original_exercise_id=first.original_exercise_id,
        original_name_en=first.original_exercise.name_en,
        original_name_fa=first.original_exercise.name_fa,
        replacement_count=len(replacements),
        replacement_ids=[replacement.id for replacement in replacements],
        reasons=_unique_enum_values(replacement.reason for replacement in replacements),
        replacement_exercises=replacement_summaries,
        current_persistent_state=persistent_state,
    )


def _unique_enum_values[
    EnumValue: (WorkoutExerciseReplacementReason, WorkoutExerciseReplacementScope)
](values: Iterable[EnumValue]) -> list[EnumValue]:
    unique: dict[EnumValue, None] = {}
    for value in values:
        unique[value] = None
    return list(unique)


def _unique_int_values(values: Iterable[int]) -> list[int]:
    unique: dict[int, None] = {}
    for value in values:
        unique[value] = None
    return list(unique)


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

    cycle.status = WorkoutCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(UTC)
    if feedback is not None:
        from app.workout_cycles.body_progress_service import compare_cycle_body_progress

        body_progress_comparison = compare_cycle_body_progress(
            db,
            user_id=user_id,
            cycle_id=cycle.id,
            commit=False,
        )
        cycle.completion_feedback = WorkoutCycleFeedback(
            body_progress_comparison_id=body_progress_comparison.id,
            adherence_percent=feedback.adherence_percent,
            performance_changes=feedback.performance_changes,
            pain_or_limitation_feedback=feedback.pain_or_limitation_feedback,
            measurements=dict(feedback.measurements),
            overall_difficulty=feedback.overall_difficulty,
            overall_recovery=feedback.overall_recovery,
            overall_satisfaction=feedback.overall_satisfaction,
            strength_progress=feedback.strength_progress,
            muscle_progress=feedback.muscle_progress,
            endurance_progress=feedback.endurance_progress,
            energy_progress=feedback.energy_progress,
            progressed_muscles=(
                [muscle.value for muscle in feedback.progressed_muscles]
                if feedback.progressed_muscles is not None
                else None
            ),
            lagging_muscles=(
                [muscle.value for muscle in feedback.lagging_muscles]
                if feedback.lagging_muscles is not None
                else None
            ),
            goal_changed=feedback.goal_changed,
            next_goal=feedback.next_goal,
            schedule_changed=feedback.schedule_changed,
            next_training_days=feedback.next_training_days,
            next_session_duration_minutes=feedback.next_session_duration_minutes,
            equipment_changed=feedback.equipment_changed,
            new_limitation=feedback.new_limitation,
            note_optional=feedback.note_optional,
        )
    db.flush()
    return cycle


def get_cycle_feedback_body_progress_context(
    db: Session,
    *,
    cycle_id: UUID,
    user_id: UUID,
) -> WorkoutCycleFeedbackBodyProgressContext | None:
    cycle = get_cycle_for_user(db, cycle_id=cycle_id, user_id=user_id)
    if cycle is None:
        raise WorkoutCycleNotFoundError
    feedback = db.scalar(
        select(WorkoutCycleFeedback).where(WorkoutCycleFeedback.cycle_id == cycle.id)
    )
    if feedback is None:
        return None

    comparison = feedback.body_progress_comparison
    comparison_response = None
    if (
        comparison is not None
        and comparison.user_id == user_id
        and comparison.cycle_id == cycle.id
    ):
        comparison_response = WorkoutCycleBodyProgressComparisonResponse(
            id=comparison.id,
            cycle_id=comparison.cycle_id,
            result=comparison.comparison_result,
            created_at=comparison.created_at,
            updated_at=comparison.updated_at,
        )
    return WorkoutCycleFeedbackBodyProgressContext(
        feedback_id=feedback.id,
        cycle_id=cycle.id,
        body_progress_comparison=comparison_response,
    )


def _plan_duration_weeks(plan: WorkoutPlan) -> int:
    raw_duration = plan.profile_snapshot.get("plan_duration_weeks")
    if isinstance(raw_duration, bool) or not isinstance(raw_duration, int):
        raise ValueError("Workout cycle duration must be 4, 6, or 8 weeks")
    if raw_duration not in SUPPORTED_CYCLE_DURATIONS:
        raise ValueError("Workout cycle duration must be 4, 6, or 8 weeks")
    return raw_duration


def _find_prescribed_exercise(
    cycle: WorkoutCycle,
    *,
    workout_plan_exercise_id: UUID,
) -> WorkoutPlanExercise | None:
    return next(
        (
            item
            for day in cycle.workout_plan.days
            for item in day.exercises
            if item.id == workout_plan_exercise_id
        ),
        None,
    )


def _validate_weekly_check_in_payload(
    cycle: WorkoutCycle,
    *,
    week_number: int,
    sessions_completed: int,
    has_pain_or_limitation: bool,
    pain_workout_plan_exercise_id: UUID | None,
    pain_note_optional: str | None,
) -> None:
    if not 1 <= week_number <= cycle.duration_weeks:
        raise WorkoutCycleWeeklyCheckInWeekOutOfRangeError(
            "Weekly check-in week must be within the workout cycle duration"
        )

    prescribed_training_days = len(cycle.workout_plan.days)
    if not 0 <= sessions_completed <= prescribed_training_days:
        raise WorkoutCycleWeeklyCheckInSessionsOutOfRangeError(
            "Completed sessions must be within the plan's prescribed weekly days"
        )

    if has_pain_or_limitation:
        if pain_workout_plan_exercise_id is None:
            raise WorkoutCycleWeeklyCheckInPainExerciseRequiredError(
                "A prescribed exercise is required when pain or limitation is reported"
            )
        if pain_note_optional is not None and len(pain_note_optional) > 500:
            raise ValueError("Pain or limitation note must be 500 characters or fewer")
        prescribed = _find_prescribed_exercise(
            cycle,
            workout_plan_exercise_id=pain_workout_plan_exercise_id,
        )
        if prescribed is None:
            raise WorkoutCycleWeeklyCheckInPainExerciseNotFoundError
    elif pain_workout_plan_exercise_id is not None or pain_note_optional is not None:
        raise WorkoutCycleWeeklyCheckInPainFollowUpNotAllowedError(
            "Pain follow-up data requires has_pain_or_limitation=True"
        )


def _set_pain_follow_up(
    check_in: WorkoutCycleWeeklyCheckIn,
    *,
    user_id: UUID,
    cycle_id: UUID,
    has_pain_or_limitation: bool,
    pain_workout_plan_exercise_id: UUID | None,
    pain_note_optional: str | None,
    db: Session,
) -> None:
    if check_in.pain_limitation is not None:
        db.delete(check_in.pain_limitation)
        check_in.pain_limitation = None
    if has_pain_or_limitation:
        assert pain_workout_plan_exercise_id is not None
        check_in.pain_limitation = WorkoutCycleWeeklyCheckInPainLimitation(
            user_id=user_id,
            cycle_id=cycle_id,
            workout_plan_exercise_id=pain_workout_plan_exercise_id,
            note_optional=pain_note_optional,
        )


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
