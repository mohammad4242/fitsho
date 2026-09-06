from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.admin.dependencies import AdminUser
from app.admin.media import (
    MediaValidationError,
    discard_managed_media_path,
    discard_media,
    store_image_upload,
)
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.config import Settings, get_settings
from app.database.session import get_db
from app.nutrition.adherence_service import (
    AdherenceError,
    adaptive_preferences,
    adherence_history,
    confirm_target_update,
)
from app.nutrition.ai_price_research import (
    FoodPriceResearchError,
    FoodPriceResearchFood,
    canonical_source_domain,
    median_band_indices,
)
from app.nutrition.catalogue_view import admin_food_catalogue, member_food_catalogue
from app.nutrition.clinical_service import (
    ClinicalError,
    authorize_lab_access,
    claim_review,
    delete_lab,
    list_lab_requests,
    list_labs,
    list_physician_labs,
    open_lab,
    request_labs,
    require_physician,
    review_lab_document,
    review_queue,
    transition_lab_request,
    upload_lab,
)
from app.nutrition.enums import (
    FoodVerificationStatus,
    MealCategory,
    NutritionDietStyle,
    NutritionLabRequestStatus,
    NutritionSupplementOrderStatus,
    PriceUpdateTriggerKind,
)
from app.nutrition.estimate_service import (
    create_estimate,
    current_estimate,
    get_structured_exercise,
    save_structured_exercise,
)
from app.nutrition.exceptions import (
    DietaryPatternNotSupportedV1Error,
    GoalReselectionRequiredDomainError,
    NutritionEstimateBlockedError,
    NutritionEstimateNotFoundError,
    NutritionOnboardingBlockedError,
    NutritionProductModeError,
    NutritionProfileNotFoundError,
    NutritionTargetInfeasibleDomainError,
    PlanSelectionInvalidError,
    SafetyDecisionNotFoundError,
    SafetyScreenRequiredError,
    SharedProfileRequiredError,
    StructuredExerciseRequiredError,
    WeeklyPlanBundleNotFoundError,
)
from app.nutrition.food_catalogue import (
    list_verified_foods,
    retire_catalogue_food,
    save_catalogue_food,
)
from app.nutrition.food_photo_service import (
    FoodPhotoError,
    authorize_photo_access,
    confirm_photo,
    confirm_photo_macro_preview,
    correct_photo_item,
    delete_photo,
    estimate_photo,
    open_photo,
    replay_idempotent_photo,
)
from app.nutrition.meal_catalogue import (
    CATEGORY_ORDER,
    MealReferencedError,
    delete_catalogue_meal,
    get_catalogue_meal,
    list_catalogue_meals,
    meal_response,
    meal_summary_response,
    preview_prepared_recipe,
    update_catalogue_meal,
)
from app.nutrition.meal_catalogue import (
    create_catalogue_meal as create_meal,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueMeal,
    NutritionFoodPriceMapping,
    NutritionFoodPriceQuote,
    NutritionFoodPriceReference,
    NutritionFoodPriceReview,
    NutritionFoodPriceUpdateRun,
    NutritionOperationalEvent,
    NutritionPriceProvider,
    NutritionSupplementCatalogue,
)
from app.nutrition.plan_editing import (
    PlanEditError,
    confirm_remove_meal,
    confirm_replace_food,
    confirm_replace_meal,
    food_replacement_options,
    meal_feedback,
    meal_replacement_options,
    partial_regenerate,
    physician_action,
    physician_adjust_food_quantity,
    physician_plan,
    physician_remove_meal,
    physician_replace_food,
    preview_remove_meal,
    preview_replace_food,
    preview_replace_meal,
    save_feedback,
    set_meal_lock,
    shopping_list,
)
from app.nutrition.plan_service import (
    ActiveWeeklyPlanNotFoundError,
    WeeklyPlanNotFoundError,
    active_weekly_plan,
    generate_weekly_plan,
    latest_plan_bundle,
    latest_weekly_plan,
    select_bundle_plan,
    weekly_plan_by_id,
    weekly_plan_history,
)
from app.nutrition.price_execution import (
    resolve_price_update_execution,
    resolve_single_food_price_researcher,
)
from app.nutrition.price_overrides import create_price_override
from app.nutrition.price_providers import configured_providers
from app.nutrition.price_update_service import run_price_update_async
from app.nutrition.pricing import floor_price_to_thousand_toman
from app.nutrition.program_catalogue import (
    ProgramLifecycle,
    ProgramWriteError,
    archive_program,
    create_program,
    get_program,
    list_programs,
    program_response,
    restore_program,
    update_program,
)
from app.nutrition.schemas import (
    AdminFoodCataloguePageResponse,
    CatalogueConsumptionInput,
    CatalogueFoodResponse,
    CatalogueFoodWrite,
    CatalogueMealImageResponse,
    CatalogueMealPageResponse,
    CatalogueMealResponse,
    CatalogueMealWrite,
    ConsumptionEntryEditInput,
    DailyCheckInInput,
    FoodCatalogueImageResponse,
    FoodCataloguePageResponse,
    FoodPhotoConfirmInput,
    FoodPhotoItemCorrectionInput,
    FoodPriceOverrideInput,
    FoodPriceOverrideResponse,
    FoodReplacementOptionsResponse,
    FreeMealTrackingInput,
    MealFeedbackInput,
    MealLockInput,
    MealReplacementOptionsResponse,
    NutritionEstimateResponse,
    NutritionProfileInput,
    NutritionProfileResponse,
    NutritionProgramPageResponse,
    NutritionProgramResponse,
    NutritionProgramWrite,
    PartialRegenerationInput,
    PhysicianFoodQuantityInput,
    PhysicianLabRequestInput,
    PhysicianLabRequestTransitionInput,
    PhysicianLabReviewInput,
    PhysicianPlanActionInput,
    PhysicianQueueView,
    PhysicianReviewQueueItemResponse,
    PhysicianReviewRequirementResponse,
    PhysicianSupplementOrderInput,
    PlanBundleSelectInput,
    PlanBundleSelectResponse,
    PlannedMealTrackingInput,
    PreparedRecipePreviewResponse,
    PreparedRecipeWrite,
    QuickApproximationInput,
    RemoveMealConfirmationInput,
    ReplaceFoodInput,
    ReplaceMealInput,
    SafetyDecisionResponse,
    SafetyEvaluationResponse,
    SafetyProfileInput,
    SharedCatalogueMealPageResponse,
    SingleFoodPriceResearchQuoteResponse,
    SingleFoodPriceResearchResponse,
    StructuredExerciseInput,
    StructuredExerciseResponse,
    SupplementAcknowledgementInput,
    SupplementCatalogueInput,
    SupplementTransitionInput,
    TargetUpdateConfirmationInput,
    WeeklyPlanFeedbackResponse,
    WeeklyPlanGenerationResponse,
    WeeklyPlanHistoryItemResponse,
    WeeklyPlanResponse,
)
from app.nutrition.security import (
    PrivateAccessError,
    RateLimitExceeded,
    consume_rate_limit,
    create_private_access_token,
    verify_private_access_token,
)
from app.nutrition.service import (
    current_safety_decision,
    evaluate_safety_profile,
    get_nutrition_profile,
    nutrition_profile_response,
    physician_review_requirement,
    safety_response,
    save_nutrition_profile,
    save_safety_profile,
)
from app.nutrition.supplement_service import (
    SupplementError,
    acknowledge_order,
    create_order,
    list_catalogue,
    list_physician_orders,
    list_user_orders,
    save_catalogue,
    transition_order,
    update_order,
)
from app.nutrition.tracking_service import (
    TrackingError,
    add_catalogue_food,
    adjust_planned_meal,
    daily_summary,
    delete_entry,
    edit_entry,
    history,
    recent_foods,
    save_free_meal,
    save_quick_approximation,
    submit_check_in,
)
from app.profile.enums import ProductMode
from app.profile.models import UserProfile

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _domain_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message},
    )


