"""Safe, non-persistent task checks for Agent Service profiles."""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import httpx
from PIL import Image, ImageDraw
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.schemas import WorkoutProviderError
from app.body_analysis.admin_config.enums import AIAgentName, AITaskType
from app.body_analysis.admin_config.schemas import (
    AgentServiceModelProfile,
    AgentServiceTaskSmokeResponse,
)
from app.body_analysis.admin_config.service import get_agent_service_capabilities
from app.body_analysis.normalization import (
    normalize_visual_physique_assessment_v4,
    visual_assessment_v4_to_normalized,
)
from app.body_analysis.providers import (
    AgentServiceProvider,
    AIProvider,
    AIProviderError,
    ImageInput,
    ModelRoute,
    ProviderErrorCode,
    ProviderRoutingPreferences,
)
from app.body_analysis.service import AnalysisExecutionConfig, BodyAnalysisService
from app.config import Settings
from app.nutrition.ai_price_research import (
    FoodPriceResearchFood,
    FoodPriceResearchOutput,
    build_food_price_research_request,
    canonical_source_domain,
)
from app.nutrition.food_photo_service import FoodPhotoOutput, build_food_photo_request
from app.nutrition.pricing import PriceObservation, normalize_observation
from app.nutrition.public_price_matching import CanonicalFoodIdentity, match_candidate
from app.nutrition.public_price_sources import PublicProductCandidate
from app.workouts.ai_coach_provider import AiCoachProvider, AiCoachRecommendationRequest

SmokeStage = Literal[
    "backend_request",
    "agent_service",
    "runner",
    "schema",
    "semantic_validation",
    "passed",
    "failed",
]


@dataclass(frozen=True)
class TaskSmokeResult:
    passed: bool
    stage: SmokeStage
    request_id: str | None
    duration_seconds: float
    error_code: str | None = None
    safe_error_message: str | None = None


