#!/usr/bin/env python3
# ruff: noqa: E501, E402
"""100-profile randomized audit script against the real Fitsho Nutrition Engine.

Generates deterministic randomized profiles, executes weekly plan generation against
the real production engine, records structured JSON data, and compiles a comprehensive
Persian PDF audit report.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import weasyprint
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

# Ensure all SQLAlchemy models and relationships are registered
import app.main  # noqa: F401
from app.auth.models import User
from app.nutrition.enums import (
    BudgetStyle,
    CookingSkill,
    DailyActivityLevel,
    DietaryPattern,
    FoodItemKind,
    MainMealCountBucket,
    MealPreparationPreference,
    MedicalConditionCode,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    PreferredVariety,
    SafetyOutcome,
    SnackCountBucket,
    StructuredExerciseSource,
    StructuredExerciseType,
    Weekday,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionEstimate,
    NutritionFoodItem,
    NutritionMedicalCondition,
    NutritionMedicalProfile,
    NutritionPlanGeneration,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionSafetyReason,
    NutritionStructuredExercise,
    NutritionWeeklyPlan,
    NutritionWeeklyPlanDay,
    NutritionWeeklyPlanFood,
    NutritionWeeklyPlanMeal,
    NutritionWeeklyPlanNutrient,
)
from app.nutrition.plan_service import generate_weekly_plan
from app.nutrition.planner_policy import PLANNER_POLICY_VERSION, PLANNER_VERSION
from app.nutrition.schemas import WeeklyPlanResponse
from app.profile.enums import FitnessGoal, ProductMode, Sex, TrainingIntensity
from app.profile.models import BodyMeasurement, UserProfile
from scripts.run_nutrition_100_profiles_audit import ProfileSpec, generate_100_profiles

DEFAULT_DB_URL = "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_nutrition_audit"

# Persian translations
FA_SEX = {"male": "مرد", "female": "زن"}
FA_GOAL = {
    "lose_weight": "کاهش وزن",
    "fat_loss": "کاهش چربی",
    "gain_weight": "افزایش وزن",
    "build_muscle": "عضله‌سازی",
    "body_recomposition": "ترکیب مجدد بدنی (ریکامپ)",
    "maintain_weight": "تثبیت وزن",
    "improve_fitness": "آمادگی جسمانی",
    "strength": "افزایش قدرت",
}
FA_ACTIVITY = {
    "sedentary": "کم‌تحرک (نشسته)",
    "light": "سبک",
    "moderate": "متوسط",
    "very_active": "بسیار پرتحرک",
}
FA_EXERCISE_TYPE = {
    "resistance": "قدرتی / بدنسازی",
    "endurance": "هوازی / استقامتی",
    "mixed": "ترکیبی",
    "other": "سایر",
}
FA_INTENSITY = {
    "light": "سبک",
    "moderate": "متوسط",
    "vigorous": "شدید",
}
FA_BUDGET_STYLE = {
    "strict": "سخت‌گیرانه",
    "flexible": "انعطاف‌پذیر",
}
FA_DIETARY_PATTERN = {
    "omnivore": "همه‌چیزخوار",
    "vegetarian": "گیاه‌خوار",
    "vegan": "وگان",
}
FA_COOKING_SKILL = {
    "none": "بدون مهارت",
    "basic": "مقدماتی",
    "confident": "ماهر",
}
FA_MEAL_PREP = {
    "daily": "روزانه",
    "batch": "پخت گروهی",
    "mixed": "ترکیبی",
    "no_cooking": "بدون پخت‌وپز",
}
FA_VARIETY = {
    "low": "کم",
    "medium": "متوسط",
    "high": "زیاد",
}
FA_WEEKDAY = {
    "saturday": "شنبه",
    "sunday": "یکشنبه",
    "monday": "دوشنبه",
    "tuesday": "سه‌شنبه",
    "wednesday": "چهارشنبه",
    "thursday": "پنج‌شنبه",
    "friday": "جمعه",
}
FA_MEAL_ROLE = {
    "breakfast": "صبحانه",
    "lunch": "ناهار",
    "dinner": "شام",
    "snack": "میان‌وعده",
    "post_workout": "بعد از تمرین",
    "pre_workout": "قبل از تمرین",
    "free_meal": "وعده آزاد",
}
FA_OUTCOME = {
    "success": "موفق",
    "infeasible": "غیرقابل اجرا (محدودیت تمپلیت/بودجه)",
    "target_infeasible": "ناممکن از نظر اهداف کالری/ماکرو",
    "safety_blocked": "توقف ایمنی پزشکی",
    "live_price_unavailable": "عدم دسترسی به قیمت‌ها",
    "failed": "ناموفق",
}
FA_REASONS = {
    "SAFE_FEASIBLE_DRAFT_GENERATED": "برنامه ایمن و قابل‌اجرا با موفقیت تولید شد",
    "NO_COMPATIBLE_TEMPLATE_SUBSTITUTE": "عدم یافتن تمپلیت سازگار در کاتالوگ با ترجیحات/رژیم غذایی کاربر",
    "INSUFFICIENT_LOW_COST_TEMPLATE_COVERAGE": "تنوع تمپلیت‌های کم‌هزینه برای سقف بودجه تعیین‌شده کافی نیست",
    "STRICT_BUDGET_EXCEEDED": "هزینه کل برنامه از سقف بودجه سخت‌گیرانه تجاوز کرد",
    "FLEXIBLE_BUDGET_CAP_EXCEEDED": "هزینه کل برنامه از سقف بودجه انعطاف‌پذیر (+۱۵٪) تجاوز کرد",
    "CALORIE_TARGET_OUTSIDE_TOLERANCE": "کالری کل خارج از محدوده مجاز هدف است",
    "CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS": "دستیابی به کالری هدف با محدودیت اندازه پرس تمپلیت‌ها ناممکن است",
    "CARBOHYDRATE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS": "تأمین کربوهیدرات هدف با محدودیت پرس‌ها امکان‌پذیر نیست",
    "PROTEIN_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS": "تأمین پروتئین هدف با محدودیت پرس‌ها امکان‌پذیر نیست",
    "FAT_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS": "تأمین چربی هدف با محدودیت پرس‌ها امکان‌پذیر نیست",
    "MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS": "انطباق هم‌زمان چند ماکرونوترینت با پرس‌های مجاز امکان‌پذیر نیست",
    "MACRONUTRIENT_FLOOR_NOT_MET": "حداقل فیزیولوژیک ماکرونوترینت‌ها تأمین نشد",
    "MACRONUTRIENT_MAXIMUM_EXCEEDED": "میزان ماکرونوترینت از حداکثر مجاز فراتر رفت",
    "GOAL_RESELECTION_REQUIRED": "هدف انتخابی کاربر با نوع تمرین یا ضوابط علمی همخوانی ندارد",
    "PHYSICIAN_MANUAL_PLAN_REQUIRED": "به دلیل وضعیت بالینی/پزشکی، تنظیم دستی توسط پزشک الزامی است",
    "UNSUPPORTED_OR_HARD_BLOCKED": "توقف ایمنی: شرایط بالینی پرخطر اعلام‌شده توسط کاربر",
    "SCHEDULED_MEAL_UNAVAILABLE": "تمپلیت غذایی زمان‌بندی‌شده در دسترس نیست",
    "PREFERENCE_EXCLUSION_NO_FEASIBLE_PLAN": "حذفیات یا سلیقه غذایی کاربر مانع از یافتن برنامه معتبر شد",
    "INSUFFICIENT_PRICE_COVERAGE": "پوشش قیمتی معتبر برای اقلام کاتالوگ کافی نیست",
    "AUDIT_SAFETY_INVARIANT_VIOLATION": "نقض محدودیت مستقل ایمنی در ارزیابی ممیزی",
    "UNHANDLED_ENGINE_ERROR": "خطای داخلی کنترل‌نشده در موتور برنامه‌ریز",
}


@dataclass
class AuditFoodItem:
    name_fa: str
    grams: float
    calories: float
    protein: float
    carbs: float
    fat: float
    cost_toman: int


@dataclass
class AuditMealItem:
    role: str
    role_fa: str
    name_fa: str
    calories: float
    protein: float
    carbs: float
    fat: float
    cost_toman: int
    foods: list[AuditFoodItem]


@dataclass
class AuditDayItem:
    day_index: int
    day_name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    cost_toman: int
    meals: list[AuditMealItem]


@dataclass
class AuditRecordDetail:
    spec: ProfileSpec
    outcome: str
    outcome_fa: str
    is_success: bool
    reason_codes: list[str]
    warning_codes: list[str]
    failure_stage_fa: str
    human_reason_fa: str
    generation_duration_seconds: float
    target_calories: float | None
    target_protein: float | None
    target_carbs: float | None
    target_fat: float | None
    bmr: float | None
    tdee: float | None
    weekly_budget_toman: int
    actual_weekly_cost_toman: int | None
    plan_id: str | None
    selected_program_code: str | None
    days: list[AuditDayItem]
    target_vs_actual: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    budget_tier: str | None = None
    requested_weight_change_kg_per_week: float | None = None
    recommended_weight_change_kg_per_week: float | None = None
    applied_weight_change_kg_per_week: float | None = None
    goal_strategy: str | None = None
    goal_strategy_version: str | None = None

    programs_considered: int | None = None
    programs_hard_rejected: int | None = None
    programs_constructed: int | None = None
    fallback_batches_used: int | None = None

    budget_plan_success: bool = False
    budget_plan_monthly_cost_irr: int | None = None
    ideal_plan_success: bool = False
    ideal_plan_monthly_cost_irr: int | None = None
    monthly_cost_gap_irr: int | None = None

    protein_preferred_gap_g_per_day: float | None = None
    calorie_preferred_gap_kcal_per_day: float | None = None
    unique_meal_gap: int | None = None
    unique_protein_source_gap: int | None = None

    show_ideal_plan: bool = False
    comparison_reason_codes: list[str] = field(default_factory=list)

    hard_allergen_violations: int = 0
    hard_exclusion_violations: int = 0
    medical_safety_violations: int = 0


def _get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            cwd=Path(__file__).resolve().parents[2],
        ).strip()
    except Exception:
        return "unknown"


def _determine_failure_stage(outcome: str, reason_codes: list[str]) -> str:
    if outcome == "safety_blocked" or any(
        c in reason_codes for c in ["PHYSICIAN_MANUAL_PLAN_REQUIRED", "UNSUPPORTED_OR_HARD_BLOCKED"]
    ):
        return "غربالگری ایمنی پزشکی"
    if outcome == "target_infeasible" or any(
        c in reason_codes
        for c in [
            "GOAL_RESELECTION_REQUIRED",
            "CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
            "CARBOHYDRATE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
            "PROTEIN_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
            "FAT_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
            "MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
        ]
    ):
        return "محاسبات علمی اهداف و بالانس ماکرو"
    if any(
        c in reason_codes
        for c in [
            "INSUFFICIENT_LOW_COST_TEMPLATE_COVERAGE",
            "STRICT_BUDGET_EXCEEDED",
            "FLEXIBLE_BUDGET_CAP_EXCEEDED",
        ]
    ):
        return "بهینه‌سازی و سقف بودجه مالی"
    if any(
        c in reason_codes
        for c in [
            "NO_COMPATIBLE_TEMPLATE_SUBSTITUTE",
            "SCHEDULED_MEAL_UNAVAILABLE",
            "PREFERENCE_EXCLUSION_NO_FEASIBLE_PLAN",
        ]
    ):
        return "گزینش و جایگزینی تمپلیت‌های کاتالوگ"
    if outcome == "live_price_unavailable" or "INSUFFICIENT_PRICE_COVERAGE" in reason_codes:
        return "پوشش و استعلام قیمت اقلام"
    return "پایپ‌لاین اجرایی موتور برنامه‌ریز"


def _build_human_reason(
    spec: ProfileSpec, outcome: str, reasons: list[str], diag: dict[str, Any]
) -> str:
    if outcome == "success":
        return "برنامه تغذیه ایمن و متناسب با اهداف کاربر با موفقیت تولید شد."

    descriptions: list[str] = []
    for r in reasons:
        if r in FA_REASONS:
            descriptions.append(FA_REASONS[r])

    if not descriptions:
        exc = diag.get("exception")
        if exc:
            return f"خطای اجرای موتور: {exc[:200]}"
        return "عدم دستیابی به برنامه تغذیه معتبر مطابق با قیود فعلی سیستم."

    return " | ".join(descriptions)


def run_100_profiles_audit(
    db_url: str = DEFAULT_DB_URL,
    seed: int = 20260903,
    count: int = 100,
) -> list[AuditRecordDetail]:
    profiles = generate_100_profiles(seed=seed, count=count)
    engine = create_engine(db_url)
    records: list[AuditRecordDetail] = []

    print(f"Starting audit: {len(profiles)} profiles against database {db_url} (seed={seed})")

    with Session(engine) as db:
        # Clear previous audit test users and plans safely
        db.execute(delete(NutritionWeeklyPlanFood))
        db.execute(delete(NutritionWeeklyPlanMeal))
        db.execute(delete(NutritionWeeklyPlanDay))
        db.execute(delete(NutritionWeeklyPlanNutrient))
        db.execute(delete(NutritionWeeklyPlan))
        db.execute(delete(NutritionPlanGeneration))
        db.execute(delete(User).where(User.email.like("audit_user_%@fitsho.test")))
        db.commit()

        foods_raw = db.scalars(select(NutritionCatalogueFood)).all()
        food_by_slug_or_name: dict[str, UUID] = {}
        for f in foods_raw:
            food_by_slug_or_name[f.slug] = f.id
            food_by_slug_or_name[f.name_fa] = f.id

        weekday_keys = [
            "saturday",
            "sunday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
        ]

        for idx, spec in enumerate(profiles, start=1):
            uid = uuid5(NAMESPACE_URL, f"fitsho-nutrition-audit:{seed}:{spec.index}")

            # 1. User
            user = User(
                id=uid, email=f"audit_user_{spec.index}@fitsho.test", password_hash="audit_hash"
            )
            db.add(user)
            db.flush()

            # 2. UserProfile
            up = UserProfile(
                user_id=uid,
                product_mode=ProductMode.NUTRITION,
                display_name=spec.name,
                birth_date=spec.birth_date,
                sex=Sex(spec.sex),
                height_cm=spec.height_cm,
                fitness_goal=FitnessGoal(spec.fitness_goal),
            )
            db.add(up)
            db.flush()

            # 3. Body measurement
            bm = BodyMeasurement(user_id=uid, weight_kg=Decimal(str(spec.weight_kg)))
            db.add(bm)

            # 4. Medical profile & conditions
            med = NutritionMedicalProfile(
                user_id=uid,
                dangerous_food_reaction_history=spec.safety_flags[
                    "dangerous_food_reaction_history"
                ],
                pregnant=spec.safety_flags["pregnant"],
                breastfeeding=spec.safety_flags["breastfeeding"],
                eating_disorder_diagnosed=spec.safety_flags["eating_disorder_diagnosed"],
                eating_disorder_active_symptoms=spec.safety_flags[
                    "eating_disorder_active_symptoms"
                ],
                emergency_or_danger_symptoms=spec.safety_flags["emergency_or_danger_symptoms"],
                complex_medication_food_interaction=spec.safety_flags[
                    "complex_medication_food_interaction"
                ],
                physician_dietary_restrictions=spec.safety_flags["physician_dietary_restrictions"],
                other_relevant_condition=spec.safety_flags["other_relevant_condition"],
            )
            db.add(med)
            db.flush()

            for c_code in spec.medical_conditions:
                db.add(NutritionMedicalCondition(user_id=uid, code=MedicalConditionCode(c_code)))

            # Safety decision
            safety_outcome = SafetyOutcome.STANDARD_AUTOMATIC
            safety_reasons = ["no_review_condition_declared"]
            if spec.safety_flags["pregnant"]:
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = ["pregnancy"]
            elif spec.safety_flags["breastfeeding"]:
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = ["breastfeeding"]
            elif (
                spec.safety_flags["eating_disorder_diagnosed"]
                or spec.safety_flags["eating_disorder_active_symptoms"]
            ):
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = ["eating_disorder"]
            elif spec.safety_flags["emergency_or_danger_symptoms"]:
                safety_outcome = SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED
                safety_reasons = ["danger_symptoms_declared"]
            elif any(
                c
                in {
                    MedicalConditionCode.KIDNEY_DISEASE.value,
                    MedicalConditionCode.DIALYSIS.value,
                    MedicalConditionCode.LIVER_DISEASE.value,
                }
                for c in spec.medical_conditions
            ):
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = [c for c in spec.medical_conditions]
            elif spec.medical_conditions:
                safety_outcome = SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW
                safety_reasons = [c for c in spec.medical_conditions]

            sec = NutritionSafetyDecision(
                user_id=uid,
                medical_condition_policy_version="medical-condition-v1",
                revision=1,
                outcome=safety_outcome,
                reasons=[NutritionSafetyReason(code=rc) for rc in safety_reasons],
            )
            db.add(sec)

            eff_meals = (
                2
                if spec.main_meal_bucket == "two_main_meals"
                else 3
                if spec.main_meal_bucket == "three_main_meals"
                else 4
            )
            eff_snacks = (
                0
                if spec.snack_bucket == "zero_snacks"
                else 1
                if spec.snack_bucket == "one_snack"
                else 2
                if spec.snack_bucket == "two_snacks"
                else 3
            )

            # 5. Nutrition profile
            np = NutritionProfile(
                user_id=uid,
                onboarding_status=NutritionOnboardingStatus.COMPLETED,
                daily_activity_level=DailyActivityLevel(spec.daily_activity_level),
                individual_monthly_food_budget_irr=spec.monthly_budget_irr,
                budget_style=BudgetStyle(spec.budget_style),
                meals_per_day=spec.meals_per_day,
                snacks_per_day=spec.snacks_per_day,
                main_meal_count_bucket=MainMealCountBucket(spec.main_meal_bucket),
                snack_count_bucket=SnackCountBucket(spec.snack_bucket),
                effective_main_meal_slots=eff_meals,
                effective_snack_slots=eff_snacks,
                preferred_plan_start_day=Weekday.SATURDAY,
                plan_style=NutritionPlanStyle(spec.plan_style),
                cooking_skill=CookingSkill(spec.cooking_skill),
                maximum_cooking_time_minutes=spec.cooking_time_minutes,
                cooking_frequency_per_week=spec.cooking_frequency_per_week,
                meal_preparation_preference=MealPreparationPreference(spec.meal_prep_preference),
                refrigerator_access=True,
                freezer_access=True,
                supplied_meals_per_week=0,
                dietary_pattern=DietaryPattern(spec.dietary_pattern),
                preferred_variety=PreferredVariety(spec.preferred_variety),
                maximum_meal_repetition_per_week=spec.max_meal_repetition,
                accepts_leftovers=True,
                accepts_batch_cooking=False,
                daily_check_in_enabled=False,
            )
            db.add(np)
            db.flush()

            # 6. Structured exercise
            ex = NutritionStructuredExercise(
                user_id=uid,
                trains=spec.trains,
                exercise_type=StructuredExerciseType(spec.exercise_type)
                if spec.exercise_type
                else None,
                days_per_week=spec.days_per_week,
                minutes_per_session=spec.minutes_per_session,
                intensity=TrainingIntensity(spec.intensity) if spec.intensity else None,
                source=StructuredExerciseSource.USER_REPORTED,
            )
            db.add(ex)

            # 7. Food items (preferences & exclusions)
            for item_name in spec.favourite_foods:
                cat_id = food_by_slug_or_name.get(item_name)
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.FAVOURITE,
                        name=item_name,
                        normalized_name=item_name.strip().casefold(),
                        catalogue_food_id=cat_id,
                    )
                )
            for item_name in spec.disliked_foods:
                cat_id = food_by_slug_or_name.get(item_name)
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.DISLIKED,
                        name=item_name,
                        normalized_name=item_name.strip().casefold(),
                        catalogue_food_id=cat_id,
                    )
                )
            for item_name in spec.allergies:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.ALLERGY,
                        name=item_name,
                        normalized_name=item_name.strip().casefold(),
                        catalogue_food_id=None,
                    )
                )
            for item_name in spec.intolerances:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.INTOLERANCE,
                        name=item_name,
                        normalized_name=item_name.strip().casefold(),
                        catalogue_food_id=None,
                    )
                )
            for item_name in spec.refused_foods:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.REFUSED,
                        name=item_name,
                        normalized_name=item_name.strip().casefold(),
                        catalogue_food_id=None,
                    )
                )

            db.commit()

            # Execute the actual production nutrition engine
            outcome: str = "failed"
            reason_codes: list[str] = []
            warning_codes: list[str] = []
            plan_obj: WeeklyPlanResponse | None = None
            gen_resp: Any = None
            gen_row: NutritionPlanGeneration | None = None
            diag: dict[str, Any] = {}
            plan_id: str | None = None
            selected_program_code: str | None = None
            actual_weekly_cost_toman: int | None = None

            start_t = time.perf_counter()
            try:
                gen_resp = generate_weekly_plan(db, uid)
                outcome = gen_resp.outcome
                reason_codes = list(gen_resp.reason_codes)
                warning_codes = list(gen_resp.warning_codes)
                plan_obj = gen_resp.plan

                gen_row = db.scalar(
                    select(NutritionPlanGeneration)
                    .where(NutritionPlanGeneration.user_id == uid)
                    .order_by(NutritionPlanGeneration.created_at.desc())
                    .limit(1)
                )
                if gen_row:
                    diag = gen_row.diagnostic_snapshot or {}
                    if gen_row.input_snapshot:
                        selected_program_code = gen_row.input_snapshot.get("nutrition_program_code")

                if plan_obj:
                    plan_id = str(plan_obj.id)
                    actual_weekly_cost_toman = plan_obj.weekly_cost_irr // 10
            except Exception as exc:
                outcome = "failed"
                reason_codes = ["UNHANDLED_ENGINE_ERROR"]
                diag = {"exception": str(exc), "exception_type": type(exc).__name__}

            duration_s = time.perf_counter() - start_t

            # Extract estimates
            est_row = db.scalar(
                select(NutritionEstimate)
                .where(NutritionEstimate.user_id == uid)
                .order_by(NutritionEstimate.created_at.desc())
                .limit(1)
            )
            target_kcal: float | None = None
            target_protein: float | None = None
            target_carbs: float | None = None
            target_fat: float | None = None
            bmr_val: float | None = None
            tdee_val: float | None = None

            if est_row and est_row.targets:
                target_map: dict[str, float] = {}
                for t in est_row.targets:
                    val = t.preferred_value
                    if val is None and t.minimum_value is not None and t.maximum_value is not None:
                        val = (t.minimum_value + t.maximum_value) / 2
                    if val is not None:
                        target_map[t.metric.value] = float(val)

                target_kcal = target_map.get("goal_calories")
                target_protein = target_map.get("protein")
                target_carbs = target_map.get("carbohydrate")
                target_fat = target_map.get("total_fat")
                bmr_val = target_map.get("bmr")
                tdee_val = target_map.get("tdee")

            # Extract generated days and meals if successful
            days_data: list[AuditDayItem] = []
            target_vs_actual: dict[str, Any] = {}

            if plan_obj and plan_obj.days:
                total_plan_cals = 0.0
                total_plan_protein = 0.0
                total_plan_carbs = 0.0
                total_plan_fat = 0.0

                for day in plan_obj.days:
                    d_name = FA_WEEKDAY[weekday_keys[day.day_index % 7]]
                    meals_data: list[AuditMealItem] = []

                    for m in day.meals:
                        foods_data: list[AuditFoodItem] = []
                        for f in m.foods:
                            f_cals = round(f.nutrients.get("energy_kcal", 0.0), 1)
                            f_prot = round(f.nutrients.get("protein_g", 0.0), 1)
                            f_carbs = round(f.nutrients.get("carbohydrate_g", 0.0), 1)
                            f_fat = round(f.nutrients.get("total_fat_g", 0.0), 1)
                            foods_data.append(
                                AuditFoodItem(
                                    name_fa=f.name_fa or f.name_en or f.slug,
                                    grams=round(f.grams, 1),
                                    calories=f_cals,
                                    protein=f_prot,
                                    carbs=f_carbs,
                                    fat=f_fat,
                                    cost_toman=f.cost_irr // 10,
                                )
                            )

                        m_cals = round(m.nutrient_totals.get("energy_kcal", 0.0), 1)
                        m_prot = round(m.nutrient_totals.get("protein_g", 0.0), 1)
                        m_carbs = round(m.nutrient_totals.get("carbohydrate_g", 0.0), 1)
                        m_fat = round(m.nutrient_totals.get("total_fat_g", 0.0), 1)

                        if m.slot_role == "main_meal":
                            main_roles = ["صبحانه", "ناهار", "شام", "وعده چهارم", "وعده پنجم"]
                            role_fa = (
                                main_roles[m.slot_index]
                                if m.slot_index < len(main_roles)
                                else f"وعده اصلی {m.slot_index + 1}"
                            )
                        elif m.slot_role == "snack":
                            role_fa = f"میان‌وعده {m.slot_index + 1}"
                        elif m.slot_role == "free_meal":
                            role_fa = "وعده آزاد"
                        else:
                            role_fa = FA_MEAL_ROLE.get(m.slot_role, m.slot_role)

                        meal_title = m.name_fa or role_fa

                        meals_data.append(
                            AuditMealItem(
                                role=m.slot_role,
                                role_fa=role_fa,
                                name_fa=meal_title,
                                calories=m_cals,
                                protein=m_prot,
                                carbs=m_carbs,
                                fat=m_fat,
                                cost_toman=m.cost_irr // 10,
                                foods=foods_data,
                            )
                        )

                    day_cals = round(day.nutrient_totals.get("energy_kcal", 0.0), 1)
                    day_prot = round(day.nutrient_totals.get("protein_g", 0.0), 1)
                    day_carbs = round(day.nutrient_totals.get("carbohydrate_g", 0.0), 1)
                    day_fat = round(day.nutrient_totals.get("total_fat_g", 0.0), 1)

                    total_plan_cals += day_cals
                    total_plan_protein += day_prot
                    total_plan_carbs += day_carbs
                    total_plan_fat += day_fat

                    days_data.append(
                        AuditDayItem(
                            day_index=day.day_index,
                            day_name=d_name,
                            calories=day_cals,
                            protein=day_prot,
                            carbs=day_carbs,
                            fat=day_fat,
                            cost_toman=day.cost_irr // 10,
                            meals=meals_data,
                        )
                    )

                avg_plan_cals = round(total_plan_cals / len(plan_obj.days), 1)
                avg_plan_protein = round(total_plan_protein / len(plan_obj.days), 1)
                avg_plan_carbs = round(total_plan_carbs / len(plan_obj.days), 1)
                avg_plan_fat = round(total_plan_fat / len(plan_obj.days), 1)

                target_vs_actual = {
                    "calories": {
                        "target": round(target_kcal, 1) if target_kcal else None,
                        "actual_avg": avg_plan_cals,
                        "diff": round(avg_plan_cals - target_kcal, 1) if target_kcal else None,
                    },
                    "protein": {
                        "target": round(target_protein, 1) if target_protein else None,
                        "actual_avg": avg_plan_protein,
                        "diff": round(avg_plan_protein - target_protein, 1)
                        if target_protein
                        else None,
                    },
                    "carbohydrate": {
                        "target": round(target_carbs, 1) if target_carbs else None,
                        "actual_avg": avg_plan_carbs,
                        "diff": round(avg_plan_carbs - target_carbs, 1) if target_carbs else None,
                    },
                    "total_fat": {
                        "target": round(target_fat, 1) if target_fat else None,
                        "actual_avg": avg_plan_fat,
                        "diff": round(avg_plan_fat - target_fat, 1) if target_fat else None,
                    },
                }

            is_success = outcome == "success"
            stage_fa = _determine_failure_stage(outcome, reason_codes)
            human_reason = _build_human_reason(spec, outcome, reason_codes, diag)

            comp = getattr(gen_resp, "comparison", None) if "gen_resp" in locals() else None
            budget_plan_success = getattr(gen_resp, "budget_plan", None) is not None or (outcome == "success" and plan_obj is not None) if "gen_resp" in locals() else False
            ideal_plan_success = getattr(gen_resp, "ideal_plan", None) is not None if "gen_resp" in locals() else False

            budget_plan_monthly_cost_irr = comp.budget_plan_monthly_cost_irr if comp else None
            ideal_plan_monthly_cost_irr = comp.ideal_plan_monthly_cost_irr if comp else None
            monthly_cost_gap_irr = comp.monthly_cost_gap_irr if comp else None

            prot_diff = None
            if comp and comp.protein_gap and comp.protein_gap.difference is not None:
                prot_diff = float(comp.protein_gap.difference)
            elif comp and comp.protein_gap_g_per_day is not None:
                prot_diff = float(comp.protein_gap_g_per_day)

            cal_diff = None
            if comp and comp.calorie_gap and comp.calorie_gap.difference is not None:
                cal_diff = float(comp.calorie_gap.difference)
            elif comp and comp.calorie_gap_kcal_per_day is not None:
                cal_diff = float(comp.calorie_gap_kcal_per_day)

            meal_gap = None
            if comp and comp.unique_meal_count_ideal is not None and comp.unique_meal_count_budget is not None:
                meal_gap = comp.unique_meal_count_ideal - comp.unique_meal_count_budget

            prot_src_gap = None
            if comp and comp.unique_protein_sources_ideal is not None and comp.unique_protein_sources_budget is not None:
                prot_src_gap = comp.unique_protein_sources_ideal - comp.unique_protein_sources_budget

            show_ideal = comp.show_ideal_plan if comp else False
            comp_reasons = list(comp.reason_codes) if comp else []

            est_snap = (est_row.input_snapshot or {}) if est_row else {}
            gen_snap = (gen_row.input_snapshot or {}) if gen_row else {}
            combo_snap = {**est_snap, **gen_snap}

            def _to_f(v: Any) -> float | None:
                if v is None:
                    return None
                try:
                    return float(v)
                except Exception:
                    return None

            req_wc = _to_f(combo_snap.get("requested_weight_change_kg_per_week"))
            rec_wc = _to_f(combo_snap.get("recommended_weight_change_kg_per_week"))
            app_wc = _to_f(combo_snap.get("applied_weight_change_kg_per_week"))
            goal_strat = combo_snap.get("goal_strategy") or diag.get("goal_strategy")
            goal_strat_v = combo_snap.get("goal_strategy_version") or diag.get("goal_strategy_version")
            b_tier = diag.get("budget_tier")

            prog_cons = diag.get("programs_considered") or diag.get("candidates_count")
            if prog_cons is None and "program_evaluations" in diag:
                prog_cons = len(diag["program_evaluations"])
            prog_rej = diag.get("programs_hard_rejected")
            prog_const = diag.get("programs_constructed")
            fallback_b = diag.get("fallback_batches_used")

            hard_allergen_viols = diag.get("hard_allergen_violations", 0)
            hard_excl_viols = diag.get("hard_exclusion_violations", 0)
            med_safety_viols = diag.get("medical_safety_violations", 0)

            rec = AuditRecordDetail(
                spec=spec,
                outcome=outcome,
                outcome_fa=FA_OUTCOME.get(outcome, outcome),
                is_success=is_success,
                reason_codes=reason_codes,
                warning_codes=warning_codes,
                failure_stage_fa=stage_fa,
                human_reason_fa=human_reason,
                generation_duration_seconds=round(duration_s, 3),
                target_calories=round(target_kcal, 1) if target_kcal else None,
                target_protein=round(target_protein, 1) if target_protein else None,
                target_carbs=round(target_carbs, 1) if target_carbs else None,
                target_fat=round(target_fat, 1) if target_fat else None,
                bmr=round(bmr_val, 1) if bmr_val else None,
                tdee=round(tdee_val, 1) if tdee_val else None,
                weekly_budget_toman=(spec.monthly_budget_irr * 12 // 52) // 10,
                actual_weekly_cost_toman=actual_weekly_cost_toman,
                plan_id=plan_id,
                selected_program_code=selected_program_code,
                days=days_data,
                target_vs_actual=target_vs_actual,
                diagnostics=diag,
                budget_tier=b_tier,
                requested_weight_change_kg_per_week=req_wc,
                recommended_weight_change_kg_per_week=rec_wc,
                applied_weight_change_kg_per_week=app_wc,
                goal_strategy=goal_strat,
                goal_strategy_version=goal_strat_v,
                programs_considered=prog_cons,
                programs_hard_rejected=prog_rej,
                programs_constructed=prog_const,
                fallback_batches_used=fallback_b,
                budget_plan_success=budget_plan_success,
                budget_plan_monthly_cost_irr=budget_plan_monthly_cost_irr,
                ideal_plan_success=ideal_plan_success,
                ideal_plan_monthly_cost_irr=ideal_plan_monthly_cost_irr,
                monthly_cost_gap_irr=monthly_cost_gap_irr,
                protein_preferred_gap_g_per_day=prot_diff,
                calorie_preferred_gap_kcal_per_day=cal_diff,
                unique_meal_gap=meal_gap,
                unique_protein_source_gap=prot_src_gap,
                show_ideal_plan=show_ideal,
                comparison_reason_codes=comp_reasons,
                hard_allergen_violations=hard_allergen_viols,
                hard_exclusion_violations=hard_excl_viols,
                medical_safety_violations=med_safety_viols,
            )
            records.append(rec)

            status_sym = "✅" if is_success else "❌"
            print(
                f"[{idx:3d}/{len(profiles):3d}] {status_sym} User {spec.index:2d}: {outcome} ({rec.generation_duration_seconds:.2f}s) - {reason_codes}"
            )

    return records


def build_audit_summary(records: list[AuditRecordDetail], seed: int) -> dict[str, Any]:
    total = len(records)
    success_count = sum(1 for r in records if r.is_success)
    failure_count = total - success_count
    success_rate = (success_count / total) * 100 if total > 0 else 0.0

    durations = [r.generation_duration_seconds for r in records]
    avg_duration = statistics.mean(durations) if durations else 0.0
    median_duration = statistics.median(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0.0
    min_duration = min(durations) if durations else 0.0

    # Failure reasons frequency
    reason_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}

    for r in records:
        if not r.is_success:
            stage_counts[r.failure_stage_fa] = stage_counts.get(r.failure_stage_fa, 0) + 1
            for rc in r.reason_codes:
                reason_counts[rc] = reason_counts.get(rc, 0) + 1

    sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
    sorted_stages = sorted(stage_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "title": "گزارش ممیزی ۱۰۰ پروفایل موتور تغذیه فیتشو",
        "timestamp": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": _get_git_commit(),
        "random_seed": seed,
        "total_profiles": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 1),
        "duration_seconds": {
            "average": round(avg_duration, 2),
            "median": round(median_duration, 2),
            "maximum": round(max_duration, 2),
            "minimum": round(min_duration, 2),
        },
        "stage_breakdown": sorted_stages,
        "failure_reasons": [
            {
                "code": code,
                "count": count,
                "description_fa": FA_REASONS.get(code, "سایر خطاهای سیستم"),
            }
            for code, count in sorted_reasons
        ],
    }


def generate_persian_html(records: list[AuditRecordDetail], summary: dict[str, Any]) -> str:
    css = """
    @page {
        size: A4;
        margin: 12mm 10mm 15mm 10mm;
        @bottom-left {
            content: "ممیزی موتور تغذیه فیتشو | Fitsho Nutrition Engine Audit";
            font-family: 'Vazirmatn', sans-serif;
            font-size: 7.5pt;
            color: #64748b;
            direction: ltr;
        }
        @bottom-right {
            content: "صفحه " counter(page) " از " counter(pages);
            font-family: 'Vazirmatn', sans-serif;
            font-size: 7.5pt;
            color: #64748b;
        }
    }
    body {
        direction: rtl;
        font-family: 'Vazirmatn', 'Noto Sans Arabic', sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        font-size: 8pt;
        line-height: 1.5;
        margin: 0;
        padding: 0;
    }
    .page-break {
        page-break-before: always;
    }
    .avoid-break {
        page-break-inside: avoid;
    }
    .cover-container {
        padding: 30px 20px;
        text-align: center;
    }
    .cover-title {
        font-size: 22pt;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .cover-subtitle {
        font-size: 11pt;
        color: #475569;
        margin-bottom: 25px;
    }
    .meta-box {
        display: inline-block;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 24px;
        margin-bottom: 25px;
        font-size: 9pt;
        color: #334155;
        text-align: right;
        min-width: 320px;
    }
    .meta-box div {
        margin: 4px 0;
    }
    .kpi-grid {
        display: flex;
        flex-direction: row;
        gap: 8px;
        margin-bottom: 20px;
    }
    .kpi-card {
        flex: 1;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 10px 8px;
        text-align: center;
    }
    .kpi-val {
        font-size: 15pt;
        font-weight: bold;
        color: #1e3a8a;
    }
    .kpi-val.success { color: #15803d; }
    .kpi-val.danger { color: #b91c1c; }
    .kpi-label {
        font-size: 7.5pt;
        color: #64748b;
        margin-top: 3px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 12px;
        font-size: 7.8pt;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 5px 8px;
        text-align: right;
    }
    th {
        background-color: #f1f5f9;
        color: #1e293b;
        font-weight: 700;
    }
    .section-header {
        font-size: 12pt;
        font-weight: 700;
        color: #0f172a;
        border-bottom: 2px solid #0284c7;
        padding-bottom: 4px;
        margin-top: 18px;
        margin-bottom: 10px;
    }
    .profile-card {
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 12px;
        background-color: #ffffff;
    }
    .profile-card.success-border {
        border-right: 5px solid #16a34a;
    }
    .profile-card.fail-border {
        border-right: 5px solid #dc2626;
    }
    .profile-topbar {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 5px;
        margin-bottom: 8px;
    }
    .profile-title {
        font-size: 10.5pt;
        font-weight: bold;
        color: #0f172a;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 7.5pt;
        font-weight: bold;
    }
    .badge-success { background: #dcfce7; color: #166534; }
    .badge-danger { background: #fee2e2; color: #991b1b; }
    .badge-muted { background: #f1f5f9; color: #475569; }
    .user-info-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 4px 10px;
        font-size: 7.5pt;
        background: #f8fafc;
        border-radius: 6px;
        padding: 6px 10px;
        margin-bottom: 8px;
    }
    .user-info-item strong {
        color: #0f172a;
    }
    .plan-container {
        margin-top: 6px;
    }
    .plan-title {
        font-size: 8.5pt;
        font-weight: bold;
        color: #1e3a8a;
        margin-bottom: 4px;
    }
    .day-box {
        background: #fafafa;
        border: 1px solid #e2e8f0;
        border-radius: 5px;
        padding: 6px 8px;
        margin-bottom: 6px;
    }
    .day-header {
        font-weight: bold;
        color: #1e40af;
        font-size: 8pt;
        margin-bottom: 3px;
        display: flex;
        justify-content: space-between;
    }
    .day-totals-span {
        color: #0284c7;
        font-size: 7.2pt;
        font-weight: normal;
    }
    .meal-block {
        margin-right: 8px;
        margin-bottom: 4px;
        font-size: 7.4pt;
        line-height: 1.4;
    }
    .meal-name {
        font-weight: bold;
        color: #334155;
    }
    .food-line {
        color: #475569;
        margin-right: 12px;
    }
    .target-vs-actual-box {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 5px;
        padding: 5px 8px;
        font-size: 7.2pt;
        color: #166534;
        margin-top: 5px;
    }
    .fail-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 6px;
        padding: 8px 10px;
        margin-top: 6px;
    }
    .fail-header {
        color: #b91c1c;
        font-weight: bold;
        font-size: 8pt;
        margin-bottom: 4px;
    }
    .fail-detail {
        font-size: 7.5pt;
        color: #450a0a;
        margin-bottom: 3px;
    }
    .code-tag {
        font-family: monospace;
        background: #fee2e2;
        color: #991b1b;
        padding: 1px 4px;
        border-radius: 3px;
        direction: ltr;
        display: inline-block;
        font-size: 7pt;
    }
    """

    html = [
        "<!DOCTYPE html>",
        "<html lang='fa' dir='rtl'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<title>گزارش ممیزی ۱۰۰ پروفایل موتور تغذیه فیتشو</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
    ]

    # COVER PAGE
    html.append("<div class='cover-container'>")
    html.append(f"<div class='cover-title'>{summary['title']}</div>")
    html.append(
        "<div class='cover-subtitle'>ارزیابی جامع و تصادفی‌سازی‌شده خروجی موتور برنامه‌ریزی تغذیه فیتشو</div>"
    )

    html.append("<div class='meta-box'>")
    html.append(f"<div><strong>تاریخ و زمان ممیزی:</strong> {summary['timestamp']}</div>")
    html.append(
        f"<div><strong>شناسه کامیت گیت:</strong> <span style='font-family:monospace;'>{summary['git_commit']}</span></div>"
    )
    html.append(f"<div><strong>سید تصادفی (Random Seed):</strong> {summary['random_seed']}</div>")
    html.append(f"<div><strong>تعداد کل پروفایل‌ها:</strong> {summary['total_profiles']}</div>")
    html.append(f"<div><strong>تولیدهای موفق:</strong> {summary['success_count']}</div>")
    html.append(f"<div><strong>تولیدهای ناموفق:</strong> {summary['failure_count']}</div>")
    html.append(f"<div><strong>نرخ موفقیت:</strong> {summary['success_rate']}%</div>")
    html.append(
        f"<div><strong>میانگین زمان تولید:</strong> {summary['duration_seconds']['average']} ثانیه</div>"
    )
    html.append(
        f"<div><strong>میانه زمان تولید:</strong> {summary['duration_seconds']['median']} ثانیه</div>"
    )
    html.append(
        f"<div><strong>حداکثر زمان تولید:</strong> {summary['duration_seconds']['maximum']} ثانیه</div>"
    )
    html.append("</div>")

    # Cover KPI cards
    html.append("<div class='kpi-grid'>")
    html.append(
        f"<div class='kpi-card'><div class='kpi-val'>{summary['total_profiles']}</div><div class='kpi-label'>کل پروفایل‌ها</div></div>"
    )
    html.append(
        f"<div class='kpi-card'><div class='kpi-val success'>{summary['success_count']}</div><div class='kpi-label'>تولید موفق</div></div>"
    )
    html.append(
        f"<div class='kpi-card'><div class='kpi-val danger'>{summary['failure_count']}</div><div class='kpi-label'>ناموفق</div></div>"
    )
    html.append(
        f"<div class='kpi-card'><div class='kpi-val'>{summary['success_rate']}%</div><div class='kpi-label'>نرخ موفقیت</div></div>"
    )
    html.append(
        f"<div class='kpi-card'><div class='kpi-val'>{summary['duration_seconds']['average']}s</div><div class='kpi-label'>میانگین زمان</div></div>"
    )
    html.append(
        f"<div class='kpi-card'><div class='kpi-val'>{summary['duration_seconds']['maximum']}s</div><div class='kpi-label'>کندترین زمان</div></div>"
    )
    html.append("</div>")
    html.append("</div>")  # cover-container

    html.append("<div class='page-break'></div>")

    # SUMMARY PAGE
    html.append("<h2 class='section-header'>خلاصه مدیریتی و تحلیل نتایج ممیزی</h2>")

    html.append("<table>")
    html.append("<thead><tr><th colspan='2'>شاخص‌های کلیدی عملکرد موتور تغذیه</th></tr></thead>")
    html.append("<tbody>")
    html.append(
        f"<tr><td><strong>تعداد کل پروفایل‌ها</strong></td><td>{summary['total_profiles']} کاربر</td></tr>"
    )
    html.append(
        f"<tr><td><strong>تولیدهای موفق (SUCCESS)</strong></td><td style='color:#15803d; font-weight:bold;'>{summary['success_count']} کاربر</td></tr>"
    )
    html.append(
        f"<tr><td><strong>تولیدهای ناموفق (FAILED)</strong></td><td style='color:#b91c1c; font-weight:bold;'>{summary['failure_count']} کاربر</td></tr>"
    )
    html.append(
        f"<tr><td><strong>نرخ موفقیت (Success Rate)</strong></td><td><strong>{summary['success_rate']}%</strong></td></tr>"
    )
    html.append(
        f"<tr><td><strong>میانگین زمان تولید هر برنامه</strong></td><td>{summary['duration_seconds']['average']} ثانیه</td></tr>"
    )
    html.append(
        f"<tr><td><strong>میانه زمان تولید (Median)</strong></td><td>{summary['duration_seconds']['median']} ثانیه</td></tr>"
    )
    html.append(
        f"<tr><td><strong>کندترین تولید (Maximum)</strong></td><td>{summary['duration_seconds']['maximum']} ثانیه</td></tr>"
    )
    html.append(
        f"<tr><td><strong>سریع‌ترین تولید (Minimum)</strong></td><td>{summary['duration_seconds']['minimum']} ثانیه</td></tr>"
    )
    html.append("</tbody></table>")

    # Stage breakdown table
    html.append(
        "<h3 style='font-size: 9pt; color: #1e3a8a; margin-top: 14px;'>تفکیک موارد ناموفق بر اساس مرحله موتور:</h3>"
    )
    html.append("<table>")
    html.append(
        "<thead><tr><th>مرحله توقف در موتور</th><th>تعداد رخ‌داد</th><th>درصد از کل شکست‌ها</th></tr></thead><tbody>"
    )
    for stage_name, count in summary["stage_breakdown"]:
        pct = (
            round((count / summary["failure_count"]) * 100, 1)
            if summary["failure_count"] > 0
            else 0
        )
        html.append(
            f"<tr><td><strong>{stage_name}</strong></td><td>{count}</td><td>{pct}%</td></tr>"
        )
    html.append("</tbody></table>")

    # Failure reasons table
    html.append(
        "<h3 style='font-size: 9pt; color: #1e3a8a; margin-top: 14px;'>جدول تفصیلی علل شکست (Failure Reason Codes):</h3>"
    )
    html.append("<table>")
    html.append(
        "<thead><tr><th>کد خطای موتور</th><th>شرح و مفهوم فارسی</th><th>تعداد</th></tr></thead><tbody>"
    )
    for r_item in summary["failure_reasons"]:
        html.append(
            f"<tr><td><span class='code-tag'>{r_item['code']}</span></td>"
            f"<td>{r_item['description_fa']}</td>"
            f"<td style='text-align:center;'>{r_item['count']}</td></tr>"
        )
    html.append("</tbody></table>")

    html.append("<div class='page-break'></div>")

    # 100 PROFILES SECTIONS
    html.append(
        "<h2 class='section-header'>نتایج تفصیلی ۱۰۰ پروفایل کاربر به همراه برنامه تولیدشده</h2>"
    )

    for rec in records:
        spec = rec.spec
        bmi = round(spec.weight_kg / ((spec.height_cm / 100) ** 2), 1)

        border_class = "success-border" if rec.is_success else "fail-border"
        badge_html = (
            "<span class='badge badge-success'>تولید موفق (SUCCESS)</span>"
            if rec.is_success
            else f"<span class='badge badge-danger'>ناموفق ({rec.outcome_fa})</span>"
        )

        html.append(f"<div class='profile-card {border_class} avoid-break'>")
        html.append("<div class='profile-topbar'>")
        html.append(f"<div class='profile-title'>پروفایل {spec.index} ({spec.name})</div>")
        html.append(
            f"<div>{badge_html} <span class='badge badge-muted'>{rec.generation_duration_seconds}s</span></div>"
        )
        html.append("</div>")

        # Profile Summary Grid
        ex_str = (
            f"{FA_EXERCISE_TYPE.get(spec.exercise_type or '', 'ورزش')} ({spec.days_per_week} روز/هفته، {spec.minutes_per_session} دقیقه، شدت {FA_INTENSITY.get(spec.intensity or '', '')})"
            if spec.trains
            else "بدون تمرین اختصاصی"
        )

        restr_items = []
        if spec.allergies:
            restr_items.append(f"آلرژی: {', '.join(spec.allergies)}")
        if spec.intolerances:
            restr_items.append(f"عدم تحمل: {', '.join(spec.intolerances)}")
        if spec.disliked_foods:
            restr_items.append(f"غذاهای نامطلوب: {', '.join(spec.disliked_foods)}")
        if spec.refused_foods:
            restr_items.append(f"ردشده: {', '.join(spec.refused_foods)}")
        restr_str = " | ".join(restr_items) if restr_items else "ندارد"

        health_items = []
        if spec.safety_flags.get("pregnant"):
            health_items.append("بارداری")
        if spec.safety_flags.get("breastfeeding"):
            health_items.append("شیردهی")
        if spec.safety_flags.get("eating_disorder_diagnosed"):
            health_items.append("سابقه اختلال خوردن")
        if spec.medical_conditions:
            health_items.extend(spec.medical_conditions)
        health_str = "، ".join(health_items) if health_items else "سالم"

        target_kcal_str = (
            f"{int(rec.target_calories)} kcal" if rec.target_calories else "محاسبه نشد"
        )
        target_prot_str = f"{int(rec.target_protein)} g" if rec.target_protein else "محاسبه نشد"
        target_carbs_str = f"{int(rec.target_carbs)} g" if rec.target_carbs else "محاسبه نشد"
        target_fat_str = f"{int(rec.target_fat)} g" if rec.target_fat else "محاسبه نشد"

        html.append("<div class='user-info-grid'>")
        html.append(
            f"<div class='user-info-item'><strong>سن و جنسیت:</strong> {spec.age} سال ({FA_SEX.get(spec.sex, spec.sex)})</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>قد و وزن:</strong> {spec.height_cm}cm | {spec.weight_kg}kg (BMI: {bmi})</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>هدف:</strong> {FA_GOAL.get(spec.fitness_goal, spec.fitness_goal)}</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>سطح فعالیت:</strong> {FA_ACTIVITY.get(spec.daily_activity_level, spec.daily_activity_level)}</div>"
        )
        html.append(
            f"<div class='user-info-item' style='grid-column: span 2;'><strong>تمرین ورزشی:</strong> {ex_str}</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>کالری هدف:</strong> {target_kcal_str}</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>پروتئین هدف:</strong> {target_prot_str}</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>کربوهیدرات/چربی هدف:</strong> {target_carbs_str} / {target_fat_str}</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>الگوی غذایی:</strong> {FA_DIETARY_PATTERN.get(spec.dietary_pattern, spec.dietary_pattern)}</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>بودجه ماهانه:</strong> {spec.monthly_budget_irr // 10:,} تومان ({FA_BUDGET_STYLE.get(spec.budget_style, spec.budget_style)})</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>تعداد وعده‌ها:</strong> {spec.meals_per_day} اصلی + {spec.snacks_per_day} میان‌وعده</div>"
        )
        html.append(
            f"<div class='user-info-item'><strong>زمان آشپزی:</strong> {spec.cooking_time_minutes} دقیقه ({FA_COOKING_SKILL.get(spec.cooking_skill, spec.cooking_skill)})</div>"
        )
        html.append(
            f"<div class='user-info-item' style='grid-column: span 2;'><strong>وضعیت سلامت:</strong> {health_str}</div>"
        )
        html.append(
            f"<div class='user-info-item' style='grid-column: span 3;'><strong>محدودیت‌ها و ترجیحات:</strong> {restr_str}</div>"
        )
        html.append("</div>")

        # Plan / Outcome Section
        if rec.is_success:
            html.append("<div class='plan-container'>")
            prog_label = (
                f" (کد برنامه انتخابی کاتالوگ: {rec.selected_program_code})"
                if rec.selected_program_code
                else ""
            )
            html.append(f"<div class='plan-title'>برنامه تغذیه تولیدشده{prog_label}:</div>")

            for day in rec.days:
                html.append("<div class='day-box'>")
                totals_text = f"کالری: {int(day.calories)} kcal | پروتئین: {int(day.protein)}g | کربوهیدرات: {int(day.carbs)}g | چربی: {int(day.fat)}g | هزینه: {day.cost_toman:,} تومان"
                html.append(
                    f"<div class='day-header'><span>📅 {day.day_name}</span><span class='day-totals-span'>{totals_text}</span></div>"
                )

                for m in day.meals:
                    m_totals = f"({int(m.calories)} kcal, P: {int(m.protein)}g, C: {int(m.carbs)}g, F: {int(m.fat)}g)"
                    html.append(
                        f"<div class='meal-block'><span class='meal-name'>▫ {m.role_fa} ({m.name_fa}) {m_totals}:</span>"
                    )
                    for f in m.foods:
                        html.append(
                            f"<div class='food-line'>- {f.name_fa}: {int(f.grams)} گرم ({int(f.calories)} kcal, پروتئین: {int(f.protein)}g, کربوهیدرات: {int(f.carbs)}g, چربی: {int(f.fat)}g)</div>"
                        )
                    html.append("</div>")

                html.append("</div>")  # day-box

            if rec.target_vs_actual:
                c_data = rec.target_vs_actual.get("calories", {})
                p_data = rec.target_vs_actual.get("protein", {})
                cb_data = rec.target_vs_actual.get("carbohydrate", {})
                f_data = rec.target_vs_actual.get("total_fat", {})
                cost_actual = rec.actual_weekly_cost_toman or 0

                html.append("<div class='target-vs-actual-box'>")
                html.append("<strong>مقایسه اهداف علمی با میانگین محقق‌شده برنامه:</strong> ")
                html.append(
                    f"کالری: {c_data.get('target', '-')} (محقق‌شده: {c_data.get('actual_avg', '-')}) | "
                )
                html.append(
                    f"پروتئین: {p_data.get('target', '-')}g (محقق‌شده: {p_data.get('actual_avg', '-')}g) | "
                )
                html.append(
                    f"کربوهیدرات: {cb_data.get('target', '-')}g (محقق‌شده: {cb_data.get('actual_avg', '-')}g) | "
                )
                html.append(
                    f"چربی: {f_data.get('target', '-')}g (محقق‌شده: {f_data.get('actual_avg', '-')}g) | "
                )
                html.append(
                    f"هزینه هفتگی محقق‌شده: {cost_actual:,} تومان (سقف بودجه هفتگی: {rec.weekly_budget_toman:,} تومان)"
                )
                html.append("</div>")

            html.append("</div>")  # plan-container

        else:
            # Failure details
            html.append("<div class='fail-box'>")
            html.append(
                f"<div class='fail-header'>❌ برنامه تغذیه برای این کاربر تولید نشد ({rec.outcome_fa})</div>"
            )
            html.append(
                f"<div class='fail-detail'><strong>مرحله توقف در موتور:</strong> {rec.failure_stage_fa}</div>"
            )

            codes_spans = " ".join([f"<span class='code-tag'>{c}</span>" for c in rec.reason_codes])
            html.append(
                f"<div class='fail-detail'><strong>کدهای خطای سیستم:</strong> {codes_spans}</div>"
            )
            html.append(
                f"<div class='fail-detail'><strong>علت عدم تولید برنامه:</strong> {rec.human_reason_fa}</div>"
            )
            html.append(
                f"<div class='fail-detail'><strong>مدت‌زمان پردازش موتور:</strong> {rec.generation_duration_seconds} ثانیه</div>"
            )
            html.append("</div>")

        html.append("</div>")  # profile-card

    html.append("</body></html>")
    return "\n".join(html)


def export_audit_json(
    records: list[AuditRecordDetail],
    summary: dict[str, Any],
    output_path: str,
) -> None:
    data = {
        "metadata": {
            "title": summary["title"],
            "generated_at": summary["timestamp"],
            "git_commit": summary["git_commit"],
            "random_seed": summary["random_seed"],
            "total_profiles": summary["total_profiles"],
            "planner_version": PLANNER_VERSION,
            "planner_policy_version": PLANNER_POLICY_VERSION,
        },
        "summary": summary,
        "records": [asdict(r) for r in records],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"Structured audit JSON saved to {output_path} ({os.path.getsize(output_path):,} bytes)")


def compile_persian_pdf(html_content: str, output_path: str) -> None:
    print(f"Compiling Persian PDF via WeasyPrint to {output_path}...")
    font_config = weasyprint.text.fonts.FontConfiguration()
    doc = weasyprint.HTML(string=html_content)
    doc.write_pdf(output_path, font_config=font_config)
    size = os.path.getsize(output_path)
    print(f"PDF successfully generated: {output_path} ({size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 100-profile randomized nutrition engine audit."
    )
    parser.add_argument("--count", type=int, default=100, help="Number of profiles (default: 100)")
    parser.add_argument(
        "--seed", type=int, default=20260903, help="Deterministic seed (default: 20260903)"
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="/home/mohammad/project/fitsho/artifacts/nutrition_engine_100_profiles_audit.json",
        help="Path for JSON output",
    )
    parser.add_argument(
        "--output-pdf",
        type=str,
        default="/home/mohammad/project/fitsho/artifacts/nutrition_engine_100_profiles_audit.pdf",
        help="Path for PDF output",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=DEFAULT_DB_URL,
        help=f"Database connection URL (default: {DEFAULT_DB_URL})",
    )
    args = parser.parse_args()

    # Ensure parent output directories exist
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_pdf).parent.mkdir(parents=True, exist_ok=True)

    records = run_100_profiles_audit(db_url=args.db_url, seed=args.seed, count=args.count)
    summary = build_audit_summary(records, seed=args.seed)

    # 1. Export structured JSON
    export_audit_json(records, summary, args.output_json)

    # 2. Render Persian PDF
    html_content = generate_persian_html(records, summary)
    compile_persian_pdf(html_content, args.output_pdf)

    print("\n" + "=" * 60)
    print("FITSHO NUTRITION ENGINE AUDIT COMPLETE")
    print("=" * 60)
    print(f"Profiles: {summary['total_profiles']}")
    print(f"Successful: {summary['success_count']}")
    print(f"Failed: {summary['failure_count']}")
    print(f"Success rate: {summary['success_rate']}%")
    print(f"Average generation time: {summary['duration_seconds']['average']}s")
    print(f"Median generation time: {summary['duration_seconds']['median']}s")
    print(f"Slowest generation: {summary['duration_seconds']['maximum']}s")
    print(f"PDF Path: {args.output_pdf}")
    print(f"JSON Path: {args.output_json}")
    print("=" * 60)


if __name__ == "__main__":
    main()
