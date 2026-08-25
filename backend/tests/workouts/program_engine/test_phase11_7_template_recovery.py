from dataclasses import replace

from app.exercises.enums import ExerciseCautionTag, MovementPattern, MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ProgramGenerationResult,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_selector import select_template_reference_result
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request
from tests.workouts.program_engine.test_template_reference import (
    _four_day_reference,
    _upper_lower_reference,
    template_request,
)


def _unadaptable_reference(slug: str, *focus_tags: str) -> TemplateReference:
    base = _four_day_reference()
    return replace(
        base,
        slug=slug,
        focus_tags=focus_tags or (TemplateFocusTag.CHEST_PRIORITY.value,),
        days=tuple(replace(base.days[0], day_number=index) for index in range(1, 5)),
    )


def _empty_reference(slug: str, *focus_tags: str) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=4,
        supported_levels=("intermediate",),
        fitness_goal="build_muscle",
        focus_tags=focus_tags,
        intensity_methods=("standard",),
        days=(),
    )


def _recovery_request(**overrides: object):
    values: dict[str, object] = {
        "available_training_days": 4,
        "primary_goal": "build_muscle",
        "training_experience": "intermediate",
        "training_age_months": 24,
        "session_duration_minutes": 60,
        "priority_muscles": [MuscleGroup.CHEST],
    }
    values.update(overrides)
    return template_request(**values)


def _template_attempts(result: ProgramGenerationResult) -> tuple[dict[str, object], ...]:
    program = result.program
    trace = program.decision_trace if program is not None else result.decision_trace
    return tuple(entry for entry in trace if entry.get("stage") == "template_attempt")


