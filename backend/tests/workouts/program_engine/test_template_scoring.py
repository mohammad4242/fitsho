from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.duration_capacity import (
    CapacityFeasibility,
    build_session_capacity,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_scoring import TemplateScore, score_template_reference
from app.workouts.program_engine.template_selector import (
    eligible_template_references,
    rank_template_references,
    select_template_reference,
    select_template_reference_result,
)
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def _template(
    slug: str,
    *focus_tags: TemplateFocusTag,
    days_per_week: int = 4,
    training_level: str = "intermediate",
) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=days_per_week,
        supported_levels=(training_level,),
        focus_tags=focus_tags,
        intensity_methods=("standard",),
        days=(),
    )


def _duration_template(
    slug: str,
    *,
    core_slots: int,
    optional_slots: int,
) -> TemplateReference:
    candidates = tuple(
        item
        for item in full_catalog()
        if item.exercise_type is ExerciseType.COMPOUND and item.primary_muscle is not None
    )[: core_slots + optional_slots]
    slots = tuple(
        TemplateReferenceSlot(
            exercise_id=candidate.id,
            exercise_slug_hint=f"{slug}-{index}",
            target_muscles=(candidate.primary_muscle,),
            movement_pattern=candidate.movement_pattern,
            intensity_method="standard",
            adaptation_priority="core" if index < core_slots else "optional",
            superset_group=None,
            superset_exercise_id=None,
            superset_exercise_slug_hint=None,
            sets=3,
            rep_min=5,
            rep_max=10,
            target_rir=2,
            rest_seconds=120,
        )
        for index, candidate in enumerate(candidates)
    )
    return TemplateReference(
        slug=slug,
        days_per_week=4,
        supported_levels=("intermediate",),
        focus_tags=(TemplateFocusTag.BALANCED,),
        intensity_methods=("standard",),
        days=tuple(
            TemplateReferenceDay(
                day_number=day_number,
                title=f"{slug}-{day_number}",
                focus=tuple(dict.fromkeys(item.primary_muscle for item in candidates)),
                slots=slots,
            )
            for day_number in range(1, 5)
        ),
    )


def _normalized(**overrides: object):
    values: dict[str, object] = {
        "primary_goal": Goal.HYPERTROPHY,
        "training_experience": TrainingExperience.INTERMEDIATE,
        "training_age_months": 24,
        "available_training_days": 4,
        "session_duration_minutes": 60,
    }
    values.update(overrides)
    return normalize_request(request(**values), RULESET)


def _body_analysis(
    *priorities: tuple[MuscleGroup, str],
) -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid4(),
            "result_version_id": uuid4(),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.9,
            "priorities": [
                {
                    "muscle": muscle,
                    "classification": classification,
                    "confidence": 0.9,
                    "severity": 0.8,
                }
                for muscle, classification in priorities
            ],
        }
    )


def _score(request_value, template: TemplateReference) -> TemplateScore:
    return score_template_reference(request_value, template, RULESET)


def test_exact_explicit_priority_beats_regional_and_balanced_templates() -> None:
    normalized = _normalized(priority_muscles=[MuscleGroup.GLUTES])
    exact = _template("a-exact", TemplateFocusTag.GLUTE_PRIORITY)
    regional = _template("z-regional", TemplateFocusTag.LOWER_PRIORITY)
    balanced = _template("zz-balanced", TemplateFocusTag.BALANCED)

    assert _score(normalized, exact).priority_score == 100
    assert _score(normalized, regional).priority_score == 40
    assert (
        select_template_reference(
            normalized, tuple(full_catalog()), (balanced, regional, exact), RULESET
        )
        == exact
    )


def test_four_day_upper_priority_template_reports_specialization_split() -> None:
    template = _template(
        "four-day-upper-priority",
        TemplateFocusTag.UPPER_LOWER,
        TemplateFocusTag.UPPER_PRIORITY,
        days_per_week=4,
    )

    assert template.split_type is SplitType.UPPER_LOWER_SPECIALIZATION


