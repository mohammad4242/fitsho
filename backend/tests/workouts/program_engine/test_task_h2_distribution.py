from collections import Counter
from dataclasses import replace

import pytest

from app.workouts.program_engine.duration_policy import calculate_resistance_minutes
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.session_structure import session_structure_errors
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.weekly_distribution import redistribute_weekly_exercises
from tests.workouts.program_engine.golden_fixtures import full_catalog, request
from tests.workouts.program_engine.test_template_reference import _upper_lower_reference


def _run_batch2_profile(monkeypatch, profile_number: int):
    import scripts.generate_e2e_report_batch2 as batch2

    captured = []
    original_generate = batch2.generate_program

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        captured.append((args[0], result))
        return result

    monkeypatch.setattr(batch2, "generate_program", capture_generate)
    monkeypatch.setattr(
        batch2,
        "TEST_PROFILES_BATCH2",
        [profile for profile in batch2.TEST_PROFILES_BATCH2 if profile["num"] == profile_number],
    )
    results = batch2.run_batch2_profiles()

    assert len(results) == 1
    assert len(captured) == 1
    return results[0], captured[0]


def test_batch2_profile_8_redistributes_vestigial_resistance_day(monkeypatch) -> None:
    (profile, response), (source, generation) = _run_batch2_profile(monkeypatch, 8)

    assert response["success"] is True
    assert generation.program is not None, generation.errors
    program = generation.program
    distribution = program.aggregate_metrics["weekly_distribution"]

    assert profile["num"] == 8
    assert distribution["status"] == "applied"
    assert distribution["reason_codes"] == ("WEEKLY_REDISTRIBUTION_APPLIED",)
    assert distribution["before_exercise_counts"] == (6, 6, 6, 5, 3)
    assert distribution["after_exercise_counts"] == (6, 5, 6, 5, 4)
    assert min(distribution["after_exercise_counts"]) > min(distribution["before_exercise_counts"])
    assert sum(distribution["after_exercise_counts"]) == sum(distribution["before_exercise_counts"])
    assert len(distribution["moved_exercise_ids"]) == 1

    before_ids = Counter(distribution["before_exercise_ids"])
    after_ids = Counter(
        str(item.exercise_id) for day in program.weekly_schedule for item in day.exercises
    )
    assert before_ids == after_ids
    assert (
        distribution["before_direct_sets_by_muscle"] == distribution["after_direct_sets_by_muscle"]
    )
    assert (
        distribution["before_effective_sets_by_muscle"]
        == distribution["after_effective_sets_by_muscle"]
    )
    assert program.split.weekdays == (0, 1, 2, 3, 5)
    assert tuple(day.weekday for day in program.weekly_schedule) == program.split.weekdays
    assert recovery_spacing_is_valid(program.weekly_schedule, RULESET)
    assert all(
        not session_structure_errors(day, source.primary_goal, source)
        for day in program.weekly_schedule
    )
    assert all(
        RULESET.general_warmup_minutes
        <= day.estimated_duration_minutes
        <= source.session_duration_minutes + RULESET.general_warmup_minutes + 10
        for day in program.weekly_schedule
    )
    assert all(
        item.is_active
        and item.is_programmable
        and not item.needs_review
        and effective_required_equipment(item.equipment, item.movement_pattern).issubset(
            source.available_equipment
        )
        and not effective_caution_tags(item).intersection(source.blocked_caution_tags)
        for day in program.weekly_schedule
        for item in day.exercises
    )

    effective = calculate_effective_volume(
        (item for day in program.weekly_schedule for item in day.exercises), RULESET
    )
    assert effective.effective_sets_by_muscle == distribution["after_effective_sets_by_muscle"]


@pytest.mark.parametrize("profile_number, before_counts", [(5, (5, 3, 4)), (10, (4, 5, 2))])
def test_batch2_constrained_controls_preserve_volume_and_day_count(
    monkeypatch, profile_number: int, before_counts: tuple[int, ...]
) -> None:
    (profile, response), (source, generation) = _run_batch2_profile(monkeypatch, profile_number)

    assert response["success"] is True
    assert generation.program is not None, generation.errors
    program = generation.program
    distribution = program.aggregate_metrics["weekly_distribution"]

    assert profile["num"] == profile_number
    assert len(program.weekly_schedule) == source.available_training_days
    assert distribution["before_exercise_counts"] == before_counts
    assert sum(distribution["after_exercise_counts"]) == sum(before_counts)
    assert {
        "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
        "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
    }.issubset(program.validation_report.warnings)
    assert (
        distribution["before_effective_sets_by_muscle"]
        == distribution["after_effective_sets_by_muscle"]
    )
    assert (
        distribution["before_direct_sets_by_muscle"] == distribution["after_direct_sets_by_muscle"]
    )
    assert Counter(distribution["before_exercise_ids"]) == Counter(
        str(item.exercise_id) for day in program.weekly_schedule for item in day.exercises
    )
    assert recovery_spacing_is_valid(program.weekly_schedule, RULESET)
    assert all(
        not session_structure_errors(day, source.primary_goal, source)
        for day in program.weekly_schedule
    )
    assert all(
        calculate_resistance_minutes(day, RULESET.general_warmup_minutes)
        <= source.session_duration_minutes + 10
        for day in program.weekly_schedule
    )
    assert all(
        item.is_active
        and item.is_programmable
        and not item.needs_review
        and effective_required_equipment(item.equipment, item.movement_pattern).issubset(
            source.available_equipment
        )
        and not effective_caution_tags(item).intersection(source.blocked_caution_tags)
        for day in program.weekly_schedule
        for item in day.exercises
    )


