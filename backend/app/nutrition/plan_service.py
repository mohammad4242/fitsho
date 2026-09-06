from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.nutrition.candidate_selection import (
    CandidateEvaluation,
    CandidateQuality,
    CandidateSelection,
    evaluate_candidate,
    failure_reason_counts,
)
from app.nutrition.enums import (
    DietaryPattern,
    FoodItemKind,
    FoodVerificationStatus,
    MealCalculationMode,
    NutritionOptimizationMode,
    NutritionPlanBudgetStatus,
    NutritionPlanGenerationOutcome,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
    NutritionPlanRole,
    NutritionTargetMetric,
    SafetyOutcome,
    Weekday,
)
from app.nutrition.estimate_service import create_estimate
from app.nutrition.exceptions import (
    GoalReselectionRequiredDomainError,
    NutritionProductModeError,
    NutritionTargetInfeasibleDomainError,
    PlanSelectionInvalidError,
    StructuredExerciseRequiredError,
    WeeklyPlanBundleNotFoundError,
)
from app.nutrition.food_constraints import normalize_food_constraints
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueMeal,
    NutritionEstimate,
    NutritionEstimateMicronutrientTarget,
    NutritionEstimateTarget,
    NutritionFoodItem,
    NutritionPlanBundle,
    NutritionPlanGeneration,
    NutritionPlanPhysicianReview,
    NutritionPreparedRecipe,
    NutritionPreparedRecipeRevision,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionStructuredExercise,
    NutritionWeeklyPlan,
    NutritionWeeklyPlanDay,
    NutritionWeeklyPlanFood,
    NutritionWeeklyPlanMeal,
    NutritionWeeklyPlanNutrient,
)
from app.nutrition.nutrition_request import (
    build_normalized_nutrition_request,
)
from app.nutrition.plan_comparison import compare_plans
from app.nutrition.planner_engine import (
    GenerationOutcome,
    PlannedFood,
    PlannerFood,
    PlannerInput,
    PlannerMealIngredient,
    PlannerMealTemplate,
    PlannerPreparedRecipe,
    PlannerResult,
    plan_week,
)
from app.nutrition.planner_policy import (
    BUDGET_OPTIMIZER_POLICY_VERSION,
    CANDIDATE_SELECTION_POLICY_VERSION,
    DEFAULT_POLICY,
    INITIAL_PROGRAM_BATCH_SIZE,
    MAX_PROGRAM_FALLBACK_BATCHES,
    PLANNER_POLICY_VERSION,
    PLANNER_VERSION,
    PREFERENCE_QUALITY_POLICY_VERSION,
    PROGRAM_SELECTION_POLICY_VERSION,
    TEMPLATE_SUBSTITUTION_POLICY_VERSION,
)
from app.nutrition.preference_snapshot import (
    PreferenceSnapshot,
    load_preference_snapshot,
)
from app.nutrition.prepared_recipe import (
    PreparedRecipeDefinition,
    PreparedRecipeIngredient,
    PreparedRecipeRatio,
    PreparedRecipeYield,
)
from app.nutrition.price_mass_conversion import planner_price_irr_per_gram
from app.nutrition.price_overrides import effective_prices
from app.nutrition.program_adaptation import AdaptedWeek, adapt_program
from app.nutrition.program_catalogue import list_programs
from app.nutrition.program_costing import (
    ProgramCostEstimate,
    estimate_program_cost,
)
from app.nutrition.program_selection import (
    ProgramCandidate,
    ProgramSelectionResult,
    rank_base_programs,
)
from app.nutrition.schemas import (
    PlanBundleSelectResponse,
    PlanComparisonMetricResponse,
    PlanComparisonResponse,
    WeeklyPlanDayResponse,
    WeeklyPlanFoodResponse,
    WeeklyPlanGenerationResponse,
    WeeklyPlanHistoryItemResponse,
    WeeklyPlanMealResponse,
    WeeklyPlanNutrientResponse,
    WeeklyPlanPreparedRecipeSummary,
    WeeklyPlanResponse,
)
from app.nutrition.service import current_safety_decision
from app.profile.models import UserProfile

_HARD_EXCLUSION_KINDS = {
    FoodItemKind.NEVER_SUGGEST,
    FoodItemKind.REFUSED,
    FoodItemKind.ALLERGY,
    FoodItemKind.INTOLERANCE,
    FoodItemKind.RELIGIOUS_CULTURAL_EXCLUSION,
}
_TARGET_UNITS = {
    "goal_calories": "kcal/day",
    "protein": "g/day",
    "carbohydrate": "g/day",
    "total_fat": "g/day",
    "fibre": "g/day",
}
_WEEKDAY_INDEX = {
    Weekday.MONDAY: 0,
    Weekday.TUESDAY: 1,
    Weekday.WEDNESDAY: 2,
    Weekday.THURSDAY: 3,
    Weekday.FRIDAY: 4,
    Weekday.SATURDAY: 5,
    Weekday.SUNDAY: 6,
}
_GOAL_WARNING_CODES = frozenset(
    {
        "TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING",
        "TRAINING_STIMULUS_MISMATCH",
    }
)
_GOAL_EXPLANATION_CODES = frozenset(
    {
        "GENERAL_FITNESS_NUTRITION_TARGET",
        "TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING",
        "TRAINING_STIMULUS_MISMATCH",
    }
)


class WeeklyPlanNotFoundError(Exception):
    pass


class ActiveWeeklyPlanNotFoundError(Exception):
    pass