def test_regional_explicit_priority_beats_unrelated_alternative() -> None:
    normalized = _normalized(priority_muscles=[MuscleGroup.CHEST])
    regional = _template("a-upper", TemplateFocusTag.UPPER_PRIORITY)
    unrelated = _template("z-lower", TemplateFocusTag.LOWER_PRIORITY)

    assert _score(normalized, regional).priority_score == 40
    assert _score(normalized, unrelated).priority_score == 0
    assert (
        select_template_reference(normalized, tuple(full_catalog()), (unrelated, regional), RULESET)
        == regional
    )


@pytest.mark.parametrize(
    "muscle",
    [
        MuscleGroup.FOREARMS,
        MuscleGroup.ABS,
        MuscleGroup.OBLIQUES,
        MuscleGroup.LOWER_BACK,
        MuscleGroup.NECK,
    ],
)
def test_supplemental_priority_does_not_drive_template_scoring(muscle: MuscleGroup) -> None:
    normalized = _normalized(priority_muscles=[muscle])
    upper = _template("upper", TemplateFocusTag.UPPER_PRIORITY)
    lower = _template("lower", TemplateFocusTag.LOWER_PRIORITY)

    assert _score(normalized, upper).priority_score == 0
    assert _score(normalized, lower).priority_score == 0


def test_supplemental_body_analysis_does_not_drive_template_scoring() -> None:
    normalized = _normalized(
        body_analysis_influence=_body_analysis((MuscleGroup.FOREARMS, "clear_lag")),
    )
    upper = _template("upper", TemplateFocusTag.UPPER_PRIORITY)

    assert _score(normalized, upper).body_analysis_score == 0


def test_explicit_priority_dominates_conflicting_body_analysis() -> None:
    normalized = _normalized(
        priority_muscles=[MuscleGroup.CHEST],
        body_analysis_influence=_body_analysis((MuscleGroup.GLUTES, "clear_lag")),
    )
    explicit = _template("a-chest", TemplateFocusTag.CHEST_PRIORITY)
    analysis = _template("z-glutes", TemplateFocusTag.GLUTE_PRIORITY)

    assert _score(normalized, explicit) == TemplateScore(100, 0, 0, 0, 0)
    assert _score(normalized, analysis) == TemplateScore(0, 40, 0, 0, 0)
    assert (
        select_template_reference(normalized, tuple(full_catalog()), (analysis, explicit), RULESET)
        == explicit
    )


def test_clear_body_lag_beats_mild_lag_without_explicit_priority() -> None:
    normalized = _normalized(
        body_analysis_influence=_body_analysis(
            (MuscleGroup.CHEST, "clear_lag"),
            (MuscleGroup.BACK, "mild_lag"),
        )
    )
    clear = _template("a-chest", TemplateFocusTag.CHEST_PRIORITY)
    mild = _template("z-back", TemplateFocusTag.BACK_PRIORITY)

    assert _score(normalized, clear).body_analysis_score == 40
    assert _score(normalized, mild).body_analysis_score == 20
    assert (
        select_template_reference(normalized, tuple(full_catalog()), (mild, clear), RULESET)
        == clear
    )


def test_body_analysis_component_is_capped() -> None:
    normalized = _normalized(
        body_analysis_influence=_body_analysis(
            (MuscleGroup.CHEST, "clear_lag"),
            (MuscleGroup.BACK, "clear_lag"),
        )
    )
    template = _template(
        "upper-specialization",
        TemplateFocusTag.CHEST_PRIORITY,
        TemplateFocusTag.BACK_PRIORITY,
    )

    assert _score(normalized, template).body_analysis_score == 40


