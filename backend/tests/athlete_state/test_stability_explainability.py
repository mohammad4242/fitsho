from __future__ import annotations

import asyncio
from typing import cast
from uuid import uuid4

from app.athlete_state.generation_adapter import AthleteStateToGenerationOverridesAdapter
from app.athlete_state.schemas import (
    AthleteStateRecoverySummary,
    AthleteStateSafetyContext,
)
from app.athlete_state.service import AthleteStateBuilder
from app.exercises.enums import MuscleGroup
from app.profile.enums import WorkoutGenerationMethod
from app.profile.service import get_profile
from app.workout_cycles.enums import WorkoutCycleWeeklyCheckInRecovery
from app.workouts.ai_coach_provider import OpenRouterAiCoachProvider
from app.workouts.program_engine.adaptation_policy import (
    CycleAdaptationAction,
    CycleAdaptationProgramSnapshot,
    CycleAdaptationReasonCode,
    decide_cycle_adaptation,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import WorkoutProgram
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings
from tests.athlete_state.longitudinal_fixtures import (
    longitudinal_scenarios,
    materialize_scenario,
)


class _NeverCalledAIProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def recommend(self, _request: object) -> object:
        self.calls += 1
        raise AssertionError("internal generation must not call AI")


def _service(db, provider: _NeverCalledAIProvider) -> WorkoutGenerationService:
    return WorkoutGenerationService(
        db,
        ai_coach_provider=cast(OpenRouterAiCoachProvider, provider),
        settings=WorkoutGenerationSettings(
            provider_name="fitsho_domain",
            model_id="program_engine_v1",
            prompt_version="none",
            generation_policy_version=RULESET.version,
            catalog_programming_version="fixture",
            max_repair_attempts=0,
            cooldown_seconds=0,
            max_candidates=5000,
            max_request_bytes=262144,
            warmup_minutes=5,
            generation_method=WorkoutGenerationMethod.FITSHO_COACH.value,
        ),
    )


def _scenario(key: str):
    return next(item for item in longitudinal_scenarios() if item.key == key)


def _program_snapshot(program: WorkoutProgram) -> CycleAdaptationProgramSnapshot:
    raw_metrics = program.aggregate_metrics["weekly_effective_sets_by_muscle"]
    assert isinstance(raw_metrics, dict)
    return CycleAdaptationProgramSnapshot(
        weekly_effective_sets_by_muscle={
            MuscleGroup(muscle): float(sets) for muscle, sets in raw_metrics.items()
        },
        priority_muscles=tuple(
            sorted(
                {
                    MuscleGroup(muscle)
                    for muscle in program.aggregate_metrics.get("priority_muscles", ())
                },
                key=lambda item: item.value,
            )
        ),
        training_days=len(program.weekly_schedule),
        session_duration_minutes=(
            program.weekly_schedule[0].estimated_duration_minutes
            if program.weekly_schedule
            else None
        ),
    )


def test_identical_longitudinal_inputs_produce_identical_decision_and_program(
    db,
) -> None:
    materialized = materialize_scenario(db, _scenario("intermediate_hypertrophy"))
    provider = _NeverCalledAIProvider()
    service = _service(db, provider)
    state = AthleteStateBuilder(db).build(materialized.user.id)
    profile = get_profile(db, materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)
    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)
    request = service._to_program_request(
        profile,
        service._with_previous_volume_history(materialized.user.id, overrides),
    )
    catalog = service._load_catalog()

    first_decision = decide_cycle_adaptation(state, history, RULESET)
    second_decision = decide_cycle_adaptation(state, history, RULESET)
    first_result = generate_program(request, catalog, RULESET)
    second_result = generate_program(request, catalog, RULESET)

    assert first_result.is_success and second_result.is_success
    assert first_decision.to_snapshot_json() == second_decision.to_snapshot_json()
    assert first_result.program == second_result.program
    assert first_result.program.split == second_result.program.split
    assert (
        first_result.program.aggregate_metrics["weekly_effective_sets_by_muscle"]
        == second_result.program.aggregate_metrics["weekly_effective_sets_by_muscle"]
    )
    assert first_result.program.decision_trace == second_result.program.decision_trace
    assert provider.calls == 0


