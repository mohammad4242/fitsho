from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import (
    CookingSkill,
    FoodItemKind,
    MealPreparationPreference,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    PhysicianReviewMode,
    PhysicianReviewStatus,
    PreferredVariety,
    SafetyOutcome,
    main_meal_effective_slots,
    snack_effective_slots,
)
from app.nutrition.exceptions import (
    NutritionOnboardingBlockedError,
    NutritionProfileNotFoundError,
    SafetyDecisionNotFoundError,
    SafetyScreenRequiredError,
    SharedProfileRequiredError,
)
from app.nutrition.food_catalogue import normalize_food_alias
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCookingEquipment,
    NutritionFoodItem,
    NutritionMedicalCondition,
    NutritionMedicalProfile,
    NutritionMedication,
    NutritionPhysicianReview,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionSafetyReason,
)
from app.nutrition.safety import SafetyAnswers, evaluate_safety
from app.nutrition.schemas import (
    FoodConstraintInput,
    NutritionProfileInput,
    NutritionProfileResponse,
    PhysicianReviewRequirementResponse,
    SafetyDecisionResponse,
    SafetyEvaluationResponse,
    SafetyProfileInput,
)
from app.profile.enums import ProductMode
from app.profile.models import UserProfile


@dataclass(frozen=True)
class NutritionSnapshot:
    profile: NutritionProfile
    equipment: tuple[NutritionCookingEquipment, ...]
    foods: tuple[NutritionFoodItem, ...]
    safety: NutritionSafetyDecision


_SAFETY_MESSAGES = {
    SafetyOutcome.STANDARD_AUTOMATIC: "عالی، می‌توانیم اطلاعات تغذیه‌ات را کامل کنیم.",
    SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW: (
        "برنامه اولیه آماده می‌شود اما برای فعال‌شدن به بررسی پزشک فیتشو نیاز دارد."
    ),
    SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED: (
        "برای حفظ ایمنی، برنامه غذایی باید توسط پزشک فیتشو تنظیم شود."
    ),
    SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED: (
        "در حال حاضر امکان ارائه برنامه خودکار ایمن برای این شرایط وجود ندارد."
    ),
}


def evaluate_safety_profile(payload: SafetyProfileInput) -> SafetyEvaluationResponse:
    evaluation = evaluate_safety(_safety_answers(payload))
    can_continue = evaluation.outcome in {
        SafetyOutcome.STANDARD_AUTOMATIC,
        SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW,
    }
    return SafetyEvaluationResponse(
        outcome=evaluation.outcome,
        policy_version=evaluation.policy_version,
        reason_codes=list(evaluation.reason_codes),
        requires_physician_review=evaluation.outcome is not SafetyOutcome.STANDARD_AUTOMATIC,
        can_continue_onboarding=can_continue,
        message=_SAFETY_MESSAGES[evaluation.outcome],
    )


def _safety_answers(payload: SafetyProfileInput) -> SafetyAnswers:
    return SafetyAnswers(
        conditions=tuple(item.code for item in payload.conditions),
        dangerous_food_reaction_history=payload.dangerous_food_reaction_history,
        pregnant=payload.pregnant,
        breastfeeding=payload.breastfeeding,
        eating_disorder_diagnosed=payload.eating_disorder_diagnosed,
        eating_disorder_active_symptoms=payload.eating_disorder_active_symptoms,
        emergency_or_danger_symptoms=payload.emergency_or_danger_symptoms,
        physician_dietary_restrictions=payload.physician_dietary_restrictions is not None,
        other_relevant_condition=payload.other_relevant_condition is not None,
        complex_medication_food_interaction=payload.complex_medication_food_interaction,
    )