def _estimate_goal_contract_codes(
    estimate: NutritionEstimate,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    codes = {
        code
        for target in estimate.targets
        for code in target.explanation_codes
        if code in _GOAL_EXPLANATION_CODES
    }
    return tuple(sorted(codes & _GOAL_WARNING_CODES)), tuple(sorted(codes))


def generate_weekly_plan(db: Session, user_id: UUID) -> WeeklyPlanGenerationResponse:
    safety = current_safety_decision(db, user_id)
    profile = db.get(NutritionProfile, user_id)
    if safety.outcome in {
        SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
        SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED,
    }:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.SAFETY_BLOCKED,
            reasons=(safety.outcome.value.upper(),),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={"ordinary_automatic_plan_created": False},
        )
        return _generation_response(generation, None)
    if profile is None:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.FAILED,
            reasons=("NUTRITION_PROFILE_REQUIRED",),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    if profile.dietary_pattern in {DietaryPattern.VEGETARIAN, DietaryPattern.VEGAN}:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.FAILED,
            reasons=("DIETARY_PATTERN_NOT_SUPPORTED_V1",),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={"dietary_pattern": profile.dietary_pattern.value},
        )
        return _generation_response(generation, None)

    try:
        estimate_response = create_estimate(db, user_id)
    except GoalReselectionRequiredDomainError:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.TARGET_INFEASIBLE,
            reasons=("GOAL_RESELECTION_REQUIRED",),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    except NutritionTargetInfeasibleDomainError as error:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.TARGET_INFEASIBLE,
            reasons=error.reason_codes,
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    except (StructuredExerciseRequiredError, NutritionProductModeError) as error:
        reason = (
            "STRUCTURED_EXERCISE_REQUIRED"
            if isinstance(error, StructuredExerciseRequiredError)
            else "NUTRITION_PRODUCT_MODE_REQUIRED"
        )
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.FAILED,
            reasons=(reason,),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    estimate = _estimate_by_id(db, estimate_response.id)

    targets = _daily_targets(estimate.targets)
    micro_targets, upper_limits, micro_metadata = _micronutrient_targets(
        estimate.micronutrient_targets
    )
    food_items = db.scalars(
        select(NutritionFoodItem).where(NutritionFoodItem.user_id == user_id)
    ).all()
    raw_constraints = [
        {"kind": item.kind.value, "term": item.name, "details": item.details} for item in food_items
    ]
    normalized_constraints = normalize_food_constraints(raw_constraints)
    unresolved_hard = tuple(
        c for c in normalized_constraints if c.code == "UNRESOLVED_HARD_FOOD_CONSTRAINT"
    )
    if unresolved_hard:
        unresolved_terms = [c.raw_label or c.code for c in unresolved_hard]
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=estimate,
            outcome=NutritionPlanGenerationOutcome.FAILED,
            reasons=("UNRESOLVED_HARD_FOOD_CONSTRAINT",),
            warnings=(),
            input_snapshot={
                "estimate_id": str(estimate.id),
                "estimate_revision": estimate.revision,
                "unresolved_food_constraints": unresolved_terms,
            },
            diagnostics={"unresolved_hard_constraints": unresolved_terms},
        )
        return _generation_response(generation, None)
    preference_snapshot = load_preference_snapshot(db, user_id, food_items)
    exclusions = tuple(
        item.normalized_name for item in food_items if item.kind in _HARD_EXCLUSION_KINDS
    )
    liked_food_ids = preference_snapshot.liked_food_ids
    disliked_food_ids = preference_snapshot.disliked_food_ids
    foods, price_snapshot, food_manifest = _planner_foods(db)
    meal_templates, meal_manifest = _planner_meal_templates(db)
    programs = list_programs(db)
    user_profile = db.get(UserProfile, user_id)
    structured_exercise = db.get(NutritionStructuredExercise, user_id)
    base_candidates: tuple[ProgramCandidate, ...] = ()
    base_selection_result: ProgramSelectionResult | None = None
    cost_estimates: dict[str, ProgramCostEstimate] = {}
    if programs and user_profile is not None and user_profile.fitness_goal is not None:
        normalized_request = build_normalized_nutrition_request(
            user_id=user_id,
            profile=profile,
            user_profile=user_profile,
            structured_exercise=structured_exercise,
            estimate=estimate,
        )
        foods_by_id = {food.food_id: food for food in foods}

        meal_templates_by_id = {t.meal_id: t for t in meal_templates}
        cost_estimates = {
            prog.code: estimate_program_cost(
                prog,
                main_meal_slots=normalized_request.main_meal_slots,
                snack_slots=normalized_request.snack_slots,
                daily_kcal=normalized_request.tdee_kcal,
                meal_templates_by_id=meal_templates_by_id,
                foods_by_id=foods_by_id,
                user_monthly_budget_irr=normalized_request.monthly_budget_irr,
            )
            for prog in programs
        }
        base_selection_result = rank_base_programs(
            programs,
            normalized_request,
            cost_estimates=cost_estimates,
        )
        base_candidates = base_selection_result.candidates

    food_manifest["meals"] = meal_manifest
    minimums, maximums = _daily_limits(estimate.targets)
    weekly_budget = profile.individual_monthly_food_budget_irr * 12 // 52
    base_input_snapshot: dict[str, object] = {
        "estimate_id": str(estimate.id),
        "estimate_revision": estimate.revision,
        "safety_decision_id": str(safety.id),
        "safety_outcome": safety.outcome.value,
        "safety_reason_codes": [reason.code for reason in safety.reasons],
        "medical_condition_policy_version": safety.medical_condition_policy_version,
        "main_meal_count_bucket": profile.main_meal_count_bucket.value,
        "snack_count_bucket": profile.snack_count_bucket.value,
        "main_meals_per_day": profile.effective_main_meal_slots,
        "snacks_per_day": profile.effective_snack_slots,
        "weekly_budget_irr": weekly_budget,
        "budget_mode": profile.budget_style.value,
        "daily_targets": _json_decimal_map(targets),
        "daily_minimums": _json_decimal_map(minimums),
        "daily_maximums": _json_decimal_map(maximums),
        "micronutrient_targets": _json_decimal_map(micro_targets),
        "micronutrient_upper_limits": _json_decimal_map(upper_limits),
        "micronutrient_reference_rows": micro_metadata,
        "food_constraints": [
            {
                "kind": getattr(c, "source", None) or getattr(c, "kind", None),
                "term": getattr(c, "raw_label", None) or getattr(c, "raw_term", None),
                "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
                "code": c.code,
            }
            for c in normalized_constraints
        ],
        "hard_exclusions": list(exclusions),
        "liked_food_ids": list(liked_food_ids),
        "disliked_food_ids": list(disliked_food_ids),
        "liked_meal_ids": list(preference_snapshot.liked_meal_ids),
        "disliked_meal_ids": list(preference_snapshot.disliked_meal_ids),
        "prefer_more_often_meal_ids": list(preference_snapshot.prefer_more_often_meal_ids),
        "excluded_meal_ids": list(preference_snapshot.excluded_meal_ids),
        "historical_meal_adherence": [
            [meal_id, str(score)]
            for meal_id, score in preference_snapshot.historical_meal_adherence
        ],
        "preference_data_sufficient": preference_snapshot.data_sufficient,
        "preference_quality_policy_version": PREFERENCE_QUALITY_POLICY_VERSION,
        "dietary_pattern": profile.dietary_pattern.value,
        "maximum_meal_repetition_per_week": profile.maximum_meal_repetition_per_week,
        "meal_distribution_policy_version": "meal-distribution-v1",
        "template_substitution_policy_version": TEMPLATE_SUBSTITUTION_POLICY_VERSION,
        "budget_optimizer_policy_version": BUDGET_OPTIMIZER_POLICY_VERSION,
        "budget_formula_version": "annualized-monthly-times-12-divided-52-v1",
        "meal_catalogue_template_ids": [item.meal_id for item in meal_templates],
        "program_selection_policy_version": (
            base_selection_result.policy_version
            if base_selection_result is not None
            else PROGRAM_SELECTION_POLICY_VERSION
        ),
        "program_selection_trace": (
            base_selection_result.decision_trace() if base_selection_result is not None else None
        ),
        "nutrition_program_id": None,
        "nutrition_program_code": None,
    }
    base_planner_input = PlannerInput(
        daily_targets=targets,
        micronutrient_targets=micro_targets,
        micronutrient_upper_limits=upper_limits,
        daily_minimums=minimums,
        daily_maximums=maximums,
        main_meals_per_day=profile.effective_main_meal_slots,
        snacks_per_day=profile.effective_snack_slots,
        weekly_budget_irr=weekly_budget,
        budget_mode=profile.budget_style.value,
        excluded_terms=exclusions,
        liked_food_ids=liked_food_ids,
        disliked_food_ids=disliked_food_ids,
        dietary_pattern=profile.dietary_pattern.value,
        maximum_meal_repetition_per_week=profile.maximum_meal_repetition_per_week,
        preference_snapshot=preference_snapshot,
        food_constraints=tuple(normalized_constraints),
    )

    optimization_cache: dict[tuple[object, ...], PlannedFood] = {}
    blueprint: BasePlanBlueprint | None = None
    evaluations: tuple[CandidateEvaluation, ...] = ()
    fallback_batches = 0

    if base_candidates:
        blueprint, evaluations, fallback_batches = _construct_frozen_base_blueprint(
            candidates=base_candidates,
            base_input=base_planner_input,
            profile=profile,
            foods=foods,
            meal_templates=meal_templates,
            preference_snapshot=preference_snapshot,
            weekly_budget=weekly_budget,
            optimization_cache=optimization_cache,
        )
        if blueprint is None:
            candidate_selection = CandidateSelection(
                selected=None,
                first_valid=None,
                evaluations=tuple(evaluations),
            )
            budget_result = _aggregate_failure_result(candidate_selection)
            goal_warning_codes, _ = _estimate_goal_contract_codes(estimate)
            budget_result = replace(
                budget_result,
                warning_codes=tuple(
                    sorted(set(budget_result.warning_codes).union(goal_warning_codes))
                ),
            )
            budget_input_snapshot = {
                **base_input_snapshot,
                "program_selection_trace": (
                    base_selection_result.decision_trace(
                        programs_constructed=len(evaluations),
                        fallback_batches_used=fallback_batches,
                    )
                    if base_selection_result is not None
                    else None
                ),
                "nutrition_program_id": None,
                "nutrition_program_code": None,
                "goal_contract_version": estimate.input_snapshot.get("goal_contract_version"),
                "training_alignment_warning_codes": estimate.input_snapshot.get(
                    "training_alignment_warning_codes", []
                ),
                "optimization_mode": NutritionOptimizationMode.BUDGET_CONSTRAINED.value,
            }
            budget_outcome = NutritionPlanGenerationOutcome(budget_result.outcome.value)
            budget_generation = _persist_generation(
                db,
                user_id=user_id,
                bundle_id=None,
                plan_role=NutritionPlanRole.BUDGET.value,
                safety=safety,
                estimate=estimate,
                outcome=budget_outcome,
                reasons=budget_result.reason_codes,
                warnings=budget_result.warning_codes,
                input_snapshot=budget_input_snapshot,
                diagnostics={
                    "food_candidate_count": len(foods),
                    "meal_template_count": len(meal_templates),
                    "program_candidate_count": len(base_candidates),
                    "evaluated_program_candidate_count": len(evaluations),
                    "successful_program_candidate_count": 0,
                    "weekly_cost_irr": str(budget_result.weekly_cost_irr),
                    "budget_status": budget_result.budget_status,
                    "selection_trace": _selection_trace(candidate_selection),
                },
            )
            return WeeklyPlanGenerationResponse(
                generation_id=budget_generation.id,
                outcome=budget_generation.outcome.value,
                reason_codes=budget_generation.reason_codes,
                warning_codes=budget_generation.warning_codes,
                plan=None,
                budget_plan=None,
                ideal_plan=None,
                comparison=None,
            )

        budget_result = blueprint.initial_budget_result
        budget_program = blueprint.program_id
        budget_program_code = blueprint.program_code
        ideal_program = blueprint.program_id
        ideal_program_code = blueprint.program_code
        blueprint_sig = blueprint.blueprint_signature

        ideal_input = replace(
            base_planner_input,
            optimization_mode=NutritionOptimizationMode.IDEAL_REFERENCE,
            template_schedule=blueprint.template_schedule,
            weekly_budget_irr=None,
            budget_mode=None,
        )
        ideal_result = plan_week(
            ideal_input,
            foods,
            meal_templates,
            policy=DEFAULT_POLICY,
            optimization_cache=optimization_cache,
        )
    else:
        budget_result = plan_week(
            base_planner_input,
            foods,
            meal_templates,
            policy=DEFAULT_POLICY,
            optimization_cache=optimization_cache,
        )
        ideal_input = replace(
            base_planner_input,
            optimization_mode=NutritionOptimizationMode.IDEAL_REFERENCE,
            weekly_budget_irr=None,
            budget_mode=None,
        )
        ideal_result = plan_week(
            ideal_input,
            foods,
            meal_templates,
            policy=DEFAULT_POLICY,
            optimization_cache=optimization_cache,
        )
        budget_program = None
        budget_program_code = None
        ideal_program = None
        ideal_program_code = None
        blueprint_sig = None

    goal_warning_codes, _ = _estimate_goal_contract_codes(estimate)
    budget_result = replace(
        budget_result,
        warning_codes=tuple(sorted(set(budget_result.warning_codes).union(goal_warning_codes))),
    )
    ideal_result = replace(
        ideal_result,
        warning_codes=tuple(sorted(set(ideal_result.warning_codes).union(goal_warning_codes))),
    )

    min_feasible_monthly_cost = None
    if budget_result.minimum_feasible_weekly_cost_irr is not None:
        min_feasible_monthly_cost = int(
            round(budget_result.minimum_feasible_weekly_cost_irr * Decimal("30") / Decimal("7"))
        )

    comparison_report = compare_plans(
        user_monthly_budget_irr=profile.individual_monthly_food_budget_irr,
        budget_plan_result=budget_result
        if budget_result.outcome is GenerationOutcome.SUCCESS
        else None,
        ideal_plan_result=ideal_result
        if ideal_result.outcome is GenerationOutcome.SUCCESS
        else None,
        minimum_feasible_monthly_cost_irr=min_feasible_monthly_cost,
    )

    if "BUDGET_PLAN_PROTEIN_PREFERRED_GAP" in comparison_report.reason_codes:
        if "BUDGET_PLAN_PROTEIN_PREFERRED_GAP" not in budget_result.warning_codes:
            budget_result = replace(
                budget_result,
                warning_codes=(*budget_result.warning_codes, "BUDGET_PLAN_PROTEIN_PREFERRED_GAP"),
            )

    bundle = NutritionPlanBundle(
        user_id=user_id,
        estimate_id=estimate.id,
        comparison_snapshot=comparison_report.to_snapshot(),
    )
    db.add(bundle)
    db.flush()

    budget_input_snapshot = {
        **base_input_snapshot,
        "blueprint_signature": blueprint_sig,
        "program_selection_trace": (
            base_selection_result.decision_trace(
                programs_constructed=len(evaluations),
                fallback_batches_used=fallback_batches,
            )
            if base_selection_result is not None
            else None
        ),
        "nutrition_program_id": str(budget_program) if budget_program else None,
        "nutrition_program_code": budget_program_code,
        "goal_contract_version": estimate.input_snapshot.get("goal_contract_version"),
        "training_alignment_warning_codes": estimate.input_snapshot.get(
            "training_alignment_warning_codes", []
        ),
        "optimization_mode": NutritionOptimizationMode.BUDGET_CONSTRAINED.value,
    }

    selected_eval = next(
        (e for e in evaluations if e.program_code == budget_program_code),
        evaluations[-1] if evaluations else None,
    )
    first_valid_eval = next(
        (e for e in evaluations if e.result.outcome is GenerationOutcome.SUCCESS), None
    )
    candidate_selection = CandidateSelection(
        selected=selected_eval,
        first_valid=first_valid_eval,
        evaluations=tuple(evaluations),
    )

    budget_outcome = NutritionPlanGenerationOutcome(budget_result.outcome.value)
    budget_generation = _persist_generation(
        db,
        user_id=user_id,
        bundle_id=bundle.id,
        plan_role=NutritionPlanRole.BUDGET.value,
        safety=safety,
        estimate=estimate,
        outcome=budget_outcome,
        reasons=budget_result.reason_codes,
        warnings=budget_result.warning_codes,
        input_snapshot=budget_input_snapshot,
        diagnostics={
            "food_candidate_count": len(foods),
            "meal_template_count": len(meal_templates),
            "program_candidate_count": len(base_candidates),
            "evaluated_program_candidate_count": len(evaluations),
            "successful_program_candidate_count": sum(
                evaluation.result.outcome is GenerationOutcome.SUCCESS for evaluation in evaluations
            ),
            "weekly_cost_irr": str(budget_result.weekly_cost_irr),
            "budget_status": budget_result.budget_status,
            "blueprint_signature": blueprint_sig,
            "selection_trace": _selection_trace(candidate_selection),
        },
        commit=False,
    )

    ideal_generation: NutritionPlanGeneration | None = None
    ideal_plan_model: NutritionWeeklyPlan | None = None
    if ideal_result.outcome is GenerationOutcome.SUCCESS:
        ideal_input_snapshot = {
            **base_input_snapshot,
            "blueprint_signature": blueprint_sig,
            "weekly_budget_irr": None,
            "budget_mode": None,
            "program_selection_trace": (
                base_selection_result.decision_trace(
                    programs_constructed=len(evaluations),
                    fallback_batches_used=fallback_batches,
                )
                if base_selection_result is not None
                else None
            ),
            "nutrition_program_id": str(ideal_program) if ideal_program else None,
            "nutrition_program_code": ideal_program_code,
            "goal_contract_version": estimate.input_snapshot.get("goal_contract_version"),
            "training_alignment_warning_codes": estimate.input_snapshot.get(
                "training_alignment_warning_codes", []
            ),
            "optimization_mode": NutritionOptimizationMode.IDEAL_REFERENCE.value,
        }
        ideal_generation = _persist_generation(
            db,
            user_id=user_id,
            bundle_id=bundle.id,
            plan_role=NutritionPlanRole.IDEAL_REFERENCE.value,
            safety=safety,
            estimate=estimate,
            outcome=NutritionPlanGenerationOutcome.SUCCESS,
            reasons=ideal_result.reason_codes,
            warnings=ideal_result.warning_codes,
            input_snapshot=ideal_input_snapshot,
            diagnostics={
                "food_candidate_count": len(foods),
                "meal_template_count": len(meal_templates),
                "program_candidate_count": len(base_candidates),
                "evaluated_program_candidate_count": len(evaluations),
                "successful_program_candidate_count": sum(
                    evaluation.result.outcome is GenerationOutcome.SUCCESS
                    for evaluation in evaluations
                ),
                "weekly_cost_irr": str(ideal_result.weekly_cost_irr),
                "budget_status": ideal_result.budget_status,
                "blueprint_signature": blueprint_sig,
                "selection_trace": _selection_trace(candidate_selection),
            },
            commit=False,
        )
        ideal_plan_model = _persist_ideal_plan(
            db,
            generation=ideal_generation,
            profile=profile,
            estimate=estimate,
            safety=safety,
            result=ideal_result,
            input_snapshot=ideal_input_snapshot,
            price_snapshot=price_snapshot,
            food_manifest=food_manifest,
            micro_metadata=micro_metadata,
            program_id=ideal_program,
        )

    budget_plan_model: NutritionWeeklyPlan | None = None
    if budget_result.outcome is GenerationOutcome.SUCCESS:
        budget_plan_model = _persist_successful_plan(
            db,
            generation=budget_generation,
            profile=profile,
            estimate=estimate,
            safety=safety,
            result=budget_result,
            input_snapshot=budget_input_snapshot,
            price_snapshot=price_snapshot,
            food_manifest=food_manifest,
            micro_metadata=micro_metadata,
            program_id=budget_program,
        )

    if (
        comparison_report.show_ideal_plan
        and budget_plan_model is not None
        and ideal_plan_model is not None
    ):
        bundle.selected_plan_id = None
        bundle.selected_plan_role = None
        bundle.selected_at = None
    elif budget_plan_model is not None:
        bundle.selected_plan_id = budget_plan_model.id
        bundle.selected_plan_role = NutritionPlanRole.BUDGET.value
        bundle.selected_at = datetime.now(UTC)
    elif ideal_plan_model is not None:
        bundle.selected_plan_id = ideal_plan_model.id
        bundle.selected_plan_role = NutritionPlanRole.IDEAL_REFERENCE.value
        bundle.selected_at = datetime.now(UTC)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    loaded_budget_plan = _load_plan(db, budget_plan_model.id) if budget_plan_model else None
    loaded_ideal_plan = _load_plan(db, ideal_plan_model.id) if ideal_plan_model else None

    def _to_metric_response(m: object) -> PlanComparisonMetricResponse | None:
        if m is None:
            return None
        return PlanComparisonMetricResponse(
            budget_value=getattr(m, "budget_value", None),
            ideal_value=getattr(m, "ideal_value", None),
            difference=getattr(m, "difference", None),
            unit=getattr(m, "unit", ""),
            target_value=getattr(m, "target_value", None),
        )

    comparison_response = PlanComparisonResponse(
        user_monthly_budget_irr=comparison_report.user_monthly_budget_irr,
        budget_plan_monthly_cost_irr=comparison_report.budget_plan_monthly_cost_irr,
        ideal_plan_monthly_cost_irr=comparison_report.ideal_plan_monthly_cost_irr,
        minimum_feasible_monthly_cost_irr=comparison_report.minimum_feasible_monthly_cost_irr,
        monthly_cost_gap_irr=comparison_report.monthly_cost_gap_irr,
        calorie_gap=_to_metric_response(comparison_report.calorie_gap),
        protein_gap=_to_metric_response(comparison_report.protein_gap),
        carbohydrate_gap=_to_metric_response(comparison_report.carbohydrate_gap),
        fat_gap=_to_metric_response(comparison_report.fat_gap),
        fibre_gap=_to_metric_response(comparison_report.fibre_gap),
        calorie_gap_kcal_per_day=comparison_report.calorie_gap_kcal_per_day,
        protein_gap_g_per_day=comparison_report.protein_gap_g_per_day,
        carbohydrate_gap_g_per_day=comparison_report.carbohydrate_gap_g_per_day,
        fat_gap_g_per_day=comparison_report.fat_gap_g_per_day,
        fibre_gap_g_per_day=comparison_report.fibre_gap_g_per_day,
        micronutrient_gaps_improved=list(comparison_report.micronutrient_gaps_improved),
        unique_meal_count_budget=comparison_report.unique_meal_count_budget,
        unique_meal_count_ideal=comparison_report.unique_meal_count_ideal,
        unique_protein_sources_budget=comparison_report.unique_protein_sources_budget,
        unique_protein_sources_ideal=comparison_report.unique_protein_sources_ideal,
        meaningful_quality_improvement=comparison_report.meaningful_quality_improvement,
        show_ideal_plan=comparison_report.show_ideal_plan,
        reason_codes=list(comparison_report.reason_codes),
        policy_version=comparison_report.policy_version,
    )

    budget_plan_resp = weekly_plan_response(loaded_budget_plan) if loaded_budget_plan else None
    ideal_plan_resp = weekly_plan_response(loaded_ideal_plan) if loaded_ideal_plan else None

    response_outcome = (
        NutritionPlanGenerationOutcome.SUCCESS.value
        if (loaded_budget_plan is not None or loaded_ideal_plan is not None)
        else budget_generation.outcome.value
    )
    return WeeklyPlanGenerationResponse(
        generation_id=budget_generation.id,
        bundle_id=bundle.id,
        selected_plan_id=bundle.selected_plan_id,
        selected_plan_role=bundle.selected_plan_role,
        outcome=response_outcome,
        reason_codes=budget_generation.reason_codes,
        warning_codes=budget_generation.warning_codes,
        plan=budget_plan_resp or ideal_plan_resp,
        budget_plan=budget_plan_resp,
        ideal_plan=ideal_plan_resp,
        comparison=comparison_response,
    )


