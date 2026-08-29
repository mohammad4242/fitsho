from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.athlete_state.generation_adapter import AthleteStateToGenerationOverridesAdapter
from app.athlete_state.service import AthleteStateBuilder
from app.exercises.enums import MuscleGroup
from app.exercises.models import Exercise
from app.profile.enums import WorkoutGenerationMethod
from app.profile.service import get_profile
from app.workouts.ai_coach_provider import OpenRouterAiCoachProvider
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise
from app.workouts.program_engine.adaptation_policy import (
    CycleAdaptationAction,
    CycleAdaptationProgramSnapshot,
    CycleAdaptationReasonCode,
    decide_cycle_adaptation,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
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


def _service(db: Session, provider: _NeverCalledAIProvider) -> WorkoutGenerationService:
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


def _run_transition(
    db: Session, key: str
) -> tuple[WorkoutGenerationService, object, object, object, object, _NeverCalledAIProvider]:
    scenario = next(item for item in longitudinal_scenarios() if item.key == key)
    materialized = materialize_scenario(db, scenario)
    provider = _NeverCalledAIProvider()
    service = _service(db, provider)
    state = AthleteStateBuilder(db).build(materialized.user.id)
    history = service._previous_volume_history(materialized.user.id)
    decision = decide_cycle_adaptation(state, history, RULESET)
    result = asyncio.run(
        service.generate(
            materialized.user.id,
            AthleteStateToGenerationOverridesAdapter.to_overrides(state),
        )
    )
    return service, materialized, state, decision, result, provider


def _effective_metrics(plan: WorkoutPlan) -> dict[MuscleGroup, float]:
    raw = plan.aggregate_metrics.get("weekly_effective_sets_by_muscle", {})
    return {MuscleGroup(muscle): float(sets) for muscle, sets in raw.items()}


def _exercise_ids(db: Session, plan_id: UUID) -> set[UUID]:
    return set(
        db.scalars(
            select(WorkoutPlanExercise.exercise_id)
            .join(WorkoutDay, WorkoutDay.id == WorkoutPlanExercise.workout_day_id)
            .where(WorkoutDay.workout_plan_id == plan_id)
        ).all()
    )


def _snapshot(plan: WorkoutPlan) -> CycleAdaptationProgramSnapshot:
    return CycleAdaptationProgramSnapshot(
        program_id=plan.id,
        weekly_effective_sets_by_muscle=_effective_metrics(plan),
        training_days=len(plan.days),
        session_duration_minutes=plan.days[0].estimated_duration_minutes if plan.days else None,
    )


def test_high_adherence_and_good_recovery_allow_conservative_progression(db: Session) -> None:
    _service, _materialized, state, decision, result, provider = _run_transition(
        db, "intermediate_hypertrophy"
    )

    assert state.adherence.percent == 100
    assert decision.overall_action is CycleAdaptationAction.INCREASE
    assert CycleAdaptationReasonCode.PROGRESSION_ALLOWED in decision.reason_codes
    assert (
        decision.volume_context.confidence
        >= RULESET.adaptation_min_volume_confidence_for_progression
    )
    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert provider.calls == 0

    previous_total = sum(decision.volume_context.previous_effective_sets_by_muscle.values())
    proposed_total = sum(_effective_metrics(result.plan).values())
    assert proposed_total <= previous_total * (1 + RULESET.max_previous_volume_increase)


def test_low_adherence_does_not_become_a_completed_volume_baseline(db: Session) -> None:
    _service, _materialized, state, decision, result, _provider = _run_transition(
        db, "low_adherence"
    )

    assert state.adherence.percent == 0
    assert decision.overall_action is not CycleAdaptationAction.INCREASE
    assert decision.volume_context.confidence == 0
    assert decision.volume_context.previous_effective_sets_by_muscle == {}
    assert CycleAdaptationReasonCode.LOW_ADHERENCE in decision.reason_codes
    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW


def test_lagging_muscle_gets_a_targeted_adjustment_when_recovery_supports_it(
    db: Session,
) -> None:
    _service, _materialized, state, decision, result, _provider = _run_transition(
        db, "plateau_lagging_muscle"
    )

    assert state.lagging_muscles
    adjustment = next(
        item for item in decision.muscle_adjustments if item.muscle.value == "shoulders"
    )
    assert decision.overall_action is CycleAdaptationAction.INCREASE
    assert adjustment.volume_delta_sets == RULESET.adaptation_lagging_muscle_volume_delta_sets
    assert adjustment.priority_delta == RULESET.adaptation_lagging_muscle_priority_delta
    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW


def test_persistent_discomfort_is_excluded_from_cycle_two_candidates(db: Session) -> None:
    _service, materialized, state, decision, result, _provider = _run_transition(
        db, "persistent_discomfort"
    )

    original_id = materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id
    assert original_id in decision.preference_constraints.disliked_exercises
    assert original_id not in decision.safety_constraints.blocked_exercises
    assert original_id not in _exercise_ids(db, result.plan.id)


def test_equipment_limited_cycle_two_avoids_dumbbell_exercises(db: Session) -> None:
    _service, materialized, _state, decision, result, _provider = _run_transition(
        db, "home_equipment_limited"
    )

    dumbbell_ids = set(
        db.scalars(select(Exercise.id).where(Exercise.slug.like("%dumbbell-chest"))).all()
    )
    assert decision.preference_constraints.unavailable_exercises == ()
    assert not dumbbell_ids.intersection(_exercise_ids(db, result.plan.id))
    assert materialized.cycles[-1].status.value == "active"


def test_pain_signal_blocks_exercise_from_normal_cycle_two_selection(db: Session) -> None:
    _service, materialized, state, decision, result, _provider = _run_transition(db, "pain_safety")

    original_id = materialized.cycles[0].workout_plan.days[0].exercises[0].exercise_id
    assert original_id in state.pain_sensitive_exercises
    assert original_id in decision.safety_constraints.blocked_exercises
    assert original_id not in decision.preference_constraints.disliked_exercises
    assert original_id not in _exercise_ids(db, result.plan.id)
    assert CycleAdaptationReasonCode.PAIN_SIGNAL_PRESENT in decision.reason_codes


def test_decision_trace_explains_cycle_transition_without_noisy_unchanged_entries(
    db: Session,
) -> None:
    _service, materialized, state, decision, result, _provider = _run_transition(
        db, "intermediate_hypertrophy"
    )
    previous = _snapshot(materialized.cycles[0].workout_plan)
    proposed = _snapshot(result.plan)
    traced = decision.with_program_comparison(previous, proposed)

    assert traced.difference_summary
    assert all(item.reason_codes for item in traced.difference_summary)
    assert all(item.provenance.cycle_ids for item in traced.difference_summary)
    assert all(
        item.previous != item.next
        for item in traced.difference_summary
        if item.change.value != "schedule"
    )
    assert traced.to_snapshot_json() == traced.to_snapshot_json()
    assert state.provenance.cycle_ids


def test_same_cycle_two_inputs_produce_identical_deterministic_programs(db: Session) -> None:
    service, materialized, state, _decision, _result, provider = _run_transition(
        db, "intermediate_hypertrophy"
    )
    profile = get_profile(db, materialized.user.id)
    overrides = AthleteStateToGenerationOverridesAdapter.to_overrides(state)
    request = service._to_program_request(
        profile,
        service._with_previous_volume_history(materialized.user.id, overrides),
    )
    catalog = service._load_catalog()
    first = generate_program(request, catalog, RULESET)
    second = generate_program(request, catalog, RULESET)

    assert first.is_success and second.is_success
    assert first.program == second.program
    assert provider.calls == 0