def test_meaningful_recovery_change_holds_progression_with_explicit_reasons(db) -> None:
    materialized = materialize_scenario(db, _scenario("intermediate_hypertrophy"))
    service = _service(db, _NeverCalledAIProvider())
    state = AthleteStateBuilder(db).build(materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)

    baseline = decide_cycle_adaptation(state, history, RULESET)
    poor_recovery = state.model_copy(
        update={
            "recovery_trend": state.recovery_trend.model_copy(
                update={
                    "summary": AthleteStateRecoverySummary.POOR,
                    "values": (
                        WorkoutCycleWeeklyCheckInRecovery.POOR,
                        WorkoutCycleWeeklyCheckInRecovery.POOR,
                    ),
                }
            )
        }
    )
    changed = decide_cycle_adaptation(poor_recovery, history, RULESET)

    assert baseline.overall_action is CycleAdaptationAction.INCREASE
    assert changed.overall_action is CycleAdaptationAction.REDUCE
    assert CycleAdaptationReasonCode.POOR_RECOVERY in changed.reason_codes
    assert CycleAdaptationReasonCode.PROGRESSION_HELD in changed.reason_codes


def test_meaningful_lagging_muscle_change_adds_targeted_reasoned_adjustment(db) -> None:
    materialized = materialize_scenario(db, _scenario("intermediate_hypertrophy"))
    service = _service(db, _NeverCalledAIProvider())
    state = AthleteStateBuilder(db).build(materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)
    changed = state.model_copy(
        update={
            "lagging_muscles": (MuscleGroup.SHOULDERS,),
            "priority_muscles": (MuscleGroup.SHOULDERS,),
        }
    )

    decision = decide_cycle_adaptation(changed, history, RULESET)

    assert decision.overall_action is CycleAdaptationAction.INCREASE
    assert decision.muscle_adjustments[0].muscle is MuscleGroup.SHOULDERS
    assert (
        CycleAdaptationReasonCode.LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY
        in decision.muscle_adjustments[0].reason_codes
    )


def test_preference_and_safety_changes_have_distinct_precedence_and_reasons(db) -> None:
    materialized = materialize_scenario(db, _scenario("intermediate_hypertrophy"))
    service = _service(db, _NeverCalledAIProvider())
    state = AthleteStateBuilder(db).build(materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)
    target_id = materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id

    disliked = state.model_copy(update={"persistent_disliked_exercises": (target_id,)})
    disliked_decision = decide_cycle_adaptation(disliked, history, RULESET)
    unsafe = disliked.model_copy(
        update={
            "pain_sensitive_exercises": (target_id,),
            "safety_context": (
                AthleteStateSafetyContext(
                    exercise_id=target_id,
                    signal_count=1,
                    source_safety_signal_ids=(uuid4(),),
                ),
            ),
        }
    )
    unsafe_decision = decide_cycle_adaptation(unsafe, history, RULESET)

    assert disliked_decision.preference_constraints.disliked_exercises == (target_id,)
    assert disliked_decision.safety_constraints.blocked_exercises == ()
    assert unsafe_decision.safety_constraints.blocked_exercises == (target_id,)
    assert unsafe_decision.preference_constraints.disliked_exercises == ()
    assert CycleAdaptationReasonCode.PAIN_SIGNAL_PRESENT in unsafe_decision.reason_codes
    assert CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_SAFETY in unsafe_decision.reason_codes


