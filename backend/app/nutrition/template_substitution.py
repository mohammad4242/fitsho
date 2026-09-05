"""Pure, bounded ranking for safe scheduled meal-template substitutions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.nutrition.food_constraints import NormalizedFoodConstraint, evaluate_food_constraints

if TYPE_CHECKING:
    from app.nutrition.planner_engine import EligibleMealTemplate, PlannerMealTemplate

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class SubstitutionAction:
    day_index: int
    role: str
    slot_index: int
    requested_template_id: str
    replacement_template_id: str
    reason_code: str


@dataclass(frozen=True)
class SubstitutionContext:
    slot_category: str
    target_kcal: Decimal
    target_protein: Decimal = ZERO
    template_usage: tuple[tuple[str, int], ...] = ()
    maximum_repetition: int = 7
    liked_food_ids: tuple[str, ...] = ()
    disliked_food_ids: tuple[str, ...] = ()
    day_index: int | None = None
    role: str | None = None
    slot_index: int | None = None
    dietary_pattern: str = ""
    excluded_terms: tuple[str, ...] = ()
    food_constraints: tuple[NormalizedFoodConstraint, ...] = ()


@dataclass(frozen=True)
class PartialWeekVariant:
    days_built: tuple[tuple[str | None, ...], ...]
    pending_slots: tuple[tuple[int, int, str, str | None, str], ...]
    substitutions: tuple[SubstitutionAction, ...]
    partial_quality_lower_bound: tuple[Decimal, ...]
    stable_variant_key: tuple[str, ...]
    usage: tuple[tuple[str, int], ...] = ()


class NoCompatibleTemplateSubstituteError(Exception):
    def __init__(
        self,
        *,
        day_index: int,
        role: str,
        slot_index: int,
        requested_template_id: str,
        category: str,
        diagnostics: tuple[dict[str, str], ...],
    ) -> None:
        self.day_index = day_index
        self.role = role
        self.slot_index = slot_index
        self.requested_template_id = requested_template_id
        self.category = category
        self.diagnostics = diagnostics
        super().__init__(f"{requested_template_id}:{category}:{day_index}:{role}:{slot_index}")


def rank_template_substitutes(
    requested: PlannerMealTemplate,
    eligible_candidates: tuple[EligibleMealTemplate, ...],
    context: SubstitutionContext,
) -> tuple[EligibleMealTemplate, ...]:
    """Return only safe, category-compatible alternatives in stable order."""

    usage = dict(context.template_usage)
    candidates = [
        candidate
        for candidate in eligible_candidates
        if _is_eligible_for_slot(
            candidate,
            context.slot_category,
            usage,
            context.maximum_repetition,
            context.food_constraints,
        )
    ]
    if not candidates:
        candidates = [
            candidate
            for candidate in eligible_candidates
            if _is_eligible_for_slot(
                candidate,
                context.slot_category,
                usage,
                context.maximum_repetition,
                context.food_constraints,
                ignore_repetition=True,
            )
        ]
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: _ranking_key(requested, candidate, context, usage),
        )
    )


def substitution_rejection_diagnostics(
    requested: PlannerMealTemplate,
    eligible_candidates: Iterable[EligibleMealTemplate],
    context: SubstitutionContext,
) -> tuple[dict[str, str], ...]:
    """Explain why the bounded safe pool could not provide a replacement."""

    usage = dict(context.template_usage)
    diagnostics: list[dict[str, str]] = []
    eligible_count = 0
    for candidate in sorted(eligible_candidates, key=lambda item: item.template.meal_id):
        reasons: list[str] = []
        if getattr(candidate.template, "verification_status", "verified") != "verified":
            reasons.append("UNVERIFIED_TEMPLATE")
        if candidate.template.category != context.slot_category:
            reasons.append("SLOT_CATEGORY_MISMATCH")
        if usage.get(candidate.template.meal_id, 0) >= context.maximum_repetition:
            reasons.append("REPETITION_LIMIT_EXCEEDED")
        if not reasons:
            eligible_count += 1
            reasons.append("ELIGIBLE")
        diagnostics.append(
            {
                **_diagnostic_context(context),
                "requested_template_id": requested.meal_id,
                "candidate_template_id": candidate.template.meal_id,
                "eligible_alternative_count": "0",
                "reason_code": "+".join(reasons),
            }
        )
    if not diagnostics:
        diagnostics.append(
            {
                **_diagnostic_context(context),
                "requested_template_id": requested.meal_id,
                "candidate_template_id": "",
                "eligible_alternative_count": "0",
                "reason_code": "NO_ELIGIBLE_ALTERNATIVES",
            }
        )
    return tuple(
        {
            **diagnostic,
            "eligible_alternative_count": str(eligible_count),
        }
        for diagnostic in diagnostics
    )


def _diagnostic_context(context: SubstitutionContext) -> dict[str, str]:
    return {
        "day_index": "" if context.day_index is None else str(context.day_index),
        "role": context.role or "",
        "slot_index": "" if context.slot_index is None else str(context.slot_index),
        "slot_category": context.slot_category,
        "dietary_pattern": context.dietary_pattern,
        "excluded_terms": "|".join(context.excluded_terms),
    }


def template_reference_metrics(
    candidate: EligibleMealTemplate,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return reference energy, protein, and cost for bounded beam ordering."""

    energy, protein, cost, _preference_penalty = _candidate_metrics(
        candidate,
        SubstitutionContext(slot_category=candidate.template.category, target_kcal=ZERO),
    )
    return energy, protein, cost


