from app.nutrition.food_constraints import (
    ConstraintSeverity,
    evaluate_food_constraints,
    normalize_food_constraints,
)


def test_known_canonical_allergen_normalization() -> None:
    constraints = normalize_food_constraints(
        allergies=("milk", "gluten"),
        intolerances=("eggs",),
    )
    codes = [c.code for c in constraints]
    assert "milk" in codes
    assert "gluten" in codes
    assert "egg" in codes
    assert all(c.severity == ConstraintSeverity.HARD for c in constraints)


def test_alias_normalization_persian() -> None:
    constraints = normalize_food_constraints(
        allergies=("گلوتن", "لبنیات", "بادام زمینی", "ماهی"),
        intolerances=("لاکتوز",),
    )
    codes = [c.code for c in constraints]
    assert codes == ["gluten", "milk", "peanut", "fish", "milk"]


def test_unknown_hard_allergy_returns_unresolved_constraint() -> None:
    # A complex/unrecognized sentence or mystery ingredient
    constraints = normalize_food_constraints(
        allergies=("ماده عجیب ناشناخته در غذا که معلوم نیست چیست",),
    )
    assert len(constraints) == 1
    assert constraints[0].code == "UNRESOLVED_HARD_FOOD_CONSTRAINT"
    assert constraints[0].severity == ConstraintSeverity.HARD

    # Evaluate against a food
    decision = evaluate_food_constraints(
        food_allergen_tags=("milk",),
        food_slug="milk",
        food_name_fa="شیر",
        constraints=constraints,
    )
    assert not decision.allowed
    assert "UNRESOLVED_HARD_FOOD_CONSTRAINT" in decision.hard_reason_codes


def test_dislike_is_soft_penalty() -> None:
    constraints = normalize_food_constraints(
        disliked_foods=("ماهی", "mushroom"),
    )
    assert len(constraints) == 2
    assert all(c.severity == ConstraintSeverity.SOFT for c in constraints)

    # Evaluate against fish
    decision = evaluate_food_constraints(
        food_allergen_tags=("fish",),
        food_slug="white-fish",
        food_name_fa="ماهی سفید",
        constraints=constraints,
    )
    assert decision.allowed  # Soft constraint does NOT hard-block
    assert len(decision.hard_reason_codes) == 0
    assert "PENALIZED_FOR_FISH" in decision.soft_penalty_codes


def test_never_suggest_and_refused_are_hard_exclusions() -> None:
    constraints = normalize_food_constraints(
        never_suggest_foods=("eggplant",),
        refused_foods=("بادمجان",),
    )
    assert all(c.severity == ConstraintSeverity.HARD for c in constraints)

    decision = evaluate_food_constraints(
        food_allergen_tags=(),
        food_slug="eggplant",
        food_name_fa="بادمجان",
        constraints=constraints,
    )
    assert not decision.allowed
    assert any("EGGPLANT" in code or "بادمجان" in code for code in decision.hard_reason_codes)


def test_structured_tag_beats_misleading_display_name() -> None:
    constraints = normalize_food_constraints(
        allergies=("milk",),
    )
    # 1. Food named "شیرینی بدون شیر" (milk-free pastry) but actually has "milk" allergen tag
    decision_tagged = evaluate_food_constraints(
        food_allergen_tags=("milk", "gluten"),
        food_slug="pastry",
        food_name_fa="شیرینی بدون شیر",
        constraints=constraints,
        allergen_metadata_verified=True,
    )
    assert not decision_tagged.allowed
    assert "EXCLUDED_BY_MILK" in decision_tagged.hard_reason_codes

    # 2. Food named "شیر نارگیل" (coconut milk) which has NO milk allergen tag and is verified
    decision_coconut = evaluate_food_constraints(
        food_allergen_tags=(),
        food_slug="coconut-milk",
        food_name_fa="شیر نارگیل",
        constraints=constraints,
        allergen_metadata_verified=True,
    )
    assert decision_coconut.allowed


def test_gluten_allergy_excludes_wheat_tagged_food() -> None:
    constraints = normalize_food_constraints(
        allergies=("gluten",),
    )
    # Sangak is tagged with wheat
    decision = evaluate_food_constraints(
        food_allergen_tags=("wheat",),
        food_slug="sangak",
        food_name_fa="نان سنگک",
        constraints=constraints,
        allergen_metadata_verified=True,
    )
    assert not decision.allowed
    assert "EXCLUDED_BY_GLUTEN" in decision.hard_reason_codes