class TaskSmokeFailure(Exception):
    def __init__(self, stage: SmokeStage, code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message


async def run_task_smoke(
    db: Session,
    *,
    task_type: AITaskType,
    agent: AIAgentName,
    profile_id: str,
    settings: Settings,
    client: httpx.AsyncClient,
    provider: AIProvider | None = None,
) -> tuple[TaskSmokeResult, AgentServiceModelProfile | None]:
    started = time.perf_counter()
    profile: AgentServiceModelProfile | None = None
    request_id: str | None = None
    try:
        capabilities = await get_agent_service_capabilities(
            client=client,
            settings=settings,
            db=db,
            task_type=task_type,
        )
        runner = next((item for item in capabilities.runners if item.agent is agent), None)
        profile = (
            next(
                (item for item in (runner.profiles or []) if item.profile_id == profile_id),
                None,
            )
            if runner is not None
            else None
        )
        if runner is None or profile is None:
            raise TaskSmokeFailure(
                "backend_request", "model_not_found", "The selected profile is unavailable."
            )
        if task_type not in profile.task_kinds:
            raise TaskSmokeFailure(
                "backend_request", "invalid_request", "The profile does not support this task."
            )
        if (
            task_type in {AITaskType.BODY_PHOTO_ANALYSIS, AITaskType.FOOD_PHOTO_ESTIMATION}
            and not profile.supports_image_input
        ):
            raise TaskSmokeFailure(
                "backend_request", "invalid_request", "The profile does not support image input."
            )
        if task_type is AITaskType.FOOD_PRICE_SEARCH and (
            not profile.supports_text_input
            or not profile.supports_structured_output
            or not profile.supports_live_web
        ):
            raise TaskSmokeFailure(
                "backend_request",
                "invalid_request",
                "The profile does not support live web research.",
            )
        if provider is None:
            provider = AgentServiceProvider(
                client,
                base_url=settings.agent_service_base_url,
                token=settings.agent_service_token,
                agent_name=agent.value,
                profile_id=profile.profile_id,
                # A task smoke may require a real image/tool turn. Keep it
                # bounded, but do not reuse the short capabilities connect
                # timeout for a provider completion.
                timeout_seconds=min(
                    300.0,
                    max(30.0, float(settings.agent_service_connect_timeout_seconds * 60)),
                ),
            )
        if task_type is AITaskType.WORKOUT_PLAN_GENERATION:
            request_id = await _smoke_workout(provider, profile)
        elif task_type is AITaskType.BODY_PHOTO_ANALYSIS:
            request_id = await _smoke_body(provider, profile)
        elif task_type is AITaskType.FOOD_PHOTO_ESTIMATION:
            request_id = await _smoke_food_photo(provider, profile)
        elif task_type is AITaskType.FOOD_PRICE_SEARCH:
            request_id = await _smoke_food_price(provider, profile)
        else:
            raise TaskSmokeFailure(
                "backend_request", "invalid_request", "This task is not supported."
            )
    except TaskSmokeFailure as error:
        return (
            TaskSmokeResult(
                passed=False,
                stage=error.stage,
                request_id=request_id,
                duration_seconds=time.perf_counter() - started,
                error_code=error.code,
                safe_error_message=error.message,
            ),
            profile,
        )
    except AIProviderError as error:
        return (
            TaskSmokeResult(
                passed=False,
                stage="agent_service",
                request_id=error.provider_request_id,
                duration_seconds=time.perf_counter() - started,
                error_code=error.code.value,
                safe_error_message=error.safe_message,
            ),
            profile,
        )
    except WorkoutProviderError as error:
        return (
            TaskSmokeResult(
                passed=False,
                stage=(
                    "semantic_validation"
                    if error.code.value == "invalid_output"
                    else "agent_service"
                ),
                request_id=None,
                duration_seconds=time.perf_counter() - started,
                error_code=error.code.value,
                safe_error_message=error.safe_message,
            ),
            profile,
        )
    except (ValidationError, ValueError, TypeError) as error:
        del error
        return (
            TaskSmokeResult(
                passed=False,
                stage="semantic_validation",
                request_id=None,
                duration_seconds=time.perf_counter() - started,
                error_code=ProviderErrorCode.INVALID_OUTPUT.value,
                safe_error_message="The selected profile returned an invalid task result.",
            ),
            profile,
        )
    return (
        TaskSmokeResult(
            passed=True,
            stage="passed",
            request_id=request_id,
            duration_seconds=time.perf_counter() - started,
        ),
        profile,
    )


async def _smoke_workout(provider: AIProvider, profile: AgentServiceModelProfile) -> str | None:
    candidates: tuple[dict[str, object], ...] = (
        {"candidate_id": "smoke-upper", "days": [{"day_number": 1, "title": "Upper"}]},
        {"candidate_id": "smoke-lower", "days": [{"day_number": 1, "title": "Lower"}]},
    )
    recommendation = await AiCoachProvider(provider).recommend(
        AiCoachRecommendationRequest(
            profile={"fitness_goal": "build_muscle", "training_days_per_week": 1},
            candidate_programs=candidates,
            primary_model=profile.model_id,
            fallback_models=(),
            temperature=0,
            max_output_tokens=512,
            routing_preferences=ProviderRoutingPreferences(),
        )
    )
    if recommendation.selected_candidate_id not in {"smoke-upper", "smoke-lower"}:
        raise TaskSmokeFailure(
            "semantic_validation",
            "invalid_output",
            "The workout result selected an unavailable candidate.",
        )
    return recommendation.provider_request_id


async def _smoke_body(provider: AIProvider, profile: AgentServiceModelProfile) -> str | None:
    config = AnalysisExecutionConfig(
        provider_name=f"agent_service:{profile.agent.value}",
        primary_model=profile.model_id,
        prompt_version="body-analysis-v4-evidence",
        schema_version="4.0",
        temperature=0,
        max_output_tokens=4096,
    )
    images = _body_fixture_images()
    response = await provider.analyze_images(BodyAnalysisService._request(config), images=images)
    visual = normalize_visual_physique_assessment_v4(response.payload)
    if visual.assessment_status != "complete":
        raise TaskSmokeFailure(
            "semantic_validation",
            "invalid_output",
            "The body result was not a complete three-view assessment.",
        )
    normalized = visual_assessment_v4_to_normalized(visual)
    if normalized.schema_version != "4.0" or normalized.overall_confidence <= 0:
        raise TaskSmokeFailure(
            "semantic_validation",
            "invalid_output",
            "The body result failed semantic validation.",
        )
    return response.provider_request_id


async def _smoke_food_photo(provider: AIProvider, profile: AgentServiceModelProfile) -> str | None:
    request = build_food_photo_request(
        primary_model=profile.model_id,
        fallback_models=(),
        provider_preferences=ProviderRoutingPreferences(),
        temperature=0,
        max_output_tokens=1024,
    )
    response = await provider.analyze_images(request, images=(_meal_fixture_image(),))
    FoodPhotoOutput.model_validate(response.payload)
    return response.provider_request_id


async def _smoke_food_price(provider: AIProvider, profile: AgentServiceModelProfile) -> str | None:
    food = FoodPriceResearchFood(
        slug="smoke-iranian-rice",
        name_fa="برنج ایرانی",
        name_en="Iranian rice",
        category="grains",
        aliases=("برنج",),
    )
    request = build_food_price_research_request(
        food,
        route=ModelRoute(primary_model=profile.model_id),
        requested_source_count=3,
        provider_preferences=ProviderRoutingPreferences(),
        temperature=0,
        max_output_tokens=1024,
    )
    response = await provider.generate_structured_text(request)
    result = FoodPriceResearchOutput.model_validate(response.payload)
    if result.food_slug != food.slug:
        raise TaskSmokeFailure(
            "semantic_validation",
            "invalid_output",
            "The price search food was not preserved.",
        )
    if len(result.quotes) < 3:
        raise TaskSmokeFailure(
            "semantic_validation",
            "invalid_output",
            "The price search did not return three independent sources.",
        )
    identity = CanonicalFoodIdentity(
        slug=food.slug,
        name_fa=food.name_fa,
        category=food.category,
        aliases=food.aliases,
    )
    domains: set[str] = set()
    units: set[str] = set()
    for quote in result.quotes:
        source_domain = canonical_source_domain(quote.source_url)
        if source_domain in domains:
            raise TaskSmokeFailure(
                "semantic_validation",
                "invalid_output",
                "The price search returned duplicate source domains.",
            )
        observation = PriceObservation(
            provider_code="smoke",
            provider_product_id=source_domain,
            product_title=quote.product_title,
            currency=quote.currency,
            normal_price=quote.normal_price,
            promotional_price=quote.promotional_price,
            package_quantity=quote.package_quantity,
            package_unit=quote.package_unit,
            observed_at=datetime.now(),
            region=quote.region,
        )
        normalized = normalize_observation(observation)
        candidate = PublicProductCandidate(
            provider_code=observation.provider_code,
            product_id=observation.provider_product_id,
            title=observation.product_title,
            public_url=quote.source_url,
            currency=observation.currency,
            normal_price=observation.normal_price,
            promotional_price=observation.promotional_price,
            package_quantity=observation.package_quantity,
            package_unit=observation.package_unit,
            observed_at=observation.observed_at,
            region=observation.region,
        )
        if not match_candidate(identity, candidate).accepted:
            raise TaskSmokeFailure(
                "semantic_validation",
                "invalid_output",
                "The price search returned a mismatched product.",
            )
        domains.add(source_domain)
        units.add(normalized.canonical_unit)
    if len(domains) < 3 or len(units) != 1:
        raise TaskSmokeFailure(
            "semantic_validation",
            "invalid_output",
            "The price search returned insufficient comparable evidence.",
        )
    return response.provider_request_id


def _body_fixture_images() -> tuple[ImageInput, ...]:
    return tuple(
        ImageInput(label=view, mime_type="image/jpeg", base64_data=_fixture_jpeg(view, body=True))
        for view in ("front", "side", "back")
    )


def _meal_fixture_image() -> ImageInput:
    return ImageInput(label="meal", mime_type="image/jpeg", base64_data=_fixture_jpeg("meal"))


def _fixture_jpeg(label: str, *, body: bool = False) -> str:
    image = Image.new("RGB", (512, 768 if body else 512), (226, 226, 226))
    draw = ImageDraw.Draw(image)
    if body:
        # A privacy-safe, headless mannequin with genuinely distinct views. A
        # flat gray silhouette made vision models classify side/back as the
        # wrong view, so the fixture uses simple clothing and body landmarks.
        draw.ellipse((125, 710, 390, 750), fill=(190, 190, 190))
        skin = (205, 150, 102)
        top = (50, 74, 104)
        shorts = (45, 48, 55)
        shoe = (35, 35, 38)
        if label == "front":
            draw.rectangle((232, 70, 280, 145), fill=skin)
            draw.rounded_rectangle((170, 125, 342, 370), radius=42, fill=top)
            draw.polygon([(175, 145), (145, 185), (155, 200), (195, 175)], fill=skin)
            draw.polygon([(337, 145), (367, 185), (357, 200), (317, 175)], fill=skin)
            draw.rounded_rectangle((185, 342, 327, 445), radius=18, fill=shorts)
            draw.polygon([(192, 430), (246, 430), (238, 665), (200, 665)], fill=skin)
            draw.polygon([(266, 430), (320, 430), (312, 665), (274, 665)], fill=skin)
            draw.rounded_rectangle((192, 655, 244, 710), radius=12, fill=shoe)
            draw.rounded_rectangle((268, 655, 320, 710), radius=12, fill=shoe)
        elif label == "side":
            draw.rectangle((244, 70, 276, 145), fill=skin)
            draw.rounded_rectangle((220, 125, 302, 370), radius=30, fill=top)
            draw.polygon([(286, 150), (326, 205), (310, 220), (278, 180)], fill=skin)
            draw.rounded_rectangle((225, 342, 300, 445), radius=16, fill=shorts)
            draw.polygon([(230, 430), (269, 430), (267, 665), (238, 665)], fill=skin)
            draw.polygon([(270, 430), (302, 430), (319, 665), (291, 665)], fill=skin)
            draw.rounded_rectangle((230, 655, 270, 710), radius=12, fill=shoe)
            draw.rounded_rectangle((290, 655, 330, 710), radius=12, fill=shoe)
        else:
            draw.rectangle((232, 70, 280, 145), fill=skin)
            draw.rounded_rectangle((170, 125, 342, 370), radius=42, fill=top)
            draw.polygon([(175, 145), (145, 185), (155, 200), (195, 175)], fill=skin)
            draw.polygon([(337, 145), (367, 185), (357, 200), (317, 175)], fill=skin)
            draw.rounded_rectangle((185, 342, 327, 445), radius=18, fill=shorts)
            draw.polygon([(192, 430), (246, 430), (238, 665), (200, 665)], fill=skin)
            draw.polygon([(266, 430), (320, 430), (312, 665), (274, 665)], fill=skin)
            draw.rounded_rectangle((192, 655, 244, 710), radius=12, fill=shoe)
            draw.rounded_rectangle((268, 655, 320, 710), radius=12, fill=shoe)
            draw.line((200, 170, 312, 170), fill=(120, 165, 195), width=5)
        draw.text((16, 16), label, fill=(45, 45, 45))
    else:
        draw.ellipse((112, 120, 275, 282), fill=(201, 155, 95))
        draw.ellipse((240, 184, 402, 346), fill=(120, 165, 92))
        draw.rectangle((145, 300, 380, 385), fill=(220, 220, 220), outline=(90, 90, 90), width=4)
        draw.text((16, 16), "synthetic meal", fill=(45, 45, 45))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return base64.b64encode(output.getvalue()).decode("ascii")


def smoke_response(
    *,
    task_type: AITaskType,
    agent: AIAgentName,
    profile_id: str,
    fingerprint: str | None,
    result: TaskSmokeResult,
    checked_at: datetime,
) -> AgentServiceTaskSmokeResponse:
    return AgentServiceTaskSmokeResponse(
        ok=result.passed,
        task_type=task_type,
        agent=agent,
        profile_id=profile_id,
        fingerprint=fingerprint,
        stage=result.stage,
        request_id=result.request_id,
        checked_at=checked_at,
        duration_seconds=result.duration_seconds,
        error_code=result.error_code,
        safe_error_message=result.safe_error_message,
    )
