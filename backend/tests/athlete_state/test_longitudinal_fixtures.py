from __future__ import annotations

from sqlalchemy.orm import Session

from app.athlete_state.service import AthleteStateBuilder
from app.profile.enums import HomeTrainingSetup, TrainingLocation
from tests.athlete_state.longitudinal_fixtures import (
    LongitudinalScenario,
    longitudinal_scenarios,
    materialize_scenario,
)


def test_all_longitudinal_scenarios_have_stable_keys_and_defining_signals() -> None:
    scenarios = longitudinal_scenarios()

    assert {scenario.key for scenario in scenarios} == {
        "novice",
        "intermediate_hypertrophy",
        "advanced_strength",
        "plateau_lagging_muscle",
        "low_adherence",
        "poor_recovery",
        "home_equipment_limited",
        "persistent_discomfort",
        "pain_safety",
    }
    assert all(isinstance(scenario, LongitudinalScenario) for scenario in scenarios)
    assert all(scenario.fingerprint() == scenario.fingerprint() for scenario in scenarios)
    assert all(scenario.defining_signals for scenario in scenarios)


def test_longitudinal_scenarios_are_deterministic() -> None:
    first = [scenario.fingerprint() for scenario in longitudinal_scenarios()]
    second = [scenario.fingerprint() for scenario in longitudinal_scenarios()]

    assert first == second


def test_longitudinal_scenarios_materialize_isolated_athlete_histories(
    db: Session,
) -> None:
    materialized = [materialize_scenario(db, scenario) for scenario in longitudinal_scenarios()]

    assert len({item.user.id for item in materialized}) == len(materialized)
    assert all(item.cycles for item in materialized)
    assert all(
        not set(item.cycle_ids).intersection(
            other_cycle_id
            for other in materialized
            if other is not item
            for other_cycle_id in other.cycle_ids
        )
        for item in materialized
    )


def test_each_scenario_builds_athlete_state_and_exposes_defining_signals(
    db: Session,
) -> None:
    for scenario in longitudinal_scenarios():
        materialized = materialize_scenario(db, scenario)
        state = AthleteStateBuilder(db).build(materialized.user.id)

        assert state.user_id == materialized.user.id
        assert state.provenance.cycle_ids
        assert state.provenance.workout_plan_ids

        if scenario.key == "low_adherence":
            assert state.adherence.percent == 0.0
        elif scenario.key == "poor_recovery":
            assert state.recovery_trend.summary.value == "poor"
        elif scenario.key == "home_equipment_limited":
            assert state.schedule.training_location is TrainingLocation.HOME
            assert state.schedule.home_training_setup is HomeTrainingSetup.BODYWEIGHT_ONLY
        elif scenario.key == "persistent_discomfort":
            assert state.uncomfortable_exercises
        elif scenario.key == "pain_safety":
            assert state.pain_sensitive_exercises
            assert state.safety_context


def test_scenario_defining_signals_are_backed_by_structured_history() -> None:
    scenarios = {scenario.key: scenario for scenario in longitudinal_scenarios()}

    assert not any(cycle.check_ins for cycle in scenarios["novice"].cycles)
    assert any(
        cycle.feedback and cycle.feedback.progressed_muscles
        for cycle in scenarios["intermediate_hypertrophy"].cycles
    )
    assert scenarios["advanced_strength"].cycles[0].duration_weeks == 6
    assert any(cycle.body_progress for cycle in scenarios["plateau_lagging_muscle"].cycles)
    assert any(
        check_in.sessions_completed == 0
        for cycle in scenarios["low_adherence"].cycles
        for check_in in cycle.check_ins
    )
    assert all(
        check_in.recovery_rating.value == "poor"
        for check_in in scenarios["poor_recovery"].cycles[0].check_ins
    )
    assert scenarios["home_equipment_limited"].profile.home_training_setup is not None
    assert any(
        replacement.preference_type is not None
        for replacement in scenarios["persistent_discomfort"].cycles[0].replacements
    )
    assert all(
        replacement.safety_signal for replacement in scenarios["pain_safety"].cycles[0].replacements
    )