def test_strength_prefers_real_structural_affinity_without_changing_eligibility() -> None:
    templates = (
        _template("z-balanced", TemplateFocusTag.BALANCED),
        _template("a-compound", TemplateFocusTag.COMPOUND_FOCUS),
        _template("b-strength", TemplateFocusTag.STRENGTH_BIAS),
    )
    strength = _normalized(primary_goal=Goal.STRENGTH)
    hypertrophy = _normalized(primary_goal=Goal.HYPERTROPHY)

    assert _score(strength, templates[1]).goal_score == 10
    assert _score(strength, templates[2]).goal_score == 25
    assert (
        select_template_reference(strength, tuple(full_catalog()), templates, RULESET)
        == templates[2]
    )
    assert eligible_template_references(strength, tuple(full_catalog()), templates) == (
        eligible_template_references(hypertrophy, tuple(full_catalog()), templates)
    )


@pytest.mark.parametrize("goal", [Goal.GENERAL_FITNESS, Goal.BODY_RECOMPOSITION])
def test_balanced_structure_has_small_goal_affinity_only_for_supported_goals(goal: Goal) -> None:
    balanced = _template("balanced", TemplateFocusTag.BALANCED)
    unrelated = _template("unrelated", TemplateFocusTag.GLUTE_PRIORITY)

    assert _score(_normalized(primary_goal=goal), balanced).goal_score == 10
    assert _score(_normalized(primary_goal=goal), unrelated).goal_score == 0
    assert _score(_normalized(primary_goal=Goal.FAT_LOSS), balanced).goal_score == 0
    assert _score(_normalized(primary_goal=Goal.MUSCLE_GAIN), unrelated).goal_score == 0


def test_female_without_explicit_priority_prefers_glute_then_lower() -> None:
    normalized = _normalized(biological_sex_optional="female")
    glute = _template("a-glute", TemplateFocusTag.GLUTE_PRIORITY)
    lower = _template("b-lower", TemplateFocusTag.LOWER_PRIORITY)
    unrelated = _template("z-unrelated", TemplateFocusTag.BACK_PRIORITY)

    assert _score(normalized, glute).sex_score == 20
    assert _score(normalized, lower).sex_score == 10
    assert _score(normalized, unrelated).sex_score == 0


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        (TemplateFocusTag.CHEST_PRIORITY, 20),
        (TemplateFocusTag.BACK_PRIORITY, 20),
        (TemplateFocusTag.UPPER_PRIORITY, 10),
        (TemplateFocusTag.LOWER_PRIORITY, 0),
    ],
)
def test_male_without_explicit_priority_has_capped_upper_affinity(
    tag: TemplateFocusTag, expected: int
) -> None:
    normalized = _normalized(biological_sex_optional="male")
    assert _score(normalized, _template(tag.value, tag)).sex_score == expected


def test_explicit_priority_disables_sex_score_and_sex_bonus_does_not_stack() -> None:
    female = _normalized(biological_sex_optional="female")
    overlapping = _template(
        "glute-lower",
        TemplateFocusTag.GLUTE_PRIORITY,
        TemplateFocusTag.LOWER_PRIORITY,
    )
    explicit = _normalized(
        biological_sex_optional="female",
        priority_muscles=[MuscleGroup.CHEST],
    )

    assert _score(female, overlapping).sex_score == 20
    assert _score(explicit, overlapping).sex_score == 0


@pytest.mark.parametrize("sex", [None, "unknown", "other", "prefer_not_to_say"])
def test_non_binary_or_missing_sex_is_neutral(sex: str | None) -> None:
    assert (
        _score(
            _normalized(biological_sex_optional=sex),
            _template("glute", TemplateFocusTag.GLUTE_PRIORITY),
        ).sex_score
        == 0
    )


def test_multiple_explicit_priorities_are_capped() -> None:
    normalized = _normalized(
        priority_muscles=[
            MuscleGroup.CHEST,
            MuscleGroup.BACK,
            MuscleGroup.GLUTES,
        ]
    )
    template = _template(
        "many-priorities",
        TemplateFocusTag.CHEST_PRIORITY,
        TemplateFocusTag.BACK_PRIORITY,
        TemplateFocusTag.GLUTE_PRIORITY,
    )

    assert _score(normalized, template).priority_score == 120


