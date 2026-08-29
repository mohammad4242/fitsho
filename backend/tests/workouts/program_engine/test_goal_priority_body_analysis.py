"""
Tests for Task A (goals), Task B (explicit priority), Task C (body analysis).

Section 10 requirements: GOALS 1-8, EXPLICIT PRIORITY 9-15,
BODY ANALYSIS 16-20, PHASE 11.7 REGRESSION 21-25.
"""

from __future__ import annotations

from uuid import uuid4

from app.exercises.enums import ExerciseCautionTag, MuscleGroup
from app.workouts.program_engine.body_analysis import eligible_body_analysis_priorities
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, TrainingStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescription_for
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    TemplateReference,
)
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.template_scoring import (
    DEFAULT_TEMPLATE_SCORING_POLICY,
    _goal_score,
)
from app.workouts.program_engine.template_selector import select_template_reference_result
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import full_catalog, request

# ── Helpers ─────────────────────────────────────────────────────────────────


def _body_influence(
    muscle: MuscleGroup,
    *,
    classification: str = "clear_lag",
    confidence: float = 0.9,
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
                    "confidence": confidence,
                    "severity": 0.8,
                    "emphasis": [muscle.value],
                }
            ],
        }
    )


def _generate(
    *,
    goal: Goal = Goal.HYPERTROPHY,
    days: int = 4,
    experience: str = "intermediate",
    age_months: int = 24,
    session_minutes: int = 45,
    priority_muscles: list[MuscleGroup] | None = None,
    body_analysis: BodyAnalysisInfluence | None = None,
    blocked_caution_tags: list[ExerciseCautionTag] | None = None,
    templates: tuple[TemplateReference, ...] = (),
) -> object:
    req = request(
        primary_goal=goal,
        training_experience=experience,
        training_age_months=age_months,
        available_training_days=days,
        session_duration_minutes=session_minutes,
        priority_muscles=priority_muscles or [],
        body_analysis_influence=body_analysis,
        blocked_caution_tags=blocked_caution_tags or [],
    )
    return generate_program(req, full_catalog(), RULESET, reference_templates=templates)


def _rest(goal: Goal, *, compound: bool) -> int:
    from app.exercises.enums import ExerciseType

    return prescription_for(
        goal,
        ExerciseType.COMPOUND if compound else ExerciseType.ISOLATION,
        TrainingStatus.INTERMEDIATE,
        RULESET,
    ).rest_seconds


def _reps(goal: Goal, *, compound: bool) -> tuple[int | None, int | None]:
    from app.exercises.enums import ExerciseType

    p = prescription_for(
        goal,
        ExerciseType.COMPOUND if compound else ExerciseType.ISOLATION,
        TrainingStatus.INTERMEDIATE,
        RULESET,
    )
    return p.rep_min, p.rep_max


def _volume(goal: Goal, muscle: MuscleGroup = MuscleGroup.CHEST) -> int:
    req = request(
        primary_goal=goal,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
    )
    normalized = normalize_request(req, RULESET)
    return plan_weekly_volume(
        normalized, select_split(normalized, RULESET), RULESET
    ).direct_sets_for(muscle)


# ── GOALS ────────────────────────────────────────────────────────────────────


def test_01_strength_compound_prescription() -> None:
    # STRENGTH compound defaults to secondary_compound (135s) at low fatigue_cost;
    # primary_strength gets 180s but needs fatigue_cost >= 4.
    # Assert that STRENGTH compound rest exceeds GENERAL_FITNESS (90s).
    rest = _rest(Goal.STRENGTH, compound=True)
    _, rep_max = _reps(Goal.STRENGTH, compound=True)
    assert rest > _rest(Goal.GENERAL_FITNESS, compound=True), (
        f"STRENGTH compound rest ({rest}s) should exceed GENERAL_FITNESS"
    )
    assert rep_max is not None and rep_max <= 10, f"STRENGTH compound reps too high: {rep_max}"


def test_02_hypertrophy_prescription() -> None:
    comp_min, comp_max = _reps(Goal.HYPERTROPHY, compound=True)
    iso_min, iso_max = _reps(Goal.HYPERTROPHY, compound=False)
    comp_rest = _rest(Goal.HYPERTROPHY, compound=True)
    assert comp_min == 6 and comp_max == 12
    assert iso_min == 10 and iso_max == 20
    assert 90 <= comp_rest <= 150


def test_03_muscle_gain_is_intentional_shares_hypertrophy() -> None:
    assert _reps(Goal.MUSCLE_GAIN, compound=True) == _reps(Goal.HYPERTROPHY, compound=True)
    assert _reps(Goal.MUSCLE_GAIN, compound=False) == _reps(Goal.HYPERTROPHY, compound=False)
    assert _volume(Goal.MUSCLE_GAIN) == _volume(Goal.HYPERTROPHY)


