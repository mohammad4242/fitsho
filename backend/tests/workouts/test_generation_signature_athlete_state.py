from __future__ import annotations

from uuid import UUID, uuid4

from app.athlete_state.generation_adapter import AthleteStateToGenerationOverridesAdapter
from app.athlete_state.schemas import AthleteStateProvenance
from app.exercises.enums import Equipment, MuscleGroup
from app.workouts.program_engine.enums import (
    Goal,
    TrainingExperience,
)
from app.workouts.program_engine.schemas import ProgramGenerationRequest
from app.workouts.signature import build_generation_request_signature
from tests.athlete_state.test_generation_adapter import _state


def _request(**changes: object) -> ProgramGenerationRequest:
    values: dict[str, object] = {
        "user_id": UUID("00000000-0000-0000-0000-000000000001"),
        "age": 30,
        "height_cm": 175,
        "weight_kg": 75.0,
        "primary_goal": Goal.MUSCLE_GAIN,
        "training_experience": TrainingExperience.BEGINNER,
        "training_age_months": 0,
        "available_training_days": 3,
        "session_duration_minutes": 60,
        "available_equipment": frozenset({Equipment.BODYWEIGHT}),
        "training_location": "home",
        "program_duration_weeks": 4,
    }
    values.update(changes)
    return ProgramGenerationRequest.model_validate(values)


def _signature(request: ProgramGenerationRequest) -> str:
    return build_generation_request_signature(
        request,
        catalog_hash="catalog-hash",
        reference_hash="reference-hash",
        engine_version="engine-v1",
        ruleset_version="rules-v1",
    )


def test_identical_effective_athlete_state_inputs_reuse_signature() -> None:
    exercise_id = uuid4()
    state = _state(
        next_training_days=4,
        persistent_disliked_exercises=(exercise_id,),
        pain_sensitive_exercises=(uuid4(),),
        lagging_muscles=(MuscleGroup.BACK,),
        adherence_percent=75.0,
    )
    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)

    assert _signature(_request(**overrides.model_dump(exclude_none=True))) == _signature(
        _request(**overrides.model_dump(exclude_none=True))
    )


def test_collection_ordering_does_not_change_signature() -> None:
    first = _request(
        disliked_exercises=frozenset({UUID(int=1), UUID(int=2)}),
        blocked_exercises=frozenset({UUID(int=3), UUID(int=4)}),
        priority_muscles=frozenset({MuscleGroup.BACK}),
        available_equipment=frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL}),
    )
    second = _request(
        disliked_exercises=frozenset({UUID(int=2), UUID(int=1)}),
        blocked_exercises=frozenset({UUID(int=4), UUID(int=3)}),
        priority_muscles=frozenset({MuscleGroup.BACK}),
        available_equipment=frozenset({Equipment.DUMBBELL, Equipment.BODYWEIGHT}),
    )

    assert _signature(first) == _signature(second)


def test_persistent_dislike_change_changes_signature() -> None:
    baseline = _signature(_request(disliked_exercises=frozenset({UUID(int=1)})))

    assert baseline != _signature(_request(disliked_exercises=frozenset({UUID(int=2)})))


def test_safety_block_change_changes_signature() -> None:
    baseline = _signature(_request(blocked_exercises=frozenset()))

    assert baseline != _signature(_request(blocked_exercises=frozenset({UUID(int=1)})))


def test_priority_muscle_change_changes_signature() -> None:
    baseline = _signature(_request(priority_muscles=frozenset({MuscleGroup.BACK})))

    assert baseline != _signature(_request(priority_muscles=frozenset({MuscleGroup.CHEST})))


def test_schedule_and_recovery_changes_change_signature() -> None:
    baseline = _signature(_request(available_training_days=3, session_duration_minutes=60))
    changed_schedule = _signature(_request(available_training_days=4, session_duration_minutes=60))
    changed_recovery = _signature(
        _request(
            recent_training_history={
                "completed_session_ratio": 0.5,
                "recovery_problems": True,
            }
        )
    )

    assert baseline != changed_schedule
    assert baseline != changed_recovery


def test_provenance_and_timestamp_only_changes_do_not_change_signature() -> None:
    exercise_id = uuid4()
    first_state = _state(persistent_disliked_exercises=(exercise_id,))
    second_state = first_state.model_copy(
        update={
            "provenance": AthleteStateProvenance(
                profile_user_id=uuid4(),
                cycle_ids=(uuid4(),),
                weekly_check_in_ids=(uuid4(),),
            )
        }
    )

    first = AthleteStateToGenerationOverridesAdapter.to_overrides(first_state)
    second = AthleteStateToGenerationOverridesAdapter.to_overrides(second_state)

    assert _signature(_request(**first.model_dump(exclude_none=True))) == _signature(
        _request(**second.model_dump(exclude_none=True))
    )