def _template_schedule(
    adapted: AdaptedWeek,
) -> tuple[tuple[tuple[str, str | None, str], ...], ...]:
    return tuple(
        tuple(
            (
                "snack"
                if slot.role == "snack"
                else "free_meal"
                if slot.role == "free_meal"
                else "post_workout"
                if slot.role == "post_workout"
                else "main_meal",
                str(slot.meal_id) if slot.meal_id is not None else None,
                slot.category.value,
            )
            for slot in day.slots
        )
        for day in adapted.days
    )


def _aggregate_failure_result(selection: CandidateSelection) -> PlannerResult:
    outcomes = tuple(evaluation.result.outcome for evaluation in selection.evaluations)
    if outcomes and all(
        outcome is GenerationOutcome.LIVE_PRICE_UNAVAILABLE for outcome in outcomes
    ):
        outcome = GenerationOutcome.LIVE_PRICE_UNAVAILABLE
    elif GenerationOutcome.TARGET_INFEASIBLE in outcomes:
        outcome = GenerationOutcome.TARGET_INFEASIBLE
    elif GenerationOutcome.INFEASIBLE in outcomes:
        outcome = GenerationOutcome.INFEASIBLE
    else:
        outcome = GenerationOutcome.FAILED
    reasons = tuple(
        sorted(
            {
                reason
                for evaluation in selection.evaluations
                for reason in evaluation.result.reason_codes
            }
        )
    )
    return PlannerResult(
        outcome=outcome,
        reason_codes=reasons or ("CANDIDATE_SEARCH_FAILED",),
    )