@router.get("/foods", response_model=list[CatalogueFoodResponse])
def read_verified_foods(db: DatabaseSession, user: CurrentUser) -> list[CatalogueFoodResponse]:
    return list_verified_foods(db)


@router.get(
    "/food-catalogue",
    response_model=FoodCataloguePageResponse,
)
def read_member_food_catalogue(
    db: DatabaseSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=60),
) -> FoodCataloguePageResponse:
    profile = db.get(UserProfile, user.id)
    if profile is None or profile.product_mode not in {ProductMode.NUTRITION, ProductMode.BOTH}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nutrition mode required")
    return member_food_catalogue(
        db,
        query=q,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/admin/food-catalogue",
    response_model=AdminFoodCataloguePageResponse,
)
def read_admin_food_catalogue(
    db: DatabaseSession,
    admin: AdminUser,
    q: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=60),
) -> AdminFoodCataloguePageResponse:
    del admin
    return admin_food_catalogue(db, query=q, category=category, page=page, page_size=page_size)


@router.post(
    "/admin/foods",
    response_model=CatalogueFoodResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def create_or_update_catalogue_food(
    payload: CatalogueFoodWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> CatalogueFoodResponse:
    del admin
    try:
        return save_catalogue_food(db, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None


@router.post(
    "/admin/foods/{slug}/image",
    response_model=FoodCatalogueImageResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def upload_catalogue_food_image(
    slug: str,
    db: DatabaseSession,
    admin: AdminUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
) -> FoodCatalogueImageResponse:
    del admin
    food = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == slug))
    if food is None or food.verification_status == FoodVerificationStatus.RETIRED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    try:
        stored = store_image_upload(file, settings, "food-catalogue")
    except MediaValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None
    previous_path = food.image_path
    try:
        food.image_path = stored.public_path
        db.commit()
    except Exception:
        db.rollback()
        discard_media(stored)
        raise
    discard_managed_media_path(previous_path, settings, "food-catalogue")
    return FoodCatalogueImageResponse(image_url=stored.public_path)


@router.post(
    "/admin/foods/{slug}/price-override",
    response_model=FoodPriceOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_food_price_override(
    slug: str,
    payload: FoodPriceOverrideInput,
    db: DatabaseSession,
    admin: AdminUser,
) -> FoodPriceOverrideResponse:
    food = db.scalar(
        select(NutritionCatalogueFood).where(
            NutritionCatalogueFood.slug == slug,
            NutritionCatalogueFood.verification_status == "verified",
        )
    )
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    override = create_price_override(
        db,
        food=food,
        admin_user_id=admin.id,
        payload=payload,
    )
    return FoodPriceOverrideResponse(
        id=override.id,
        food_id=override.food_id,
        reference_price_toman=override.reference_price_toman,
        canonical_unit=override.canonical_unit,
        reason=override.reason,
        created_at=override.created_at,
    )


@router.post(
    "/admin/foods/{slug}/price-research",
    response_model=SingleFoodPriceResearchResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def research_single_food_price(
    slug: str,
    request: Request,
    db: DatabaseSession,
    admin: AdminUser,
    settings: AppSettings,
    apply: bool = False,
) -> SingleFoodPriceResearchResponse:
    food = db.scalar(
        select(NutritionCatalogueFood)
        .options(selectinload(NutritionCatalogueFood.aliases))
        .where(
            NutritionCatalogueFood.slug == slug,
            NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
        )
    )
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    researcher = resolve_single_food_price_researcher(
        db,
        settings=settings,
        agent_http_client=getattr(request.app.state, "agent_http_client", None),
        timeout_seconds=420.0,
    )
    if researcher is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Agent Service is not configured or enabled for food price search",
        )

    aliases = tuple(alias.alias for alias in food.aliases if alias.language == "fa")
    research_food = FoodPriceResearchFood(
        slug=food.slug,
        name_fa=food.name_fa,
        name_en=food.name_en,
        category=food.category,
        aliases=aliases,
    )
    try:
        result = await researcher.research(research_food, expand_sources=False)
    except FoodPriceResearchError as error:
        return SingleFoodPriceResearchResponse(
            food_slug=food.slug,
            food_name_fa=food.name_fa,
            candidate_reference_price_toman=None,
            canonical_unit=None,
            quotes=[
                SingleFoodPriceResearchQuoteResponse(
                    source_name=e.source_name,
                    source_url=e.source_url,
                    source_domain=e.source_domain,
                    product_title=e.product_title,
                    normal_price_toman=e.normalized_normal_price_toman,
                    promotional_price_toman=e.observation.promotional_price,
                    package_quantity=e.observation.package_quantity,
                    package_unit=e.observation.package_unit,
                    match_accepted=e.match_accepted,
                )
                for e in error.evidence
            ],
            status="failed",
            message=str(error),
        )
    except Exception as error:
        return SingleFoodPriceResearchResponse(
            food_slug=food.slug,
            food_name_fa=food.name_fa,
            candidate_reference_price_toman=None,
            canonical_unit=None,
            quotes=[],
            status="failed",
            message=str(error),
        )

    quotes = [
        SingleFoodPriceResearchQuoteResponse(
            source_name=e.source_name,
            source_url=e.source_url,
            source_domain=e.source_domain,
            product_title=e.product_title,
            normal_price_toman=e.normalized_normal_price_toman,
            promotional_price_toman=e.observation.promotional_price,
            package_quantity=e.observation.package_quantity,
            package_unit=e.observation.package_unit,
            match_accepted=e.match_accepted,
        )
        for e in result.evidence
    ]
    accepted = [e for e in result.evidence if e.match_accepted]
    candidate_price: Decimal | None = None
    canonical_unit: str | None = None
    if accepted:
        values = [e.normalized_normal_price_toman for e in accepted]
        indexes = median_band_indices(values)
        trusted = [accepted[i] for i in indexes] if indexes else accepted
        average_price = sum((e.normalized_normal_price_toman for e in trusted), Decimal())
        average_price /= Decimal(len(trusted))
        candidate_price = floor_price_to_thousand_toman(average_price)
        canonical_unit = trusted[0].canonical_unit

    if apply and candidate_price is not None and canonical_unit is not None:
        unit_literal = (
            "TOMAN_PER_KG"
            if "KG" in canonical_unit
            else "TOMAN_PER_LITER"
            if "LITER" in canonical_unit
            else "TOMAN_PER_UNIT"
        )
        create_price_override(
            db,
            food=food,
            admin_user_id=admin.id,
            payload=FoodPriceOverrideInput(
                reference_price_toman=candidate_price,
                canonical_unit=unit_literal,
                reason="استعلام خودکار و تأیید قیمت با ایجنت",
            ),
        )

    return SingleFoodPriceResearchResponse(
        food_slug=food.slug,
        food_name_fa=food.name_fa,
        candidate_reference_price_toman=candidate_price,
        canonical_unit=canonical_unit,
        quotes=quotes,
        status="success" if candidate_price is not None else "no_quotes",
        message=None
        if candidate_price is not None
        else "قیمتی در فروشگاه‌های آنلاین برای این ماده غذایی یافت نشد.",
    )


@router.get(
    "/meal-catalogue",
    response_model=SharedCatalogueMealPageResponse,
)
def read_shared_meal_catalogue(
    db: DatabaseSession,
    user: CurrentUser,
    category: MealCategory | None = None,
    status_filter: Literal["published", "draft", "all"] = "published",
) -> SharedCatalogueMealPageResponse:
    target_status: FoodVerificationStatus | None = FoodVerificationStatus.VERIFIED
    if user.is_admin:
        if status_filter == "draft":
            target_status = FoodVerificationStatus.DRAFT
        elif status_filter == "all":
            target_status = None
        else:
            target_status = FoodVerificationStatus.VERIFIED
    else:
        target_status = FoodVerificationStatus.VERIFIED

    meals = list_catalogue_meals(db, category=category, verification_status=target_status)
    return SharedCatalogueMealPageResponse(
        items=[meal_summary_response(meal) for meal in meals],
        categories=list(CATEGORY_ORDER),
    )


@router.get(
    "/admin/meals",
    response_model=CatalogueMealPageResponse,
)
def read_catalogue_meals(
    db: DatabaseSession,
    admin: AdminUser,
    category: MealCategory | None = None,
) -> CatalogueMealPageResponse:
    del admin
    return CatalogueMealPageResponse(
        items=[meal_response(meal, db) for meal in list_catalogue_meals(db, category)],
        categories=list(CATEGORY_ORDER),
    )


@router.post(
    "/admin/meals/prepared-recipe/preview",
    response_model=PreparedRecipePreviewResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def preview_catalogue_prepared_recipe(
    payload: PreparedRecipeWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> PreparedRecipePreviewResponse:
    del admin
    try:
        return preview_prepared_recipe(db, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None


@router.get(
    "/admin/meals/{meal_id}",
    response_model=CatalogueMealResponse,
)
def read_catalogue_meal(
    meal_id: UUID,
    db: DatabaseSession,
    admin: AdminUser,
) -> CatalogueMealResponse:
    del admin
    meal = get_catalogue_meal(db, meal_id)
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    return meal_response(meal, db)


@router.post(
    "/admin/meals",
    response_model=CatalogueMealResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_catalogue_meal(
    payload: CatalogueMealWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> CatalogueMealResponse:
    del admin
    try:
        return meal_response(create_meal(db, payload), db)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None


@router.put(
    "/admin/meals/{meal_id}",
    response_model=CatalogueMealResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def replace_catalogue_meal(
    meal_id: UUID,
    payload: CatalogueMealWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> CatalogueMealResponse:
    del admin
    try:
        meal = update_catalogue_meal(db, meal_id, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    return meal_response(meal, db)


@router.post(
    "/admin/meals/{meal_id}/image",
    response_model=CatalogueMealImageResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def upload_catalogue_meal_image(
    meal_id: UUID,
    db: DatabaseSession,
    admin: AdminUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
) -> CatalogueMealImageResponse:
    del admin
    meal = db.get(NutritionCatalogueMeal, meal_id)
    if meal is None or meal.verification_status == FoodVerificationStatus.RETIRED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    try:
        stored = store_image_upload(file, settings, "meal-catalogue")
    except MediaValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None
    previous_path = meal.image_path
    try:
        meal.image_path = stored.public_path
        db.commit()
    except Exception:
        db.rollback()
        discard_media(stored)
        raise
    discard_managed_media_path(previous_path, settings, "meal-catalogue")
    return CatalogueMealImageResponse(image_url=stored.public_path)


@router.delete(
    "/admin/meals/{meal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_catalogue_meal(
    meal_id: UUID,
    db: DatabaseSession,
    admin: AdminUser,
    settings: AppSettings,
) -> None:
    del admin
    meal = db.get(NutritionCatalogueMeal, meal_id)
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    try:
        image_path = delete_catalogue_meal(db, meal_id)
    except MealReferencedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "meal_referenced", "message": str(exc)},
        ) from exc
    if image_path:
        discard_managed_media_path(image_path, settings, "meal-catalogue")


@router.get(
    "/admin/programs",
    response_model=NutritionProgramPageResponse,
)
def read_nutrition_programs(
    db: DatabaseSession,
    admin: AdminUser,
    diet_style: NutritionDietStyle | None = None,
    lifecycle: ProgramLifecycle = "active",
) -> NutritionProgramPageResponse:
    del admin
    return NutritionProgramPageResponse(
        items=[
            program_response(program)
            for program in list_programs(db, diet_style=diet_style, lifecycle=lifecycle)
        ],
        diet_styles=list(NutritionDietStyle),
    )


@router.get(
    "/admin/programs/{program_id}",
    response_model=NutritionProgramResponse,
)
def read_nutrition_program(
    program_id: UUID,
    db: DatabaseSession,
    admin: AdminUser,
) -> NutritionProgramResponse:
    del admin
    program = get_program(db, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program_response(program)


@router.post(
    "/admin/programs",
    response_model=NutritionProgramResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_nutrition_program(
    payload: NutritionProgramWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> NutritionProgramResponse:
    del admin
    try:
        return program_response(create_program(db, payload))
    except ProgramWriteError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None


@router.put(
    "/admin/programs/{program_id}",
    response_model=NutritionProgramResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def replace_nutrition_program(
    program_id: UUID,
    payload: NutritionProgramWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> NutritionProgramResponse:
    del admin
    try:
        program = update_program(db, program_id, payload)
    except ProgramWriteError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program_response(program)


@router.delete(
    "/admin/programs/{program_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def archive_nutrition_program(
    program_id: UUID,
    db: DatabaseSession,
    admin: AdminUser,
) -> None:
    del admin
    if not archive_program(db, program_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")


@router.post(
    "/admin/programs/{program_id}/restore",
    response_model=NutritionProgramResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def restore_nutrition_program(
    program_id: UUID,
    db: DatabaseSession,
    admin: AdminUser,
) -> NutritionProgramResponse:
    del admin
    program = restore_program(db, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program_response(program)


@router.delete(
    "/admin/foods/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def retire_food(
    slug: str,
    db: DatabaseSession,
    admin: AdminUser,
) -> None:
    del admin
    try:
        retire_catalogue_food(db, slug)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None


def _monitoring_toman(value: Decimal | None) -> str | None:
    if value is None:
        return None
    formatted = format(value / Decimal("10"), "f").rstrip("0").rstrip(".")
    return formatted or "0"


def _review_quote_evidence(
    db: DatabaseSession,
    review: NutritionFoodPriceReview,
    providers: dict[str, NutritionPriceProvider],
) -> list[dict[str, object]]:
    source_ids: list[str] = []
    for value in review.source_quote_ids[:5]:
        if isinstance(value, str):
            try:
                UUID(value)
            except ValueError:
                continue
            source_ids.append(value)
    if not source_ids:
        return []
    quotes = db.scalars(
        select(NutritionFoodPriceQuote).where(
            NutritionFoodPriceQuote.id.in_([UUID(value) for value in source_ids]),
            NutritionFoodPriceQuote.food_id == review.food_id,
        )
    ).all()
    quotes_by_id = {str(quote.id): quote for quote in quotes}
    result: list[dict[str, object]] = []
    for source_id in source_ids:
        quote = quotes_by_id.get(source_id)
        if quote is None:
            continue
        raw_quote = quote.raw_quote
        provider = providers.get(quote.provider_code)
        source_url = raw_quote.get("source_url")
        source_url = source_url if isinstance(source_url, str) else None
        source_domain = raw_quote.get("source_domain")
        if not isinstance(source_domain, str) and source_url is not None:
            try:
                source_domain = canonical_source_domain(source_url)
            except ValueError:
                source_domain = None
        if not isinstance(source_domain, str):
            source_domain = provider.name if provider is not None else quote.provider_code
        source_name = raw_quote.get("source_name")
        if not isinstance(source_name, str):
            source_name = provider.name if provider is not None else quote.provider_code
        product_title = raw_quote.get("title")
        if not isinstance(product_title, str):
            product_title = ""
        result.append(
            {
                "id": quote.id,
                "provider_code": quote.provider_code,
                "source_name": source_name,
                "source_domain": source_domain,
                "source_url": source_url,
                "product_title": product_title,
                "normal_price_toman": _monitoring_toman(quote.normal_price_irr),
                "promotional_price_toman": _monitoring_toman(quote.promotional_price_irr),
                "normalized_normal_price_toman": _monitoring_toman(quote.normalized_normal_irr),
                "package_quantity": format(quote.package_quantity, "f").rstrip("0").rstrip("."),
                "package_unit": quote.package_unit,
                "observed_at": quote.observed_at,
            }
        )
    return result


@router.get("/admin/monitoring")
def read_nutrition_monitoring(db: DatabaseSession, admin: AdminUser) -> dict[str, object]:
    del admin
    latest_runs = db.scalars(
        select(NutritionFoodPriceUpdateRun)
        .order_by(NutritionFoodPriceUpdateRun.started_at.desc())
        .limit(10)
    ).all()
    providers = db.scalars(
        select(NutritionPriceProvider).order_by(NutritionPriceProvider.code)
    ).all()
    ai_events = db.scalars(
        select(NutritionOperationalEvent).where(NutritionOperationalEvent.category == "ai")
    ).all()
    reviews = db.execute(
        select(NutritionFoodPriceReview, NutritionCatalogueFood.slug)
        .join(NutritionCatalogueFood, NutritionCatalogueFood.id == NutritionFoodPriceReview.food_id)
        .order_by(NutritionFoodPriceReview.created_at.desc())
        .limit(50)
    ).all()
    broken_mappings = db.execute(
        select(NutritionFoodPriceMapping, NutritionCatalogueFood.slug)
        .join(
            NutritionCatalogueFood, NutritionCatalogueFood.id == NutritionFoodPriceMapping.food_id
        )
        .where(
            (NutritionFoodPriceMapping.broken_at.is_not(None))
            | (NutritionFoodPriceMapping.active.is_(False))
        )
        .order_by(NutritionFoodPriceMapping.provider_code, NutritionCatalogueFood.slug)
    ).all()
    food_count = db.scalar(select(func.count()).select_from(NutritionCatalogueFood)) or 0
    accepted_reference_count = (
        db.scalar(select(func.count()).select_from(NutritionFoodPriceReference)) or 0
    )
    return {
        "counts": {
            "foods": food_count,
            "meals": db.scalar(select(func.count()).select_from(NutritionCatalogueMeal)) or 0,
            "accepted_price_references": accepted_reference_count,
            "price_reviews": db.scalar(select(func.count()).select_from(NutritionFoodPriceReview))
            or 0,
            "supplements": db.scalar(select(func.count()).select_from(NutritionSupplementCatalogue))
            or 0,
        },
        "recent_price_runs": [
            {
                "id": run.id,
                "status": run.status.value,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "foods_attempted": run.foods_attempted,
                "foods_updated": run.foods_updated,
                "foods_needing_review": run.foods_needing_review,
                "provider_failures": run.provider_failures,
                "trigger_kind": run.trigger_kind.value,
                "failure_codes": run.failure_codes,
            }
            for run in latest_runs
        ],
        "provider_health": [
            {
                "code": provider.code,
                "enabled": provider.enabled,
                "last_success_at": provider.last_success_at,
                "last_error": provider.last_error,
                "parser_version": provider.parser_version,
            }
            for provider in providers
        ],
        "coverage_warning": (
            "INSUFFICIENT_PRICE_COVERAGE"
            if food_count and accepted_reference_count < food_count
            else None
        ),
        "price_reviews": [
            {
                "id": review.id,
                "food_slug": food_slug,
                "reason_codes": review.reason_codes,
                "candidate_reference_price_toman": _monitoring_toman(
                    review.candidate_reference_price_toman * Decimal("10")
                    if review.candidate_reference_price_toman is not None
                    else None
                ),
                "created_at": review.created_at,
                "quotes": _review_quote_evidence(
                    db,
                    review,
                    {provider.code: provider for provider in providers},
                ),
            }
            for review, food_slug in reviews
        ],
        "broken_mappings": [
            {
                "id": mapping.id,
                "food_slug": food_slug,
                "provider_code": mapping.provider_code,
                "provider_product_id": mapping.provider_product_id,
                "broken_at": mapping.broken_at,
            }
            for mapping, food_slug in broken_mappings
        ],
        "ai_usage": {
            "requests": sum(int(str(event.counters.get("requests", 0))) for event in ai_events),
            "errors": sum(int(str(event.counters.get("errors", 0))) for event in ai_events),
            "input_tokens": sum(
                int(str(event.counters.get("input_tokens", 0))) for event in ai_events
            ),
            "output_tokens": sum(
                int(str(event.counters.get("output_tokens", 0))) for event in ai_events
            ),
        },
    }


@router.post(
    "/admin/prices/refresh",
    dependencies=[Depends(require_trusted_origin)],
)
async def trigger_manual_price_refresh(
    request: Request,
    db: DatabaseSession,
    admin: AdminUser,
    settings: AppSettings,
) -> dict[str, object]:
    del admin
    try:
        execution = resolve_price_update_execution(
            db,
            settings=settings,
            price_http_client=request.app.state.food_price_http_client,
            agent_http_client=getattr(request.app.state, "agent_http_client", None),
            direct_provider_factory=lambda: configured_providers(
                settings, request.app.state.food_price_http_client
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    run = await run_price_update_async(
        db,
        providers=execution.providers,
        agent_researcher=execution.agent_researcher,
        retry_attempts=settings.food_price_provider_retries,
        trigger_kind=PriceUpdateTriggerKind.MANUAL,
    )
    return {
        "id": run.id,
        "status": run.status.value,
        "trigger_kind": run.trigger_kind.value,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "foods_attempted": run.foods_attempted,
        "foods_updated": run.foods_updated,
        "foods_needing_review": run.foods_needing_review,
        "provider_failures": run.provider_failures,
        "failure_codes": run.failure_codes,
    }


@router.post("/safety/evaluate", response_model=SafetyEvaluationResponse)
def preview_safety(payload: SafetyProfileInput) -> SafetyEvaluationResponse:
    return evaluate_safety_profile(payload)


@router.put(
    "/safety",
    response_model=SafetyDecisionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update_safety(
    payload: SafetyProfileInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> SafetyDecisionResponse:
    try:
        return safety_response(save_safety_profile(db, user.id, payload))
    except SharedProfileRequiredError:
        raise _domain_error(
            "SHARED_PROFILE_REQUIRED", "ابتدا اطلاعات پایه پروفایل را کامل کنید."
        ) from None


@router.get("/safety", response_model=SafetyDecisionResponse)
def read_safety(db: DatabaseSession, user: CurrentUser) -> SafetyDecisionResponse:
    try:
        return safety_response(current_safety_decision(db, user.id))
    except SafetyDecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SAFETY_DECISION_NOT_FOUND", "message": "ارزیابی ایمنی ثبت نشده است."},
        ) from None


@router.put(
    "/profile",
    response_model=NutritionProfileResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update_nutrition_profile(
    payload: NutritionProfileInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionProfileResponse:
    try:
        return nutrition_profile_response(save_nutrition_profile(db, user.id, payload))
    except SharedProfileRequiredError:
        raise _domain_error(
            "SHARED_PROFILE_REQUIRED", "ابتدا اطلاعات پایه پروفایل را کامل کنید."
        ) from None
    except SafetyScreenRequiredError:
        raise _domain_error(
            "SAFETY_SCREEN_REQUIRED", "پیش از ادامه، ارزیابی ایمنی را کامل کنید."
        ) from None
    except DietaryPatternNotSupportedV1Error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DIETARY_PATTERN_NOT_SUPPORTED_V1",
                "message": "الگوی تغذیه‌ای گیاه‌خواری یا وگان در نسخه ۱ پشتیبانی نمی‌شود.",
            },
        ) from None
    except NutritionOnboardingBlockedError:
        raise _domain_error(
            "NUTRITION_ONBOARDING_BLOCKED",
            "برای حفظ ایمنی، ادامه این مسیر فقط با بررسی پزشک ممکن است.",
        ) from None


@router.get("/profile", response_model=NutritionProfileResponse)
def read_nutrition_profile(
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionProfileResponse:
    try:
        return nutrition_profile_response(get_nutrition_profile(db, user.id))
    except NutritionProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_PROFILE_NOT_FOUND",
                "message": "پروفایل تغذیه ثبت نشده است.",
            },
        ) from None


@router.put(
    "/structured-exercise",
    response_model=StructuredExerciseResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update_structured_exercise(
    payload: StructuredExerciseInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> StructuredExerciseResponse:
    try:
        return save_structured_exercise(db, user.id, payload)
    except NutritionProfileNotFoundError:
        raise _domain_error(
            "NUTRITION_PROFILE_REQUIRED",
            "ابتدا اطلاعات تغذیه را کامل کنید.",
        ) from None
    except NutritionProductModeError:
        raise _domain_error(
            "NUTRITION_PRODUCT_MODE_REQUIRED",
            "این اطلاعات فقط در مسیر تغذیه ثبت می‌شود.",
        ) from None


@router.get("/structured-exercise", response_model=StructuredExerciseResponse)
def read_structured_exercise(
    db: DatabaseSession,
    user: CurrentUser,
) -> StructuredExerciseResponse:
    try:
        return get_structured_exercise(db, user.id)
    except (NutritionProfileNotFoundError, StructuredExerciseRequiredError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "STRUCTURED_EXERCISE_NOT_FOUND",
                "message": "اطلاعات تمرین ساختاریافته ثبت نشده است.",
            },
        ) from None
    except NutritionProductModeError:
        raise _domain_error(
            "NUTRITION_PRODUCT_MODE_REQUIRED",
            "برآورد تغذیه برای این مسیر فعال نیست.",
        ) from None


@router.post(
    "/estimates",
    response_model=NutritionEstimateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def generate_estimate(
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionEstimateResponse:
    try:
        return create_estimate(db, user.id)
    except NutritionEstimateBlockedError:
        raise _domain_error(
            "NUTRITION_ESTIMATE_BLOCKED",
            "به‌دلیل وضعیت ایمنی، برآورد عمومی تغذیه برای این حساب مجاز نیست.",
        ) from None
    except GoalReselectionRequiredDomainError:
        raise _domain_error(
            "GOAL_RESELECTION_REQUIRED",
            "برای فردی که تمرین نمی‌کند، هدف عضله‌سازی قابل برآورد نیست.",
        ) from None
    except NutritionTargetInfeasibleDomainError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TARGET_INFEASIBLE",
                "message": "حداقل‌های علمی در بازه کالری انتخاب‌شده قابل جمع نیستند.",
                "reason_codes": list(error.reason_codes),
            },
        ) from None
    except StructuredExerciseRequiredError:
        raise _domain_error(
            "STRUCTURED_EXERCISE_REQUIRED",
            "اطلاعات تمرین برای محاسبه دقیق انرژی لازم است.",
        ) from None
    except NutritionProfileNotFoundError:
        raise _domain_error(
            "NUTRITION_PROFILE_REQUIRED",
            "اطلاعات لازم برای برآورد تغذیه کامل نیست.",
        ) from None
    except NutritionProductModeError:
        raise _domain_error(
            "NUTRITION_PRODUCT_MODE_REQUIRED",
            "برآورد تغذیه برای این مسیر فعال نیست.",
        ) from None


@router.get("/estimates/current", response_model=NutritionEstimateResponse)
def read_current_estimate(
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionEstimateResponse:
    try:
        return current_estimate(db, user.id)
    except NutritionEstimateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_ESTIMATE_NOT_FOUND",
                "message": "هنوز برآورد تغذیه‌ای ثبت نشده است.",
            },
        ) from None


@router.get(
    "/review-requirement",
    response_model=PhysicianReviewRequirementResponse,
)
def read_review_requirement(
    db: DatabaseSession,
    user: CurrentUser,
) -> PhysicianReviewRequirementResponse:
    try:
        return physician_review_requirement(db, user.id)
    except SafetyDecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SAFETY_DECISION_NOT_FOUND", "message": "ارزیابی ایمنی ثبت نشده است."},
        ) from None


@router.post(
    "/plans",
    response_model=WeeklyPlanGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def generate_plan(
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanGenerationResponse:
    try:
        return generate_weekly_plan(db, user.id)
    except SafetyDecisionNotFoundError:
        raise _domain_error(
            "SAFETY_SCREEN_REQUIRED", "پیش از ساخت برنامه، ارزیابی ایمنی را کامل کنید."
        ) from None
    except StructuredExerciseRequiredError:
        raise _domain_error(
            "STRUCTURED_EXERCISE_REQUIRED",
            "اطلاعات تمرین برای محاسبه برنامه لازم است.",
        ) from None


@router.post("/plan-bundles/{bundle_id}/select", response_model=PlanBundleSelectResponse)
def select_plan_in_bundle(
    bundle_id: str,
    payload: PlanBundleSelectInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> PlanBundleSelectResponse:
    try:
        bundle_uuid = UUID(bundle_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PLAN_BUNDLE_NOT_FOUND", "message": "بسته برنامه غذایی پیدا نشد."},
        ) from None

    chosen_plan_id = payload.plan_id or payload.selected_plan_id
    chosen_role = payload.plan_role or payload.selected_plan_role

    try:
        return select_bundle_plan(
            db,
            user_id=user.id,
            bundle_id=bundle_uuid,
            plan_id=chosen_plan_id,
            plan_role=chosen_role,
        )
    except WeeklyPlanBundleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PLAN_BUNDLE_NOT_FOUND", "message": "بسته برنامه غذایی پیدا نشد."},
        ) from None
    except PlanSelectionInvalidError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PLAN_SELECTION_INVALID", "message": str(err)},
        ) from None


@router.get("/plan-bundles/latest", response_model=WeeklyPlanGenerationResponse | None)
def read_latest_plan_bundle(
    db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanGenerationResponse | None:
    return latest_plan_bundle(db, user.id)


@router.get("/plans/latest", response_model=WeeklyPlanResponse)
def read_latest_plan(db: DatabaseSession, user: CurrentUser) -> WeeklyPlanResponse:
    try:
        return latest_weekly_plan(db, user.id)
    except WeeklyPlanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_PLAN_NOT_FOUND",
                "message": "هنوز برنامه غذایی هفتگی ساخته نشده است.",
            },
        ) from None


@router.get("/plans/active", response_model=WeeklyPlanResponse)
def read_active_plan(db: DatabaseSession, user: CurrentUser) -> WeeklyPlanResponse:
    try:
        return active_weekly_plan(db, user.id)
    except ActiveWeeklyPlanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ACTIVE_NUTRITION_PLAN_NOT_FOUND",
                "message": "هنوز برنامه تأییدشده و فعالی وجود ندارد.",
            },
        ) from None


@router.get("/plans/history", response_model=list[WeeklyPlanHistoryItemResponse])
def read_plan_history(
    db: DatabaseSession, user: CurrentUser
) -> list[WeeklyPlanHistoryItemResponse]:
    return weekly_plan_history(db, user.id)


@router.get("/plans/{plan_id}", response_model=WeeklyPlanResponse)
def read_plan_revision(
    plan_id: str,
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanResponse:
    try:
        return weekly_plan_by_id(db, user.id, UUID(plan_id))
    except (ValueError, WeeklyPlanNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_PLAN_NOT_FOUND",
                "message": "نسخه برنامه غذایی پیدا نشد.",
            },
        ) from None


def _plan_edit_error(error: PlanEditError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    if error.code == "PHYSICIAN_ROLE_REQUIRED":
        status_code = status.HTTP_403_FORBIDDEN
    messages = {
        "PLAN_REVIEW_IN_PROGRESS": (
            "این نسخه در حال بررسی پزشک است و تا پایان بررسی نمی‌توان وعده‌های آن را تغییر داد."
        ),
        "STALE_PLAN_REVISION": (
            "نسخه برنامه تغییر کرده است. صفحه را به‌روزرسانی کن و دوباره تلاش کن."
        ),
        "MEAL_NOT_FOUND": "وعده موردنظر دیگر در این نسخه وجود ندارد.",
        "MEAL_LOCKED": "این وعده قفل است و ابتدا باید قفل آن را باز کنی.",
        "INCOMPATIBLE_MEAL_REPLACEMENT": "این وعده جایگزین با نقش وعده سازگار نیست.",
        "FOOD_REPLACEMENT_NOT_FOUND": "ماده غذایی انتخاب‌شده دیگر برای این جایگزینی در دسترس نیست.",
    }
    return HTTPException(
        status_code=status_code,
        detail={
            "code": error.code,
            "message": messages.get(error.code, "عملیات برنامه غذایی انجام نشد."),
        },
    )


@router.get("/plans/{plan_id}/feedback", response_model=WeeklyPlanFeedbackResponse)
def read_meal_feedback(plan_id: UUID, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    try:
        return meal_feedback(db, user.id, plan_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.get(
    "/plans/{plan_id}/meal-replacement-options",
    response_model=MealReplacementOptionsResponse,
)
def read_meal_replacement_options(
    plan_id: UUID, meal_id: UUID, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return meal_replacement_options(db, user.id, plan_id, meal_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.get(
    "/plans/{plan_id}/food-replacement-options",
    response_model=FoodReplacementOptionsResponse,
)
def read_food_replacement_options(
    plan_id: UUID, meal_id: UUID, food_id: UUID, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return food_replacement_options(db, user.id, plan_id, meal_id, food_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.get("/plans/{plan_id}/shopping-list")
def read_shopping_list(plan_id: UUID, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    try:
        return shopping_list(db, user.id, plan_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.put("/plans/{plan_id}/meals/{meal_id}/lock", dependencies=[Depends(require_trusted_origin)])
def update_meal_lock(
    plan_id: UUID, meal_id: UUID, payload: MealLockInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return set_meal_lock(db, user.id, plan_id, meal_id, payload.is_locked)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.put(
    "/plans/{plan_id}/meals/{meal_id}/feedback", dependencies=[Depends(require_trusted_origin)]
)
def update_meal_feedback(
    plan_id: UUID, meal_id: UUID, payload: MealFeedbackInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return save_feedback(db, user.id, plan_id, meal_id, payload.feedback_type, payload.notes)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post("/plans/{plan_id}/edits/remove-meal/preview")
def preview_meal_removal(
    plan_id: UUID, meal_id: UUID, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return preview_remove_meal(db, user.id, plan_id, meal_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/plans/{plan_id}/edits/remove-meal/confirm",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_meal_removal(
    plan_id: UUID, payload: RemoveMealConfirmationInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return confirm_remove_meal(
            db, user.id, plan_id, payload.expected_plan_revision_id, payload.meal_id
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post("/plans/{plan_id}/edits/replace-meal/preview")
def preview_meal_replacement(
    plan_id: UUID, payload: ReplaceMealInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return preview_replace_meal(
            db, user.id, plan_id, payload.meal_id, payload.replacement_meal_id
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/plans/{plan_id}/edits/replace-meal/confirm",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_meal_replacement(
    plan_id: UUID, payload: ReplaceMealInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return confirm_replace_meal(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.meal_id,
            payload.replacement_meal_id,
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post("/plans/{plan_id}/edits/replace-food/preview")
def preview_food_replacement(
    plan_id: UUID, payload: ReplaceFoodInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return preview_replace_food(
            db, user.id, plan_id, payload.meal_id, payload.food_id, payload.replacement_food_id
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/plans/{plan_id}/edits/replace-food/confirm",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_food_replacement(
    plan_id: UUID, payload: ReplaceFoodInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return confirm_replace_food(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.meal_id,
            payload.food_id,
            payload.replacement_food_id,
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/plans/{plan_id}/edits/partial-regenerate",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def regenerate_plan_partially(
    plan_id: UUID, payload: PartialRegenerationInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return partial_regenerate(
            db, user.id, plan_id, payload.expected_plan_revision_id, payload.day_indexes
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/action",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def review_plan(
    plan_id: UUID, payload: PhysicianPlanActionInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return physician_action(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.action,
            payload.notes,
            payload.internal_notes,
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.get("/physician/plans/{plan_id}", response_model=WeeklyPlanResponse)
def read_physician_plan(
    plan_id: UUID, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return physician_plan(db, user.id, plan_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/edits/remove-meal",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def physician_edit_remove_meal(
    plan_id: UUID,
    payload: RemoveMealConfirmationInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanResponse:
    try:
        return physician_remove_meal(
            db, user.id, plan_id, payload.expected_plan_revision_id, payload.meal_id
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/edits/food-quantity",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def physician_edit_food_quantity(
    plan_id: UUID,
    payload: PhysicianFoodQuantityInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanResponse:
    try:
        return physician_adjust_food_quantity(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.meal_id,
            payload.food_id,
            Decimal(str(payload.grams)),
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/edits/replace-food",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def physician_edit_food_replacement(
    plan_id: UUID,
    payload: ReplaceFoodInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanResponse:
    try:
        return physician_replace_food(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.meal_id,
            payload.food_id,
            payload.replacement_food_id,
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


def _tracking_error(error: TrackingError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=error_status, detail={"code": error.code})


@router.put("/tracking/check-in", dependencies=[Depends(require_trusted_origin)])
def update_daily_check_in(
    payload: DailyCheckInInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return submit_check_in(db, user.id, payload.entry_date, payload.status, payload.note)
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.post(
    "/tracking/entries/catalogue",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_catalogue_consumption(
    payload: CatalogueConsumptionInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return add_catalogue_food(
            db,
            user.id,
            payload.entry_date,
            payload.food_id,
            Decimal(str(payload.grams)),
            payload.note,
        )
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.post(
    "/tracking/entries/quick",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_quick_consumption(
    payload: QuickApproximationInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    return save_quick_approximation(
        db,
        user.id,
        payload.entry_date,
        payload.display_name,
        Decimal(str(payload.calories)),
        Decimal(str(payload.protein_g)) if payload.protein_g is not None else None,
    )


@router.put(
    "/tracking/free-meals/{meal_id}",
    dependencies=[Depends(require_trusted_origin)],
)
def update_free_meal_consumption(
    meal_id: UUID,
    payload: FreeMealTrackingInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return save_free_meal(
            db,
            user.id,
            meal_id,
            payload.entry_date,
            Decimal(str(payload.calories)),
            Decimal(str(payload.protein_g)),
            Decimal(str(payload.carbohydrate_g)),
            Decimal(str(payload.fat_g)),
        )
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.get("/tracking/days/{entry_date}")
def read_daily_tracking(
    entry_date: date, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    return daily_summary(db, user.id, entry_date)


@router.get("/tracking/history")
def read_tracking_history(
    start: date, end: date, db: DatabaseSession, user: CurrentUser
) -> list[dict[str, object]]:
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail={"code": "INVALID_DATE_RANGE"})
    return history(db, user.id, start, end)


@router.get("/tracking/recent-foods")
def read_recent_foods(
    db: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[dict[str, object]]:
    return recent_foods(db, user.id, limit)


@router.put(
    "/tracking/entries/{entry_id}",
    dependencies=[Depends(require_trusted_origin)],
)
def update_consumption_entry(
    entry_id: UUID,
    payload: ConsumptionEntryEditInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return edit_entry(
            db,
            user.id,
            entry_id,
            grams=Decimal(str(payload.grams)) if payload.grams is not None else None,
            display_name=payload.display_name,
            calories=Decimal(str(payload.calories)) if payload.calories is not None else None,
            protein=Decimal(str(payload.protein_g)) if payload.protein_g is not None else None,
            note=payload.note,
            fields=set(payload.model_fields_set),
        )
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.put(
    "/tracking/planned-meals/{meal_id}",
    dependencies=[Depends(require_trusted_origin)],
)
def update_planned_meal_tracking(
    meal_id: UUID,
    payload: PlannedMealTrackingInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return adjust_planned_meal(
            db,
            user.id,
            meal_id,
            payload.entry_date,
            payload.status,
            Decimal(str(payload.portion_ratio)) if payload.portion_ratio is not None else None,
        )
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.delete(
    "/tracking/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_consumption_entry(entry_id: UUID, db: DatabaseSession, user: CurrentUser) -> None:
    try:
        delete_entry(db, user.id, entry_id)
    except TrackingError as error:
        raise _tracking_error(error) from None


def _food_photo_error(error: FoodPhotoError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    if error.code in {"INVALID_FOOD_PHOTO", "FOOD_PHOTO_TOO_LARGE"}:
        error_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    if error.code == "FOOD_PHOTO_PROVIDER_UNAVAILABLE":
        error_status = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=error_status, detail={"code": error.code})


@router.post(
    "/tracking/photo-estimates",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def create_food_photo_estimate(
    request: Request,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    consent: Annotated[bool, Header(alias="X-Fitsho-Food-Photo-Consent")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
    language: str = Query(default="fa"),
) -> dict[str, object]:
    try:
        if idempotency_key is not None and not 8 <= len(idempotency_key) <= 128:
            raise FoodPhotoError("INVALID_IDEMPOTENCY_KEY")
        replayed = replay_idempotent_photo(db, user.id, idempotency_key)
        if replayed is not None:
            return replayed
        consume_rate_limit(
            db,
            actor_user_id=user.id,
            operation="food_photo_estimation",
            limit=settings.food_photo_rate_limit,
            window_seconds=settings.nutrition_upload_rate_window_seconds,
        )
        resolved_lang = (
            "en"
            if (language == "en" or (accept_language and accept_language.lower().startswith("en")))
            else "fa"
        )
        return await estimate_photo(
            db,
            user.id,
            file,
            consent,
            settings,
            request.app.state.ai_http_client,
            idempotency_key,
            getattr(request.app.state, "agent_http_client", None),
            language=resolved_lang,
        )
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMIT_EXCEEDED"},
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.patch(
    "/tracking/photo-estimates/{estimate_id}/items/{item_id}",
    dependencies=[Depends(require_trusted_origin)],
)
def correct_food_photo_estimate_item(
    estimate_id: UUID,
    item_id: str,
    payload: FoodPhotoItemCorrectionInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return correct_photo_item(
            db,
            user.id,
            estimate_id,
            item_id,
            food_id=payload.food_id,
            estimated_amount=(
                Decimal(str(payload.estimated_amount))
                if payload.estimated_amount is not None
                else None
            ),
            remove=payload.remove,
        )
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.post(
    "/tracking/photo-estimates/{estimate_id}/confirm",
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_food_photo_estimate(
    estimate_id: UUID,
    payload: FoodPhotoConfirmInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> list[dict[str, object]]:
    try:
        return confirm_photo(db, user.id, estimate_id, payload.entry_date)
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.post(
    "/tracking/photo-estimates/{estimate_id}/free-meal-preview",
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_free_meal_photo_preview(
    estimate_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, float]:
    try:
        return confirm_photo_macro_preview(db, user.id, estimate_id)
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.delete(
    "/tracking/photo-estimates/{estimate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_food_photo_estimate(
    estimate_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> None:
    try:
        delete_photo(db, user.id, estimate_id, settings)
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.post(
    "/tracking/photo-estimates/{estimate_id}/access-grant",
    dependencies=[Depends(require_trusted_origin)],
)
def grant_food_photo_access(
    estimate_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> dict[str, object]:
    try:
        authorize_photo_access(db, user.id, estimate_id)
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None
    token = create_private_access_token(
        settings,
        actor_user_id=user.id,
        resource_id=estimate_id,
        purpose="food_photo",
    )
    return {
        "access_url": (
            f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/file?token={token}"
        ),
        "expires_in_seconds": settings.private_file_access_ttl_seconds,
    }


@router.get("/tracking/photo-estimates/{estimate_id}/file")
def download_food_photo(
    estimate_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    token: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    try:
        if token is None:
            raise PrivateAccessError
        verify_private_access_token(
            settings,
            token,
            actor_user_id=user.id,
            resource_id=estimate_id,
            purpose="food_photo",
        )
        handle, content_type = open_photo(db, user.id, estimate_id, settings)
    except PrivateAccessError:
        raise HTTPException(
            status_code=403, detail={"code": "PRIVATE_ACCESS_TOKEN_REQUIRED"}
        ) from None
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None
    return StreamingResponse(handle, media_type=content_type)


@router.get("/adherence")
def read_adherence(
    start: date, end: date, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail={"code": "INVALID_DATE_RANGE"})
    return adherence_history(db, user.id, start, end)


@router.get("/adaptive-preferences")
def read_adaptive_preferences(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    return adaptive_preferences(db, user.id)


@router.post(
    "/targets/confirm-update",
    dependencies=[Depends(require_trusted_origin)],
)
def update_confirmed_target(
    payload: TargetUpdateConfirmationInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return confirm_target_update(db, user.id, payload.requested_goal, payload.confirmed)
    except AdherenceError as error:
        raise HTTPException(status_code=409, detail={"code": error.code}) from None


def _clinical_error(error: ClinicalError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    if error.code == "PHYSICIAN_ROLE_REQUIRED":
        error_status = status.HTTP_403_FORBIDDEN
    if error.code in {"INVALID_LAB_DOCUMENT", "LAB_DOCUMENT_TOO_LARGE"}:
        error_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=error_status, detail={"code": error.code})


@router.post(
    "/labs",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def create_lab_document(
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    test_date: Annotated[date | None, Form()] = None,
    laboratory_name: Annotated[str | None, Form()] = None,
    user_note: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    request_id: Annotated[UUID | None, Form()] = None,
) -> dict[str, object]:
    try:
        consume_rate_limit(
            db,
            actor_user_id=user.id,
            operation="nutrition_lab_upload",
            limit=settings.nutrition_lab_upload_rate_limit,
            window_seconds=settings.nutrition_upload_rate_window_seconds,
        )
        return await upload_lab(
            db,
            user.id,
            file,
            settings,
            test_date=test_date,
            laboratory_name=laboratory_name,
            user_note=user_note,
            category=category,
            request_id=request_id,
        )
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMIT_EXCEEDED"},
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.get("/labs")
def read_lab_documents(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    return list_labs(db, user.id)


@router.get("/labs/{document_id}/file")
def download_lab_document(
    document_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    token: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    try:
        if token is None:
            raise PrivateAccessError
        verify_private_access_token(
            settings,
            token,
            actor_user_id=user.id,
            resource_id=document_id,
            purpose="nutrition_lab",
        )
        handle, content_type, filename = open_lab(db, user.id, document_id, settings)
    except PrivateAccessError:
        raise HTTPException(
            status_code=403, detail={"code": "PRIVATE_ACCESS_TOKEN_REQUIRED"}
        ) from None
    except ClinicalError as error:
        raise _clinical_error(error) from None
    return StreamingResponse(
        handle,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post(
    "/labs/{document_id}/access-grant",
    dependencies=[Depends(require_trusted_origin)],
)
def grant_lab_document_access(
    document_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> dict[str, object]:
    try:
        authorize_lab_access(db, user.id, document_id)
    except ClinicalError as error:
        raise _clinical_error(error) from None
    token = create_private_access_token(
        settings,
        actor_user_id=user.id,
        resource_id=document_id,
        purpose="nutrition_lab",
    )
    return {
        "access_url": f"/api/v1/nutrition/labs/{document_id}/file?token={token}",
        "expires_in_seconds": settings.private_file_access_ttl_seconds,
    }


@router.delete(
    "/labs/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_lab_document(
    document_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> None:
    try:
        delete_lab(db, user.id, document_id, settings)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.get("/physician/reviews", response_model=list[PhysicianReviewQueueItemResponse])
def read_physician_queue(
    db: DatabaseSession,
    user: CurrentUser,
    view: PhysicianQueueView = "pending",
) -> list[PhysicianReviewQueueItemResponse]:
    try:
        return [
            PhysicianReviewQueueItemResponse.model_validate(item)
            for item in review_queue(db, user.id, view)
        ]
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.get("/physician/access")
def read_physician_access(db: DatabaseSession, user: CurrentUser) -> dict[str, bool]:
    try:
        require_physician(db, user.id)
    except ClinicalError as error:
        raise _clinical_error(error) from None
    return {"authorized": True}


@router.get("/lab-requests")
def read_user_lab_requests(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    return list_lab_requests(db, user.id)


@router.get("/physician/plans/{plan_id}/labs")
def read_physician_lab_documents(
    plan_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> list[dict[str, object]]:
    try:
        return list_physician_labs(db, user.id, plan_id)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.put(
    "/physician/labs/{document_id}/review",
    dependencies=[Depends(require_trusted_origin)],
)
def update_physician_lab_review(
    document_id: UUID,
    payload: PhysicianLabReviewInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return review_lab_document(
            db,
            user.id,
            document_id,
            payload.review_status,
            payload.notes,
        )
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.put(
    "/physician/lab-requests/{request_id}",
    dependencies=[Depends(require_trusted_origin)],
)
def update_physician_lab_request(
    request_id: UUID,
    payload: PhysicianLabRequestTransitionInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    if payload.status not in {
        NutritionLabRequestStatus.REVIEWED,
        NutritionLabRequestStatus.CANCELLED,
    }:
        raise HTTPException(status_code=422, detail={"code": "INVALID_LAB_REQUEST_TRANSITION"})
    try:
        return transition_lab_request(db, user.id, request_id, payload.status)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.post(
    "/physician/reviews/{review_id}/claim",
    dependencies=[Depends(require_trusted_origin)],
)
def claim_physician_review(
    review_id: UUID, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return claim_review(db, user.id, review_id)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/request-labs",
    dependencies=[Depends(require_trusted_origin)],
)
def create_physician_lab_request(
    plan_id: UUID,
    payload: PhysicianLabRequestInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return request_labs(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.requested_tests,
            payload.user_visible_reason,
        )
    except ClinicalError as error:
        raise _clinical_error(error) from None


def _supplement_error(error: SupplementError) -> HTTPException:
    error_status = (
        status.HTTP_403_FORBIDDEN
        if error.code == "PHYSICIAN_ROLE_REQUIRED"
        else status.HTTP_409_CONFLICT
    )
    if error.code.endswith("NOT_FOUND"):
        error_status = status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=error_status, detail={"code": error.code, **error.details})


@router.get("/supplements/catalogue")
def read_supplement_catalogue(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    return list_catalogue(db)


@router.put(
    "/admin/supplements/catalogue",
    dependencies=[Depends(require_trusted_origin)],
)
def update_supplement_catalogue(
    payload: SupplementCatalogueInput, db: DatabaseSession, admin: AdminUser
) -> dict[str, object]:
    del admin
    return save_catalogue(db, payload.model_dump(mode="json"))


@router.post(
    "/physician/plans/{plan_id}/supplement-orders",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_physician_supplement_order(
    plan_id: UUID,
    payload: PhysicianSupplementOrderInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        data = payload.model_dump(mode="python", exclude={"supplement_id"})
        return create_order(db, user.id, plan_id, payload.supplement_id, data)
    except SupplementError as error:
        raise _supplement_error(error) from None


@router.get("/physician/plans/{plan_id}/supplement-orders")
def read_physician_supplement_orders(
    plan_id: UUID, db: DatabaseSession, user: CurrentUser
) -> list[dict[str, object]]:
    try:
        return list_physician_orders(db, user.id, plan_id)
    except SupplementError as error:
        raise _supplement_error(error) from None


@router.put(
    "/physician/supplement-orders/{order_id}",
    dependencies=[Depends(require_trusted_origin)],
)
def modify_physician_supplement_order(
    order_id: UUID,
    payload: PhysicianSupplementOrderInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        data = payload.model_dump(mode="python", exclude={"supplement_id"})
        return update_order(db, user.id, order_id, payload.supplement_id, data)
    except SupplementError as error:
        raise _supplement_error(error) from None


@router.post(
    "/physician/supplement-orders/{order_id}/transition",
    dependencies=[Depends(require_trusted_origin)],
)
def update_supplement_order_status(
    order_id: UUID,
    payload: SupplementTransitionInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return transition_order(
            db, user.id, order_id, NutritionSupplementOrderStatus(payload.status)
        )
    except SupplementError as error:
        raise _supplement_error(error) from None


@router.get("/supplement-orders")
def read_user_supplement_orders(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    return list_user_orders(db, user.id)


@router.post(
    "/supplement-orders/{order_id}/acknowledge",
    dependencies=[Depends(require_trusted_origin)],
)
def acknowledge_supplement_order(
    order_id: UUID,
    payload: SupplementAcknowledgementInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return acknowledge_order(db, user.id, order_id, payload.adherence_note)
    except SupplementError as error:
        raise _supplement_error(error) from None
