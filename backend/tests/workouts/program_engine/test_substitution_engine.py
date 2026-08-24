from dataclasses import replace

from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.workouts.program_engine.enums import (
    BalanceAbility,
    BodyPosition,
    Goal,
    Laterality,
    LoadLimit,
    StabilityDemand,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    SubstitutionTier,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import SubstitutionCause
from tests.workouts.program_engine.golden_fixtures import exercise, request


def test_engine_classifies_and_orders_all_four_semantic_tiers() -> None:
    target = replace(
        exercise("tier-target", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        muscle_focus=MuscleFocus.LATS,
        substitution_group="row",
    )
    tier_a = replace(
        exercise("tier-a", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        muscle_focus=MuscleFocus.LATS,
        substitution_group="row",
    )
    tier_b = replace(
        exercise("tier-b", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        muscle_focus=MuscleFocus.LATS,
        substitution_group="different-row",
    )
    tier_c = replace(
        exercise("tier-c", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        muscle_focus=MuscleFocus.MID_BACK_RHOMBOIDS,
        substitution_group="different-row",
    )
    tier_d = replace(
        exercise("tier-d", MovementPattern.VERTICAL_PULL, MuscleGroup.BACK),
        muscle_focus=MuscleFocus.LATS,
        substitution_group="different-pull",
        equipment=frozenset({Equipment.DUMBBELL}),
    )

    decision = rank_substitutions(
        normalize_request(request()),
        target,
        (tier_d, tier_c, tier_b, tier_a),
        SubstitutionContext(
            cause=SubstitutionCause.DISPLAY_ALTERNATIVE,
            allowed_patterns=frozenset(
                {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}
            ),
            target_muscles=frozenset({MuscleGroup.BACK}),
            day_focus="pull",
        ),
        ruleset=RULESET,
        limit=4,
    )

    assert tuple(option.exercise for option in decision.options) == (
        tier_a,
        tier_b,
        tier_c,
        tier_d,
    )
    assert tuple(option.tier for option in decision.options) == tuple(SubstitutionTier)


def test_curated_knowledge_is_preference_only_after_hard_filters() -> None:
    unsafe = exercise("curated-unsafe", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    safe = exercise("curated-safe", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    same_group = exercise(
        "curated-same-group",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
    )
    target = replace(
        exercise("curated-target", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        curated_alternative_ids=(unsafe.id, safe.id),
    )
    decision = rank_substitutions(
        normalize_request(
            request(blocked_exercises=frozenset({unsafe.id}))
        ),
        target,
        (same_group, unsafe, safe),
        SubstitutionContext(cause=SubstitutionCause.SAFETY),
        ruleset=RULESET,
    )

    assert tuple(option.exercise for option in decision.options) == (safe, same_group)
    assert "SUBSTITUTION_CURATED_ALTERNATIVE" in decision.options[0].reason_codes


def test_missing_equipment_preserves_exact_role_and_explains_adaptation() -> None:
    target = replace(
        exercise("barbell-row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        equipment=frozenset({Equipment.BARBELL}),
    )
    replacement = replace(
        exercise("dumbbell-row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        equipment=frozenset({Equipment.DUMBBELL}),
    )

    decision = rank_substitutions(
        normalize_request(request(available_equipment=frozenset({Equipment.DUMBBELL}))),
        target,
        (replacement,),
        SubstitutionContext(cause=SubstitutionCause.MISSING_EQUIPMENT),
        ruleset=RULESET,
    )

    assert decision.options[0].tier in {SubstitutionTier.A, SubstitutionTier.B}
    assert "SUBSTITUTION_EQUIPMENT_ADAPTED" in decision.options[0].reason_codes


def test_axial_and_balance_causes_prefer_safer_candidate_within_tier() -> None:
    target = replace(
        exercise("risk-target", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        axial_loading_level=LoadLimit.HIGH,
        stability_demand=StabilityDemand.HIGH,
    )
    moderate = replace(
        exercise("risk-moderate", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        axial_loading_level=LoadLimit.MODERATE,
        stability_demand=StabilityDemand.MODERATE,
        body_position=BodyPosition.STANDING,
        laterality=Laterality.UNILATERAL,
    )
    safest = replace(
        exercise("risk-low", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        axial_loading_level=LoadLimit.LOW,
        stability_demand=StabilityDemand.LOW,
        body_position=BodyPosition.SUPPORTED,
        laterality=Laterality.BILATERAL,
    )
    source = normalize_request(
        request(
            axial_load_limit=LoadLimit.HIGH,
            balance_requirement=BalanceAbility.HIGH,
        )
    )

    for cause in (SubstitutionCause.AXIAL_LOAD, SubstitutionCause.BALANCE):
        decision = rank_substitutions(
            source,
            target,
            (moderate, safest),
            SubstitutionContext(cause=cause),
            ruleset=RULESET,
        )
        assert decision.options[0].exercise is safest
        assert "SUBSTITUTION_CONSTRAINT_ADAPTED" in decision.options[0].reason_codes


def test_all_active_constraints_are_hard_even_when_candidate_role_is_exact() -> None:
    target = exercise("multi-target", MovementPattern.ELBOW_FLEXION, MuscleGroup.BICEPS)
    unavailable = replace(
        target,
        id=exercise("multi-equipment", target.movement_pattern, target.primary_muscle).id,
        equipment=frozenset({Equipment.BARBELL}),
    )
    wrist = replace(
        target,
        id=exercise("multi-wrist", target.movement_pattern, target.primary_muscle).id,
        caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
    )
    axial = replace(
        target,
        id=exercise("multi-axial", target.movement_pattern, target.primary_muscle).id,
        axial_loading_level=LoadLimit.HIGH,
    )
    unstable = replace(
        target,
        id=exercise("multi-balance", target.movement_pattern, target.primary_muscle).id,
        stability_demand=StabilityDemand.HIGH,
    )
    wrong_rom = replace(
        target,
        id=exercise("multi-rom", target.movement_pattern, target.primary_muscle).id,
        range_of_motion_profile=frozenset({"deep"}),
    )
    safe = replace(
        target,
        id=exercise("multi-safe", target.movement_pattern, target.primary_muscle).id,
        range_of_motion_profile=frozenset({"short"}),
        stability_demand=StabilityDemand.LOW,
    )
    source = normalize_request(
        request(
            available_equipment=frozenset({Equipment.BODYWEIGHT}),
            blocked_caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
            axial_load_limit=LoadLimit.LOW,
            balance_requirement=BalanceAbility.LIMITED,
            allowed_range_of_motion=frozenset({"short"}),
        )
    )

    decision = rank_substitutions(
        source,
        target,
        (unavailable, wrist, axial, unstable, wrong_rom, safe),
        SubstitutionContext(cause=SubstitutionCause.SAFETY),
        ruleset=RULESET,
    )

    assert tuple(option.exercise for option in decision.options) == (safe,)


def test_incompatible_push_degradation_returns_explicit_no_replacement() -> None:
    target = exercise("vertical-target", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS)
    horizontal = exercise(
        "horizontal-candidate",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.SHOULDERS,
    )

    decision = rank_substitutions(
        normalize_request(request()),
        target,
        (horizontal,),
        SubstitutionContext(
            cause=SubstitutionCause.MISSING_EQUIPMENT,
            allowed_patterns=frozenset(
                {MovementPattern.VERTICAL_PUSH, MovementPattern.HORIZONTAL_PUSH}
            ),
            target_muscles=frozenset({MuscleGroup.SHOULDERS}),
        ),
        ruleset=RULESET,
    )

    assert decision.options == ()
    assert decision.reason_codes == ("SUBSTITUTION_NO_VALID_REPLACEMENT",)


def test_overhead_limit_rejects_another_exact_overhead_candidate() -> None:
    target = exercise("overhead-target", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS)
    another_overhead = exercise(
        "overhead-candidate",
        MovementPattern.VERTICAL_PUSH,
        MuscleGroup.SHOULDERS,
        equipment=frozenset({Equipment.DUMBBELL}),
    )

    decision = rank_substitutions(
        normalize_request(request(overhead_limit=LoadLimit.NONE)),
        target,
        (another_overhead,),
        SubstitutionContext(cause=SubstitutionCause.OVERHEAD),
        ruleset=RULESET,
    )

    assert decision.options == ()
    assert decision.reason_codes == ("SUBSTITUTION_NO_VALID_REPLACEMENT",)


def test_strength_role_preservation_and_input_order_are_deterministic() -> None:
    source = normalize_request(
        request(
            primary_goal=Goal.STRENGTH,
            training_experience="advanced",
            training_age_months=72,
            available_equipment=frozenset({Equipment.DUMBBELL, Equipment.BODYWEIGHT}),
        )
    )
    target = replace(
        exercise("strength-target", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        equipment=frozenset({Equipment.DUMBBELL}),
    )
    primary = replace(
        exercise("strength-primary", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        equipment=frozenset({Equipment.DUMBBELL}),
        substitution_group="other",
    )
    secondary = replace(
        exercise("strength-secondary", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        equipment=frozenset({Equipment.BODYWEIGHT}),
        substitution_group="other",
    )
    context = SubstitutionContext(cause=SubstitutionCause.DISPLAY_ALTERNATIVE)

    forward = rank_substitutions(
        source,
        target,
        (secondary, primary),
        context,
        ruleset=RULESET,
    )
    reverse = rank_substitutions(
        source,
        target,
        (primary, secondary),
        context,
        ruleset=RULESET,
    )

    assert forward.options[0].exercise is primary
    assert "SUBSTITUTION_STRENGTH_ROLE_PRESERVED" in forward.options[0].reason_codes
    assert tuple(option.exercise.id for option in forward.options) == tuple(
        option.exercise.id for option in reverse.options
    )
