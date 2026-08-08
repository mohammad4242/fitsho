import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import (
    EstimateConfidence,
    NutritionEstimateStatus,
    NutritionTargetMetric,
    SafetyOutcome,
    StructuredExerciseSource,
    StructuredExerciseType,
)
from app.nutrition.exceptions import (
    GoalReselectionRequiredDomainError,
    NutritionEstimateBlockedError,
    NutritionEstimateNotFoundError,
    NutritionProductModeError,
    NutritionProfileNotFoundError,
    NutritionTargetInfeasibleDomainError,
    StructuredExerciseRequiredError,
)
from app.nutrition.models import (
    MicronutrientReference,
    NutritionEstimate,
    NutritionEstimateMicronutrientTarget,
    NutritionEstimateTarget,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionStructuredExercise,
)
from app.nutrition.schemas import (
    NutritionEstimateResponse,
    NutritionMicronutrientTargetResponse,
    NutritionTargetResponse,
    StructuredExerciseInput,
    StructuredExerciseResponse,
)
from app.nutrition.scientific import (
    FORMULA_VERSION,
    POLICY_VERSION,
    GoalReselectionRequiredError,
    ScientificInputs,
    ScientificResult,
    StructuredExercise,
    TargetInfeasibleError,
    calculate_targets,
)
from app.nutrition.service import current_safety_decision
from app.profile.enums import ProductMode, Sex, TrainingIntensity
from app.profile.models import BodyMeasurement, UserProfile
from app.profile.schemas import calculate_age
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan

AUTOMATIC_POPULATION = "Adults 18-100 without a manual-only nutrition safety state"
MICRONUTRIENT_POLICY_VERSION = "micronutrient-dri-v1"

_ADULT_MET_VALUES = {
    TrainingIntensity.LIGHT: Decimal("2.5"),
    TrainingIntensity.MODERATE: Decimal("4.5"),
    TrainingIntensity.VIGOROUS: Decimal("7.0"),
}
_OLDER_MET_VALUES = {
    TrainingIntensity.LIGHT: Decimal("2.3"),
    TrainingIntensity.MODERATE: Decimal("4.3"),
    TrainingIntensity.VIGOROUS: Decimal("6.3"),
}


@dataclass(frozen=True)
class ResolvedStructuredExercise:
    trains: bool
    exercise_type: StructuredExerciseType | None
    days_per_week: int | None
    minutes_per_session: int | None
    intensity: TrainingIntensity | None
    source: StructuredExerciseSource
    active_plan_id: UUID | None = None

    def response(self) -> StructuredExerciseResponse:
        return StructuredExerciseResponse(
            trains=self.trains,
            exercise_type=self.exercise_type,
            days_per_week=self.days_per_week,
            minutes_per_session=self.minutes_per_session,
            intensity=self.intensity,
            source=self.source,
        )


@dataclass(frozen=True)
class EstimateContext:
    db: Session
    profile: UserProfile
    nutrition_profile: NutritionProfile
    safety: NutritionSafetyDecision
    measurement: BodyMeasurement
    exercise: ResolvedStructuredExercise
    inputs: ScientificInputs
    snapshot: dict[str, object]
    signature: str


def save_structured_exercise(
    db: Session,
    user_id: UUID,
    payload: StructuredExerciseInput,
) -> StructuredExerciseResponse:
    profile = db.get(UserProfile, user_id)
    if profile is None or profile.product_mode is not ProductMode.NUTRITION:
        raise NutritionProductModeError
    if db.get(NutritionProfile, user_id) is None:
        raise NutritionProfileNotFoundError
    exercise = db.get(NutritionStructuredExercise, user_id)
    values = {
        "trains": payload.trains,
        "exercise_type": payload.exercise_type,
        "days_per_week": payload.days_per_week,
        "minutes_per_session": payload.minutes_per_session,
        "intensity": payload.intensity,
        "source": StructuredExerciseSource.USER_REPORTED,
    }
    if exercise is None:
        exercise = NutritionStructuredExercise(user_id=user_id, **values)
        db.add(exercise)
    else:
        for field_name, value in values.items():
            setattr(exercise, field_name, value)
    try:
        db.commit()
        db.refresh(exercise)
    except SQLAlchemyError:
        db.rollback()
        raise
    return _stored_exercise(exercise).response()


def get_structured_exercise(db: Session, user_id: UUID) -> StructuredExerciseResponse:
    return _resolve_exercise(db, _required_profile(db, user_id)).response()