def test_balanced_fallback_is_weak() -> None:
    normalized = _normalized(
        body_analysis_influence=_body_analysis((MuscleGroup.CHEST, "mild_lag"))
    )
    balanced = _template("z-balanced", TemplateFocusTag.BALANCED)
    chest = _template("a-chest", TemplateFocusTag.CHEST_PRIORITY)

    assert _score(normalized, balanced).fallback_score == 5
    assert _score(normalized, chest).body_analysis_score == 20
    assert (
        select_template_reference(normalized, tuple(full_catalog()), (balanced, chest), RULESET)
        == chest
    )


def test_session_duration_and_hard_constraint_inputs_do_not_participate_in_score() -> None:
    template = _template("balanced", TemplateFocusTag.BALANCED)
    baseline = _normalized(session_duration_minutes=30)
    changed = _normalized(
        age=62,
        session_duration_minutes=120,
        available_equipment=[Equipment.BARBELL],
        preferred_weekdays=(0, 2, 4),
    )

    assert _score(baseline, template) == _score(changed, template)


def test_duration_feasible_template_ranks_above_optional_overloaded_template() -> None:
    normalized = _normalized(primary_goal=Goal.STRENGTH, session_duration_minutes=30)
    catalog = tuple(full_catalog())
    capacity = build_session_capacity(
        normalized,
        catalog,
        RULESET,
    )
    tight = _duration_template("z-tight", core_slots=2, optional_slots=3)
    feasible = _duration_template("a-feasible", core_slots=2, optional_slots=0)

    first = rank_template_references(
        normalized,
        catalog,
        (tight, feasible),
        RULESET,
        session_capacity=capacity,
    )
    second = rank_template_references(
        normalized,
        catalog,
        (feasible, tight),
        RULESET,
        session_capacity=capacity,
    )

    assert first == second
    assert tuple(item.template.slug for item in first) == ("a-feasible", "z-tight")
    assert first[0].feasibility.duration_status is CapacityFeasibility.COMFORTABLY_FEASIBLE
    assert first[1].feasibility.duration_status is CapacityFeasibility.FEASIBLE_BUT_TIGHT
    assert first[1].feasibility.optional_slots_likely_trimmed > 0


def test_optional_duration_overage_is_not_a_hard_template_rejection() -> None:
    normalized = _normalized(primary_goal=Goal.STRENGTH, session_duration_minutes=30)
    catalog = tuple(full_catalog())
    capacity = build_session_capacity(
        normalized,
        catalog,
        RULESET,
    )
    tight = _duration_template("tight", core_slots=2, optional_slots=3)

    result = select_template_reference_result(
        normalized,
        catalog,
        (tight,),
        RULESET,
        session_capacity=capacity,
    )

    assert tuple(item.template.slug for item in result.candidates) == (tight.slug,)
    assert result.hard_rejections == ()


def test_provably_impossible_template_core_duration_is_hard_rejected() -> None:
    normalized = _normalized(primary_goal=Goal.STRENGTH, session_duration_minutes=30)
    catalog = tuple(full_catalog())
    capacity = build_session_capacity(
        normalized,
        catalog,
        RULESET,
    )
    impossible = _duration_template("impossible", core_slots=6, optional_slots=0)

    result = select_template_reference_result(
        normalized,
        catalog,
        (impossible,),
        RULESET,
        session_capacity=capacity,
    )

    assert result.candidates == ()
    assert result.hard_rejections[0].reason_codes == ("REQUIRED_CORE_DURATION_INFEASIBLE",)