@dataclass(frozen=True)
class BasePlanBlueprint:
    program_id: UUID | None
    program_code: str | None
    blueprint_signature: str
    adapted_week: AdaptedWeek
    template_schedule: tuple[tuple[tuple[str, str | None, str], ...], ...]
    candidate_proposal: ProgramCandidate | None
    evaluations: tuple[CandidateEvaluation, ...]
    fallback_batches_used: int
    initial_budget_result: PlannerResult


def _construct_frozen_base_blueprint(
    *,
    candidates: tuple[ProgramCandidate, ...],
    base_input: PlannerInput,
    profile: NutritionProfile,
    foods: tuple[PlannerFood, ...],
    meal_templates: tuple[PlannerMealTemplate, ...],
    preference_snapshot: PreferenceSnapshot,
    weekly_budget: int,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> tuple[BasePlanBlueprint | None, tuple[CandidateEvaluation, ...], int]:
    evaluations: list[CandidateEvaluation] = []
    proposals_by_code: dict[str, ProgramCandidate] = {}
    fallback_batches_used = 0
    batch_size = INITIAL_PROGRAM_BATCH_SIZE
    num_candidates = len(candidates)

    for batch_start in range(0, num_candidates, batch_size):
        if batch_start > 0:
            if fallback_batches_used >= MAX_PROGRAM_FALLBACK_BATCHES:
                break
            fallback_batches_used += 1
        batch = candidates[batch_start : batch_start + batch_size]
        for proposal in batch:
            proposals_by_code[proposal.program.code] = proposal
            try:
                adapted = adapt_program(
                    proposal.program,
                    profile.main_meal_count_bucket,
                    profile.snack_count_bucket,
                )
            except Exception:
                incompatible_result = PlannerResult(
                    outcome=GenerationOutcome.INFEASIBLE,
                    reason_codes=("PROGRAM_STRUCTURE_INCOMPATIBLE",),
                )
                evaluations.append(
                    evaluate_candidate(
                        proposal,
                        incompatible_result,
                        weekly_budget_irr=Decimal(weekly_budget),
                        preference_snapshot=preference_snapshot,
                    )
                )
                continue

            candidate_schedule = _template_schedule(adapted)
            candidate_input = replace(
                base_input,
                optimization_mode=NutritionOptimizationMode.BUDGET_CONSTRAINED,
                template_schedule=candidate_schedule,
                weekly_budget_irr=weekly_budget,
                budget_mode=profile.budget_style.value,
            )
            candidate_result = plan_week(
                candidate_input,
                foods,
                meal_templates,
                policy=DEFAULT_POLICY,
                optimization_cache=optimization_cache,
            )
            evaluations.append(
                evaluate_candidate(
                    proposal,
                    candidate_result,
                    weekly_budget_irr=Decimal(weekly_budget),
                    preference_snapshot=preference_snapshot,
                )
            )

            if candidate_result.outcome is GenerationOutcome.SUCCESS:
                sig_str = (
                    f"{proposal.program.code}:{profile.main_meal_count_bucket.value}:"
                    f"{profile.snack_count_bucket.value}:{str(candidate_schedule)}"
                )
                sig = sha256(sig_str.encode()).hexdigest()
                blueprint = BasePlanBlueprint(
                    program_id=proposal.program.id,
                    program_code=proposal.program.code,
                    blueprint_signature=sig,
                    adapted_week=adapted,
                    template_schedule=candidate_schedule,
                    candidate_proposal=proposal,
                    evaluations=tuple(evaluations),
                    fallback_batches_used=fallback_batches_used,
                    initial_budget_result=candidate_result,
                )
                return blueprint, tuple(evaluations), fallback_batches_used

    # Low-budget fallback: If no candidate succeeded under budget constraints,
    # find a safe candidate blueprint that succeeds in IDEAL_REFERENCE mode.
    # This provides a valid Ideal plan while setting budget_plan = None.
    for evaluation in evaluations:
        fallback_prop = proposals_by_code.get(evaluation.program_code)
        if fallback_prop is None:
            continue
        if "PROGRAM_STRUCTURE_INCOMPATIBLE" in evaluation.result.reason_codes:
            continue
        if "NO_COMPATIBLE_TEMPLATE_SUBSTITUTE" in evaluation.result.reason_codes:
            continue
        try:
            adapted = adapt_program(
                fallback_prop.program,
                profile.main_meal_count_bucket,
                profile.snack_count_bucket,
            )
        except Exception:
            continue
        candidate_schedule = _template_schedule(adapted)
        candidate_input_ideal = replace(
            base_input,
            optimization_mode=NutritionOptimizationMode.IDEAL_REFERENCE,
            template_schedule=candidate_schedule,
            weekly_budget_irr=None,
            budget_mode=None,
        )
        candidate_result_ideal = plan_week(
            candidate_input_ideal,
            foods,
            meal_templates,
            policy=DEFAULT_POLICY,
            optimization_cache=optimization_cache,
        )
        if candidate_result_ideal.outcome is GenerationOutcome.SUCCESS:
            sig_str = (
                f"{fallback_prop.program.code}:{profile.main_meal_count_bucket.value}:"
                f"{profile.snack_count_bucket.value}:{str(candidate_schedule)}"
            )
            sig = sha256(sig_str.encode()).hexdigest()
            blueprint = BasePlanBlueprint(
                program_id=fallback_prop.program.id,
                program_code=fallback_prop.program.code,
                blueprint_signature=sig,
                adapted_week=adapted,
                template_schedule=candidate_schedule,
                candidate_proposal=fallback_prop,
                evaluations=tuple(evaluations),
                fallback_batches_used=fallback_batches_used,
                initial_budget_result=evaluation.result,
            )
            return blueprint, tuple(evaluations), fallback_batches_used

    return None, tuple(evaluations), fallback_batches_used


def _quality_snapshot(quality: CandidateQuality | None) -> dict[str, object] | None:
    if quality is None:
        return None
    return {
        "core_nutrition_max_deviation": str(quality.core_nutrition_max_deviation),
        "core_nutrition_total_deviation": str(quality.core_nutrition_total_deviation),
        "micronutrient_gap_penalty": str(quality.micronutrient_gap_penalty),
        "diet_quality_penalty": str(quality.diet_quality_penalty),
        "sports_nutrition_distribution_penalty": str(quality.sports_nutrition_distribution_penalty),
        "budget_utilization_penalty": str(quality.budget_utilization_penalty),
        "preference_and_feedback_penalty": str(quality.preference_and_feedback_penalty),
        "repetition_penalty": str(quality.repetition_penalty),
        "warning_burden": quality.warning_burden,
        "repair_burden": quality.repair_burden,
        "substitution_burden": quality.substitution_burden,
        "preferred_program_style_penalty": quality.preferred_program_style_penalty,
        "stable_program_code": quality.stable_program_code,
        "stable_variant_key": list(quality.stable_variant_key),
    }


def _selection_trace(selection: CandidateSelection) -> dict[str, object]:
    successful = tuple(
        evaluation
        for evaluation in selection.evaluations
        if evaluation.result.outcome is GenerationOutcome.SUCCESS
    )
    selected = selection.selected
    first_valid = selection.first_valid
    differs = (
        selected is not None
        and first_valid is not None
        and (selected.program_code, selected.stable_variant_key)
        != (first_valid.program_code, first_valid.stable_variant_key)
    )
    return {
        "schema_version": "nutrition-selection-trace-v1",
        "strategy": CANDIDATE_SELECTION_POLICY_VERSION,
        "template_substitution_policy_version": TEMPLATE_SUBSTITUTION_POLICY_VERSION,
        "budget_optimizer_policy_version": BUDGET_OPTIMIZER_POLICY_VERSION,
        "proposed_candidate_count": len(selection.evaluations),
        "active_candidate_count": len(selection.evaluations),
        "evaluated_candidate_count": len(selection.evaluations),
        "successful_candidate_count": len(successful),
        "first_valid_program_code": first_valid.program_code if first_valid else None,
        "selected_program_code": selected.program_code if selected else None,
        "selected_differs_from_first_valid": differs,
        "first_valid_quality": _quality_snapshot(first_valid.quality if first_valid else None),
        "selected_quality": _quality_snapshot(selected.quality if selected else None),
        "selected_quality_not_worse_than_first_valid": (
            selected.quality.sort_key() <= first_valid.quality.sort_key()
            if selected is not None
            and selected.quality is not None
            and first_valid is not None
            and first_valid.quality is not None
            else None
        ),
        "failure_reason_counts": failure_reason_counts(selection.evaluations),
        "candidates": [
            {
                "program_id": str(evaluation.program_id)
                if evaluation.program_id is not None
                else None,
                "program_code": evaluation.program_code,
                "variant_key": "|".join(evaluation.stable_variant_key),
                "preconstruction_rank": evaluation.preconstruction_rank,
                "preferred_style": evaluation.preferred_style,
                "outcome": evaluation.result.outcome.value,
                "reason_codes": list(evaluation.result.reason_codes),
                "substitution_actions": [
                    {
                        "day_index": action.day_index,
                        "role": action.role,
                        "slot_index": action.slot_index,
                        "requested_template_id": action.requested_template_id,
                        "replacement_template_id": action.replacement_template_id,
                        "reason_code": action.reason_code,
                    }
                    for action in evaluation.result.substitution_actions[:32]
                ],
                "substitution_diagnostics": list(evaluation.result.substitution_diagnostics[:32]),
                "budget_repair_actions": [
                    {
                        "day_index": action.day_index,
                        "role": action.role,
                        "slot_index": action.slot_index,
                        "action_type": action.action_type,
                        "before_cost_irr": str(action.before_cost_irr),
                        "after_cost_irr": str(action.after_cost_irr),
                        "saved_irr": str(action.saved_irr),
                        "reason_code": action.reason_code,
                    }
                    for action in evaluation.result.budget_repair_actions[:32]
                ],
                "budget_diagnostics": evaluation.result.budget_diagnostics,
                "quality": _quality_snapshot(evaluation.quality),
            }
            for evaluation in selection.evaluations
        ],
    }


def latest_weekly_plan(db: Session, user_id: UUID) -> WeeklyPlanResponse:
    latest_bundle = db.scalar(
        select(NutritionPlanBundle)
        .where(NutritionPlanBundle.user_id == user_id)
        .order_by(NutritionPlanBundle.created_at.desc())
        .limit(1)
    )
    if latest_bundle is not None and latest_bundle.selected_plan_id is not None:
        selected_plan = db.scalar(
            _plan_query().where(
                NutritionWeeklyPlan.id == latest_bundle.selected_plan_id,
                NutritionWeeklyPlan.user_id == user_id,
            )
        )
        if selected_plan is not None:
            return weekly_plan_response(selected_plan)

    plan = db.scalar(
        _plan_query()
        .join(
            NutritionPlanGeneration, NutritionWeeklyPlan.generation_id == NutritionPlanGeneration.id
        )
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.is_user_visible.is_(True),
            NutritionPlanGeneration.plan_role != NutritionPlanRole.IDEAL_REFERENCE.value,
        )
        .order_by(NutritionWeeklyPlan.revision.desc())
    )
    if plan is None:
        raise WeeklyPlanNotFoundError
    return weekly_plan_response(plan)


