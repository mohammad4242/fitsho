from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.athlete_state.generation_adapter import AthleteStateToGenerationOverridesAdapter
from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultyTrend,
    AthleteStateProvenance,
    AthleteStateRecoverySummary,
    AthleteStateRecoveryTrend,
    AthleteStateScheduleContext,
)
from app.athlete_state.service import AthleteStateBuilder
from app.exercises.enums import MuscleGroup
from app.workout_cycles.enums import (
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
)
from app.workout_cycles.service import record_exercise_replacement
from app.workouts.schemas import ProgramGenerationOverrides
from tests.workout_cycles.test_cycle_body_progress_comparison import _cycle_with_snapshots


def _state(
    *,
    next_training_days: int | None = None,
    persistent_disliked_exercises: tuple = (),
    uncomfortable_exercises: tuple = (),
    unavailable_exercises: tuple = (),
    pain_sensitive_exercises: tuple = (),
    lagging_muscles: tuple = (),
    adherence_percent: float | None = None,
    recovery_summary: AthleteStateRecoverySummary = AthleteStateRecoverySummary.UNKNOWN,
) -> AthleteState:
    return AthleteState(
        user_id=uuid4(),
        adherence=AthleteStateAdherence(
            sessions_completed=0,
            planned_sessions=0,
            percent=adherence_percent,
        ),
        recovery_trend=AthleteStateRecoveryTrend(summary=recovery_summary),
        difficulty_trend=AthleteStateDifficultyTrend(),
        persistent_disliked_exercises=persistent_disliked_exercises,
        uncomfortable_exercises=uncomfortable_exercises,
        unavailable_exercises=unavailable_exercises,
        pain_sensitive_exercises=pain_sensitive_exercises,
        priority_muscles=lagging_muscles,
        lagging_muscles=lagging_muscles,
        schedule=AthleteStateScheduleContext(
            next_training_days=next_training_days,
            next_session_duration_minutes=60 if next_training_days is not None else None,
        ),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(),
    )


def test_adapter_maps_direct_schedule_fields_to_generation_overrides() -> None:
    state = _state(next_training_days=4)

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)

    assert overrides.available_training_days == 4
    assert overrides.session_duration_minutes == 60


def test_adapter_keeps_unknown_and_deferred_signals_neutral() -> None:
    state = _state()

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)

    assert overrides == ProgramGenerationOverrides()
    assert overrides.disliked_exercises == frozenset()
    assert overrides.priority_muscles == frozenset()
    assert overrides.blocked_exercises == frozenset()
    assert overrides.recent_training_history is None


def test_persistent_dislike_and_discomfort_map_to_disliked_exercises() -> None:
    disliked_id = uuid4()
    uncomfortable_id = uuid4()

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        _state(
            persistent_disliked_exercises=(disliked_id,),
            uncomfortable_exercises=(uncomfortable_id,),
        )
    )

    assert overrides.disliked_exercises == frozenset({disliked_id, uncomfortable_id})


def test_temporary_replacement_does_not_reach_generation_overrides(db: Session) -> None:
    user, cycle = _cycle_with_snapshots(db)
    prescribed = cycle.workout_plan.days[0].exercises[0]
    prescribed_id = prescribed.id
    safe_id = UUID(prescribed.substitution_exercise_ids[0])
    record_exercise_replacement(
        db,
        user_id=user.id,
        workout_plan_exercise_id=prescribed_id,
        replacement_exercise_id=safe_id,
        reason=WorkoutExerciseReplacementReason.DISLIKE,
        scope=WorkoutExerciseReplacementScope.THIS_TIME,
    )

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        AthleteStateBuilder(db).build(user.id)
    )

    assert overrides.disliked_exercises == frozenset()
    assert overrides.blocked_exercises == frozenset()


def test_persistent_unavailable_exercises_map_to_blocked_exercises() -> None:
    unavailable_id = uuid4()

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        _state(unavailable_exercises=(unavailable_id,))
    )

    assert overrides.blocked_exercises == frozenset({unavailable_id})


def test_pain_safety_takes_precedence_over_dislike() -> None:
    exercise_id = uuid4()

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        _state(
            persistent_disliked_exercises=(exercise_id,),
            pain_sensitive_exercises=(exercise_id,),
        )
    )

    assert overrides.blocked_exercises == frozenset({exercise_id})
    assert overrides.disliked_exercises == frozenset()


def test_lagging_muscles_map_to_priority_muscles() -> None:
    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        _state(lagging_muscles=(MuscleGroup.BACK,))
    )

    assert overrides.priority_muscles == frozenset({MuscleGroup.BACK})


def test_recovery_maps_to_recent_training_history() -> None:
    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        _state(
            adherence_percent=75.0,
            recovery_summary=AthleteStateRecoverySummary.POOR,
        )
    )

    assert overrides.recent_training_history is not None
    assert overrides.recent_training_history.completed_session_ratio == 0.75
    assert overrides.recent_training_history.recovery_problems is True


def test_good_recovery_and_adherence_preserve_positive_context() -> None:
    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(
        _state(
            adherence_percent=100.0,
            recovery_summary=AthleteStateRecoverySummary.GOOD,
        )
    )

    assert overrides.recent_training_history is not None
    assert overrides.recent_training_history.completed_session_ratio == 1.0
    assert overrides.recent_training_history.recovery_problems is False


def test_adapter_output_contains_no_raw_persistence_models() -> None:
    state = _state(next_training_days=3)

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)
    payload = overrides.model_dump(mode="json")

    assert set(payload) == set(ProgramGenerationOverrides.model_fields)
    assert all(
        not value.__class__.__module__.startswith("app.workout_cycles")
        for value in payload.values()
    )


def test_adapter_conversion_is_deterministic() -> None:
    state = _state(next_training_days=5)

    first = AthleteStateToGenerationOverridesAdapter.to_overrides(state)
    second = AthleteStateToGenerationOverridesAdapter.to_overrides(state)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.model_dump_json() == second.model_dump_json()
