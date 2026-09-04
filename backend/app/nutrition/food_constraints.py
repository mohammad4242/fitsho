"""Single source of truth for food-level hard and soft constraints."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.nutrition.enums import CanonicalAllergen


class ConstraintSeverity(StrEnum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class NormalizedFoodConstraint:
    code: str
    severity: ConstraintSeverity
    source: str
    raw_label: str | None = None


@dataclass(frozen=True)
class FoodConstraintDecision:
    allowed: bool
    hard_reason_codes: tuple[str, ...] = ()
    soft_penalty_codes: tuple[str, ...] = ()

    @property
    def is_hard_blocked(self) -> bool:
        return not self.allowed

    @property
    def penalty(self) -> Decimal:
        return Decimal(len(self.soft_penalty_codes))


_CANONICAL_ALLERGEN_ALIASES: dict[str, CanonicalAllergen] = {
    # Gluten
    "gluten": CanonicalAllergen.GLUTEN,
    "گلوتن": CanonicalAllergen.GLUTEN,
    "سلیاک": CanonicalAllergen.GLUTEN,
    "celiac": CanonicalAllergen.GLUTEN,
    # Wheat
    "wheat": CanonicalAllergen.WHEAT,
    "گندم": CanonicalAllergen.WHEAT,
    # Milk / Dairy
    "milk": CanonicalAllergen.MILK,
    "شیر": CanonicalAllergen.MILK,
    "لبنیات": CanonicalAllergen.MILK,
    "dairy": CanonicalAllergen.MILK,
    "لاکتوز": CanonicalAllergen.MILK,
    "lactose": CanonicalAllergen.MILK,
    "پنیر": CanonicalAllergen.MILK,
    "ماست": CanonicalAllergen.MILK,
    "کشک": CanonicalAllergen.MILK,
    "دوغ": CanonicalAllergen.MILK,
    "کره": CanonicalAllergen.MILK,
    "خامه": CanonicalAllergen.MILK,
    # Egg
    "egg": CanonicalAllergen.EGG,
    "eggs": CanonicalAllergen.EGG,
    "تخم مرغ": CanonicalAllergen.EGG,
    "تخم‌مرغ": CanonicalAllergen.EGG,
    # Peanut
    "peanut": CanonicalAllergen.PEANUT,
    "peanuts": CanonicalAllergen.PEANUT,
    "بادام زمینی": CanonicalAllergen.PEANUT,
    "بادام‌زمینی": CanonicalAllergen.PEANUT,
    # Tree nut
    "tree_nut": CanonicalAllergen.TREE_NUT,
    "tree_nuts": CanonicalAllergen.TREE_NUT,
    "nut": CanonicalAllergen.TREE_NUT,
    "nuts": CanonicalAllergen.TREE_NUT,
    "گردو": CanonicalAllergen.TREE_NUT,
    "بادام": CanonicalAllergen.TREE_NUT,
    "پسته": CanonicalAllergen.TREE_NUT,
    "فندق": CanonicalAllergen.TREE_NUT,
    "آجیل": CanonicalAllergen.TREE_NUT,
    "مغزها": CanonicalAllergen.TREE_NUT,
    "walnut": CanonicalAllergen.TREE_NUT,
    "almond": CanonicalAllergen.TREE_NUT,
    "pistachio": CanonicalAllergen.TREE_NUT,
    "hazelnut": CanonicalAllergen.TREE_NUT,
    # Soy
    "soy": CanonicalAllergen.SOY,
    "soya": CanonicalAllergen.SOY,
    "soybean": CanonicalAllergen.SOY,
    "soybeans": CanonicalAllergen.SOY,
    "سویا": CanonicalAllergen.SOY,
    # Fish
    "fish": CanonicalAllergen.FISH,
    "ماهی": CanonicalAllergen.FISH,
    "تن ماهی": CanonicalAllergen.FISH,
    # Shellfish
    "shellfish": CanonicalAllergen.SHELLFISH,
    "میگو": CanonicalAllergen.SHELLFISH,
    "shrimp": CanonicalAllergen.SHELLFISH,
    "خرچنگ": CanonicalAllergen.SHELLFISH,
    # Sesame
    "sesame": CanonicalAllergen.SESAME,
    "کنجد": CanonicalAllergen.SESAME,
    "ارده": CanonicalAllergen.SESAME,
    "tahini": CanonicalAllergen.SESAME,
}

_KNOWN_FOOD_TERMS: frozenset[str] = frozenset({
    "chicken", "مرغ", "سینه مرغ", "فیله مرغ", "ران مرغ",
    "beef", "گوشت گوساله", "گوشت قرمز", "گوشت گوسفند", "lamb", "گوشت چرخ‌کرده",
    "lentils", "عدس", "chickpeas", "نخود", "beans", "لوبیا",
    "rice", "برنج", "bread", "نان", "سنگک", "بربری", "لواش", "تافتون",
    "pasta", "ماکارونی", "پاستا", "oats", "جو دوسر", "اوتمیل",
    "eggplant", "بادمجان", "mushroom", "قارچ", "tomato", "گوجه",
    "cucumber", "خیار", "onion", "پیاز", "spinach", "اسفناج",
    "olive", "زیتون", "oil", "روغن",
})


def _clean_term(term: str) -> str:
    cleaned = term.strip().casefold()
    cleaned = re.sub(r"[،,\n\t]+", " ", cleaned)
    return " ".join(cleaned.split())


def _matches_term(needle: str, haystack_slug: str, haystack_name: str) -> bool:
    """Check if needle matches as whole word in slug or name."""
    if not needle:
        return False
    # Check in slug separated by hyphens
    slug_tokens = set(haystack_slug.replace("_", "-").split("-"))
    if needle in slug_tokens:
        return True
    # Check in Persian / English name by words
    name_tokens = set(re.split(r"[\s\-_،,]+", haystack_name.casefold()))
    if needle in name_tokens:
        return True
    # Multi-word needle check in combined text
    combined = f"{haystack_slug} {haystack_name}".casefold()
    return needle in combined


def normalize_food_constraints(
    raw_constraints: Iterable[dict[str, object] | object] | None = None,
    *,
    allergies: tuple[str, ...] = (),
    intolerances: tuple[str, ...] = (),
    religious_cultural_exclusions: tuple[str, ...] = (),
    never_suggest_foods: tuple[str, ...] = (),
    refused_foods: tuple[str, ...] = (),
    disliked_foods: tuple[str, ...] = (),
) -> tuple[NormalizedFoodConstraint, ...]:
    """Normalize user-declared dietary restrictions and preferences."""
    if raw_constraints is not None:
        allergy_list = list(allergies)
        intolerance_list = list(intolerances)
        religious_list = list(religious_cultural_exclusions)
        never_list = list(never_suggest_foods)
        refused_list = list(refused_foods)
        dislike_list = list(disliked_foods)
        for item in raw_constraints:
            kind = getattr(item, "kind", None) or (
                item.get("kind") if isinstance(item, dict) else None
            )
            term = (
                getattr(item, "term", None)
                or getattr(item, "name", None)
                or (item.get("term") if isinstance(item, dict) else None)
                or (item.get("name") if isinstance(item, dict) else None)
            )
            if not term:
                continue
            kind_str = str(kind.value if hasattr(kind, "value") else kind).lower()
            if kind_str == "allergy":
                allergy_list.append(str(term))
            elif kind_str == "intolerance":
                intolerance_list.append(str(term))
            elif kind_str == "religious_cultural_exclusion":
                religious_list.append(str(term))
            elif kind_str == "never_suggest":
                never_list.append(str(term))
            elif kind_str == "refused":
                refused_list.append(str(term))
            elif kind_str in {"dislike", "disliked"}:
                dislike_list.append(str(term))
            else:
                never_list.append(str(term))
        allergies = tuple(allergy_list)
        intolerances = tuple(intolerance_list)
        religious_cultural_exclusions = tuple(religious_list)
        never_suggest_foods = tuple(never_list)
        refused_foods = tuple(refused_list)
        disliked_foods = tuple(dislike_list)

    results: list[NormalizedFoodConstraint] = []

    # 1. Allergies (HARD)
    for raw in allergies:
        clean = _clean_term(raw)
        if not clean:
            continue
        allergen = _CANONICAL_ALLERGEN_ALIASES.get(clean)
        if allergen is not None:
            results.append(
                NormalizedFoodConstraint(
                    code=allergen.value,
                    severity=ConstraintSeverity.HARD,
                    source="allergy",
                    raw_label=raw.strip(),
                )
            )
        elif clean in _KNOWN_FOOD_TERMS or len(clean.split()) == 1:
            results.append(
                NormalizedFoodConstraint(
                    code=clean,
                    severity=ConstraintSeverity.HARD,
                    source="allergy",
                    raw_label=raw.strip(),
                )
            )
        else:
            results.append(
                NormalizedFoodConstraint(
                    code="UNRESOLVED_HARD_FOOD_CONSTRAINT",
                    severity=ConstraintSeverity.HARD,
                    source="allergy",
                    raw_label=raw.strip(),
                )
            )

    # 2. Intolerances (HARD per roadmap conservative rule)
    for raw in intolerances:
        clean = _clean_term(raw)
        if not clean:
            continue
        allergen = _CANONICAL_ALLERGEN_ALIASES.get(clean)
        if allergen is not None:
            results.append(
                NormalizedFoodConstraint(
                    code=allergen.value,
                    severity=ConstraintSeverity.HARD,
                    source="intolerance",
                    raw_label=raw.strip(),
                )
            )
        elif clean in _KNOWN_FOOD_TERMS or len(clean.split()) == 1:
            results.append(
                NormalizedFoodConstraint(
                    code=clean,
                    severity=ConstraintSeverity.HARD,
                    source="intolerance",
                    raw_label=raw.strip(),
                )
            )
        else:
            results.append(
                NormalizedFoodConstraint(
                    code="UNRESOLVED_HARD_FOOD_CONSTRAINT",
                    severity=ConstraintSeverity.HARD,
                    source="intolerance",
                    raw_label=raw.strip(),
                )
            )

    # 3. Religious / cultural exclusions (HARD)
    for raw in religious_cultural_exclusions:
        clean = _clean_term(raw)
        if not clean:
            continue
        results.append(
            NormalizedFoodConstraint(
                code=clean,
                severity=ConstraintSeverity.HARD,
                source="religious_cultural",
                raw_label=raw.strip(),
            )
        )

    # 4. Never suggest / refused foods (HARD)
    for raw in (*never_suggest_foods, *refused_foods):
        clean = _clean_term(raw)
        if not clean:
            continue
        allergen = _CANONICAL_ALLERGEN_ALIASES.get(clean)
        code = allergen.value if allergen is not None else clean
        results.append(
            NormalizedFoodConstraint(
                code=code,
                severity=ConstraintSeverity.HARD,
                source="never_suggest",
                raw_label=raw.strip(),
            )
        )

    # 5. Disliked foods (SOFT)
    for raw in disliked_foods:
        clean = _clean_term(raw)
        if not clean:
            continue
        allergen = _CANONICAL_ALLERGEN_ALIASES.get(clean)
        code = allergen.value if allergen is not None else clean
        results.append(
            NormalizedFoodConstraint(
                code=code,
                severity=ConstraintSeverity.SOFT,
                source="disliked",
                raw_label=raw.strip(),
            )
        )

    return tuple(results)


def evaluate_food_constraints(
    *,
    constraints: tuple[NormalizedFoodConstraint, ...] = (),
    food_allergen_tags: tuple[str, ...] = (),
    food_slug: str = "",
    food_name_fa: str = "",
    allergen_metadata_verified: bool = False,
    allergen_tags: tuple[str, ...] | None = None,
    slug: str | None = None,
    name_fa: str | None = None,
    name_en: str | None = None,
) -> FoodConstraintDecision:
    """Evaluate whether a food item satisfies all constraints and calculate penalties."""
    tags = allergen_tags if allergen_tags is not None else food_allergen_tags
    s = slug if slug is not None else food_slug
    fa = name_fa if name_fa is not None else food_name_fa
    hard_reasons: list[str] = []
    soft_penalties: list[str] = []
    normalized_tags = {tag.strip().casefold() for tag in tags if tag.strip()}

    for constraint in constraints:
        if constraint.code == "UNRESOLVED_HARD_FOOD_CONSTRAINT":
            hard_reasons.append("UNRESOLVED_HARD_FOOD_CONSTRAINT")
            continue

        is_allergen_code = any(
            allergen.value == constraint.code for allergen in CanonicalAllergen
        )

        matched = False
        if is_allergen_code:
            # Check structured tags authoritative first
            if constraint.code == CanonicalAllergen.GLUTEN.value:
                # All wheat foods contain gluten
                matched = (
                    CanonicalAllergen.GLUTEN.value in normalized_tags
                    or CanonicalAllergen.WHEAT.value in normalized_tags
                )
            elif constraint.code in normalized_tags:
                matched = True
            elif not allergen_metadata_verified and not normalized_tags:
                # Fallback to string matching if unverified & tags unpopulated
                matched = _matches_term(
                    constraint.code.casefold(), s, fa
                ) or _matches_term(
                    (constraint.raw_label or "").casefold(), s, fa
                )
        else:
            # Keyword or slug matching for specific foods or categories
            matched = _matches_term(
                constraint.code.casefold(), s, fa
            ) or _matches_term(
                (constraint.raw_label or "").casefold(), s, fa
            )

        if matched:
            if constraint.severity == ConstraintSeverity.HARD:
                hard_reasons.append(f"EXCLUDED_BY_{constraint.code.upper().replace(' ', '_')}")
            else:
                soft_penalties.append(f"PENALIZED_FOR_{constraint.code.upper().replace(' ', '_')}")

    allowed = len(hard_reasons) == 0
    return FoodConstraintDecision(
        allowed=allowed,
        hard_reason_codes=tuple(hard_reasons),
        soft_penalty_codes=tuple(soft_penalties),
    )