def create_estimate(db: Session, user_id: UUID) -> NutritionEstimateResponse:
    context = _estimate_context(db, user_id)
    existing = db.scalar(
        select(NutritionEstimate)
        .where(
            NutritionEstimate.user_id == user_id,
            NutritionEstimate.input_signature == context.signature,
            NutritionEstimate.policy_version == POLICY_VERSION,
        )
        .options(selectinload(NutritionEstimate.targets))
        .options(selectinload(NutritionEstimate.micronutrient_targets))
    )
    if existing is not None:
        return estimate_response(existing, is_stale=False)

    try:
        result = calculate_targets(context.inputs)
    except GoalReselectionRequiredError as error:
        raise GoalReselectionRequiredDomainError from error
    except TargetInfeasibleError as error:
        raise NutritionTargetInfeasibleDomainError(error.reason_codes) from error
    latest_revision = db.scalar(
        select(NutritionEstimate.revision)
        .where(NutritionEstimate.user_id == user_id)
        .order_by(NutritionEstimate.revision.desc())
        .limit(1)
    )
    estimate_id = uuid4()
    estimate = NutritionEstimate(
        id=estimate_id,
        user_id=user_id,
        safety_decision_id=context.safety.id,
        policy_version=POLICY_VERSION,
        formula_version=FORMULA_VERSION,
        revision=(latest_revision or 0) + 1,
        input_signature=context.signature,
        input_snapshot=context.snapshot,
        status=(
            NutritionEstimateStatus.ACTIVE
            if context.safety.outcome is SafetyOutcome.STANDARD_AUTOMATIC
            else NutritionEstimateStatus.REVIEW_REQUIRED
        ),
        overall_confidence=EstimateConfidence(result.confidence),
        confidence_reasons=list(result.confidence_reasons),
        targets=_target_rows(estimate_id, result),
        micronutrient_targets=_micronutrient_rows(estimate_id, context),
    )
    db.add(estimate)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = db.scalar(
            select(NutritionEstimate)
            .where(
                NutritionEstimate.user_id == user_id,
                NutritionEstimate.input_signature == context.signature,
                NutritionEstimate.policy_version == POLICY_VERSION,
            )
            .options(selectinload(NutritionEstimate.targets))
            .options(selectinload(NutritionEstimate.micronutrient_targets))
        )
        if raced is None:
            raise
        return estimate_response(raced, is_stale=False)
    return estimate_response(_get_estimate(db, estimate_id), is_stale=False)


def current_estimate(db: Session, user_id: UUID) -> NutritionEstimateResponse:
    estimate = db.scalar(
        select(NutritionEstimate)
        .where(NutritionEstimate.user_id == user_id)
        .options(selectinload(NutritionEstimate.targets))
        .options(selectinload(NutritionEstimate.micronutrient_targets))
        .order_by(NutritionEstimate.revision.desc())
        .limit(1)
    )
    if estimate is None:
        raise NutritionEstimateNotFoundError
    try:
        signature = _estimate_context(db, user_id).signature
    except (
        NutritionEstimateBlockedError,
        NutritionProfileNotFoundError,
        StructuredExerciseRequiredError,
    ):
        signature = ""
    return estimate_response(estimate, is_stale=signature != estimate.input_signature)


def estimate_response(
    estimate: NutritionEstimate,
    *,
    is_stale: bool,
) -> NutritionEstimateResponse:
    targets = {
        target.metric.value: NutritionTargetResponse(
            unit=target.unit,
            minimum=_float_or_none(target.minimum_value),
            preferred=_float_or_none(target.preferred_value),
            preferred_maximum=_float_or_none(target.preferred_maximum_value),
            maximum=_float_or_none(target.maximum_value),
            confidence=target.confidence,
            source_ids=target.source_ids,
            explanation_codes=target.explanation_codes,
        )
        for target in estimate.targets
    }
    micronutrients = {
        target.nutrient_code: NutritionMicronutrientTargetResponse(
            reference_kind=target.reference_kind,
            target_value=float(target.target_value),
            unit=target.unit,
            unit_form=target.unit_form,
            upper_limit_value=_float_or_none(target.upper_limit_value),
            upper_limit_kind=target.upper_limit_kind,
            upper_limit_scope=target.upper_limit_scope,
            aggregation_window=target.aggregation_window,
            policy_version=target.policy_version,
            source_reference=target.source_reference,
            applicable_population=target.applicable_population,
            confidence=target.confidence,
            explanation_codes=target.explanation_codes,
        )
        for target in estimate.micronutrient_targets
    }
    return NutritionEstimateResponse(
        id=estimate.id,
        revision=estimate.revision,
        status=estimate.status,
        policy_version=estimate.policy_version,
        formula_version=estimate.formula_version,
        confidence=estimate.overall_confidence,
        confidence_reasons=estimate.confidence_reasons,
        is_stale=is_stale,
        targets=targets,
        micronutrients=micronutrients,
        created_at=estimate.created_at,
    )