def active_weekly_plan(db: Session, user_id: UUID) -> WeeklyPlanResponse:
    latest_bundle = db.scalar(
        select(NutritionPlanBundle)
        .where(NutritionPlanBundle.user_id == user_id)
        .order_by(NutritionPlanBundle.created_at.desc())
        .limit(1)
    )
    selected_plan_id = latest_bundle.selected_plan_id if latest_bundle else None

    due_query = (
        _plan_query()
        .join(
            NutritionPlanGeneration, NutritionWeeklyPlan.generation_id == NutritionPlanGeneration.id
        )
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.PHYSICIAN_APPROVED,
            NutritionWeeklyPlan.start_date <= date.today(),
        )
    )
    if selected_plan_id is not None:
        due_query = due_query.where(
            (NutritionWeeklyPlan.id == selected_plan_id)
            | (NutritionPlanGeneration.plan_role != NutritionPlanRole.IDEAL_REFERENCE.value)
        )
    else:
        due_query = due_query.where(
            NutritionPlanGeneration.plan_role != NutritionPlanRole.IDEAL_REFERENCE.value
        )

    due = db.scalar(
        due_query.order_by(NutritionWeeklyPlan.revision.desc()).limit(1).with_for_update()
    )
    if due is not None and due.review and due.review.status == NutritionPlanReviewStatus.APPROVED:
        for current in db.scalars(
            select(NutritionWeeklyPlan)
            .join(
                NutritionPlanGeneration,
                NutritionWeeklyPlan.generation_id == NutritionPlanGeneration.id,
            )
            .where(
                NutritionWeeklyPlan.user_id == user_id,
                NutritionWeeklyPlan.id != due.id,
                NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
            )
        ):
            current.lifecycle_status = NutritionPlanLifecycleStatus.ARCHIVED
        due.lifecycle_status = NutritionPlanLifecycleStatus.ACTIVE
        db.commit()

    if selected_plan_id is not None:
        plan = db.scalar(
            _plan_query().where(
                NutritionWeeklyPlan.id == selected_plan_id,
                NutritionWeeklyPlan.user_id == user_id,
                NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
            )
        )
        if plan is not None:
            return weekly_plan_response(plan)

    plan = db.scalar(
        _plan_query()
        .join(
            NutritionPlanGeneration, NutritionWeeklyPlan.generation_id == NutritionPlanGeneration.id
        )
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionPlanGeneration.plan_role != NutritionPlanRole.IDEAL_REFERENCE.value,
            NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
        )
        .order_by(NutritionWeeklyPlan.revision.desc())
    )
    if plan is None:
        raise ActiveWeeklyPlanNotFoundError
    return weekly_plan_response(plan)


def select_bundle_plan(
    db: Session,
    *,
    user_id: UUID,
    bundle_id: UUID,
    plan_id: UUID | None = None,
    plan_role: str | None = None,
) -> PlanBundleSelectResponse:
    bundle = db.scalar(
        select(NutritionPlanBundle)
        .where(NutritionPlanBundle.id == bundle_id, NutritionPlanBundle.user_id == user_id)
        .options(selectinload(NutritionPlanBundle.generations))
    )
    if bundle is None:
        raise WeeklyPlanBundleNotFoundError("Plan bundle not found")

    plans_with_role = db.execute(
        select(NutritionWeeklyPlan, NutritionPlanGeneration.plan_role)
        .join(
            NutritionPlanGeneration,
            NutritionWeeklyPlan.generation_id == NutritionPlanGeneration.id,
        )
        .where(
            NutritionPlanGeneration.bundle_id == bundle_id,
            NutritionWeeklyPlan.user_id == user_id,
        )
    ).all()

    target_plan: NutritionWeeklyPlan | None = None
    target_role: str | None = None

    for plan, role in plans_with_role:
        if plan_id is not None and plan.id == plan_id:
            target_plan = plan
            target_role = role
            break
        if plan_role is not None and role == plan_role:
            target_plan = plan
            target_role = role
            break

    if target_plan is None or target_role is None:
        raise PlanSelectionInvalidError("Selected plan does not belong to the specified bundle")

    target_plan.is_user_visible = True
    if target_plan.lifecycle_status == NutritionPlanLifecycleStatus.GENERATED:
        target_plan.lifecycle_status = NutritionPlanLifecycleStatus.PENDING_PHYSICIAN_REVIEW

    now = datetime.now(UTC)
    bundle.selected_plan_id = target_plan.id
    bundle.selected_plan_role = target_role
    bundle.selected_at = now
    db.commit()

    loaded_plan = _load_plan(db, target_plan.id)
    if loaded_plan is None:
        raise WeeklyPlanNotFoundError("Selected weekly plan could not be reloaded")

    return PlanBundleSelectResponse(
        bundle_id=bundle.id,
        selected_plan_id=target_plan.id,
        selected_plan_role=target_role,
        selected_at=now,
        plan=weekly_plan_response(loaded_plan),
    )


def weekly_plan_by_id(db: Session, user_id: UUID, plan_id: UUID) -> WeeklyPlanResponse:
    plan = db.scalar(
        _plan_query().where(
            NutritionWeeklyPlan.id == plan_id,
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.is_user_visible.is_(True),
        )
    )
    if plan is None:
        raise WeeklyPlanNotFoundError
    return weekly_plan_response(plan)


def weekly_plan_history(db: Session, user_id: UUID) -> list[WeeklyPlanHistoryItemResponse]:
    plans = db.scalars(
        select(NutritionWeeklyPlan)
        .join(
            NutritionPlanGeneration, NutritionWeeklyPlan.generation_id == NutritionPlanGeneration.id
        )
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionPlanGeneration.plan_role != NutritionPlanRole.IDEAL_REFERENCE.value,
        )
        .options(selectinload(NutritionWeeklyPlan.review))
        .order_by(NutritionWeeklyPlan.revision.desc())
    ).all()
    return [
        WeeklyPlanHistoryItemResponse(
            id=plan.id,
            revision=plan.revision,
            lifecycle_status=plan.lifecycle_status.value,
            review_status=plan.review.status.value if plan.review else "missing",
            weekly_cost_irr=plan.weekly_cost_irr,
            weekly_budget_irr=plan.weekly_budget_irr,
            budget_status=plan.budget_status.value,
            created_at=plan.created_at,
        )
        for plan in plans
    ]