def test_weekly_redistribution_reports_stable_constrained_reason_without_safe_move() -> None:
    source = request(available_training_days=2, session_duration_minutes=45)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    base_days = result.program.weekly_schedule
    core_days = tuple(
        replace(
            day,
            exercises=tuple(
                replace(
                    item,
                    reason_codes=(*item.reason_codes, "TEMPLATE_ADAPTATION_PRIORITY:core"),
                )
                for item in day.exercises
            ),
        )
        for day in base_days
    )
    imbalanced_days = (
        replace(core_days[0], exercises=core_days[0].exercises[:4]),
        replace(core_days[1], exercises=core_days[1].exercises[:1]),
    )
    normalized = normalize_request(source, RULESET)

    first = redistribute_weekly_exercises(
        imbalanced_days,
        normalized,
        RULESET,
        preserve_template_core_structure=True,
    )
    second = redistribute_weekly_exercises(
        imbalanced_days,
        normalized,
        RULESET,
        preserve_template_core_structure=True,
    )

    assert first == second
    assert first.status == "constrained"
    assert first.reason_codes == ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",)
    assert first.days == imbalanced_days


def test_donor_at_main_exercise_floor_is_not_depleted() -> None:
    source = request(available_training_days=2, session_duration_minutes=60)
    generated = generate_program(source, full_catalog(), RULESET)
    assert generated.program is not None, generated.errors
    base_days = generated.program.weekly_schedule
    imbalanced_days = (
        replace(base_days[0], exercises=base_days[0].exercises[:3]),
        replace(base_days[1], exercises=base_days[1].exercises[:5]),
    )

    result = redistribute_weekly_exercises(
        imbalanced_days,
        normalize_request(source, RULESET),
        RULESET,
    )

    assert result.before_exercise_counts == (3, 5)
    assert result.after_exercise_counts == (3, 5)
    assert (
        main_exercise_count(imbalanced_days[1].exercises) == RULESET.minimum_exercises_per_session
    )
    assert main_exercise_count(result.days[1].exercises) == RULESET.minimum_exercises_per_session
    assert result.status == "constrained"
    assert result.reason_codes == ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",)
    assert result.days == imbalanced_days


def test_template_non_core_work_without_slot_metadata_stays_stationary() -> None:
    source = request(available_training_days=3, session_duration_minutes=60)
    generated = generate_program(source, full_catalog(), RULESET)
    assert generated.program is not None, generated.errors
    base_days = generated.program.weekly_schedule
    candidate = base_days[0].exercises[1]
    assert candidate.primary_muscle is not None
    template_days = tuple(
        replace(
            day,
            focus=f"template_reference_{index + 1}",
            template_target_muscles=(candidate.primary_muscle,),
            exercises=tuple(
                replace(
                    item,
                    reason_codes=(
                        *item.reason_codes,
                        "TEMPLATE_REFERENCE_EXERCISE",
                    ),
                )
                for item in day.exercises
            ),
        )
        for index, day in enumerate(base_days)
    )
    donor = template_days[0]
    recipient = replace(template_days[2], exercises=template_days[2].exercises[:4])
    imbalanced_days = (donor, template_days[1], recipient)

    result = redistribute_weekly_exercises(
        imbalanced_days,
        normalize_request(source, RULESET),
        RULESET,
        preserve_template_core_structure=True,
    )

    assert result.status == "constrained"
    assert result.reason_codes == ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",)
    assert result.days == imbalanced_days


def test_template_redistribution_preserves_core_exercise_ownership() -> None:
    template, catalog = _upper_lower_reference()
    template = replace(template, slug="task-h2-core-ownership-reference")
    source = request(
        available_training_days=4,
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        session_duration_minutes=60,
    )

    result = generate_program(source, catalog, RULESET, reference_templates=(template,))

    assert result.program is not None, result.errors
    distribution = result.program.aggregate_metrics["weekly_distribution"]
    assert distribution["status"] in {"applied", "not_needed", "constrained"}
    assert distribution["before_exercise_counts"]
    for reference_day, output_day in zip(
        template.days, result.program.weekly_schedule, strict=True
    ):
        core_ids = {
            slot.exercise_id
            for slot in reference_day.slots
            if slot.adaptation_priority == "core" and slot.exercise_id is not None
        }
        output_ids = {item.exercise_id for item in output_day.exercises}
        assert core_ids <= output_ids
