from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleFeedback
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan

SUPPORTED_CYCLE_DURATIONS = frozenset({4, 6, 8})


class WorkoutCycleNotFoundError(Exception):
    pass


class WorkoutCycleAlreadyCompletedError(Exception):
    pass


class WorkoutCyclePlanInactiveError(Exception):
    pass


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
