from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService
from app.athlete_state.generation_adapter import AthleteStateToGenerationOverridesAdapter
from app.athlete_state.service import AthleteStateBuilder
from app.exercises.enums import ExerciseCautionTag, MovementPattern, MuscleGroup
from app.profile.enums import WorkoutGenerationMethod
from app.profile.service import get_profile
from app.workout_cycles.enums import (
    WorkoutCycleExerciseFeedbackType,
    WorkoutExercisePreferenceType,
)
from app.workout_cycles.models import (
    WorkoutCycleExerciseFeedback,
    WorkoutExercisePreference,
    WorkoutExerciseReplacement,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BalanceAbility,
    ImpactLimit,
    LoadLimit,
    RedFlag,
    StabilityDemand,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.service import WorkoutGenerationService
from tests.athlete_state.longitudinal_fixtures import longitudinal_scenarios, materialize_scenario
from tests.athlete_state.test_cycle_transitions import (
    _exercise_ids,
    _run_transition,
)


def _generation_context(
    db: Session,
) -> tuple[WorkoutGenerationService, Any, Any, tuple[Any, ...], Any]:
    service, materialized, state, _decision, _result, _provider = _run_transition(
        db, "intermediate_hypertrophy"
    )
    request = service._to_program_request(
        get_profile(db, materialized.user.id),
        AthleteStateToGenerationOverridesAdapter.to_overrides(state),
    )
    return service, materialized, request, service._load_catalog(), state


def _selected_ids(program: Any) -> set[UUID]:
    return {item.exercise_id for day in program.weekly_schedule for item in day.exercises}


def _generate_with_constraint(
    request: Any,
    catalog: tuple[Any, ...],
    *,
    target_id: UUID,
    request_updates: dict[str, object],
    candidate_updates: dict[str, object] | None = None,
    days: int = 4,
) -> tuple[Any, set[UUID]]:
    updates = {"available_training_days": days, **request_updates}
    effective_request = request.model_copy(update=updates)
    effective_catalog = tuple(
        replace(item, **(candidate_updates or {})) if item.id == target_id else item
        for item in catalog
    )
    normalized = normalize_request(effective_request, RULESET)
    eligibility = filter_eligible_exercises(normalized, effective_catalog)
    assert any(item.exercise_id == target_id for item in eligibility.rejected)
    result = generate_program(effective_request, effective_catalog, RULESET)
    assert result.is_success, result.errors
    assert target_id not in _selected_ids(result.program)
    return result.program, {item.id for item in eligibility.eligible}


@pytest.mark.parametrize(
    ("name", "request_updates", "candidate_updates"),
    [
        (
            "movement pattern",
            {"blocked_movement_patterns": frozenset({MovementPattern.HORIZONTAL_PUSH})},
            {},
        ),
        (
            "caution tag",
            {"blocked_caution_tags": frozenset({ExerciseCautionTag.WRIST_LOADING})},
            {"caution_tags": frozenset({ExerciseCautionTag.WRIST_LOADING})},
        ),
        (
            "ROM",
            {"allowed_range_of_motion": frozenset({"supported"})},
            {"range_of_motion_profile": frozenset({"deep_knee_flexion"})},
        ),
        (
            "axial load",
            {"axial_load_limit": LoadLimit.LOW},
            {"axial_loading_level": LoadLimit.HIGH},
        ),
        (
            "impact",
            {"impact_limit": ImpactLimit.LOW},
            {"impact_level": ImpactLimit.HIGH},
        ),
        (
            "overhead",
            {"overhead_limit": LoadLimit.NONE},
            {},
        ),
        (
            "balance",
            {"balance_requirement": BalanceAbility.LIMITED},
            {"stability_demand": StabilityDemand.HIGH},
        ),
    ],
)
def test_cycle_two_never_selects_exercise_rejected_by_hard_safety_rule(
    db: Session,
    name: str,
    request_updates: dict[str, object],
    candidate_updates: dict[str, object],
) -> None:
    _service_instance, materialized, request, catalog, _state = _generation_context(db)
    target = next(
        item
        for item in catalog
        if item.id == materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id
    )
    if name == "overhead":
        target = next(
            item for item in catalog if item.movement_pattern is MovementPattern.VERTICAL_PUSH
        )
    if name == "movement pattern":
        alternative = next(
            item for item in catalog if item.movement_pattern is MovementPattern.VERTICAL_PUSH
        )
        catalog = tuple(
            replace(
                item,
                primary_muscle=MuscleGroup.CHEST,
                secondary_muscles=(MuscleGroup.SHOULDERS,),
            )
            if item.id == alternative.id
            else item
            for item in catalog
        )
    if name == "balance":
        catalog = tuple(
            replace(item, stability_demand=StabilityDemand.LOW) if item.id != target.id else item
            for item in catalog
        )
    if name == "ROM":
        catalog = tuple(
            replace(item, range_of_motion_profile=frozenset({"supported"}))
            if item.id != target.id
            else item
            for item in catalog
        )

    program, eligible_ids = _generate_with_constraint(
        request,
        catalog,
        target_id=target.id,
        request_updates=request_updates,
        candidate_updates=candidate_updates,
    )
    assert target.id not in eligible_ids
    assert target.id not in _selected_ids(program)


def test_medical_red_flag_stops_cycle_two_generation(db: Session) -> None:
    _service_instance, _materialized, request, catalog, _state = _generation_context(db)
    result = generate_program(
        request.model_copy(update={"current_pain_or_red_flags": (RedFlag.CHEST_PAIN,)}),
        catalog,
        RULESET,
    )

    assert not result.is_success
    assert result.error_code.value == "PROGRAM_REJECTED_SAFETY_STATUS"
    assert result.safety_status.value == "stop_and_refer"


def test_current_and_repeated_pain_remain_hard_safety_constraints(db: Session) -> None:
    _service_instance, materialized, state, decision, result, provider = _run_transition(
        db, "pain_safety"
    )
    original_id = materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id

    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert original_id in state.pain_sensitive_exercises
    assert original_id in decision.safety_constraints.blocked_exercises
    assert decision.safety_constraints.signal_counts_by_exercise[original_id] >= 2
    assert "REPEATED_PAIN_SIGNAL" in {item.value for item in decision.reason_codes}
    assert original_id not in _exercise_ids(db, result.plan.id)
    assert provider.calls == 0

    request = _service_instance._to_program_request(
        get_profile(db, materialized.user.id),
        AthleteStateToGenerationOverridesAdapter.to_overrides(state),
    )
    eligible_ids = {
        item.id
        for item in filter_eligible_exercises(
            normalize_request(request, RULESET), _service_instance._load_catalog()
        ).eligible
    }
    for substitution in decision.safety_constraints.safe_substitutions:
        assert substitution.replacement_exercise_id in eligible_ids
        assert (
            substitution.replacement_exercise_id
            not in decision.safety_constraints.blocked_exercises
        )


def test_safety_overrides_conflicting_persistent_preference(db: Session) -> None:
    scenario = next(item for item in longitudinal_scenarios() if item.key == "pain_safety")
    materialized = materialize_scenario(db, scenario)
    original_id = materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id
    replacement = db.scalar(
        select(WorkoutExerciseReplacement).where(
            WorkoutExerciseReplacement.cycle_id == materialized.cycles[0].id,
            WorkoutExerciseReplacement.original_exercise_id == original_id,
        )
    )
    assert replacement is not None
    db.add(
        WorkoutCycleExerciseFeedback(
            id=uuid4(),
            user_id=materialized.user.id,
            cycle_id=materialized.cycles[0].id,
            workout_plan_exercise_id=replacement.workout_plan_exercise_id,
            exercise_id=original_id,
            feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
            persistent=True,
        )
    )
    db.add(
        WorkoutExercisePreference(
            id=uuid4(),
            user_id=materialized.user.id,
            exercise_id=original_id,
            preference_type=WorkoutExercisePreferenceType.DISLIKE,
            source_replacement_id=replacement.id,
        )
    )
    db.flush()
    state = AthleteStateBuilder(db).build(materialized.user.id)
    decision = __import__(
        "app.workouts.program_engine.adaptation_policy",
        fromlist=["decide_cycle_adaptation"],
    ).decide_cycle_adaptation(state, ruleset=RULESET)

    assert original_id in decision.safety_constraints.blocked_exercises
    assert original_id not in decision.preference_constraints.disliked_exercises
    reason_codes = {item.value for item in decision.reason_codes}
    assert "EXERCISE_BLOCKED_FOR_SAFETY" in reason_codes
    assert "PAIN_SIGNAL_PRESENT" in reason_codes


def test_ai_coach_cannot_receive_or_select_safety_rejected_candidate(db: Session) -> None:
    _service_instance, materialized, _state, decision, _result, _provider = _run_transition(
        db, "pain_safety"
    )
    original_id = materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id
    safe_id = next(
        item.id
        for item in _service_instance._load_catalog()
        if item.id not in decision.safety_constraints.blocked_exercises
    )
    base = {
        "generation_method": WorkoutGenerationMethod.AI,
        "athlete_state": _state,
        "adaptation_decision": decision,
        "safe_candidates": ({"candidate_id": "safe", "exercise_ids": (safe_id,)},),
        "deterministic_selected_candidate_id": "safe",
    }
    with pytest.raises(ValueError):
        AIReasoningInput.model_validate(
            {
                **base,
                "safe_candidates": ({"candidate_id": "unsafe", "exercise_ids": (original_id,)},),
            }
        )

    request = AIReasoningInput.model_validate(base)

    class UnsafeProvider:
        async def reason(self, _request: object) -> object:
            return {
                "summary": "unsafe selection",
                "reason_codes": ["SAFE_CANDIDATE_SET"],
                "selected_candidate_id": "unsafe",
                "rankings": [],
            }

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().reason(request, UnsafeProvider()))

    class MalformedProvider:
        async def reason(self, _request: object) -> object:
            return {"summary": "missing required structured fields"}

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().reason(request, MalformedProvider()))


def test_internal_cycle_generation_never_calls_ai_provider(db: Session) -> None:
    _service_instance, _materialized, _state, _decision, result, provider = _run_transition(
        db, "intermediate_hypertrophy"
    )

    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert provider.calls == 0
