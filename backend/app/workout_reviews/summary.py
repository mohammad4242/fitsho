from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.athlete_state.schemas import AthleteState
from app.athlete_state.service import AthleteStateBuilder
from app.exercises.enums import MuscleGroup
from app.workout_cycles.models import WorkoutCycle
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.schemas import WorkoutReviewAthleteSummary
from app.workouts.models import WorkoutPlan
from app.workouts.program_engine.adaptation_policy import (
    CycleAdaptationDecision,
    CycleAdaptationProgramSnapshot,
    decide_cycle_adaptation,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import RecentTrainingHistory


def build_athlete_summary(
    state: AthleteState,
    *,
    previous_approved_plan_id: UUID | None,
) -> WorkoutReviewAthleteSummary:
    """Map the already-derived state into the coach-review response contract."""
    return WorkoutReviewAthleteSummary(
        athlete_state=state,
        previous_approved_plan_id=previous_approved_plan_id,
    )


def build_review_athlete_summary(
    db: Session,
    review: WorkoutPlanReview,
) -> WorkoutReviewAthleteSummary:
    state = AthleteStateBuilder(db).build(review.user_id)
    return build_athlete_summary(
        state,
        previous_approved_plan_id=review.source_plan.previous_program_id,
    )


def build_fitsho_recommendation(
    db: Session,
    review: WorkoutPlanReview,
    *,
    state: AthleteState | None = None,
) -> CycleAdaptationDecision:
    """Expose the existing deterministic adaptation contract to Coach Review."""
    athlete_state = state or AthleteStateBuilder(db).build(review.user_id)
    previous = _previous_plan(db, review)
    history = _history_from_previous(athlete_state, previous)
    base_decision = decide_cycle_adaptation(athlete_state, history, RULESET)
    proposed = _plan_snapshot(review.source_plan, cycle_id=None)
    proposed = proposed.model_copy(
        update={
            "priority_muscles": tuple(athlete_state.priority_muscles),
            "disliked_exercises": base_decision.preference_constraints.disliked_exercises,
            "unavailable_exercises": base_decision.preference_constraints.unavailable_exercises,
            "blocked_exercises": base_decision.safety_constraints.blocked_exercises,
            "preferred_alternatives": base_decision.preference_constraints.preferred_alternatives,
        }
    )
    if previous is None:
        return base_decision
    previous_cycle_id = db.scalar(
        select(WorkoutCycle.id).where(
            WorkoutCycle.user_id == review.user_id,
            WorkoutCycle.workout_plan_id == previous.id,
        )
    )
    return decide_cycle_adaptation(
        athlete_state,
        history,
        RULESET,
        previous_program=_plan_snapshot(previous, cycle_id=previous_cycle_id),
        proposed_program=proposed,
    )


def _previous_plan(db: Session, review: WorkoutPlanReview) -> WorkoutPlan | None:
    previous_id = review.source_plan.previous_program_id
    if previous_id is None:
        return None
    return db.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == previous_id, WorkoutPlan.user_id == review.user_id)
        .options(selectinload(WorkoutPlan.days))
    )


def _history_from_previous(
    state: AthleteState,
    previous: WorkoutPlan | None,
) -> RecentTrainingHistory:
    if previous is None:
        return RecentTrainingHistory()
    metrics = previous.aggregate_metrics
    direct = _muscle_metrics(
        metrics.get("weekly_direct_sets_by_muscle") or metrics.get("planned_direct_sets_by_muscle")
    )
    effective = _muscle_metrics(metrics.get("weekly_effective_sets_by_muscle"))
    adherence = state.adherence.percent / 100 if state.adherence.percent is not None else 0.0
    return RecentTrainingHistory(
        completed_session_ratio=adherence,
        previous_weekly_direct_sets_by_muscle=direct,
        previous_weekly_effective_sets_by_muscle=effective,
        previous_volume_confidence=adherence if adherence > 0 else None,
        previous_volume_source="prescribed_plan" if direct or effective else "none",
        previous_volume_reason_codes=(
            "HISTORY_FROM_APPROVED_PLAN",
            "HISTORY_SCALED_BY_ADHERENCE",
        )
        if direct or effective
        else (),
    )


def _plan_snapshot(
    plan: WorkoutPlan,
    *,
    cycle_id: UUID | None,
) -> CycleAdaptationProgramSnapshot:
    profile = plan.profile_snapshot
    return CycleAdaptationProgramSnapshot(
        program_id=plan.id,
        cycle_id=cycle_id,
        weekly_effective_sets_by_muscle=_muscle_metrics(
            plan.aggregate_metrics.get("weekly_effective_sets_by_muscle")
        ),
        priority_muscles=_muscle_values(profile.get("priority_muscles")),
        training_days=_bounded_int(
            profile.get("available_training_days")
            or profile.get("training_days_per_week")
            or len(plan.days),
            minimum=1,
            maximum=7,
        ),
        session_duration_minutes=_bounded_int(
            profile.get("session_duration_minutes"), minimum=20, maximum=180
        ),
        disliked_exercises=_uuid_values(profile.get("disliked_exercises")),
        unavailable_exercises=_uuid_values(profile.get("unavailable_exercises")),
        blocked_exercises=_uuid_values(profile.get("blocked_exercises")),
    )


def _muscle_metrics(value: object) -> dict[MuscleGroup, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[MuscleGroup, float] = {}
    for key, raw_value in value.items():
        try:
            muscle = key if isinstance(key, MuscleGroup) else MuscleGroup(str(key))
            result[muscle] = float(raw_value)
        except (TypeError, ValueError):
            continue
    return result


def _muscle_values(value: object) -> tuple[MuscleGroup, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    values: set[MuscleGroup] = set()
    for item in value:
        try:
            values.add(item if isinstance(item, MuscleGroup) else MuscleGroup(str(item)))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(values, key=lambda muscle: muscle.value))


def _uuid_values(value: object) -> tuple[UUID, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    values: set[UUID] = set()
    for item in value:
        try:
            values.add(item if isinstance(item, UUID) else UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(values, key=str))


def _bounded_int(value: object, *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed is not None and minimum <= parsed <= maximum else None