def _is_eligible_for_slot(
    candidate: EligibleMealTemplate,
    category: str,
    usage: dict[str, int],
    maximum_repetition: int,
    constraints: tuple[NormalizedFoodConstraint, ...] = (),
    *,
    ignore_repetition: bool = False,
) -> bool:
    if getattr(candidate.template, "verification_status", "verified") != "verified":
        return False
    if candidate.template.category != category:
        return False
    if not ignore_repetition and usage.get(candidate.template.meal_id, 0) >= maximum_repetition:
        return False
    if constraints:
        for _item, food in candidate.items:
            decision = evaluate_food_constraints(
                constraints=constraints,
                slug=food.slug,
                name_fa=food.name_fa,
                name_en=food.name_en,
                allergen_tags=getattr(food, "allergen_tags", ()),
                allergen_metadata_verified=getattr(food, "allergen_metadata_verified", False),
            )
            if decision.is_hard_blocked:
                return False
        for _food_id, recipe_food in candidate.prepared_recipe_foods:
            decision = evaluate_food_constraints(
                constraints=constraints,
                slug=recipe_food.slug,
                name_fa=recipe_food.name_fa,
                name_en=recipe_food.name_en,
                allergen_tags=getattr(recipe_food, "allergen_tags", ()),
                allergen_metadata_verified=getattr(
                    recipe_food, "allergen_metadata_verified", False
                ),
            )
            if decision.is_hard_blocked:
                return False
    return True


def _ranking_key(
    requested: PlannerMealTemplate,
    candidate: EligibleMealTemplate,
    context: SubstitutionContext,
    usage: dict[str, int],
) -> tuple[object, ...]:
    requested_roles = {
        item.functional_role for item in requested.items if item.functional_role is not None
    }
    candidate_roles = {
        item.functional_role for item, _food in candidate.items if item.functional_role is not None
    }
    role_penalty = len(requested_roles - candidate_roles)
    energy, protein, cost, preference_penalty = _candidate_metrics(candidate, context)
    target_kcal = max(context.target_kcal, ONE)
    target_protein = max(context.target_protein, ONE)
    return (
        role_penalty,
        abs(energy - context.target_kcal) / target_kcal,
        abs(protein - context.target_protein) / target_protein,
        usage.get(candidate.template.meal_id, 0),
        preference_penalty,
        cost,
        candidate.template.meal_id,
    )


def _candidate_metrics(
    candidate: EligibleMealTemplate,
    context: SubstitutionContext,
) -> tuple[Decimal, Decimal, Decimal, int]:
    nutrients: dict[str, Decimal] = {}
    cost = ZERO
    preference_penalty = 0
    for item, food in candidate.items:
        grams = item.reference_grams
        for code, value in food.nutrients_per_100g.items():
            nutrients[code] = nutrients.get(code, ZERO) + value * grams / Decimal("100")
        cost += food.price_irr_per_gram * grams
        if food.food_id in context.liked_food_ids:
            preference_penalty -= 1
        if food.food_id in context.disliked_food_ids:
            preference_penalty += 1
        if context.food_constraints:
            decision = evaluate_food_constraints(
                constraints=context.food_constraints,
                slug=food.slug,
                name_fa=food.name_fa,
                name_en=food.name_en,
                allergen_tags=getattr(food, "allergen_tags", ()),
                allergen_metadata_verified=getattr(food, "allergen_metadata_verified", False),
            )
            if decision.penalty > ZERO:
                preference_penalty += 1
    if candidate.template.prepared_recipe is not None:
        foods_by_id = dict(candidate.prepared_recipe_foods)
        for ingredient in candidate.template.prepared_recipe.definition.ingredients:
            recipe_food = foods_by_id.get(str(ingredient.food_id))
            if recipe_food is None:
                continue
            grams = ingredient.reference_grams
            for code, value in recipe_food.nutrients_per_100g.items():
                nutrients[code] = nutrients.get(code, ZERO) + value * grams / Decimal("100")
            cost += recipe_food.price_irr_per_gram * grams
            if recipe_food.food_id in context.liked_food_ids:
                preference_penalty -= 1
            if recipe_food.food_id in context.disliked_food_ids:
                preference_penalty += 1
            if context.food_constraints:
                decision = evaluate_food_constraints(
                    constraints=context.food_constraints,
                    slug=recipe_food.slug,
                    name_fa=recipe_food.name_fa,
                    name_en=recipe_food.name_en,
                    allergen_tags=getattr(recipe_food, "allergen_tags", ()),
                    allergen_metadata_verified=getattr(
                        recipe_food, "allergen_metadata_verified", False
                    ),
                )
                if decision.penalty > ZERO:
                    preference_penalty += 1
    return (
        nutrients.get("energy_kcal", ZERO),
        nutrients.get("protein_g", ZERO),
        cost,
        preference_penalty,
    )