def _require_shared_profile(db: Session, user_id: UUID, *, lock: bool = False) -> UserProfile:
    statement = select(UserProfile).where(UserProfile.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    profile = db.scalar(statement)
    if (
        profile is None
        or profile.product_mode not in {ProductMode.NUTRITION, ProductMode.BOTH}
        or profile.display_name is None
        or profile.birth_date is None
        or profile.sex is None
        or profile.height_cm is None
        or profile.fitness_goal is None
    ):
        raise SharedProfileRequiredError
    return profile


def save_safety_profile(
    db: Session,
    user_id: UUID,
    payload: SafetyProfileInput,
) -> NutritionSafetyDecision:
    _require_shared_profile(db, user_id, lock=True)
    medical = db.scalar(
        select(NutritionMedicalProfile)
        .where(NutritionMedicalProfile.user_id == user_id)
        .with_for_update()
    )
    values = {
        "dangerous_food_reaction_history": payload.dangerous_food_reaction_history,
        "pregnant": payload.pregnant,
        "breastfeeding": payload.breastfeeding,
        "eating_disorder_diagnosed": payload.eating_disorder_diagnosed,
        "eating_disorder_active_symptoms": payload.eating_disorder_active_symptoms,
        "emergency_or_danger_symptoms": payload.emergency_or_danger_symptoms,
        "complex_medication_food_interaction": payload.complex_medication_food_interaction,
        "physician_dietary_restrictions": payload.physician_dietary_restrictions,
        "other_relevant_condition": payload.other_relevant_condition,
    }
    if medical is None:
        medical = NutritionMedicalProfile(user_id=user_id, **values)
        db.add(medical)
    else:
        for field_name, value in values.items():
            setattr(medical, field_name, value)

    evaluation = evaluate_safety(_safety_answers(payload))
    try:
        db.flush()
        db.execute(
            delete(NutritionMedicalCondition).where(NutritionMedicalCondition.user_id == user_id)
        )
        db.execute(delete(NutritionMedication).where(NutritionMedication.user_id == user_id))
        db.add_all(
            [
                NutritionMedicalCondition(
                    user_id=user_id,
                    code=item.code,
                    details=item.details,
                )
                for item in payload.conditions
            ]
        )
        db.add_all(
            [
                NutritionMedication(
                    user_id=user_id,
                    name=item.name,
                    dosage=item.dosage,
                    notes=item.notes,
                )
                for item in payload.medications
            ]
        )
        latest_revision = db.scalar(
            select(NutritionSafetyDecision.revision)
            .where(NutritionSafetyDecision.user_id == user_id)
            .order_by(NutritionSafetyDecision.revision.desc())
            .limit(1)
        )
        decision = NutritionSafetyDecision(
            user_id=user_id,
            medical_condition_policy_version=evaluation.policy_version,
            revision=(latest_revision or 0) + 1,
            outcome=evaluation.outcome,
            reasons=[NutritionSafetyReason(code=code) for code in evaluation.reason_codes],
        )
        db.add(decision)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return current_safety_decision(db, user_id)


def current_safety_decision(db: Session, user_id: UUID) -> NutritionSafetyDecision:
    decision = db.scalar(
        select(NutritionSafetyDecision)
        .where(NutritionSafetyDecision.user_id == user_id)
        .options(selectinload(NutritionSafetyDecision.reasons))
        .order_by(NutritionSafetyDecision.revision.desc())
        .limit(1)
    )
    if decision is None:
        raise SafetyDecisionNotFoundError
    return decision


def safety_response(decision: NutritionSafetyDecision) -> SafetyDecisionResponse:
    can_continue = decision.outcome in {
        SafetyOutcome.STANDARD_AUTOMATIC,
        SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW,
    }
    return SafetyDecisionResponse(
        id=decision.id,
        outcome=decision.outcome,
        policy_version=decision.medical_condition_policy_version,
        reason_codes=[item.code for item in decision.reasons],
        requires_physician_review=decision.outcome is not SafetyOutcome.STANDARD_AUTOMATIC,
        can_continue_onboarding=can_continue,
        message=_SAFETY_MESSAGES[decision.outcome],
        created_at=decision.created_at,
    )


def physician_review_requirement(
    db: Session,
    user_id: UUID,
) -> PhysicianReviewRequirementResponse:
    decision = current_safety_decision(db, user_id)
    modes = {
        SafetyOutcome.STANDARD_AUTOMATIC: PhysicianReviewMode.NONE,
        SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW: (
            PhysicianReviewMode.AUTOMATIC_DRAFT_REVIEW
        ),
        SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED: PhysicianReviewMode.MANUAL_PLAN,
        SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED: PhysicianReviewMode.BLOCKED,
    }
    review = db.scalar(
        select(NutritionPhysicianReview)
        .where(
            NutritionPhysicianReview.user_id == user_id,
            NutritionPhysicianReview.safety_decision_id == decision.id,
        )
        .order_by(NutritionPhysicianReview.created_at.desc())
        .limit(1)
    )
    return PhysicianReviewRequirementResponse(
        required=decision.outcome is not SafetyOutcome.STANDARD_AUTOMATIC,
        mode=modes[decision.outcome],
        status=review.status if review is not None else PhysicianReviewStatus.NOT_REQUESTED,
        safety_decision_id=decision.id,
    )


def save_nutrition_profile(
    db: Session,
    user_id: UUID,
    payload: NutritionProfileInput,
) -> NutritionSnapshot:
    _require_shared_profile(db, user_id)
    try:
        decision = current_safety_decision(db, user_id)
    except SafetyDecisionNotFoundError as error:
        raise SafetyScreenRequiredError from error
    if decision.outcome in {
        SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
        SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED,
    }:
        raise NutritionOnboardingBlockedError

    profile = db.get(NutritionProfile, user_id)
    scalar_values = payload.model_dump(
        exclude={
            "cooking_equipment",
            "plan_style",
            "cooking_skill",
            "maximum_cooking_time_minutes",
            "cooking_frequency_per_week",
            "meal_preparation_preference",
            "refrigerator_access",
            "freezer_access",
            "supplied_meals_per_week",
            "supplied_meal_source",
            "foods_available_at_home",
            "favourite_foods",
            "disliked_foods",
            "never_suggest_foods",
            "refused_foods",
            "allergies",
            "intolerances",
            "religious_cultural_exclusions",
            "preferred_variety",
            "maximum_meal_repetition_per_week",
            "accepts_leftovers",
            "accepts_batch_cooking",
        }
    )
    scalar_values["meals_per_day"] = payload.meals_per_day
    scalar_values["snacks_per_day"] = payload.snacks_per_day
    scalar_values["main_meal_count_bucket"] = payload.main_meal_count_bucket
    scalar_values["snack_count_bucket"] = payload.snack_count_bucket
    assert payload.main_meal_count_bucket is not None
    assert payload.snack_count_bucket is not None
    scalar_values["effective_main_meal_slots"] = main_meal_effective_slots(
        payload.main_meal_count_bucket
    )
    scalar_values["effective_snack_slots"] = snack_effective_slots(payload.snack_count_bucket)
    if profile is None:
        # These columns predate Task 2A. Keep safe defaults for old non-null columns,
        # but never expose or ask them as Nutrition inputs.
        scalar_values.update(
            plan_style=NutritionPlanStyle.BALANCED,
            cooking_skill=CookingSkill.NONE,
            maximum_cooking_time_minutes=0,
            cooking_frequency_per_week=0,
            meal_preparation_preference=MealPreparationPreference.NO_COOKING,
            refrigerator_access=True,
            freezer_access=True,
            supplied_meals_per_week=0,
            supplied_meal_source=None,
            preferred_variety=PreferredVariety.MEDIUM,
            maximum_meal_repetition_per_week=3,
            accepts_leftovers=True,
            accepts_batch_cooking=False,
        )
    scalar_values["onboarding_status"] = NutritionOnboardingStatus.COMPLETED
    if profile is None:
        profile = NutritionProfile(user_id=user_id, **scalar_values)
        db.add(profile)
    else:
        for field_name, value in scalar_values.items():
            setattr(profile, field_name, value)

    try:
        db.flush()
        # Cooking/preparation data is legacy-only and is deliberately not rewritten.
        db.execute(delete(NutritionFoodItem).where(NutritionFoodItem.user_id == user_id))
        db.add_all(_food_items(db, user_id, payload))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return get_nutrition_profile(db, user_id)


def _food_items(
    db: Session,
    user_id: UUID,
    payload: NutritionProfileInput,
) -> list[NutritionFoodItem]:
    items: list[NutritionFoodItem] = []
    canonical_foods = db.scalars(
        select(NutritionCatalogueFood).options(selectinload(NutritionCatalogueFood.aliases))
    ).all()
    candidates: dict[str, set[UUID]] = {}
    for food in canonical_foods:
        catalogue_names = (
            food.name_fa,
            food.name_en,
            food.slug,
            *(alias.alias for alias in food.aliases),
        )
        for value in catalogue_names:
            candidates.setdefault(normalize_food_alias(value), set()).add(food.id)
    resolved_food_ids = {
        key: next(iter(food_ids))
        for key, food_ids in candidates.items()
        if len(food_ids) == 1
    }
    string_collections = {
        FoodItemKind.FAVOURITE: payload.favourite_foods,
        FoodItemKind.DISLIKED: payload.disliked_foods,
        FoodItemKind.RELIGIOUS_CULTURAL_EXCLUSION: payload.religious_cultural_exclusions,
    }
    for kind, names in string_collections.items():
        items.extend(_named_items(user_id, kind, names, resolved_food_ids))
    items.extend(_constraint_items(user_id, FoodItemKind.ALLERGY, payload.allergies))
    items.extend(_constraint_items(user_id, FoodItemKind.INTOLERANCE, payload.intolerances))
    return items


def _named_items(
    user_id: UUID,
    kind: FoodItemKind,
    names: list[str],
    resolved_food_ids: dict[str, UUID],
) -> list[NutritionFoodItem]:
    return [
        NutritionFoodItem(
            user_id=user_id,
            kind=kind,
            name=name,
            normalized_name=normalize_food_alias(name),
            catalogue_food_id=(
                resolved_food_ids.get(normalize_food_alias(name))
                if kind in {FoodItemKind.FAVOURITE, FoodItemKind.DISLIKED}
                else None
            ),
        )
        for name in names
    ]


def _constraint_items(
    user_id: UUID,
    kind: FoodItemKind,
    values: list[FoodConstraintInput],
) -> list[NutritionFoodItem]:
    return [
        NutritionFoodItem(
            user_id=user_id,
            kind=kind,
            name=item.name,
            normalized_name=item.name.casefold(),
            details=item.details,
        )
        for item in values
    ]


def get_nutrition_profile(db: Session, user_id: UUID) -> NutritionSnapshot:
    profile = db.get(NutritionProfile, user_id)
    if profile is None:
        raise NutritionProfileNotFoundError
    equipment = tuple(
        db.scalars(
            select(NutritionCookingEquipment)
            .where(NutritionCookingEquipment.user_id == user_id)
            .order_by(NutritionCookingEquipment.equipment)
        ).all()
    )
    foods = tuple(
        db.scalars(
            select(NutritionFoodItem)
            .where(NutritionFoodItem.user_id == user_id)
            .order_by(NutritionFoodItem.kind, NutritionFoodItem.normalized_name)
        ).all()
    )
    return NutritionSnapshot(
        profile=profile,
        equipment=equipment,
        foods=foods,
        safety=current_safety_decision(db, user_id),
    )


def nutrition_profile_response(snapshot: NutritionSnapshot) -> NutritionProfileResponse:
    grouped: dict[FoodItemKind, list[NutritionFoodItem]] = {kind: [] for kind in FoodItemKind}
    for item in snapshot.foods:
        grouped[item.kind].append(item)

    def names(kind: FoodItemKind) -> list[str]:
        return [item.name for item in grouped[kind]]

    def constraints(kind: FoodItemKind) -> list[FoodConstraintInput]:
        return [FoodConstraintInput(name=item.name, details=item.details) for item in grouped[kind]]

    profile = snapshot.profile
    return NutritionProfileResponse(
        user_id=profile.user_id,
        onboarding_status=profile.onboarding_status,
        daily_activity_level=profile.daily_activity_level,
        metabolic_basis=profile.metabolic_basis,
        individual_monthly_food_budget_irr=profile.individual_monthly_food_budget_irr,
        currency="IRR",
        weekly_budget_irr=profile.individual_monthly_food_budget_irr * 12 // 52,
        budget_style=profile.budget_style,
        meals_per_day=profile.meals_per_day,
        snacks_per_day=profile.snacks_per_day,
        main_meal_count_bucket=profile.main_meal_count_bucket,
        snack_count_bucket=profile.snack_count_bucket,
        preferred_plan_start_day=profile.preferred_plan_start_day,
        plan_style=profile.plan_style,
        cooking_skill=profile.cooking_skill,
        maximum_cooking_time_minutes=profile.maximum_cooking_time_minutes,
        cooking_frequency_per_week=profile.cooking_frequency_per_week,
        meal_preparation_preference=profile.meal_preparation_preference,
        refrigerator_access=profile.refrigerator_access,
        freezer_access=profile.freezer_access,
        cooking_equipment=[item.equipment for item in snapshot.equipment],
        supplied_meals_per_week=profile.supplied_meals_per_week,
        supplied_meal_source=profile.supplied_meal_source,
        foods_available_at_home=names(FoodItemKind.AVAILABLE_AT_HOME),
        favourite_foods=names(FoodItemKind.FAVOURITE),
        disliked_foods=names(FoodItemKind.DISLIKED),
        never_suggest_foods=names(FoodItemKind.NEVER_SUGGEST),
        refused_foods=names(FoodItemKind.REFUSED),
        allergies=constraints(FoodItemKind.ALLERGY),
        intolerances=constraints(FoodItemKind.INTOLERANCE),
        dietary_pattern=profile.dietary_pattern,
        religious_cultural_exclusions=names(FoodItemKind.RELIGIOUS_CULTURAL_EXCLUSION),
        preferred_variety=profile.preferred_variety,
        maximum_meal_repetition_per_week=profile.maximum_meal_repetition_per_week,
        accepts_leftovers=profile.accepts_leftovers,
        accepts_batch_cooking=profile.accepts_batch_cooking,
        work_shift_context=profile.work_shift_context,
        physician_review_required=(snapshot.safety.outcome is not SafetyOutcome.STANDARD_AUTOMATIC),
        daily_check_in_enabled=profile.daily_check_in_enabled,
        preferred_check_in_time=profile.preferred_check_in_time,
        effective_main_meal_slots=profile.effective_main_meal_slots,
        effective_snack_slots=profile.effective_snack_slots,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