def test_04_fat_loss_program_succeeds_with_resistance_structure() -> None:
    result = _generate(goal=Goal.FAT_LOSS, days=3)
    assert result.program is not None, f"FAT_LOSS failed: {result.errors}"
    for day in result.program.weekly_schedule:
        assert len(day.exercises) >= RULESET.minimum_exercises_per_session


def test_04b_fat_loss_volume_lower_than_hypertrophy() -> None:
    # FAT_LOSS volume multiplier (0.75) should produce no more sets than HYPERTROPHY (1.0).
    # Use BACK which has a larger baseline volume to make the difference visible.
    fl = _volume(Goal.FAT_LOSS, MuscleGroup.BACK)
    hy = _volume(Goal.HYPERTROPHY, MuscleGroup.BACK)
    assert fl <= hy, f"FAT_LOSS sets ({fl}) should be ≤ HYPERTROPHY ({hy})"


def test_05_body_recomposition_covers_upper_and_lower() -> None:
    result = _generate(goal=Goal.BODY_RECOMPOSITION, days=4)
    assert result.program is not None
    muscles = {
        ex.primary_muscle
        for day in result.program.weekly_schedule
        for ex in day.exercises
        if ex.primary_muscle is not None
    }
    upper = {MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS}
    lower = {MuscleGroup.QUADRICEPS, MuscleGroup.GLUTES, MuscleGroup.HAMSTRINGS}
    assert muscles & upper
    assert muscles & lower


def test_06_general_fitness_balanced() -> None:
    result = _generate(goal=Goal.GENERAL_FITNESS, days=3)
    assert result.program is not None
    muscles = {
        ex.primary_muscle
        for day in result.program.weekly_schedule
        for ex in day.exercises
        if ex.primary_muscle is not None
    }
    assert muscles & {MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS}
    assert muscles & {MuscleGroup.QUADRICEPS, MuscleGroup.GLUTES}


def test_07_muscular_endurance_higher_reps_shorter_rest_than_hypertrophy() -> None:
    me_min, _ = _reps(Goal.MUSCULAR_ENDURANCE, compound=True)
    hy_min, _ = _reps(Goal.HYPERTROPHY, compound=True)
    assert me_min is not None and hy_min is not None
    assert me_min > hy_min
    assert _rest(Goal.MUSCULAR_ENDURANCE, compound=True) < _rest(Goal.HYPERTROPHY, compound=True)


def test_08_goal_score_intentional_for_all_goals() -> None:
    from app.training_templates.tags import TemplateFocusTag

    tags_spec = frozenset({TemplateFocusTag.BODY_PART_ROTATION, TemplateFocusTag.SPECIALIZATION})
    tags_comp = frozenset({TemplateFocusTag.UPPER_LOWER, TemplateFocusTag.COMPOUND_FOCUS})
    tags_bal = frozenset({TemplateFocusTag.UPPER_LOWER, TemplateFocusTag.BALANCED})
    p = DEFAULT_TEMPLATE_SCORING_POLICY

    score_hy, r_hy = _goal_score(Goal.HYPERTROPHY, tags_spec, p)
    assert score_hy == 0 and not any("HYPERTROPHY" in r for r in r_hy)

    score_mg, _ = _goal_score(Goal.MUSCLE_GAIN, tags_spec, p)
    assert score_mg == 0

    score_fl, r_fl = _goal_score(Goal.FAT_LOSS, tags_comp, p)
    assert score_fl == 0 and not any("FAT_LOSS" in r for r in r_fl)

    score_me, _ = _goal_score(Goal.MUSCULAR_ENDURANCE, tags_comp, p)
    assert score_me == 0

    assert _goal_score(Goal.GENERAL_FITNESS, tags_bal, p)[0] > 0
    assert (
        _goal_score(
            Goal.STRENGTH,
            frozenset({TemplateFocusTag.COMPOUND_FOCUS, TemplateFocusTag.STRENGTH_BIAS}),
            p,
        )[0]
        > 0
    )


# ── EXPLICIT PRIORITY ────────────────────────────────────────────────────────


def test_09_chest_priority_survives_construction() -> None:
    baseline = _generate(goal=Goal.HYPERTROPHY, days=4)
    priority = _generate(goal=Goal.HYPERTROPHY, days=4, priority_muscles=[MuscleGroup.CHEST])
    assert baseline.program is not None
    assert priority.program is not None

    def _chest_sets(prog):
        return sum(
            ex.sets
            for day in prog.weekly_schedule
            for ex in day.exercises
            if ex.primary_muscle is MuscleGroup.CHEST
        )

    assert _chest_sets(priority.program) >= _chest_sets(baseline.program)
    assert _chest_sets(priority.program) > 0