def test_final_program_trace_preserves_proven_duration_core_rejection() -> None:
    impossible = _duration_template("impossible-final", core_slots=6, optional_slots=0)
    source = request(
        primary_goal=Goal.STRENGTH,
        session_duration_minutes=30,
        available_training_days=4,
        training_experience="intermediate",
        training_age_months=24,
    )

    result = generate_program(
        source,
        full_catalog(),
        RULESET,
        reference_templates=(impossible,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics.get("reference_template") is None
    selection = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "template_selection"
    )
    assert selection["hard_rejections"] == (
        {
            "slug": impossible.slug,
            "reason_codes": ("REQUIRED_CORE_DURATION_INFEASIBLE",),
        },
    )


def test_ranking_is_repeatable_and_uses_stable_slug_tie_break() -> None:
    normalized = _normalized()
    templates = (_template("a-template"), _template("z-template"))
    catalog = tuple(full_catalog())

    first = rank_template_references(normalized, catalog, templates, RULESET)
    second = rank_template_references(normalized, catalog, templates, RULESET)

    assert first == second
    assert tuple(item.template.slug for item in first) == ("z-template", "a-template")
    assert all(item.score == TemplateScore(0, 0, 0, 0, 0) for item in first)


def test_days_level_and_resolvable_core_slots_remain_hard_eligibility() -> None:
    normalized = _normalized()
    impossible = _template("best-score", TemplateFocusTag.CHEST_PRIORITY)
    impossible = replace(
        impossible,
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Unavailable core",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint="unavailable",
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.VERTICAL_PUSH,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        superset_exercise_id=None,
                        superset_exercise_slug_hint=None,
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
    wrong_days = _template("wrong-days", days_per_week=3)
    wrong_level = _template("wrong-level", training_level="advanced")

    eligible = eligible_template_references(
        normalized,
        (),
        (impossible, wrong_days, wrong_level),
    )

    assert eligible == ()


def _core_template(slug: str, *tags: TemplateFocusTag) -> TemplateReference:
    return replace(
        _template(slug, *tags),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Shoulder rotation",
                focus=(MuscleGroup.SHOULDERS,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint="shoulder-rotation",
                        target_muscles=(MuscleGroup.SHOULDERS,),
                        movement_pattern=MovementPattern.SHOULDER_EXTERNAL_ROTATION,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        superset_exercise_id=None,
                        superset_exercise_slug_hint=None,
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


def test_equipment_incompatibility_excludes_a_high_scoring_template_before_ranking() -> None:
    normalized = _normalized(
        priority_muscles=[MuscleGroup.CHEST],
        available_equipment=[Equipment.BODYWEIGHT],
    )
    barbell_only = exercise(
        "barbell-shoulder-rotation",
        MovementPattern.SHOULDER_EXTERNAL_ROTATION,
        MuscleGroup.SHOULDERS,
        equipment=frozenset({Equipment.BARBELL}),
    )
    eligible = filter_eligible_exercises(normalized, (barbell_only,)).eligible
    high_score = _core_template("high-score", TemplateFocusTag.CHEST_PRIORITY)
    fallback = _template("fallback")

    assert _score(normalized, high_score).priority_score == 100
    assert (
        select_template_reference(normalized, eligible, (high_score, fallback), RULESET) == fallback
    )


def test_safety_exclusion_removes_a_high_scoring_template_before_ranking() -> None:
    normalized = _normalized(
        priority_muscles=[MuscleGroup.CHEST],
        blocked_movement_patterns=[MovementPattern.SHOULDER_EXTERNAL_ROTATION],
    )
    unsafe = exercise(
        "blocked-shoulder-rotation",
        MovementPattern.SHOULDER_EXTERNAL_ROTATION,
        MuscleGroup.SHOULDERS,
    )
    eligibility = filter_eligible_exercises(normalized, (unsafe,))
    high_score = _core_template("high-score", TemplateFocusTag.CHEST_PRIORITY)
    fallback = _template("fallback")

    assert not eligibility.eligible
    assert (
        select_template_reference(normalized, eligibility.eligible, (high_score, fallback), RULESET)
        == fallback
    )


def test_scoring_does_not_introduce_goal_or_sex_tags() -> None:
    forbidden = {
        "female",
        "male",
        "women_program",
        "men_program",
        "fat_loss",
        "strength",
        "hypertrophy",
    }
    assert forbidden.isdisjoint(tag.value for tag in TemplateFocusTag)