def _persist_generation(
    db: Session,
    *,
    user_id: UUID,
    safety: NutritionSafetyDecision,
    estimate: NutritionEstimate | None,
    outcome: NutritionPlanGenerationOutcome,
    reasons: tuple[str, ...],
    warnings: tuple[str, ...],
    input_snapshot: dict[str, object],
    diagnostics: dict[str, object],
    commit: bool = True,
    bundle_id: UUID | None = None,
    plan_role: str = NutritionPlanRole.LEGACY.value,
) -> NutritionPlanGeneration:
    signature = sha256(
        json.dumps(input_snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    generation = NutritionPlanGeneration(
        user_id=user_id,
        estimate_id=estimate.id if estimate else None,
        safety_decision_id=safety.id,
        outcome=outcome,
        reason_codes=list(reasons),
        warning_codes=list(warnings),
        input_signature=signature,
        input_snapshot=input_snapshot,
        diagnostic_snapshot=diagnostics,
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
        bundle_id=bundle_id,
        plan_role=plan_role,
    )
    db.add(generation)
    if commit:
        db.commit()
        db.refresh(generation)
    else:
        db.flush()
    return generation


def _safety_snapshot(safety: NutritionSafetyDecision) -> dict[str, object]:
    return {
        "safety_decision_id": str(safety.id),
        "safety_outcome": safety.outcome.value,
        "safety_reason_codes": [reason.code for reason in safety.reasons],
        "medical_condition_policy_version": safety.medical_condition_policy_version,
    }


def _persist_successful_plan(
    db: Session,
    *,
    generation: NutritionPlanGeneration,
    profile: NutritionProfile,
    estimate: NutritionEstimate,
    safety: NutritionSafetyDecision,
    result: PlannerResult,
    input_snapshot: dict[str, object],
    price_snapshot: dict[str, object],
    food_manifest: dict[str, object],
    micro_metadata: dict[str, dict[str, object]],
    program_id: UUID | None,
) -> NutritionWeeklyPlan:
    latest_revision = db.scalar(
        select(NutritionWeeklyPlan.revision)
        .where(NutritionWeeklyPlan.user_id == profile.user_id)
        .order_by(NutritionWeeklyPlan.revision.desc())
        .limit(1)
    )
    start_date = _next_weekday(date.today(), profile.preferred_plan_start_day)
    plan_revision = (latest_revision or 0) + 1
    plan = NutritionWeeklyPlan(
        program_id=program_id,
        user_id=profile.user_id,
        generation_id=generation.id,
        estimate_id=estimate.id,
        safety_decision_id=safety.id,
        revision=plan_revision,
        lifecycle_status=NutritionPlanLifecycleStatus.PENDING_PHYSICIAN_REVIEW,
        is_user_visible=True,
        start_date=start_date,
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
        scientific_policy_version=estimate.policy_version,
        formula_version=estimate.formula_version,
        food_data_manifest=food_manifest,
        input_snapshot=input_snapshot,
        price_snapshot=price_snapshot,
        repair_snapshot=[
            *(
                {
                    "action_type": "portion_adjustment",
                    "day_index": action.day_index,
                    "role": action.role,
                    "slot_index": action.slot_index,
                    "food_id": action.food_id,
                    "before_grams": str(action.before_grams),
                    "after_grams": str(action.after_grams),
                    "reason_code": action.reason_code,
                }
                for action in result.portion_adjustment_actions
            ),
            *(
                {
                    "nutrient_code": action.nutrient_code,
                    "food_slug": action.food_slug,
                    "grams_added": str(action.grams_added),
                    "day_index": action.day_index,
                    "reason_code": action.reason_code,
                }
                for action in result.repair_actions
            ),
            *(
                {
                    "action_type": action.action_type,
                    "role": action.role,
                    "slot_index": action.slot_index,
                    "before_cost_irr": str(action.before_cost_irr),
                    "after_cost_irr": str(action.after_cost_irr),
                    "saved_irr": str(action.saved_irr),
                    "day_index": action.day_index,
                    "reason_code": action.reason_code,
                }
                for action in result.budget_repair_actions
            ),
        ],
        warning_codes=list(result.warning_codes),
        explanation_codes=[
            "DETERMINISTIC_PLAN",
            "PHYSICIAN_REVIEW_REQUIRED",
            *_estimate_goal_contract_codes(estimate)[1],
        ],
        weekly_cost_irr=int(result.weekly_cost_irr),
        weekly_budget_irr=profile.individual_monthly_food_budget_irr * 12 // 52,
        budget_status=NutritionPlanBudgetStatus(result.budget_status),
        days=[
            NutritionWeeklyPlanDay(
                day_index=day.day_index,
                plan_date=start_date + timedelta(days=day.day_index),
                cost_irr=int(day.cost_irr),
                nutrient_totals=_json_nutrient_pairs(day.nutrients),
                meals=[
                    NutritionWeeklyPlanMeal(
                        catalogue_meal_id=(
                            UUID(meal.template_id) if meal.template_id is not None else None
                        ),
                        catalogue_meal_category=meal.template_category,
                        slot_role=meal.role,
                        slot_index=meal.slot_index,
                        target_distribution=_meal_target_distribution(
                            input_snapshot, meal.role, profile
                        ),
                        nutrient_totals=_json_nutrient_pairs(meal.nutrients),
                        cost_irr=int(meal.cost_irr),
                        foods=[
                            NutritionWeeklyPlanFood(
                                food_id=(UUID(food.food_id) if food.food_id is not None else None),
                                item_kind=food.item_kind,
                                food_slug=food.slug,
                                food_name_fa=food.name_fa,
                                food_name_en=food.name_en,
                                grams=food.grams,
                                cost_irr=int(food.cost_irr),
                                nutrient_snapshot=_json_nutrient_pairs(food.nutrients),
                                price_snapshot=(
                                    _food_price_snapshot(price_snapshot, food.food_id)
                                    if food.food_id is not None
                                    else {
                                        "kind": "prepared_recipe",
                                        "price_reference_ids": (food.recipe_snapshot or {}).get(
                                            "price_reference_ids", []
                                        ),
                                    }
                                ),
                                recipe_snapshot=food.recipe_snapshot,
                            )
                            for food in meal.foods
                        ],
                    )
                    for meal in day.meals
                ],
            )
            for day in result.days
        ],
        nutrients=[
            NutritionWeeklyPlanNutrient(
                nutrient_code=code,
                unit=_nutrient_unit(code, micro_metadata),
                reference_kind=_reference_kind(code, micro_metadata),
                preferred_value=comparison.preferred,
                minimum_or_maximum_value=comparison.minimum_or_maximum,
                planned_value=comparison.planned,
                difference_from_preferred=comparison.difference_from_preferred,
                difference_from_limit=comparison.difference_from_limit,
                status=comparison.status,
                reason_codes=list(comparison.reason_codes),
                data_confidence=comparison.data_confidence,
                explanation_codes=(
                    ["DIETARY_REFERENCE_GAP"]
                    if comparison.status
                    in {
                        "below_reference_target",
                        "below_preferred_but_acceptable",
                    }
                    else []
                ),
            )
            for code, comparison in sorted((result.nutrient_comparisons or {}).items())
        ],
        review=NutritionPlanPhysicianReview(
            status=NutritionPlanReviewStatus.PENDING,
            expected_plan_revision=plan_revision,
        ),
    )
    db.add(plan)
    db.flush()
    return plan


def _persist_ideal_plan(
    db: Session,
    *,
    generation: NutritionPlanGeneration,
    profile: NutritionProfile,
    estimate: NutritionEstimate,
    safety: NutritionSafetyDecision,
    result: PlannerResult,
    input_snapshot: dict[str, object],
    price_snapshot: dict[str, object],
    food_manifest: dict[str, object],
    micro_metadata: dict[str, dict[str, object]],
    program_id: UUID | None,
) -> NutritionWeeklyPlan:
    """Persist an ideal reference plan — GENERATED lifecycle, no physician review."""
    latest_revision = db.scalar(
        select(NutritionWeeklyPlan.revision)
        .where(NutritionWeeklyPlan.user_id == profile.user_id)
        .order_by(NutritionWeeklyPlan.revision.desc())
        .limit(1)
    )
    start_date = _next_weekday(date.today(), profile.preferred_plan_start_day)
    plan_revision = (latest_revision or 0) + 1
    plan = NutritionWeeklyPlan(
        program_id=program_id,
        user_id=profile.user_id,
        generation_id=generation.id,
        estimate_id=estimate.id,
        safety_decision_id=safety.id,
        revision=plan_revision,
        lifecycle_status=NutritionPlanLifecycleStatus.GENERATED,
        is_user_visible=True,
        start_date=start_date,
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
        scientific_policy_version=estimate.policy_version,
        formula_version=estimate.formula_version,
        food_data_manifest=food_manifest,
        input_snapshot=input_snapshot,
        price_snapshot=price_snapshot,
        repair_snapshot=[
            *(
                {
                    "action_type": "portion_adjustment",
                    "day_index": action.day_index,
                    "role": action.role,
                    "slot_index": action.slot_index,
                    "food_id": action.food_id,
                    "before_grams": str(action.before_grams),
                    "after_grams": str(action.after_grams),
                    "reason_code": action.reason_code,
                }
                for action in result.portion_adjustment_actions
            ),
            *(
                {
                    "nutrient_code": action.nutrient_code,
                    "food_slug": action.food_slug,
                    "grams_added": str(action.grams_added),
                    "day_index": action.day_index,
                    "reason_code": action.reason_code,
                }
                for action in result.repair_actions
            ),
        ],
        warning_codes=list(result.warning_codes),
        explanation_codes=[
            "DETERMINISTIC_PLAN",
            "IDEAL_REFERENCE_PLAN",
            *_estimate_goal_contract_codes(estimate)[1],
        ],
        weekly_cost_irr=int(result.weekly_cost_irr),
        weekly_budget_irr=profile.individual_monthly_food_budget_irr * 12 // 52,
        budget_status=(
            NutritionPlanBudgetStatus.OVER_BUDGET
            if int(result.weekly_cost_irr) > (profile.individual_monthly_food_budget_irr * 12 // 52)
            else NutritionPlanBudgetStatus.WITHIN_BUDGET
        ),
        days=[
            NutritionWeeklyPlanDay(
                day_index=day.day_index,
                plan_date=start_date + timedelta(days=day.day_index),
                cost_irr=int(day.cost_irr),
                nutrient_totals=_json_nutrient_pairs(day.nutrients),
                meals=[
                    NutritionWeeklyPlanMeal(
                        catalogue_meal_id=(
                            UUID(meal.template_id) if meal.template_id is not None else None
                        ),
                        catalogue_meal_category=meal.template_category,
                        slot_role=meal.role,
                        slot_index=meal.slot_index,
                        target_distribution=_meal_target_distribution(
                            input_snapshot, meal.role, profile
                        ),
                        nutrient_totals=_json_nutrient_pairs(meal.nutrients),
                        cost_irr=int(meal.cost_irr),
                        foods=[
                            NutritionWeeklyPlanFood(
                                food_id=(UUID(food.food_id) if food.food_id is not None else None),
                                item_kind=food.item_kind,
                                food_slug=food.slug,
                                food_name_fa=food.name_fa,
                                food_name_en=food.name_en,
                                grams=food.grams,
                                cost_irr=int(food.cost_irr),
                                nutrient_snapshot=_json_nutrient_pairs(food.nutrients),
                                price_snapshot=(
                                    _food_price_snapshot(price_snapshot, food.food_id)
                                    if food.food_id is not None
                                    else {
                                        "kind": "prepared_recipe",
                                        "price_reference_ids": (food.recipe_snapshot or {}).get(
                                            "price_reference_ids", []
                                        ),
                                    }
                                ),
                                recipe_snapshot=food.recipe_snapshot,
                            )
                            for food in meal.foods
                        ],
                    )
                    for meal in day.meals
                ],
            )
            for day in result.days
        ],
        nutrients=[
            NutritionWeeklyPlanNutrient(
                nutrient_code=code,
                unit=_nutrient_unit(code, micro_metadata),
                reference_kind=_reference_kind(code, micro_metadata),
                preferred_value=comparison.preferred,
                minimum_or_maximum_value=comparison.minimum_or_maximum,
                planned_value=comparison.planned,
                difference_from_preferred=comparison.difference_from_preferred,
                difference_from_limit=comparison.difference_from_limit,
                status=comparison.status,
                reason_codes=list(comparison.reason_codes),
                data_confidence=comparison.data_confidence,
                explanation_codes=(
                    ["DIETARY_REFERENCE_GAP"]
                    if comparison.status
                    in {
                        "below_reference_target",
                        "below_preferred_but_acceptable",
                    }
                    else []
                ),
            )
            for code, comparison in sorted((result.nutrient_comparisons or {}).items())
        ],
        review=None,
    )
    db.add(plan)
    db.flush()
    return plan


def _planner_foods(
    db: Session,
) -> tuple[tuple[PlannerFood, ...], dict[str, object], dict[str, object]]:
    foods = db.scalars(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.compositions),
        )
        .order_by(NutritionCatalogueFood.slug)
    ).all()
    references = effective_prices(
        db,
        [food.id for food in foods],
        maximum_age_hours=DEFAULT_POLICY.maximum_price_age_hours,
    )
    candidates: list[PlannerFood] = []
    snapshots: list[dict[str, object]] = []
    manifest: list[dict[str, object]] = []
    for food in foods:
        reference = references.get(food.id)
        if reference is None:
            continue
        conversion = planner_price_irr_per_gram(
            food_slug=food.slug,
            reference_price_toman=reference.reference_price_toman,
            canonical_unit=reference.canonical_unit,
        )
        candidates.append(
            PlannerFood(
                food_id=str(food.id),
                slug=food.slug,
                name_fa=food.name_fa,
                name_en=food.name_en,
                roles=tuple(sorted(role.role.value for role in food.roles)),
                nutrients_per_100g={
                    composition.nutrient_code: composition.value_per_100g
                    for composition in food.compositions
                },
                price_irr_per_gram=conversion.price_irr_per_gram,
                price_reference_id=reference.reference_id,
                dietary_patterns=tuple(food.dietary_patterns),
                allergen_tags=tuple(food.allergen_tags or []),
                allergen_metadata_verified=bool(food.allergen_metadata_verified),
            )
        )
        snapshots.append(
            {
                "food_id": str(food.id),
                "slug": food.slug,
                "reference_id": reference.reference_id,
                "reference_price_toman": str(reference.reference_price_toman),
                "canonical_unit": reference.canonical_unit,
                "price_irr_per_gram": str(conversion.price_irr_per_gram),
                "sample_count": reference.sample_count,
                "confidence": reference.confidence,
                "accepted_at": reference.accepted_at.isoformat(),
                "source": reference.source,
                "price_mass_conversion_version": conversion.conversion_version,
                "price_mass_conversion_method": conversion.conversion_method,
                "grams_per_price_unit": str(conversion.grams_per_price_unit),
                "price_mass_conversion_source": conversion.source_name,
                "price_mass_conversion_source_reference": conversion.source_reference,
                "freshness_policy_hours": DEFAULT_POLICY.maximum_price_age_hours,
            }
        )
        manifest.append(
            {
                "food_id": str(food.id),
                "slug": food.slug,
                "source_name": food.source_name,
                "source_reference": food.source_reference,
                "source_food_id": food.source_food_id,
            }
        )
    return (
        tuple(candidates),
        {"currency": "IRR", "references": snapshots},
        {"foods": manifest},
    )


def _planner_meal_templates(
    db: Session,
) -> tuple[tuple[PlannerMealTemplate, ...], list[dict[str, object]]]:
    meals = db.scalars(
        select(NutritionCatalogueMeal)
        .where(
            or_(
                NutritionCatalogueMeal.verification_status == FoodVerificationStatus.VERIFIED,
                NutritionCatalogueMeal.calculation_mode == MealCalculationMode.PREPARED_RECIPE,
            )
        )
        .options(
            selectinload(NutritionCatalogueMeal.items),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.ingredients),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.ratios),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.data_gaps),
        )
        .order_by(NutritionCatalogueMeal.category, NutritionCatalogueMeal.id)
    ).all()
    templates = tuple(
        PlannerMealTemplate(
            meal_id=str(meal.id),
            name_fa=meal.name_fa,
            name_en=meal.name_en,
            category=meal.category.value,
            items=tuple(
                PlannerMealIngredient(
                    food_id=str(item.food_id),
                    reference_grams=item.reference_grams,
                    min_grams=item.min_grams,
                    max_grams=item.max_grams,
                    is_required=item.is_required,
                    functional_role=(
                        item.functional_role.value if item.functional_role is not None else None
                    ),
                )
                for item in meal.items
            ),
            prepared_recipe=_planner_prepared_recipe(meal),
            verification_status=meal.verification_status.value,
        )
        for meal in meals
    )
    return templates, [
        {
            "meal_id": template.meal_id,
            "category": template.category,
            "ingredient_bounds": [
                {
                    "food_id": item.food_id,
                    "reference_grams": str(item.reference_grams),
                    "min_grams": str(item.min_grams),
                    "max_grams": str(item.max_grams),
                    "is_required": item.is_required,
                    "functional_role": item.functional_role,
                }
                for item in template.items
            ],
            "prepared_recipe": (
                {
                    "revision_id": template.prepared_recipe.revision_id,
                    "verification_status": template.prepared_recipe.verification_status,
                    "provenance": template.prepared_recipe.provenance,
                    "data_gaps": list(template.prepared_recipe.data_gaps),
                    "calculation_version": (
                        template.prepared_recipe.definition.calculation_version
                    ),
                    "ingredient_bounds": [
                        {
                            "food_id": str(item.food_id),
                            "reference_grams": str(item.reference_grams),
                            "min_grams": str(item.min_grams),
                            "max_grams": str(item.max_grams),
                            "is_required": item.is_required,
                        }
                        for item in template.prepared_recipe.definition.ingredients
                    ],
                    "ratio_constraints": [
                        {
                            "numerator_food_id": str(item.numerator_food_id),
                            "denominator_food_id": str(item.denominator_food_id),
                            "min_ratio": str(item.min_ratio),
                            "max_ratio": str(item.max_ratio),
                        }
                        for item in template.prepared_recipe.definition.ratios
                    ],
                    "yield": {
                        "method": template.prepared_recipe.definition.cooked_yield.method,
                        "reference_input_grams": str(
                            template.prepared_recipe.definition.cooked_yield.reference_input_grams
                        ),
                        "final_cooked_yield_grams": str(
                            template.prepared_recipe.definition.cooked_yield.final_cooked_yield_grams
                        ),
                    },
                }
                if template.prepared_recipe is not None
                else None
            ),
        }
        for template in templates
    ]