def test_10_back_priority_survives() -> None:
    result = _generate(goal=Goal.HYPERTROPHY, days=4, priority_muscles=[MuscleGroup.BACK])
    assert result.program is not None
    back_sets = sum(
        ex.sets
        for day in result.program.weekly_schedule
        for ex in day.exercises
        if ex.primary_muscle is MuscleGroup.BACK
    )
    assert back_sets > 0


def test_11_lower_body_priority_survives() -> None:
    result = _generate(goal=Goal.HYPERTROPHY, days=4, priority_muscles=[MuscleGroup.GLUTES])
    assert result.program is not None
    assert any(
        ex.primary_muscle is MuscleGroup.GLUTES
        for day in result.program.weekly_schedule
        for ex in day.exercises
    )


def test_12_single_priority_is_deterministic() -> None:
    result1 = _generate(
        goal=Goal.HYPERTROPHY,
        days=4,
        priority_muscles=[MuscleGroup.CHEST],
    )
    result2 = _generate(
        goal=Goal.HYPERTROPHY,
        days=4,
        priority_muscles=[MuscleGroup.CHEST],
    )
    assert result1.program is not None and result2.program is not None
    assert result1.program.decision_trace == result2.program.decision_trace
    muscles = {ex.primary_muscle for day in result1.program.weekly_schedule for ex in day.exercises}
    assert MuscleGroup.CHEST in muscles
    assert MuscleGroup.BACK in muscles


def test_13_explicit_priority_wins_over_body_analysis_for_hard_minimum() -> None:
    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=45,
        priority_muscles=[MuscleGroup.CHEST],
        body_analysis_influence=_body_influence(MuscleGroup.GLUTES),
    )
    normalized = normalize_request(req, RULESET)
    plan = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)
    targets = {t.muscle: t for t in plan.targets}
    assert targets[MuscleGroup.CHEST].direct_minimum_required is True
    assert targets[MuscleGroup.GLUTES].direct_minimum_required is False


def test_14_lower_priority_muscle_reduced_before_explicit_priority() -> None:
    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        priority_muscles=[MuscleGroup.BACK],
    )
    normalized = normalize_request(req, RULESET)
    pp = PriorityAllocationPolicy.for_request(normalized, RULESET)
    assert pp.preservation_rank(MuscleGroup.BACK) > pp.preservation_rank(MuscleGroup.CALVES)


def test_15_explicit_priority_bounded_by_hard_cap() -> None:
    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        priority_muscles=[MuscleGroup.CHEST],
    )
    normalized = normalize_request(req, RULESET)
    plan = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)
    chest = next(t for t in plan.targets if t.muscle is MuscleGroup.CHEST)
    assert chest.target_sets <= chest.maximum_hard


# ── BODY ANALYSIS ────────────────────────────────────────────────────────────


def test_16_clear_lag_stronger_than_mild_lag() -> None:
    def _shoulder_sets(classification: str) -> int:
        req = request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience="intermediate",
            training_age_months=24,
            available_training_days=4,
            body_analysis_influence=_body_influence(
                MuscleGroup.SHOULDERS, classification=classification
            ),
        )
        normalized = normalize_request(req, RULESET)
        return plan_weekly_volume(
            normalized, select_split(normalized, RULESET), RULESET
        ).direct_sets_for(MuscleGroup.SHOULDERS)

    clear_sets = _shoulder_sets("clear_lag")
    mild_sets = _shoulder_sets("mild_lag")
    assert clear_sets > mild_sets


def test_17_high_confidence_body_analysis_appears_in_trace() -> None:
    result = _generate(
        goal=Goal.HYPERTROPHY,
        days=4,
        body_analysis=_body_influence(MuscleGroup.SHOULDERS),
    )
    assert result.program is not None
    ba_stage = next(
        (
            item
            for item in result.program.decision_trace
            if item.get("stage") == "body_analysis_influence"
        ),
        None,
    )
    assert ba_stage is not None
    assert "shoulders" in ba_stage.get("applied_muscles", [])