def test_non_generation_provenance_and_collection_order_do_not_change_effective_decision(
    db,
) -> None:
    materialized = materialize_scenario(db, _scenario("persistent_discomfort"))
    provider = _NeverCalledAIProvider()
    service = _service(db, provider)
    state = AthleteStateBuilder(db).build(materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)
    noisy = state.model_copy(
        update={
            "uncomfortable_exercises": tuple(reversed(state.uncomfortable_exercises)),
            "replacement_context": tuple(reversed(state.replacement_context)),
            "provenance": state.provenance.model_copy(
                update={
                    "cycle_ids": tuple(reversed(state.provenance.cycle_ids)),
                    "replacement_ids": tuple(reversed(state.provenance.replacement_ids)),
                    "weekly_check_in_ids": tuple(reversed(state.provenance.weekly_check_in_ids)),
                }
            ),
        }
    )
    first = decide_cycle_adaptation(state, history, RULESET)
    second = decide_cycle_adaptation(noisy, history, RULESET)
    profile = get_profile(db, materialized.user.id)
    first_request = service._to_program_request(
        profile,
        service._with_previous_volume_history(
            materialized.user.id,
            AthleteStateToGenerationOverridesAdapter.to_overrides(state),
        ),
    )
    second_request = service._to_program_request(
        profile,
        service._with_previous_volume_history(
            materialized.user.id,
            AthleteStateToGenerationOverridesAdapter.to_overrides(noisy),
        ),
    )
    catalog = service._load_catalog()

    assert first.overall_action == second.overall_action
    assert first.reason_codes == second.reason_codes
    assert first.preference_constraints == second.preference_constraints
    assert first.safety_constraints == second.safety_constraints
    first_program = generate_program(first_request, catalog, RULESET)
    second_program = generate_program(second_request, catalog, RULESET)
    assert first_program.is_success and second_program.is_success
    assert first_program.program == second_program.program
    assert provider.calls == 0


def test_difference_summary_is_complete_deterministic_and_has_no_noisy_entries(db) -> None:
    materialized = materialize_scenario(db, _scenario("intermediate_hypertrophy"))
    service = _service(db, _NeverCalledAIProvider())
    state = AthleteStateBuilder(db).build(materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)
    decision = decide_cycle_adaptation(state, history, RULESET)
    profile = get_profile(db, materialized.user.id)
    request = service._to_program_request(
        profile,
        service._with_previous_volume_history(
            materialized.user.id,
            AthleteStateToGenerationOverridesAdapter.to_overrides(state),
        ),
    )
    result = generate_program(request, service._load_catalog(), RULESET)
    assert result.is_success and result.program is not None
    previous = CycleAdaptationProgramSnapshot(
        program_id=materialized.cycles[0].workout_plan_id,
        cycle_id=materialized.cycles[0].id,
        weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 1.0},
        training_days=1,
        session_duration_minutes=20,
    )
    proposed = _program_snapshot(result.program)
    traced = decision.with_program_comparison(previous, proposed)
    repeated = decision.with_program_comparison(previous, proposed)

    assert traced.difference_summary
    assert traced.to_snapshot_json() == repeated.to_snapshot_json()
    assert all(item.previous != item.next for item in traced.difference_summary)
    assert all(item.reason_codes for item in traced.difference_summary)
    assert all(item.provenance.workout_plan_ids for item in traced.difference_summary)
    assert any(item.change.value == "overall_training_demand" for item in traced.difference_summary)
    assert any(item["stage"] == "difference_summary" for item in traced.decision_trace)


def test_internal_generation_keeps_ai_boundary_closed(db) -> None:
    materialized = materialize_scenario(db, _scenario("novice"))
    provider = _NeverCalledAIProvider()
    service = _service(db, provider)
    state = AthleteStateBuilder(db).build(materialized.user.id)

    result = asyncio.run(
        service.generate(
            materialized.user.id,
            AthleteStateToGenerationOverridesAdapter.to_overrides(state),
        )
    )

    assert result.plan.status.value == "pending_review"
    assert provider.calls == 0
