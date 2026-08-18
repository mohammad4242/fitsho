from __future__ import annotations

from uuid import uuid4

from app.athlete_state.generation_adapter import AthleteStateToGenerationOverridesAdapter
from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultyTrend,
    AthleteStateProvenance,
    AthleteStateRecoveryTrend,
    AthleteStateScheduleContext,
)
from app.exercises.enums import MuscleGroup
from app.workouts.schemas import ProgramGenerationOverrides


def _state(*, next_training_days: int | None = None) -> AthleteState:
    return AthleteState(
        user_id=uuid4(),
        adherence=AthleteStateAdherence(sessions_completed=0, planned_sessions=0),
        recovery_trend=AthleteStateRecoveryTrend(),
        difficulty_trend=AthleteStateDifficultyTrend(),
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


def test_adapter_defers_semantic_history_mappings_to_task_7_2() -> None:
    state = _state(next_training_days=4).model_copy(
        update={
            "persistent_disliked_exercises": (uuid4(),),
            "pain_sensitive_exercises": (uuid4(),),
            "lagging_muscles": (MuscleGroup.BACK,),
            "recovery_trend": {"summary": "poor"},
        }
    )

    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)

    assert overrides.available_training_days == 4
    assert overrides.disliked_exercises == frozenset()
    assert overrides.blocked_exercises == frozenset()
    assert overrides.priority_muscles == frozenset()
    assert overrides.recent_training_history is None


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