def _estimate_context(db: Session, user_id: UUID) -> EstimateContext:
    profile = _required_profile(db, user_id)
    safety = current_safety_decision(db, user_id)
    if safety.outcome in {
        SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
        SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED,
    }:
        raise NutritionEstimateBlockedError
    nutrition_profile = db.get(NutritionProfile, user_id)
    if nutrition_profile is None:
        raise NutritionProfileNotFoundError
    measurement = db.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == user_id)
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
        .limit(1)
    )
    if measurement is None:
        raise NutritionProfileNotFoundError
    exercise = _resolve_exercise(db, profile)
    assert profile.birth_date is not None
    assert profile.height_cm is not None
    assert profile.fitness_goal is not None
    age = calculate_age(profile.birth_date, date.today())
    metabolic_basis = _metabolic_basis(profile, nutrition_profile)
    scientific_exercise = _scientific_exercise(age, exercise)
    inputs = ScientificInputs(
        age=age,
        height_cm=Decimal(profile.height_cm),
        weight_kg=measurement.weight_kg,
        metabolic_basis=metabolic_basis,
        daily_activity_level=nutrition_profile.daily_activity_level.value,
        fitness_goal=profile.fitness_goal.value,
        structured_exercise=scientific_exercise,
    )
    snapshot: dict[str, object] = {
        "product_mode": profile.product_mode.value,
        "birth_date": profile.birth_date.isoformat(),
        "calculation_date": date.today().isoformat(),
        "age": age,
        "height_cm": profile.height_cm,
        "weight_kg": str(measurement.weight_kg),
        "weight_measured_at": measurement.measured_at.isoformat(),
        "profile_sex": profile.sex.value if profile.sex is not None else None,
        "metabolic_basis": metabolic_basis,
        "fitness_goal": profile.fitness_goal.value,
        "daily_activity_level": nutrition_profile.daily_activity_level.value,
        "structured_exercise": _exercise_snapshot(exercise),
        "safety_decision_id": str(safety.id),
        "safety_outcome": safety.outcome.value,
        "medical_policy_version": safety.medical_condition_policy_version,
        "nutrition_policy_version": POLICY_VERSION,
        "formula_version": FORMULA_VERSION,
    }
    signature = sha256(
        json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return EstimateContext(
        db=db,
        profile=profile,
        nutrition_profile=nutrition_profile,
        safety=safety,
        measurement=measurement,
        exercise=exercise,
        inputs=inputs,
        snapshot=snapshot,
        signature=signature,
    )


def _required_profile(db: Session, user_id: UUID) -> UserProfile:
    profile = db.get(UserProfile, user_id)
    if (
        profile is None
        or profile.product_mode not in {ProductMode.NUTRITION, ProductMode.BOTH}
        or profile.display_name is None
        or profile.birth_date is None
        or profile.sex is None
        or profile.height_cm is None
        or profile.fitness_goal is None
    ):
        raise NutritionProfileNotFoundError
    return profile


def _resolve_exercise(db: Session, profile: UserProfile) -> ResolvedStructuredExercise:
    if profile.product_mode is ProductMode.NUTRITION:
        stored = db.get(NutritionStructuredExercise, profile.user_id)
        if stored is None:
            raise StructuredExerciseRequiredError
        return _stored_exercise(stored)
    if profile.product_mode is not ProductMode.BOTH:
        raise NutritionProductModeError
    if (
        profile.training_days_per_week is None
        or profile.session_duration_minutes is None
        or profile.training_intensity is None
    ):
        raise StructuredExerciseRequiredError

    active_plan = db.scalar(
        select(WorkoutPlan)
        .where(
            WorkoutPlan.user_id == profile.user_id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
        .options(selectinload(WorkoutPlan.days))
        .order_by(WorkoutPlan.activated_at.desc())
        .limit(1)
    )
    if active_plan is not None and active_plan.days:
        minutes = round(
            sum(day.estimated_duration_minutes for day in active_plan.days) / len(active_plan.days)
        )
        return ResolvedStructuredExercise(
            trains=True,
            exercise_type=StructuredExerciseType.RESISTANCE,
            days_per_week=len(active_plan.days),
            minutes_per_session=minutes,
            intensity=profile.training_intensity,
            source=StructuredExerciseSource.ACTIVE_FITSHO_PLAN,
            active_plan_id=active_plan.id,
        )
    return ResolvedStructuredExercise(
        trains=True,
        exercise_type=StructuredExerciseType.RESISTANCE,
        days_per_week=profile.training_days_per_week,
        minutes_per_session=profile.session_duration_minutes,
        intensity=profile.training_intensity,
        source=StructuredExerciseSource.TRAINING_PROFILE,
    )


def _stored_exercise(exercise: NutritionStructuredExercise) -> ResolvedStructuredExercise:
    return ResolvedStructuredExercise(
        trains=exercise.trains,
        exercise_type=exercise.exercise_type,
        days_per_week=exercise.days_per_week,
        minutes_per_session=exercise.minutes_per_session,
        intensity=exercise.intensity,
        source=exercise.source,
    )


def _scientific_exercise(
    age: int,
    exercise: ResolvedStructuredExercise,
) -> StructuredExercise | None:
    if not exercise.trains:
        return None
    assert exercise.exercise_type is not None
    assert exercise.days_per_week is not None
    assert exercise.minutes_per_session is not None
    assert exercise.intensity is not None
    older = age >= 60
    return StructuredExercise(
        exercise_type=exercise.exercise_type.value,
        days_per_week=exercise.days_per_week,
        minutes_per_session=exercise.minutes_per_session,
        met_value=(_OLDER_MET_VALUES if older else _ADULT_MET_VALUES)[exercise.intensity],
        met_baseline_kcal_per_kg_hour=Decimal("0.810") if older else Decimal("1.0"),
    )


def _metabolic_basis(
    profile: UserProfile,
    nutrition_profile: NutritionProfile,
) -> Literal["female_coefficient", "male_coefficient"] | None:
    if profile.sex is Sex.FEMALE:
        return "female_coefficient"
    if profile.sex is Sex.MALE:
        return "male_coefficient"
    if nutrition_profile.metabolic_basis is None:
        return None
    if nutrition_profile.metabolic_basis.value == "female_coefficient":
        return "female_coefficient"
    return "male_coefficient"


def _exercise_snapshot(exercise: ResolvedStructuredExercise) -> dict[str, object]:
    return {
        "trains": exercise.trains,
        "exercise_type": exercise.exercise_type.value if exercise.exercise_type else None,
        "days_per_week": exercise.days_per_week,
        "minutes_per_session": exercise.minutes_per_session,
        "intensity": exercise.intensity.value if exercise.intensity else None,
        "source": exercise.source.value,
        "active_plan_id": str(exercise.active_plan_id) if exercise.active_plan_id else None,
    }


def _target_rows(estimate_id: UUID, result: ScientificResult) -> list[NutritionEstimateTarget]:
    bands = {
        NutritionTargetMetric.BMR: result.bmr,
        NutritionTargetMetric.NON_EXERCISE_ENERGY: result.non_exercise_energy,
        NutritionTargetMetric.EXERCISE_ENERGY: result.exercise_energy,
        NutritionTargetMetric.TDEE: result.tdee,
        NutritionTargetMetric.GOAL_CALORIES: result.goal_calories,
        NutritionTargetMetric.PROTEIN: result.protein,
        NutritionTargetMetric.CARBOHYDRATE: result.carbohydrate,
        NutritionTargetMetric.TOTAL_FAT: result.total_fat,
        NutritionTargetMetric.FIBRE: result.fibre,
        NutritionTargetMetric.FREE_SUGAR: result.free_sugar,
        NutritionTargetMetric.ADDED_SUGAR: result.added_sugar,
        NutritionTargetMetric.SATURATED_FAT: result.saturated_fat,
        NutritionTargetMetric.TRANS_FAT: result.trans_fat,
        NutritionTargetMetric.SODIUM: result.sodium,
    }
    confidence = EstimateConfidence(result.confidence)
    return [
        NutritionEstimateTarget(
            estimate_id=estimate_id,
            metric=metric,
            unit=band.unit,
            minimum_value=band.minimum,
            preferred_value=band.preferred,
            preferred_maximum_value=band.preferred_maximum,
            maximum_value=band.maximum,
            confidence=confidence,
            source_ids=_source_ids(metric),
            applicable_population=AUTOMATIC_POPULATION,
            rounding_rule="10 kcal display; 1 g nutrients; 10 mg sodium",
            explanation_codes=[f"{metric.value.upper()}_ESTIMATE", *result.confidence_reasons],
        )
        for metric, band in bands.items()
    ]


def _micronutrient_rows(
    estimate_id: UUID, context: EstimateContext
) -> list[NutritionEstimateMicronutrientTarget]:
    sex = context.profile.sex.value if context.profile.sex is not None else "all"
    references = context.db.scalars(
        select(MicronutrientReference).where(
            MicronutrientReference.policy_version == MICRONUTRIENT_POLICY_VERSION,
            MicronutrientReference.age_min <= context.inputs.age,
            (MicronutrientReference.age_max.is_(None))
            | (MicronutrientReference.age_max >= context.inputs.age),
        )
    ).all()
    selected: dict[str, MicronutrientReference] = {}
    for reference in references:
        if reference.sex.value not in {"all", sex}:
            continue
        if reference.dietary_pattern_modifier not in {
            "none",
            context.nutrition_profile.dietary_pattern.value,
        }:
            continue
        if reference.reference_kind.value not in {"rda", "ai", "medical_override"}:
            continue
        current = selected.get(reference.nutrient_code)
        rank = (
            reference.reference_kind.value == "medical_override",
            reference.reference_kind.value == "rda",
            reference.sex.value == sex,
            reference.dietary_pattern_modifier != "none",
            reference.age_min,
        )
        if current is None or rank > (
            current.reference_kind.value == "medical_override",
            current.reference_kind.value == "rda",
            current.sex.value == sex,
            current.dietary_pattern_modifier != "none",
            current.age_min,
        ):
            selected[reference.nutrient_code] = reference

    rows: list[NutritionEstimateMicronutrientTarget] = []
    for nutrient, reference in selected.items():
        upper = next(
            (
                candidate
                for candidate in references
                if candidate.nutrient_code == nutrient
                and candidate.reference_kind.value in {"ul", "cdrr"}
                and candidate.sex.value in {"all", sex}
            ),
            None,
        )
        rows.append(
            NutritionEstimateMicronutrientTarget(
                estimate_id=estimate_id,
                nutrient_code=nutrient,
                reference_kind=reference.reference_kind.value,
                target_value=reference.target_value,
                unit=reference.unit,
                unit_form=reference.unit_form,
                upper_limit_value=upper.target_value if upper else None,
                upper_limit_kind=upper.reference_kind.value if upper else None,
                upper_limit_scope=upper.upper_limit_scope.value if upper else "none",
                aggregation_window=reference.aggregation_window.value,
                policy_version=reference.policy_version,
                source_reference=reference.source_reference,
                applicable_population=(
                    f"age {reference.age_min}-{reference.age_max or 'plus'}, "
                    f"sex {reference.sex.value}, life stage {reference.life_stage}"
                ),
                confidence=EstimateConfidence.HIGH,
                explanation_codes=[
                    "MICRONUTRIENT_REFERENCE_SELECTED",
                    "DIETARY_INTAKE_IS_NOT_DIAGNOSIS",
                ],
            )
        )
    return rows


def _source_ids(metric: NutritionTargetMetric) -> list[str]:
    if metric is NutritionTargetMetric.BMR:
        return ["mifflin-1990-pmid-2305711"]
    if metric in {
        NutritionTargetMetric.NON_EXERCISE_ENERGY,
        NutritionTargetMetric.EXERCISE_ENERGY,
        NutritionTargetMetric.TDEE,
        NutritionTargetMetric.GOAL_CALORIES,
    }:
        return ["nasem-energy-2023", "compendium-2024"]
    if metric is NutritionTargetMetric.PROTEIN:
        return ["nasem-dri-2005", "morton-pmid-28698222", "espen-adjusted-weight-2022"]
    if metric is NutritionTargetMetric.SODIUM:
        return ["nasem-sodium-potassium-2019"]
    return ["who-healthy-diet-2026"]


def _get_estimate(db: Session, estimate_id: UUID) -> NutritionEstimate:
    estimate = db.scalar(
        select(NutritionEstimate)
        .where(NutritionEstimate.id == estimate_id)
        .options(selectinload(NutritionEstimate.targets))
    )
    if estimate is None:
        raise NutritionEstimateNotFoundError
    return estimate


def _float_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