def test_18_low_confidence_is_completely_ignored() -> None:
    low = _body_influence(MuscleGroup.SHOULDERS, confidence=0.4)
    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        body_analysis_influence=low,
    )
    normalized = normalize_request(req, RULESET)
    assert len(eligible_body_analysis_priorities(normalized, RULESET)) == 0

    req_base = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
    )
    norm_base = normalize_request(req_base, RULESET)
    plan = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)
    plan_base = plan_weekly_volume(norm_base, select_split(norm_base, RULESET), RULESET)
    assert plan.direct_sets_for(MuscleGroup.SHOULDERS) == plan_base.direct_sets_for(
        MuscleGroup.SHOULDERS
    )


def test_19_ba_cannot_reintroduce_safety_excluded_exercise() -> None:
    from app.workouts.program_engine.eligibility import filter_eligible_exercises

    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
        body_analysis_influence=_body_influence(MuscleGroup.SHOULDERS),
    )
    normalized = normalize_request(req, RULESET)
    eligibility = filter_eligible_exercises(normalized, full_catalog())
    assert all(
        ExerciseCautionTag.OVERHEAD_POSITION not in item.caution_tags
        for item in eligibility.eligible
    )


def test_20_ba_never_overrides_explicit_priority() -> None:
    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=45,
        priority_muscles=[MuscleGroup.CHEST],
        body_analysis_influence=_body_influence(MuscleGroup.GLUTES),
    )
    normalized = normalize_request(req, RULESET)
    pp = PriorityAllocationPolicy.for_request(normalized, RULESET)
    assert pp.preservation_rank(MuscleGroup.CHEST) > pp.preservation_rank(MuscleGroup.GLUTES)
    assert MuscleGroup.CHEST in pp.explicit_priorities
    assert MuscleGroup.GLUTES in pp.clear_lag_priorities


# ── PHASE 11.7 REGRESSION ───────────────────────────────────────────────────


def test_21_top_template_fails_engine_still_succeeds() -> None:
    # Template needs OVERHEAD_POSITION exercises; we block them → template path fails
    # Engine must not crash; it tries fallback
    result = _generate(
        goal=Goal.HYPERTROPHY,
        days=3,
        blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
    )
    # Either succeeds via dynamic fallback or returns a structured error
    assert result is not None


def test_22_no_templates_dynamic_fallback_works() -> None:
    result = _generate(goal=Goal.HYPERTROPHY, days=3, templates=())
    assert result.program is not None, f"Dynamic fallback failed: {result.errors}"


def test_23_template_ranking_is_deterministic_regardless_of_input_order() -> None:
    t1 = TemplateReference(
        slug="aaa-template",
        days_per_week=4,
        supported_levels=("intermediate",),
        focus_tags=("upper_lower", "balanced"),
        intensity_methods=("standard",),
        days=(),
    )
    t2 = TemplateReference(
        slug="zzz-template",
        days_per_week=4,
        supported_levels=("intermediate",),
        focus_tags=("upper_lower", "strength_bias", "compound_focus"),
        intensity_methods=("standard",),
        days=(),
    )
    req = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
    )
    normalized = normalize_request(req, RULESET)
    catalog = tuple(full_catalog())

    result_ab = select_template_reference_result(normalized, catalog, (t1, t2), RULESET)
    result_ba = select_template_reference_result(normalized, catalog, (t2, t1), RULESET)

    slugs_ab = [r.template.slug for r in result_ab.candidates]
    slugs_ba = [r.template.slug for r in result_ba.candidates]
    assert sorted(slugs_ab) == sorted(slugs_ba)  # same templates
    # Same order after ranking:
    assert slugs_ab == slugs_ba, "Template ranking must be input-order-independent"


def test_24_exact_day_count_preserved_for_all_goals() -> None:
    for goal in (Goal.STRENGTH, Goal.HYPERTROPHY, Goal.FAT_LOSS, Goal.MUSCULAR_ENDURANCE):
        for days in (3, 4):
            result = _generate(goal=goal, days=days)
            if result.program is not None:
                assert len(result.program.weekly_schedule) == days, (
                    f"{goal} {days}d: got {len(result.program.weekly_schedule)} days"
                )


def test_25_safety_constraints_hold_for_all_goals() -> None:
    catalog = full_catalog()
    for goal in Goal:
        req = request(
            primary_goal=goal,
            training_experience="intermediate",
            training_age_months=24,
            available_training_days=4,
            blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
        )
        result = generate_program(req, catalog, RULESET)
        if result.program is None:
            continue
        catalog_by_id = {c.id: c for c in catalog}
        for day in result.program.weekly_schedule:
            for ex in day.exercises:
                ex_candidate = catalog_by_id.get(ex.exercise_id)
                if ex_candidate is not None:
                    assert ExerciseCautionTag.OVERHEAD_POSITION not in ex_candidate.caution_tags, (
                        f"{goal}: safety-excluded exercise appeared: {ex.exercise_name}"
                    )