def _planner_prepared_recipe(meal: NutritionCatalogueMeal) -> PlannerPreparedRecipe | None:
    if meal.calculation_mode is not MealCalculationMode.PREPARED_RECIPE:
        return None
    if meal.prepared_recipe is None or not meal.prepared_recipe.revisions:
        return None
    revision = meal.prepared_recipe.revisions[-1]
    if revision.verification_status is FoodVerificationStatus.RETIRED:
        return None
    return PlannerPreparedRecipe(
        revision_id=str(revision.id),
        name_fa=meal.name_fa.split(" + ", 1)[0],
        name_en=meal.name_en.split(" with ", 1)[0],
        verification_status=revision.verification_status.value,
        provenance={
            "source_name": revision.source_name,
            "source_reference": revision.source_reference,
            "notes": revision.notes,
            "yield_source_name": revision.yield_source_name,
            "yield_source_reference": revision.yield_source_reference,
            "yield_notes": revision.yield_notes,
        },
        data_gaps=tuple(
            {
                "ingredient_name_fa": gap.ingredient_name_fa,
                "ingredient_name_en": gap.ingredient_name_en,
                "message_fa": gap.message_fa,
                "message_en": gap.message_en,
            }
            for gap in revision.data_gaps
        ),
        definition=PreparedRecipeDefinition(
            calculation_version=revision.calculation_version,
            ingredients=tuple(
                PreparedRecipeIngredient(
                    food_id=str(item.food_id),
                    reference_grams=item.reference_grams,
                    min_grams=item.min_grams,
                    max_grams=item.max_grams,
                    is_required=item.is_required,
                )
                for item in revision.ingredients
            ),
            ratios=tuple(
                PreparedRecipeRatio(
                    numerator_food_id=str(item.numerator_food_id),
                    denominator_food_id=str(item.denominator_food_id),
                    min_ratio=item.min_ratio,
                    max_ratio=item.max_ratio,
                )
                for item in revision.ratios
            ),
            cooked_yield=PreparedRecipeYield(
                method=revision.yield_method,
                reference_input_grams=revision.reference_input_grams,
                final_cooked_yield_grams=revision.final_cooked_yield_grams,
            ),
        ),
    )


def _daily_targets(rows: list[NutritionEstimateTarget]) -> dict[str, Decimal]:
    by_metric = {row.metric: row for row in rows}

    def selected(metric: NutritionTargetMetric) -> Decimal:
        row = by_metric[metric]
        if row.preferred_value is not None:
            return row.preferred_value
        if row.minimum_value is not None and row.preferred_maximum_value is not None:
            return (row.minimum_value + row.preferred_maximum_value) / Decimal("2")
        if row.minimum_value is not None and row.maximum_value is not None:
            return (row.minimum_value + row.maximum_value) / Decimal("2")
        if row.minimum_value is not None:
            return row.minimum_value
        raise ValueError(f"No usable target for {metric.value}")

    return {
        "goal_calories": selected(NutritionTargetMetric.GOAL_CALORIES),
        "protein": selected(NutritionTargetMetric.PROTEIN),
        "carbohydrate": selected(NutritionTargetMetric.CARBOHYDRATE),
        "total_fat": selected(NutritionTargetMetric.TOTAL_FAT),
        "fibre": selected(NutritionTargetMetric.FIBRE),
    }


def _daily_limits(
    rows: list[NutritionEstimateTarget],
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    minimums: dict[str, Decimal] = {}
    maximums: dict[str, Decimal] = {}
    metric_names = {
        NutritionTargetMetric.PROTEIN: "protein",
        NutritionTargetMetric.CARBOHYDRATE: "carbohydrate",
        NutritionTargetMetric.TOTAL_FAT: "total_fat",
        NutritionTargetMetric.FIBRE: "fibre",
        NutritionTargetMetric.FREE_SUGAR: "free_sugar",
        NutritionTargetMetric.ADDED_SUGAR: "added_sugar",
        NutritionTargetMetric.SATURATED_FAT: "saturated_fat",
        NutritionTargetMetric.TRANS_FAT: "trans_fat",
        NutritionTargetMetric.SODIUM: "sodium",
    }
    for row in rows:
        name = metric_names.get(row.metric)
        if name is None:
            continue
        if row.minimum_value is not None:
            minimums[name] = row.minimum_value
        maximum = (
            row.maximum_value if row.maximum_value is not None else row.preferred_maximum_value
        )
        if maximum is not None:
            maximums[name] = maximum
    return minimums, maximums


def _micronutrient_targets(
    rows: list[NutritionEstimateMicronutrientTarget],
) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, dict[str, object]]]:
    targets: dict[str, Decimal] = {}
    upper_limits: dict[str, Decimal] = {}
    metadata: dict[str, dict[str, object]] = {}
    for row in rows:
        food_code = _composition_code(row.nutrient_code, row.unit)
        targets[food_code] = row.target_value
        if row.upper_limit_value is not None and row.upper_limit_scope == "total_intake":
            upper_limits[food_code] = row.upper_limit_value
        metadata[food_code] = {
            "nutrient_code": row.nutrient_code,
            "unit": row.unit,
            "reference_kind": row.reference_kind,
            "policy_version": row.policy_version,
            "upper_limit_scope": row.upper_limit_scope,
            "aggregation_window": row.aggregation_window,
        }
    return targets, upper_limits, metadata