def test_top_ranked_template_failure_recovers_with_second_without_dynamic_fallback() -> None:
    good = replace(
        _four_day_reference(),
        slug="a-second-good",
        focus_tags=(TemplateFocusTag.BALANCED.value,),
    )
    result = generate_program(
        _recovery_request(),
        full_catalog(),
        RULESET,
        reference_templates=(_unadaptable_reference("z-top-failing"), good),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == good.slug
    assert [entry["slug"] for entry in _template_attempts(result)] == [
        "z-top-failing",
        "a-second-good",
    ]
    assert [entry["status"] for entry in _template_attempts(result)] == [
        "rejected",
        "succeeded",
    ]
    assert not any(
        entry.get("stage") == "construction_recovery" for entry in result.program.decision_trace
    )


def test_multiple_ranked_templates_fail_before_later_template_succeeds() -> None:
    good = replace(
        _four_day_reference(),
        slug="a-later-good",
        focus_tags=(TemplateFocusTag.BALANCED.value,),
    )
    result = generate_program(
        _recovery_request(),
        full_catalog(),
        RULESET,
        reference_templates=(
            _unadaptable_reference("z-first-failing"),
            _empty_reference("y-second-failing", TemplateFocusTag.UPPER_PRIORITY.value),
            good,
        ),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == good.slug
    attempts = _template_attempts(result)
    assert [entry["rank"] for entry in attempts] == [1, 2, 3]
    assert [entry["slug"] for entry in attempts] == [
        "z-first-failing",
        "y-second-failing",
        "a-later-good",
    ]
    assert attempts[0]["reason_codes"]
    assert attempts[1]["reason_codes"]
    assert attempts[2]["status"] == "succeeded"
    rejections = tuple(
        entry
        for entry in result.program.decision_trace
        if entry.get("stage") == "template_reference" and entry.get("status") == "rejected"
    )
    assert all(
        not any(
            item.get("stage") in {"template_selection", "template_attempt"}
            for item in rejection.get("decision_trace", ())
        )
        for rejection in rejections
    )


def test_all_template_candidates_are_exhausted_before_dynamic_fallback() -> None:
    result = generate_program(
        _recovery_request(),
        full_catalog(),
        RULESET,
        reference_templates=(
            _unadaptable_reference("z-first-failing"),
            _empty_reference("y-second-failing", TemplateFocusTag.UPPER_PRIORITY.value),
        ),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics.get("reference_template") is None
    attempts = _template_attempts(result)
    assert [entry["status"] for entry in attempts] == ["rejected", "rejected"]
    exhausted = next(
        entry
        for entry in result.program.decision_trace
        if entry.get("stage") == "template_recovery"
    )
    assert exhausted["status"] == "exhausted"
    assert exhausted["attempted_count"] == 2
    assert exhausted["reason_codes"] == ("TEMPLATE_ALTERNATIVES_EXHAUSTED",)
    assert any(
        entry.get("stage") == "construction_recovery" for entry in result.program.decision_trace
    )


def test_template_retry_order_and_trace_are_deterministic() -> None:
    templates = (
        _unadaptable_reference("z-first-failing"),
        _empty_reference("y-second-failing", TemplateFocusTag.UPPER_PRIORITY.value),
        replace(
            _four_day_reference(),
            slug="a-later-good",
            focus_tags=(TemplateFocusTag.BALANCED.value,),
        ),
    )
    source = _recovery_request()

    first = generate_program(source, full_catalog(), RULESET, reference_templates=templates)
    second = generate_program(
        source,
        tuple(reversed(full_catalog())),
        RULESET,
        reference_templates=tuple(reversed(templates)),
    )

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    assert _template_attempts(first) == _template_attempts(second)
    assert first.program == second.program


def test_retry_preserves_safety_equipment_limitations_and_exact_day_count() -> None:
    good, catalog = _upper_lower_reference()
    catalog.append(
        exercise(
            "extra-safe-chest-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
        )
    )
    good = replace(
        good,
        slug="a-safe-good",
        focus_tags=(TemplateFocusTag.BALANCED.value,),
    )
    blocked_id = good.days[0].slots[0].exercise_id
    assert blocked_id is not None
    source = _recovery_request(
        blocked_exercises=[blocked_id],
        blocked_movement_patterns=[MovementPattern.VERTICAL_PUSH],
        blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
    )

    result = generate_program(
        source,
        catalog,
        RULESET,
        reference_templates=(_unadaptable_reference("z-top-failing"), good),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == good.slug
    assert len(result.program.weekly_schedule) == source.available_training_days
    catalog_by_id = {candidate.id: candidate for candidate in catalog}
    for day in result.program.weekly_schedule:
        for programmed in day.exercises:
            candidate = catalog_by_id[programmed.exercise_id]
            assert candidate.id != blocked_id
            assert candidate.movement_pattern not in source.blocked_movement_patterns
            assert not candidate.caution_tags.intersection(source.blocked_caution_tags)
            assert candidate.equipment.issubset(source.available_equipment)


def test_equal_scores_prefer_more_feasible_template_deterministically() -> None:
    catalog = tuple(full_catalog())
    exact_candidate = next(
        item
        for item in catalog
        if item.movement_pattern is MovementPattern.HORIZONTAL_PUSH
        and item.primary_muscle is MuscleGroup.CHEST
    )

    def candidate(slug: str, exercise_id: object) -> TemplateReference:
        return TemplateReference(
            slug=slug,
            days_per_week=4,
            supported_levels=("intermediate",),
            fitness_goal="build_muscle",
            focus_tags=(TemplateFocusTag.BALANCED.value,),
            intensity_methods=("standard",),
            days=(
                TemplateReferenceDay(
                    day_number=1,
                    title=slug,
                    focus=(MuscleGroup.CHEST,),
                    slots=(
                        TemplateReferenceSlot(
                            exercise_id=exercise_id,
                            exercise_slug_hint=slug,
                            target_muscles=(MuscleGroup.CHEST,),
                            movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                            intensity_method="standard",
                            adaptation_priority="core",
                            superset_group=None,
                            sets=3,
                            rep_min=8,
                            rep_max=12,
                            target_rir=2,
                            rest_seconds=90,
                        ),
                    ),
                ),
            ),
        )

    normalized = normalize_request(
        request(
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            available_training_days=4,
        ),
        RULESET,
    )
    exact = candidate("a-exact", exact_candidate.id)
    substitution = candidate("z-substitution", None)

    first = select_template_reference_result(normalized, catalog, (substitution, exact), RULESET)
    second = select_template_reference_result(normalized, catalog, (exact, substitution), RULESET)

    assert first == second
    assert [item.template.slug for item in first.candidates] == ["a-exact", "z-substitution"]
    trace = first.decision_trace()
    assert trace["candidates"][0]["rank"] == 1
    assert trace["candidates"][0]["feasibility"]["exact_slot_matches"] == 1
    assert trace["candidates"][1]["feasibility"]["substitution_slots"] == 1