def _composition_code(code: str, unit: str) -> str:
    suffix = unit.casefold().replace("µ", "u").replace("μ", "u")
    return code if code.endswith(f"_{suffix}") else f"{code}_{suffix}"


def _estimate_by_id(db: Session, estimate_id: UUID) -> NutritionEstimate:
    estimate = db.scalar(
        select(NutritionEstimate)
        .where(NutritionEstimate.id == estimate_id)
        .options(
            selectinload(NutritionEstimate.targets),
            selectinload(NutritionEstimate.micronutrient_targets),
        )
    )
    if estimate is None:
        raise ValueError("Estimate disappeared after creation")
    return estimate


def _plan_query() -> Select[tuple[NutritionWeeklyPlan]]:
    return select(NutritionWeeklyPlan).options(
        selectinload(NutritionWeeklyPlan.review),
        selectinload(NutritionWeeklyPlan.nutrients),
        selectinload(NutritionWeeklyPlan.days)
        .selectinload(NutritionWeeklyPlanDay.meals)
        .selectinload(NutritionWeeklyPlanMeal.foods),
        selectinload(NutritionWeeklyPlan.days)
        .selectinload(NutritionWeeklyPlanDay.meals)
        .selectinload(NutritionWeeklyPlanMeal.catalogue_meal),
    )


def _load_plan(db: Session, plan_id: UUID) -> NutritionWeeklyPlan:
    plan = db.scalar(_plan_query().where(NutritionWeeklyPlan.id == plan_id))
    if plan is None:
        raise WeeklyPlanNotFoundError
    return plan


def weekly_plan_response(plan: NutritionWeeklyPlan) -> WeeklyPlanResponse:
    review_status = plan.review.status.value if plan.review else "missing"
    return WeeklyPlanResponse(
        id=plan.id,
        revision=plan.revision,
        lifecycle_status=plan.lifecycle_status.value,
        is_user_visible=plan.is_user_visible,
        physician_approved=(
            plan.lifecycle_status
            in {
                NutritionPlanLifecycleStatus.PHYSICIAN_APPROVED,
                NutritionPlanLifecycleStatus.ACTIVE,
            }
            and review_status == NutritionPlanReviewStatus.APPROVED.value
        ),
        review_status=review_status,
        physician_approved_at=(
            plan.review.reviewed_at
            if plan.review and plan.review.status == NutritionPlanReviewStatus.APPROVED
            else None
        ),
        physician_display_name=(
            "Fitsho physician"
            if plan.review and plan.review.status == NutritionPlanReviewStatus.APPROVED
            else None
        ),
        physician_user_visible_notes=plan.review.user_visible_notes if plan.review else None,
        physician_change_summary=(plan.review.structured_change_summary if plan.review else []),
        supersedes_plan_id=plan.supersedes_plan_id,
        start_date=plan.start_date,
        planner_policy_version=plan.planner_policy_version,
        planner_version=plan.planner_version,
        scientific_policy_version=plan.scientific_policy_version,
        formula_version=plan.formula_version,
        weekly_cost_irr=plan.weekly_cost_irr,
        weekly_budget_irr=plan.weekly_budget_irr,
        budget_status=plan.budget_status.value,
        warning_codes=plan.warning_codes,
        explanation_codes=plan.explanation_codes,
        input_snapshot=plan.input_snapshot,
        price_snapshot=plan.price_snapshot,
        food_data_manifest=plan.food_data_manifest,
        repair_actions=plan.repair_snapshot,
        nutrients={
            nutrient.nutrient_code: WeeklyPlanNutrientResponse(
                nutrient_code=nutrient.nutrient_code,
                unit=nutrient.unit,
                reference_kind=nutrient.reference_kind,
                preferred=_float(nutrient.preferred_value),
                minimum_or_maximum=_float(nutrient.minimum_or_maximum_value),
                planned=float(nutrient.planned_value),
                difference_from_preferred=_float(nutrient.difference_from_preferred),
                difference_from_limit=_float(nutrient.difference_from_limit),
                status=nutrient.status,
                reason_codes=nutrient.reason_codes,
                data_confidence=nutrient.data_confidence,
                explanation_codes=nutrient.explanation_codes,
            )
            for nutrient in plan.nutrients
        },
        days=[
            WeeklyPlanDayResponse(
                day_index=day.day_index,
                plan_date=day.plan_date,
                nutrient_totals=_float_map(day.nutrient_totals),
                cost_irr=day.cost_irr,
                meals=[
                    WeeklyPlanMealResponse(
                        id=meal.id,
                        catalogue_meal_id=meal.catalogue_meal_id,
                        catalogue_meal_category=meal.catalogue_meal_category,
                        name_fa=(meal.catalogue_meal.name_fa if meal.catalogue_meal else None),
                        name_en=(meal.catalogue_meal.name_en if meal.catalogue_meal else None),
                        meal_code=(meal.catalogue_meal.code if meal.catalogue_meal else None),
                        image_url=(meal.catalogue_meal.image_path if meal.catalogue_meal else None),
                        slot_role=meal.slot_role.value,
                        slot_index=meal.slot_index,
                        target_distribution=_float_map(meal.target_distribution),
                        nutrient_totals=_float_map(meal.nutrient_totals),
                        cost_irr=meal.cost_irr,
                        is_locked=meal.is_locked,
                        foods=[
                            WeeklyPlanFoodResponse(
                                food_id=food.food_id,
                                item_kind=food.item_kind,
                                slug=food.food_slug,
                                name_fa=food.food_name_fa,
                                name_en=food.food_name_en,
                                grams=float(food.grams),
                                cost_irr=food.cost_irr,
                                nutrients=_float_map(food.nutrient_snapshot),
                                prepared_recipe=_public_prepared_recipe_summary(
                                    food.recipe_snapshot
                                ),
                            )
                            for food in meal.foods
                        ],
                    )
                    for meal in day.meals
                ],
            )
            for day in plan.days
        ],
        created_at=plan.created_at,
    )


def _public_prepared_recipe_summary(
    snapshot: dict[str, object] | None,
) -> WeeklyPlanPreparedRecipeSummary | None:
    if snapshot is None:
        return None
    raw_nutrients = snapshot.get("nutrients_per_100g")
    raw_cost = snapshot.get("cost_irr_per_100g")
    if not isinstance(raw_nutrients, dict) or not isinstance(raw_cost, (int, float, str)):
        return None
    public_codes = {
        "energy_kcal",
        "protein_g",
        "carbohydrate_g",
        "total_fat_g",
        "fibre_g",
    }
    nutrients = {
        str(code): float(value)
        for code, value in raw_nutrients.items()
        if code in public_codes and isinstance(value, (int, float, str))
    }
    status = "verified" if snapshot.get("verification_status") == "verified" else "estimated"
    return WeeklyPlanPreparedRecipeSummary(
        status=status,
        nutrients_per_100g=nutrients,
        cost_irr_per_100g=float(raw_cost),
    )


def _generation_response(
    generation: NutritionPlanGeneration,
    plan: NutritionWeeklyPlan | None,
    *,
    budget_plan: NutritionWeeklyPlan | None = None,
    ideal_plan: NutritionWeeklyPlan | None = None,
    comparison: PlanComparisonResponse | None = None,
) -> WeeklyPlanGenerationResponse:
    plan_resp = weekly_plan_response(plan) if plan else None
    budget_resp = weekly_plan_response(budget_plan) if budget_plan else plan_resp
    ideal_resp = weekly_plan_response(ideal_plan) if ideal_plan else None
    return WeeklyPlanGenerationResponse(
        generation_id=generation.id,
        outcome=generation.outcome.value,
        reason_codes=generation.reason_codes,
        warning_codes=generation.warning_codes,
        plan=plan_resp,
        budget_plan=budget_resp,
        ideal_plan=ideal_resp,
        comparison=comparison,
    )


def _meal_target_distribution(
    snapshot: dict[str, object], role: str, profile: NutritionProfile
) -> dict[str, str]:
    raw_targets = snapshot["daily_targets"]
    if not isinstance(raw_targets, dict):
        return {}
    if role == "snack" and profile.effective_snack_slots:
        share = Decimal("0.15") / Decimal(profile.effective_snack_slots)
    else:
        share = (Decimal("0.85") if profile.effective_snack_slots else Decimal("1")) / Decimal(
            profile.effective_main_meal_slots
        )
    return {str(code): str(Decimal(str(value)) * share) for code, value in raw_targets.items()}


def _food_price_snapshot(snapshot: dict[str, object], food_id: str) -> dict[str, object]:
    references = snapshot.get("references", [])
    if isinstance(references, list):
        for reference in references:
            if isinstance(reference, dict) and reference.get("food_id") == food_id:
                return dict(reference)
    return {"food_id": food_id, "status": "unavailable"}


def _next_weekday(today: date, preferred: Weekday) -> date:
    delta = (_WEEKDAY_INDEX[preferred] - today.weekday()) % 7
    return today + timedelta(days=delta)


def _json_decimal_map(values: dict[str, Decimal]) -> dict[str, str]:
    return {key: str(value) for key, value in sorted(values.items())}


def _json_nutrient_pairs(values: tuple[tuple[str, Decimal], ...]) -> dict[str, str]:
    return {key: str(value) for key, value in values}


def _float_map(values: dict[str, object]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in values.items():
        if not isinstance(value, (str, int, float, Decimal)):
            raise TypeError(f"Nutrient value for {key} is not numeric")
        result[key] = float(value)
    return result


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _nutrient_unit(code: str, metadata: dict[str, dict[str, object]]) -> str:
    if code in metadata:
        return str(metadata[code]["unit"])
    return _TARGET_UNITS.get(code, "unknown")


def _reference_kind(code: str, metadata: dict[str, dict[str, object]]) -> str | None:
    return str(metadata[code]["reference_kind"]) if code in metadata else None
