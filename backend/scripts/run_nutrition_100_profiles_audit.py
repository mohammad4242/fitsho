# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import os
import random
import socketserver
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import weasyprint
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

# Ensure all SQLAlchemy models and relationships are registered
import app.main  # noqa: F401
from app.auth.models import User
from app.nutrition.audit_gates import (
    AUDIT_SCHEMA_VERSION,
    FROZEN_HOLDOUT_DEFINITION_VERSION,
    summarize_audit,
)
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
    NutritionCatalogueMeal,
    NutritionEstimate,
    NutritionFoodItem,
    NutritionMedicalCondition,
    NutritionMedicalProfile,
    NutritionPlanGeneration,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionSafetyReason,
    NutritionStructuredExercise,
)
from app.nutrition.plan_service import generate_weekly_plan
from app.nutrition.planner_policy import PLANNER_POLICY_VERSION, PLANNER_VERSION
from app.nutrition.schemas import WeeklyPlanResponse
from app.profile.enums import FitnessGoal, ProductMode, Sex, TrainingIntensity
from app.profile.models import BodyMeasurement, UserProfile

DB_URL = "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_nutrition_audit"
HOLDOUT_PROFILE_SEED = 20261017

# Persian translations
FA_SEX = {"male": "مرد", "female": "زن"}
FA_GOAL = {
    "lose_weight": "کاهش وزن",
    "fat_loss": "چربی‌سوزی",
    "gain_weight": "افزایش وزن",
    "build_muscle": "عضله‌سازی",
    "body_recomposition": "ترکیب بدنی (ریکامپ)",
    "maintain_weight": "تثبیت وزن",
    "improve_fitness": "آمادگی جسمانی",
    "strength": "افزایش قدرت",
}
FA_ACTIVITY = {
    "sedentary": "بی‌تحرک (پشت‌میزنشین)",
    "light": "سبک (تحرک کم روزمره)",
    "moderate": "متوسط (تحرک روزانه خوب)",
    "very_active": "بسیار پرتحرک (شغل سنگین/فعال)",
}
FA_EXERCISE_TYPE = {
    "resistance": "بدنسازی / قدرتی",
    "endurance": "هوازی / استقامتی",
    "mixed": "ترکیبی (قدرتی + هوازی)",
    "other": "سایر رشته‌های ورزشی",
}
FA_INTENSITY = {
    "light": "سبک",
    "moderate": "متوسط",
    "vigorous": "شدید / سنگین",
}
FA_BUDGET_STYLE = {
    "strict": "سخت‌گیرانه",
    "flexible": "انعطاف‌پذیر",
}
FA_DIETARY_PATTERN = {
    "omnivore": "همه‌چیزخوار",
    "vegetarian": "گیاه‌خوار (لاکتو-اوو)",
    "vegan": "کاملاً وگان (گیاه‌خوار محض)",
}
FA_COOKING_SKILL = {
    "none": "بدون مهارت",
    "basic": "مقدماتی",
    "confident": "ماهر",
}
FA_MEAL_PREP = {
    "daily": "روزانه و تازه",
    "batch": "پخت انبوه (هفتگی)",
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
    "post_workout": "پس از تمرین",
    "free_meal": "وعده آزاد",
}
FA_OUTCOME = {
    "success": "موفق",
    "infeasible": "غیرقابل اجرا (بودجه یا کاتالوگ)",
    "target_infeasible": "ناممکن از نظر اهداف علمی/ماکرو",
    "safety_blocked": "توقف ایمنی پزشکی",
    "live_price_unavailable": "عدم دسترسی به قیمت‌ها",
    "failed": "ناموفق",
    "unhandled_engine_error": "خطای داخلی کنترل‌نشده در موتور",
}
FA_REASONS = {
    "SAFE_FEASIBLE_DRAFT_GENERATED": "برنامه ایمن و قابل‌اجرا تولید شد",
    "STRICT_BUDGET_EXCEEDED": "هزینه هفتگی فراتر از سقف بودجه سخت‌گیرانه است",
    "FLEXIBLE_BUDGET_CAP_EXCEEDED": "هزینه هفتگی فراتر از سقف بودجه انعطاف‌پذیر (+۱۵٪) است",
    "GOAL_RESELECTION_REQUIRED": "هدف انتخابی با نوع فعالیت یا ضوابط علمی همخوانی ندارد",
    "PHYSICIAN_MANUAL_PLAN_REQUIRED": "نیاز به تنظیم دستی رژیم توسط پزشک به دلیل شرایط بالینی",
    "UNSUPPORTED_OR_HARD_BLOCKED": "توقف ایمنی: شرایط سلامتی کاربر در سیستم خودکار پشتیبانی نمی‌شود",
    "CALORIE_TARGET_OUTSIDE_TOLERANCE": "کالری نهایی وعده‌ها خارج از محدوده تلورانس کالری هدف است",
    "MACRONUTRIENT_FLOOR_NOT_MET": "کف مجاز فیزیولوژیک پروتئین، کربوهیدرات یا چربی تأمین نشد",
    "MACRONUTRIENT_MAXIMUM_EXCEEDED": "میزان ماکرونوترینت از سقف مجاز فراتر رفت",
    "NUTRIENT_UPPER_LIMIT_EXCEEDED": "مصرف ریزمغذی‌ها از حد بالای مجاز ایمنی (UL) تجاوز کرد",
    "INSUFFICIENT_PRICE_COVERAGE": "پوشش قیمتی یا اقلام غذایی برای این الگو کافی نیست",
    "SCHEDULED_MEAL_UNAVAILABLE": "عدم دسترسی به تمپلیت غذایی تعیین‌شده در برنامه (کرش کاتالوگ)",
    "UNHANDLED_ENGINE_ERROR": "خطای داخلی کنترل‌نشده در پایپ‌لاین موتور",
    "UNHANDLED_VALUE_ERROR": "خطای مقدار نامعتبر در موتور برنامه‌ریز",
}


@dataclass
class ProfileSpec:
    index: int
    name: str
    sex: str
    age: int
    birth_date: date
    height_cm: int
    weight_kg: float
    fitness_goal: str
    daily_activity_level: str
    trains: bool
    exercise_type: str | None
    days_per_week: int | None
    minutes_per_session: int | None
    intensity: str | None
    meals_per_day: int
    snacks_per_day: int
    main_meal_bucket: str
    snack_bucket: str
    monthly_budget_irr: int
    budget_style: str
    dietary_pattern: str
    plan_style: str
    cooking_skill: str
    cooking_time_minutes: int
    cooking_frequency_per_week: int
    meal_prep_preference: str
    preferred_variety: str
    max_meal_repetition: int
    favourite_foods: list[str]
    disliked_foods: list[str]
    allergies: list[str]
    intolerances: list[str]
    refused_foods: list[str]
    never_suggest_foods: list[str]
    religious_exclusions: list[str]
    medical_conditions: list[str]
    safety_flags: dict[str, bool]


@dataclass
class DailyMealFoodItem:
    name_fa: str
    grams: float
    cost_irr: int


@dataclass
class DailyMealItem:
    role: str
    category: str
    name_fa: str
    cost_irr: int
    foods: list[DailyMealFoodItem]


@dataclass
class DayPlanItem:
    day_index: int
    day_name: str
    cost_irr: int
    calories: float
    protein: float
    carbs: float
    fat: float
    meals: list[DailyMealItem]


@dataclass
class AuditRecord:
    spec: ProfileSpec
    outcome: str
    reason_codes: list[str]
    warning_codes: list[str]
    diagnostics: dict[str, Any]
    target_calories: float | None
    target_protein: float | None
    target_carbs: float | None
    target_fat: float | None
    bmr: float | None
    tdee: float | None
    weekly_budget_irr: int
    calculated_weekly_cost_irr: int | None
    plan_id: str | None
    days: list[DayPlanItem]
    root_cause: str
    solution: str
    generation_latency_ms: float = 0.0
    safety_invariant_violations: list[str] = field(default_factory=list)


def generate_100_profiles(seed: int = 20260903, count: int = 100) -> list[ProfileSpec]:
    rng = random.Random(seed)
    today = date(2026, 9, 3)

    profiles: list[ProfileSpec] = []

    sample_favourites = [
        "سینه مرغ", "عدس", "موز", "جو دوسر", "گردو", "سیب", "تخم‌مرغ", "برنج", "کره بادام‌زمینی", "ماست"
    ]
    sample_dislikes = [
        "بادمجان", "کرفس", "پیاز", "قارچ", "کدو سبز", "ماهی", "گل کلم", "فلفل دلمه‌ای"
    ]
    allergy_candidates = [
        "بادام‌زمینی", "شیر", "تخم‌مرغ", "ماهی", "گلوتن", "کنجد", "سویا"
    ]

    for i in range(1, count + 1):
        sex = "male" if rng.random() < 0.52 else "female"

        r_age = rng.random()
        if r_age < 0.25:
            age = rng.randint(19, 26)
        elif r_age < 0.70:
            age = rng.randint(27, 45)
        elif r_age < 0.90:
            age = rng.randint(46, 59)
        else:
            age = rng.randint(60, 72)

        birth_date = date(today.year - age, rng.randint(1, 12), rng.randint(1, 28))

        if sex == "male":
            height = rng.randint(164, 194)
            target_bmi = rng.uniform(19.5, 34.0)
        else:
            height = rng.randint(150, 178)
            target_bmi = rng.uniform(18.5, 33.0)

        weight = round((target_bmi * ((height / 100) ** 2)), 1)
        weight = max(42.0, min(135.0, weight))

        r_goal = rng.random()
        if r_goal < 0.35:
            goal = "lose_weight"
        elif r_goal < 0.52:
            goal = "build_muscle"
        elif r_goal < 0.65:
            goal = "fat_loss"
        elif r_goal < 0.78:
            goal = "body_recomposition"
        elif r_goal < 0.88:
            goal = "gain_weight"
        elif r_goal < 0.96:
            goal = "maintain_weight"
        else:
            goal = "improve_fitness"

        r_act = rng.random()
        if r_act < 0.22:
            act_level = "sedentary"
        elif r_act < 0.52:
            act_level = "light"
        elif r_act < 0.85:
            act_level = "moderate"
        else:
            act_level = "very_active"

        trains = rng.random() < 0.75
        ex_type = None
        days_per_week = None
        minutes_per_session = None
        intensity = None

        if trains:
            r_ex = rng.random()
            if r_ex < 0.60:
                ex_type = "resistance"
            elif r_ex < 0.82:
                ex_type = "mixed"
            elif r_ex < 0.94:
                ex_type = "endurance"
            else:
                ex_type = "other"

            days_per_week = rng.choice([2, 3, 4, 5, 6])
            minutes_per_session = rng.choice([30, 45, 60, 75, 90])
            intensity = rng.choice(["light", "moderate", "vigorous"])
        else:
            trains = False

        r_meal = rng.random()
        if r_meal < 0.20:
            meals_count = 2
            meal_bucket = "two_main_meals"
        elif r_meal < 0.80:
            meals_count = 3
            meal_bucket = "three_main_meals"
        else:
            meals_count = 4
            meal_bucket = "four_or_more_main_meals"

        r_snack = rng.random()
        if r_snack < 0.15:
            snacks_count = 0
            snack_bucket = "zero_snacks"
        elif r_snack < 0.65:
            snacks_count = 1
            snack_bucket = "one_snack"
        elif r_snack < 0.90:
            snacks_count = 2
            snack_bucket = "two_snacks"
        else:
            snacks_count = 3
            snack_bucket = "three_or_more_snacks"

        r_b = rng.random()
        if r_b < 0.18:
            monthly_budget = rng.choice([15_000_000, 20_000_000, 25_000_000, 30_000_000, 35_000_000, 40_000_000])
        elif r_b < 0.55:
            monthly_budget = rng.choice([50_000_000, 60_000_000, 75_000_000, 90_000_000, 110_000_000])
        elif r_b < 0.85:
            monthly_budget = rng.choice([140_000_000, 180_000_000, 220_000_000, 260_000_000])
        else:
            monthly_budget = rng.choice([320_000_000, 400_000_000, 500_000_000, 600_000_000])

        budget_style = "strict" if rng.random() < 0.45 else "flexible"

        r_diet = rng.random()
        if r_diet < 0.72:
            dietary_pattern = "omnivore"
        elif r_diet < 0.88:
            dietary_pattern = "vegetarian"
        else:
            dietary_pattern = "vegan"

        plan_style = rng.choice(["economical", "balanced", "simple"])
        cooking_skill = rng.choice(["none", "basic", "confident"])
        cooking_time = rng.choice([15, 30, 45, 60, 90])
        cooking_freq = rng.randint(1, 7)
        meal_prep = rng.choice(["daily", "batch", "mixed", "no_cooking"])
        variety = rng.choice(["low", "medium", "high"])
        max_rep = rng.randint(1, 5)

        liked: list[str] = []
        if rng.random() < 0.50:
            liked = rng.sample(sample_favourites, rng.randint(1, 3))

        disliked: list[str] = []
        if rng.random() < 0.35:
            disliked = rng.sample(sample_dislikes, rng.randint(1, 2))

        allergies: list[str] = []
        intolerances: list[str] = []
        if rng.random() < 0.28:
            selected_all = rng.sample(allergy_candidates, rng.randint(1, 2))
            if rng.random() < 0.60:
                allergies = selected_all[:1]
            else:
                intolerances = selected_all[:1]
            if len(selected_all) > 1 and rng.random() < 0.40:
                allergies.append(selected_all[1])

        refused: list[str] = []
        if rng.random() < 0.10:
            refused = ["سوسیس", "سس مایونز"]

        med_conditions: list[str] = []
        safety_flags = {
            "dangerous_food_reaction_history": False,
            "pregnant": False,
            "breastfeeding": False,
            "eating_disorder_diagnosed": False,
            "eating_disorder_active_symptoms": False,
            "emergency_or_danger_symptoms": False,
            "complex_medication_food_interaction": False,
            "physician_dietary_restrictions": False,
            "other_relevant_condition": False,
        }

        r_safety = rng.random()
        if r_safety < 0.80:
            pass
        elif r_safety < 0.90:
            cond = rng.choice([
                MedicalConditionCode.CONTROLLED_HYPERTENSION.value,
                MedicalConditionCode.LIPID_DISORDER.value,
                MedicalConditionCode.TYPE_2_DIABETES_NON_INSULIN.value,
            ])
            med_conditions.append(cond)
        else:
            r_block = rng.random()
            if r_block < 0.35 and sex == "female" and 20 <= age <= 42:
                safety_flags["pregnant"] = True
            elif r_block < 0.60 and sex == "female" and 20 <= age <= 42:
                safety_flags["breastfeeding"] = True
            elif r_block < 0.80:
                safety_flags["eating_disorder_diagnosed"] = True
            else:
                med_conditions.append(MedicalConditionCode.KIDNEY_DISEASE.value)

        spec = ProfileSpec(
            index=i,
            name=f"کاربر شماره {i}",
            sex=sex,
            age=age,
            birth_date=birth_date,
            height_cm=height,
            weight_kg=weight,
            fitness_goal=goal,
            daily_activity_level=act_level,
            trains=trains,
            exercise_type=ex_type,
            days_per_week=days_per_week,
            minutes_per_session=minutes_per_session,
            intensity=intensity,
            meals_per_day=meals_count,
            snacks_per_day=snacks_count,
            main_meal_bucket=meal_bucket,
            snack_bucket=snack_bucket,
            monthly_budget_irr=monthly_budget,
            budget_style=budget_style,
            dietary_pattern=dietary_pattern,
            plan_style=plan_style,
            cooking_skill=cooking_skill,
            cooking_time_minutes=cooking_time,
            cooking_frequency_per_week=cooking_freq,
            meal_prep_preference=meal_prep,
            preferred_variety=variety,
            max_meal_repetition=max_rep,
            favourite_foods=liked,
            disliked_foods=disliked,
            allergies=allergies,
            intolerances=intolerances,
            refused_foods=refused,
            never_suggest_foods=[],
            religious_exclusions=[],
            medical_conditions=med_conditions,
            safety_flags=safety_flags,
        )
        profiles.append(spec)

    return profiles


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=Path(__file__).parents[2]
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _catalogue_version(db: Session) -> str:
    foods = db.scalars(select(NutritionCatalogueFood)).all()
    meals = db.scalars(select(NutritionCatalogueMeal)).all()
    rows = [
        *(f"food:{food.id}:{food.slug}:{food.data_version}:{food.verification_status.value}" for food in foods),
        *(f"meal:{meal.id}:{meal.code}:{meal.verification_status.value}" for meal in meals),
    ]
    return sha256("\n".join(sorted(rows)).encode()).hexdigest()[:16]


def independent_safety_invariants(
    spec: ProfileSpec,
    plan: WeeklyPlanResponse,
    foods_by_id: dict[str, NutritionCatalogueFood],
    meals_by_id: dict[str, NutritionCatalogueMeal],
) -> list[str]:
    violations: list[str] = []
    if spec.medical_conditions or any(spec.safety_flags.values()):
        violations.append("MEDICAL_SAFETY_VIOLATION")
    weekly_budget = spec.monthly_budget_irr * 12 // 52
    budget_cap = (
        weekly_budget
        if spec.budget_style == "strict"
        else int(Decimal(weekly_budget) * Decimal("1.15"))
    )
    if plan.weekly_cost_irr > budget_cap:
        violations.append("STRICT_BUDGET_VIOLATION" if spec.budget_style == "strict" else "FLEXIBLE_BUDGET_VIOLATION")

    restricted_names = {
        _normalise(name)
        for name in (*spec.allergies, *spec.intolerances, *spec.refused_foods, *spec.never_suggest_foods)
    }
    meal_usage: dict[str, int] = {}
    for day in plan.days:
        main_count = 0
        snack_count = 0
        for meal in day.meals:
            if meal.slot_role == "snack":
                snack_count += 1
            else:
                main_count += 1
            meal_id = str(meal.catalogue_meal_id) if meal.catalogue_meal_id else None
            catalogue_meal = meals_by_id.get(meal_id or "")
            if meal_id:
                meal_usage[meal_id] = meal_usage.get(meal_id, 0) + 1
                if catalogue_meal is None or catalogue_meal.verification_status.value != "verified":
                    violations.append("UNVERIFIED_MEAL")
            bounds = {
                str(item.food_id): item
                for item in catalogue_meal.items
            } if catalogue_meal else {}
            for food in meal.foods:
                if _normalise(food.name_fa) in restricted_names:
                    violations.append("EXCLUDED_OR_ALLERGENIC_FOOD")
                if food.food_id is None:
                    continue
                catalogue_food = foods_by_id.get(str(food.food_id))
                if catalogue_food is None or catalogue_food.verification_status.value != "verified":
                    violations.append("UNVERIFIED_FOOD")
                elif spec.dietary_pattern not in catalogue_food.dietary_patterns:
                    violations.append("DIETARY_PATTERN_VIOLATION")
                bound = bounds.get(str(food.food_id))
                if bound and not (float(bound.min_grams) <= food.grams <= float(bound.max_grams)):
                    violations.append("PORTION_BOUND_VIOLATION")
        if main_count != spec.meals_per_day:
            violations.append("MEAL_COUNT_CONTRACT_VIOLATION")
        if snack_count != spec.snacks_per_day:
            violations.append("SNACK_COUNT_CONTRACT_VIOLATION")
    if any(count > spec.max_meal_repetition for count in meal_usage.values()):
        violations.append("REPETITION_CONTRACT_VIOLATION")
    for nutrient in plan.nutrients.values():
        if nutrient.difference_from_limit is not None and nutrient.difference_from_limit > 0:
            violations.append("UPPER_LIMIT_VIOLATION")
    return sorted(set(violations))


def _normalise(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def run_audit(profiles: list[ProfileSpec], profile_seed: int = 20260903) -> list[AuditRecord]:
    engine = create_engine(DB_URL)
    records: list[AuditRecord] = []

    print(f"Starting audit of {len(profiles)} profiles against {DB_URL}...")

    with Session(engine) as db:
        db.execute(delete(User).where(User.email.like("audit_user_%@fitsho.test")))
        db.commit()
        foods_raw = db.scalars(select(NutritionCatalogueFood)).all()
        foods_by_id = {str(food.id): food for food in foods_raw}
        meals_by_id = {
            str(meal.id): meal for meal in db.scalars(select(NutritionCatalogueMeal)).all()
        }
        catalogue_version = _catalogue_version(db)
        food_by_slug_or_name: dict[str, UUID] = {}
        for f in foods_raw:
            food_by_slug_or_name[f.slug] = f.id
            food_by_slug_or_name[f.name_fa] = f.id

        for idx, spec in enumerate(profiles, start=1):
            uid = uuid5(NAMESPACE_URL, f"fitsho-nutrition-audit:{profile_seed}:{spec.index}")
            u = User(id=uid, email=f"audit_user_{spec.index}@fitsho.test", password_hash="hash")
            db.add(u)
            db.flush()

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

            bm = BodyMeasurement(user_id=uid, weight_kg=Decimal(str(spec.weight_kg)))
            db.add(bm)

            med = NutritionMedicalProfile(
                user_id=uid,
                dangerous_food_reaction_history=spec.safety_flags["dangerous_food_reaction_history"],
                pregnant=spec.safety_flags["pregnant"],
                breastfeeding=spec.safety_flags["breastfeeding"],
                eating_disorder_diagnosed=spec.safety_flags["eating_disorder_diagnosed"],
                eating_disorder_active_symptoms=spec.safety_flags["eating_disorder_active_symptoms"],
                emergency_or_danger_symptoms=spec.safety_flags["emergency_or_danger_symptoms"],
                complex_medication_food_interaction=spec.safety_flags["complex_medication_food_interaction"],
                physician_dietary_restrictions=spec.safety_flags["physician_dietary_restrictions"],
                other_relevant_condition=spec.safety_flags["other_relevant_condition"],
            )
            db.add(med)
            db.flush()
            for c_code in spec.medical_conditions:
                db.add(NutritionMedicalCondition(user_id=uid, code=MedicalConditionCode(c_code)))

            safety_outcome = SafetyOutcome.STANDARD_AUTOMATIC
            safety_reasons = ["no_review_condition_declared"]
            if spec.safety_flags["pregnant"]:
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = ["pregnancy"]
            elif spec.safety_flags["breastfeeding"]:
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = ["breastfeeding"]
            elif spec.safety_flags["eating_disorder_diagnosed"] or spec.safety_flags["eating_disorder_active_symptoms"]:
                safety_outcome = SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
                safety_reasons = ["eating_disorder"]
            elif spec.safety_flags["emergency_or_danger_symptoms"]:
                safety_outcome = SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED
                safety_reasons = ["danger_symptoms_declared"]
            elif any(c in {MedicalConditionCode.KIDNEY_DISEASE.value, MedicalConditionCode.DIALYSIS.value, MedicalConditionCode.LIVER_DISEASE.value} for c in spec.medical_conditions):
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

            eff_meals = 2 if spec.main_meal_bucket == "two_main_meals" else 3 if spec.main_meal_bucket == "three_main_meals" else 4
            eff_snacks = 0 if spec.snack_bucket == "zero_snacks" else 1 if spec.snack_bucket == "one_snack" else 2 if spec.snack_bucket == "two_snacks" else 3

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

            ex = NutritionStructuredExercise(
                user_id=uid,
                trains=spec.trains,
                exercise_type=StructuredExerciseType(spec.exercise_type) if spec.exercise_type else None,
                days_per_week=spec.days_per_week,
                minutes_per_session=spec.minutes_per_session,
                intensity=TrainingIntensity(spec.intensity) if spec.intensity else None,
                source=StructuredExerciseSource.USER_REPORTED,
            )
            db.add(ex)

            for item_name in spec.favourite_foods:
                cat_id = food_by_slug_or_name.get(item_name)
                db.add(NutritionFoodItem(
                    user_id=uid, kind=FoodItemKind.FAVOURITE, name=item_name,
                    normalized_name=item_name.strip().casefold(), catalogue_food_id=cat_id
                ))
            for item_name in spec.disliked_foods:
                cat_id = food_by_slug_or_name.get(item_name)
                db.add(NutritionFoodItem(
                    user_id=uid, kind=FoodItemKind.DISLIKED, name=item_name,
                    normalized_name=item_name.strip().casefold(), catalogue_food_id=cat_id
                ))
            for item_name in spec.allergies:
                db.add(NutritionFoodItem(
                    user_id=uid, kind=FoodItemKind.ALLERGY, name=item_name,
                    normalized_name=item_name.strip().casefold(), catalogue_food_id=None
                ))
            for item_name in spec.intolerances:
                db.add(NutritionFoodItem(
                    user_id=uid, kind=FoodItemKind.INTOLERANCE, name=item_name,
                    normalized_name=item_name.strip().casefold(), catalogue_food_id=None
                ))
            for item_name in spec.refused_foods:
                db.add(NutritionFoodItem(
                    user_id=uid, kind=FoodItemKind.REFUSED, name=item_name,
                    normalized_name=item_name.strip().casefold(), catalogue_food_id=None
                ))

            db.commit()

            outcome: str = "failed"
            reason_codes: list[str] = []
            warning_codes: list[str] = []
            plan_id: str | None = None
            plan_obj: WeeklyPlanResponse | None = None
            diag: dict[str, Any] = {}
            weekly_cost_irr: int | None = None
            generation_started = time.perf_counter()

            try:
                gen_resp = generate_weekly_plan(db, uid)
                outcome = gen_resp.outcome
                reason_codes = list(gen_resp.reason_codes)
                warning_codes = list(gen_resp.warning_codes)
                plan_obj = gen_resp.plan
                if plan_obj:
                    plan_id = str(plan_obj.id)
                    weekly_cost_irr = plan_obj.weekly_cost_irr

                gen_row = db.scalar(
                    select(NutritionPlanGeneration)
                    .where(NutritionPlanGeneration.user_id == uid)
                    .order_by(NutritionPlanGeneration.created_at.desc())
                    .limit(1)
                )
                if gen_row:
                    diag = gen_row.diagnostic_snapshot or {}
                    if not weekly_cost_irr and "weekly_cost_irr" in diag:
                        try:
                            weekly_cost_irr = int(Decimal(str(diag["weekly_cost_irr"])))
                        except Exception:
                            pass

            except ValueError as val_err:
                outcome = "infeasible"
                err_msg = str(val_err)
                if "Scheduled Meal Catalogue template is unavailable" in err_msg:
                    reason_codes = ["SCHEDULED_MEAL_UNAVAILABLE"]
                else:
                    reason_codes = ["UNHANDLED_VALUE_ERROR"]
                diag = {"exception": err_msg, "exception_type": "ValueError"}
            except Exception as unhandled_err:
                outcome = "failed"
                reason_codes = ["UNHANDLED_ENGINE_ERROR"]
                diag = {"exception": str(unhandled_err), "exception_type": type(unhandled_err).__name__}
            generation_latency_ms = (time.perf_counter() - generation_started) * 1000.0
            invariant_violations = (
                independent_safety_invariants(spec, plan_obj, foods_by_id, meals_by_id)
                if outcome == "success" and plan_obj is not None
                else []
            )
            if invariant_violations:
                diag["planner_outcome"] = outcome
                diag["audit_safety_invariant_violations"] = invariant_violations
                outcome = "failed"
                reason_codes = ["AUDIT_SAFETY_INVARIANT_VIOLATION"]
            diag["audit_schema_version"] = AUDIT_SCHEMA_VERSION
            diag["catalogue_version"] = catalogue_version

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
                target_map = {t.metric.value: float(t.preferred_value or 0) for t in est_row.targets}
                target_kcal = target_map.get("goal_calories")
                target_protein = target_map.get("protein")
                target_carbs = target_map.get("carbohydrate")
                target_fat = target_map.get("total_fat")
                bmr_val = target_map.get("bmr")
                tdee_val = target_map.get("tdee")

            day_plan_items: list[DayPlanItem] = []
            if plan_obj and plan_obj.days:
                weekday_keys = ["saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
                for day in plan_obj.days:
                    meals_items: list[DailyMealItem] = []
                    for m in day.meals:
                        food_items = [
                            DailyMealFoodItem(
                                name_fa=f.name_fa,
                                grams=round(f.grams, 1),
                                cost_irr=f.cost_irr,
                            )
                            for f in m.foods
                        ]
                        meals_items.append(
                            DailyMealItem(
                                role=m.slot_role,
                                category=m.catalogue_meal_category or "main_meal",
                                name_fa=m.name_fa or FA_MEAL_ROLE.get(m.slot_role, m.slot_role),
                                cost_irr=m.cost_irr,
                                foods=food_items,
                            )
                        )
                    d_name = FA_WEEKDAY[weekday_keys[day.day_index % 7]]
                    day_plan_items.append(
                        DayPlanItem(
                            day_index=day.day_index,
                            day_name=d_name,
                            cost_irr=day.cost_irr,
                            calories=round(day.nutrient_totals.get("energy_kcal", 0.0), 1),
                            protein=round(day.nutrient_totals.get("protein_g", 0.0), 1),
                            carbs=round(day.nutrient_totals.get("carbohydrate_g", 0.0), 1),
                            fat=round(day.nutrient_totals.get("total_fat_g", 0.0), 1),
                            meals=meals_items,
                        )
                    )

            rc_text, sol_text = analyze_failure(spec, outcome, reason_codes, diag, target_kcal, target_protein, weekly_cost_irr)

            record = AuditRecord(
                spec=spec,
                outcome=outcome,
                reason_codes=reason_codes,
                warning_codes=warning_codes,
                diagnostics=diag,
                target_calories=target_kcal,
                target_protein=target_protein,
                target_carbs=target_carbs,
                target_fat=target_fat,
                bmr=bmr_val,
                tdee=tdee_val,
                weekly_budget_irr=spec.monthly_budget_irr * 12 // 52,
                calculated_weekly_cost_irr=weekly_cost_irr,
                plan_id=plan_id,
                days=day_plan_items,
                root_cause=rc_text,
                solution=sol_text,
                generation_latency_ms=generation_latency_ms,
                safety_invariant_violations=invariant_violations,
            )
            records.append(record)

            if idx % 10 == 0 or idx == len(profiles):
                print(f"Progress: {idx}/{len(profiles)} profiles audited. Status: {outcome} ({reason_codes})")

    return records


def analyze_failure(
    spec: ProfileSpec,
    outcome: str,
    reasons: list[str],
    diag: dict[str, Any],
    target_kcal: float | None,
    target_protein: float | None,
    weekly_cost_irr: int | None,
) -> tuple[str, str]:
    if outcome == "success":
        return ("", "")

    weekly_budget_toman = (spec.monthly_budget_irr * 12 // 52) // 10
    weekly_cost_toman = (weekly_cost_irr // 10) if weekly_cost_irr else None

    if "STRICT_BUDGET_EXCEEDED" in reasons or "FLEXIBLE_BUDGET_CAP_EXCEEDED" in reasons:
        is_strict = "STRICT_BUDGET_EXCEEDED" in reasons
        cost_str = f"{weekly_cost_toman:,} تومان" if weekly_cost_toman else "فراتر از سقف"
        budget_str = f"{weekly_budget_toman:,} تومان"
        cause = (
            f"بودجه هفتگی کاربر {budget_str} ({'سخت‌گیرانه' if is_strict else 'انعطاف‌پذیر'}) تعیین شده بود، "
            f"اما ارزان‌ترین چیدمان معتبر تمپلیت‌های برنامه توسط موتور حداقل {cost_str} هزینه دارد و از سقف مجاز فراتر رفت."
        )
        sol = (
            "موتور برنامه‌ریز باید پیش از اعلام شکست، تمپلیت‌های فوق‌اقتصادی‌تر را جایگزین کند و "
            "منابع پروتئینی ارزان‌تر (نظیر حبوبات و تخم‌مرغ) را جایگزین گوشت/مرغ نماید."
        )
        return cause, sol

    if "SCHEDULED_MEAL_UNAVAILABLE" in reasons or "UNHANDLED_VALUE_ERROR" in reasons:
        cause = (
            f"کاربر رژیم {FA_DIETARY_PATTERN.get(spec.dietary_pattern, spec.dietary_pattern)} یا محدودیت غذایی دارد، "
            "اما ماتریس کاتالوگ برنامه غذایی انتخابی (Program Catalogue) شامل وعده‌های گوشتی یا حیوانی است. "
            "با حذف اقلام ممنوعه، تمپلیت‌های وعده نامعتبر شده و موتور به دلیل نبود مکانیزم جایگزینی (Fallback) متوقف شده است."
        )
        sol = (
            "افزودن برنامه‌های هفتگی اختصاصی برای گیاه‌خواران/وگان‌ها به کاتالوگ و پیاده‌سازی "
            "مکانیزم Template Substitution خودکار در زمان نامعتبر شدن یک وعده زمان‌بندی‌شده."
        )
        return cause, sol

    if "GOAL_RESELECTION_REQUIRED" in reasons:
        if spec.fitness_goal == "improve_fitness":
            cause = "هدف کاربر «آمادگی جسمانی» (improve_fitness) انتخاب شده است که در فرمول‌های علمی ماژول تغذیه به رسمیت شناخته نشده و رد می‌شود."
            sol = "تعریف ضرایب کالری و ماکرو برای هدف آمادگی جسمانی عمومی یا هدایت خودکار آن به ضرایب تثبیت وزن در لایه سرویس."
        else:
            cause = (
                f"کاربر هدف «{FA_GOAL.get(spec.fitness_goal, spec.fitness_goal)}» را برگزیده اما "
                f"نوع تمرین آن ({FA_EXERCISE_TYPE.get(spec.exercise_type or '', 'بدون تمرین')}) مقاومتی نیست. طبق قرارداد علمی سیستم، این ترکیب نیازمند تغییر هدف است."
            )
            sol = "امکان‌پذیر کردن برنامه تغذیه با ضرایب پایه پروتئین بدون الزام به تمرین مقاومتی، یا پیشنهاد اصلاح هدف در UI."
        return cause, sol

    if outcome == "safety_blocked" or "PHYSICIAN_MANUAL_PLAN_REQUIRED" in reasons or "UNSUPPORTED_OR_HARD_BLOCKED" in reasons:
        cond_names = []
        if spec.safety_flags.get("pregnant"):
            cond_names.append("بارداری")
        if spec.safety_flags.get("breastfeeding"):
            cond_names.append("شیردهی")
        if spec.safety_flags.get("eating_disorder_diagnosed"):
            cond_names.append("سابقه اختلال خوردن")
        if spec.safety_flags.get("emergency_or_danger_symptoms"):
            cond_names.append("علائم هشداردهنده بالینی")
        for c in spec.medical_conditions:
            cond_names.append(c)
        cond_str = "، ".join(cond_names) if cond_names else "شرایط بالینی اعلام‌شده"
        cause = (
            f"پروتکل ایمنی پزشکی سیستم به دلیل وضعیت سلامت کاربر ({cond_str}) اجازه تولید خودکار برنامه بدون نظارت مستقیم پزشک را نمی‌دهد."
        )
        sol = (
            "ایجاد پیش‌نویس اولیه محافظه‌کارانه و ارسال به کارتابل پزشک به جای مسدودسازی کامل، "
            "یا ارائه توصیه‌های عمومی سبک زندگی تا زمان تأیید پزشک."
        )
        return cause, sol

    if "CALORIE_TARGET_OUTSIDE_TOLERANCE" in reasons:
        cause = (
            "بعد از محاسبه و clamp شدن پرس غذاها در تمپلیت‌های منتخب، کالری نهایی بیش از ۱۰٪ با هدف علمی فاصله گرفته است."
        )
        sol = "پیاده‌سازی الگوریتم تنظیم مقیاس (Dynamic Rescaling) روی غذاهای غیراصلی جهت همگرا کردن کالری به هدف."
        return cause, sol

    if "MACRONUTRIENT_FLOOR_NOT_MET" in reasons or "MACRONUTRIENT_MAXIMUM_EXCEEDED" in reasons:
        cause = "ماکرونوترینت‌های محاسبه‌شده برنامه پس از تخصیص غذاها در تمپلیت‌ها، خارج از کریدور حداقل یا حداکثر مجاز فیزیولوژیک قرار گرفت."
        sol = "اصلاح وزن‌های مبنا در تمپلیت‌های کاتالوگ و اضافه کردن مرحله بالانس ماکروها قبل از اعتبارسنجی نهایی."
        return cause, sol

    if "NUTRIENT_UPPER_LIMIT_EXCEEDED" in reasons:
        cause = "میزان تجمعی یکی از ریزمغذی‌ها در برنامه هفتگی از سقف ایمنی مجاز (Tolerable Upper Intake Level) تجاوز کرده است."
        sol = "پیاده‌سازی مرحله تعدیل ریزمغذی (Micro Repair) برای کاهش حجم اقلام با چگالی بیش‌ازحد ریزمغذی خاص."
        return cause, sol

    if "INSUFFICIENT_PRICE_COVERAGE" in reasons:
        cause = "اقلام غذایی مجاز پس از فیلتر آلرژی‌ها و الگوهای مصرف، تنوع کافی برای پر کردن همه تمپلیت‌ها را نداشتند."
        sol = "توسعه سبد مواد غذایی کاتالوگ و تمپلیت‌های سبک با مواد اولیه در دسترس‌تر."
        return cause, sol

    exc = diag.get("exception", "")
    cause = f"خطای ناشناخته در فرآیند اجرا: {', '.join(reasons)} - {exc[:150]}"
    sol = "لاگ‌گذاری تفصیلی در سرویس برنامه‌ریز و افزودن ترای-کچ برای گزارش کد خطای مشخص."
    return cause, sol


def build_summary(records: list[AuditRecord]) -> dict[str, Any]:
    total = len(records)
    success_count = sum(1 for r in records if r.outcome == "success")
    failure_count = total - success_count
    success_rate = (success_count / total) * 100

    category_counts = {
        "Budget (تجاوز از بودجه)": 0,
        "Missing Template / Catalogue (عدم تطابق رژیم گیاه‌خواری/وگان یا آلرژی با تمپلیت‌ها)": 0,
        "Safety Block (توقف بالینی و ایمنی)": 0,
        "Goal Reselection (ناسازگاری هدف و تمرین)": 0,
        "Calorie / Macro Feasibility (انحراف کالری یا ماکرو)": 0,
        "Nutrient Upper Limit (سقف ریزمغذی‌ها)": 0,
        "Price Coverage (پوشش قیمتی اقلام)": 0,
        "Other / Unhandled (سایر خطاها)": 0,
    }

    reason_freq: dict[str, int] = {}

    for r in records:
        if r.outcome != "success":
            for rc in r.reason_codes:
                reason_freq[rc] = reason_freq.get(rc, 0) + 1

            if any(c in r.reason_codes for c in ["STRICT_BUDGET_EXCEEDED", "FLEXIBLE_BUDGET_CAP_EXCEEDED"]):
                category_counts["Budget (تجاوز از بودجه)"] += 1
            elif any(c in r.reason_codes for c in ["SCHEDULED_MEAL_UNAVAILABLE", "UNHANDLED_VALUE_ERROR"]):
                category_counts["Missing Template / Catalogue (عدم تطابق رژیم گیاه‌خواری/وگان یا آلرژی با تمپلیت‌ها)"] += 1
            elif r.outcome == "safety_blocked" or any(c in r.reason_codes for c in ["PHYSICIAN_MANUAL_PLAN_REQUIRED", "UNSUPPORTED_OR_HARD_BLOCKED"]):
                category_counts["Safety Block (توقف بالینی و ایمنی)"] += 1
            elif "GOAL_RESELECTION_REQUIRED" in r.reason_codes:
                category_counts["Goal Reselection (ناسازگاری هدف و تمرین)"] += 1
            elif any(c in r.reason_codes for c in ["CALORIE_TARGET_OUTSIDE_TOLERANCE", "MACRONUTRIENT_FLOOR_NOT_MET", "MACRONUTRIENT_MAXIMUM_EXCEEDED"]):
                category_counts["Calorie / Macro Feasibility (انحراف کالری یا ماکرو)"] += 1
            elif "NUTRIENT_UPPER_LIMIT_EXCEEDED" in r.reason_codes:
                category_counts["Nutrient Upper Limit (سقف ریزمغذی‌ها)"] += 1
            elif "INSUFFICIENT_PRICE_COVERAGE" in r.reason_codes:
                category_counts["Price Coverage (پوشش قیمتی اقلام)"] += 1
            else:
                category_counts["Other / Unhandled (سایر خطاها)"] += 1

    top_reasons = sorted(reason_freq.items(), key=lambda x: x[1], reverse=True)

    generation_summary = summarize_audit(asdict(record) for record in records)
    return {
        **generation_summary,
        "total": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 1),
        "category_counts": category_counts,
        "top_reasons": top_reasons,
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
    }


def generate_html(
    records: list[AuditRecord], summary: dict[str, Any], *, profile_seed: int
) -> str:
    css = """
    @page {
        size: A4;
        margin: 14mm 12mm 16mm 12mm;
        @bottom-left {
            content: "Fitsho Nutrition Engine - 100 Profiles Audit Report";
            font-family: 'Noto Sans Arabic', 'DejaVu Sans', sans-serif;
            font-size: 7pt;
            color: #64748b;
        }
        @bottom-right {
            content: "صفحه " counter(page) " از " counter(pages);
            font-family: 'Noto Sans Arabic', 'DejaVu Sans', sans-serif;
            font-size: 7.5pt;
            color: #64748b;
        }
    }
    body {
        direction: rtl;
        font-family: 'Noto Sans Arabic', 'DejaVu Sans', sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        font-size: 8.5pt;
        line-height: 1.55;
        margin: 0;
        padding: 0;
    }
    .page-break {
        page-break-before: always;
    }
    .avoid-break {
        page-break-inside: avoid;
    }
    h1, h2, h3, h4 {
        margin-top: 0;
        color: #0f172a;
    }
    .header-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%);
        color: #ffffff;
        padding: 16px 20px;
        border-radius: 10px;
        margin-bottom: 16px;
    }
    .header-banner h1 {
        color: #ffffff;
        font-size: 16pt;
        margin-bottom: 4px;
    }
    .header-banner p {
        margin: 0;
        font-size: 9pt;
        opacity: 0.9;
    }
    .kpi-grid {
        display: flex;
        flex-direction: row;
        gap: 10px;
        margin-bottom: 16px;
    }
    .kpi-box {
        flex: 1;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px 12px;
        text-align: center;
    }
    .kpi-val {
        font-size: 16pt;
        font-weight: bold;
        color: #1e3a8a;
    }
    .kpi-val.success { color: #059669; }
    .kpi-val.danger { color: #dc2626; }
    .kpi-label {
        font-size: 8pt;
        color: #64748b;
        margin-top: 2px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 14px;
        font-size: 8pt;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 6px 8px;
        text-align: right;
    }
    th {
        background-color: #f1f5f9;
        color: #334155;
        font-weight: bold;
    }
    .profile-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 14px;
        background-color: #ffffff;
    }
    .profile-card.success-border {
        border-right: 5px solid #059669;
    }
    .profile-card.fail-border {
        border-right: 5px solid #dc2626;
    }
    .profile-header {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 6px;
        margin-bottom: 8px;
    }
    .profile-title {
        font-size: 11pt;
        font-weight: bold;
        color: #0f172a;
    }
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 7.5pt;
        font-weight: bold;
    }
    .badge-success { background: #dcfce7; color: #15803d; }
    .badge-fail { background: #fee2e2; color: #b91c1c; }
    .badge-warning { background: #fef3c7; color: #b45309; }
    .badge-info { background: #e0f2fe; color: #0369a1; }
    .info-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 6px 12px;
        font-size: 7.8pt;
        margin-bottom: 8px;
    }
    .info-item {
        color: #475569;
    }
    .info-item strong {
        color: #1e293b;
    }
    .plan-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px;
        margin-top: 8px;
    }
    .day-row {
        margin-bottom: 6px;
        padding-bottom: 6px;
        border-bottom: 1px dashed #e2e8f0;
    }
    .day-row:last-child {
        border-bottom: none;
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .day-title {
        font-weight: bold;
        color: #1e3a8a;
        font-size: 8pt;
        margin-bottom: 2px;
    }
    .meal-inline {
        font-size: 7.6pt;
        color: #334155;
        margin-right: 8px;
    }
    .meal-foods {
        color: #64748b;
    }
    .day-summary-tag {
        float: left;
        font-size: 7.2pt;
        color: #0369a1;
        background: #e0f2fe;
        padding: 1px 6px;
        border-radius: 3px;
    }
    .fail-box {
        background: #fff5f5;
        border: 1px solid #fed7d7;
        border-radius: 6px;
        padding: 8px 12px;
        margin-top: 8px;
    }
    .fail-title {
        color: #c53030;
        font-weight: bold;
        font-size: 8.5pt;
        margin-bottom: 4px;
    }
    .fail-reason-code {
        font-family: monospace;
        background: #fee2e2;
        color: #991b1b;
        padding: 1px 5px;
        border-radius: 3px;
        font-size: 7.5pt;
        direction: ltr;
        display: inline-block;
    }
    .cause-block {
        font-size: 8pt;
        color: #4a5568;
        margin-top: 4px;
    }
    .sol-block {
        font-size: 8pt;
        color: #2b6cb0;
        margin-top: 4px;
        font-weight: 500;
    }
    .section-title {
        border-bottom: 2px solid #0284c7;
        padding-bottom: 4px;
        margin-top: 18px;
        margin-bottom: 10px;
        font-size: 11pt;
        color: #0f172a;
    }
    .recs-list {
        padding-right: 18px;
        margin: 6px 0;
        font-size: 8.2pt;
    }
    .recs-list li {
        margin-bottom: 4px;
    }
    """

    html = [
        "<!DOCTYPE html>",
        "<html lang='fa' dir='rtl'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<title>گزارش ممیزی موتور برنامه‌ریزی تغذیه Fitsho</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
    ]

    # Cover / Header Banner
    html.append("<div class='header-banner'>")
    html.append("<h1>گزارش ارزیابی جامع موتور تغذیه Fitsho (Audit ۱۰۰ کاربر)</h1>")
    html.append("<p>بررسی عملکرد، پایداری، پوشش کاتالوگ، و امکان‌پذیری تولید رژیم غذایی روی ۱۰۰ پروفایل تصادفی ولی واقعی</p>")
    html.append(
        f"<p style='font-size: 8pt; opacity: 0.8; margin-top: 4px;'>"
        f"Audit schema: {AUDIT_SCHEMA_VERSION} | Commit: {_git_commit()} | "
        f"Profile seed: {profile_seed} | دیتابیس مستقل تستی</p>"
    )
    html.append("</div>")

    # Management Summary KPIs
    html.append("<div class='kpi-grid'>")
    html.append(f"<div class='kpi-box'><div class='kpi-val'>{summary['total']}</div><div class='kpi-label'>تعداد کل پروفایل‌ها</div></div>")
    html.append(f"<div class='kpi-box'><div class='kpi-val success'>{summary['success_count']}</div><div class='kpi-label'>تولید موفق برنامه</div></div>")
    html.append(f"<div class='kpi-box'><div class='kpi-val danger'>{summary['failure_count']}</div><div class='kpi-label'>شکست / عدم تولید</div></div>")
    html.append(f"<div class='kpi-box'><div class='kpi-val'>{summary['success_rate']}%</div><div class='kpi-label'>نرخ موفقیت (Success Rate)</div></div>")
    html.append("</div>")

    # Category Breakdown Table
    html.append("<h2 class='section-title'>۱. تفکیک نتایج و دسته‌بندی علل شکست</h2>")
    html.append("<table>")
    html.append("<thead><tr><th>دسته‌بندی علت شکست</th><th>تعداد رخ‌داد</th><th>درصد از کل آزمون‌ها</th><th>شرح و دامنه تأثیر</th></tr></thead>")
    html.append("<tbody>")
    for cat, count in summary["category_counts"].items():
        pct = round((count / summary["total"]) * 100, 1)
        desc = ""
        if "Budget" in cat:
            desc = "هزینه تمپلیت‌های غذایی بیش از سقف بودجه نقدی کاربر است"
        elif "Missing Template" in cat:
            desc = "کاتالوگ برنامه فاقد تمپلیت سازگار با رژیم‌های گیاه‌خواری/وگان یا حذفیات آلرژی است"
        elif "Safety" in cat:
            desc = "مسدودسازی بالینی به دلیل بارداری، شیردهی، سابقه اختلال خوردن یا بیماری کلیوی"
        elif "Goal" in cat:
            desc = "عدم انطباق هدف هایپرتروفی/ریکامپ با فقدان تمرین مقاومتی یا هدف نامعتبر"
        elif "Calorie" in cat:
            desc = "انحراف بیش از ۱۰٪ کالری محقق‌شده از هدف علمی بعد از پرس‌بندی"
        elif "Nutrient" in cat:
            desc = "تجاوز یک ریزمغذی از سقف ایمنی Tolerable Upper Limit"
        elif "Price" in cat:
            desc = "نبود اقلام دارای قیمت معتبر پس از اعمال فیلتر آلرژی"
        else:
            desc = "سایر خطاهای کنترل‌نشده سیستم"

        html.append(f"<tr><td><strong>{cat}</strong></td><td style='text-align:center;'>{count}</td><td style='text-align:center;'>{pct}%</td><td>{desc}</td></tr>")
    html.append("</tbody></table>")

    # Detailed Reason Codes Table
    html.append("<h3 style='font-size: 9.5pt; color: #334155; margin-top: 12px;'>جدول فراوانی تمامی کدهای خطا (Reason Codes):</h3>")
    html.append("<table>")
    html.append("<thead><tr><th>کد خطا (Reason Code)</th><th>معنی و مفهوم فارسی</th><th>تعداد</th></tr></thead>")
    html.append("<tbody>")
    for code, count in summary["top_reasons"]:
        fa_desc = FA_REASONS.get(code, "خطای سیستم")
        html.append(f"<tr><td><span class='fail-reason-code'>{code}</span></td><td>{fa_desc}</td><td style='text-align:center;'>{count}</td></tr>")
    html.append("</tbody></table>")

    # Top 5 Architectural Issues
    html.append("<h2 class='section-title'>۲. مهم‌ترین آسیب‌پذیری‌ها و نقاط ضعف شناسایی‌شده در موتور Fitsho</h2>")
    html.append("<ol class='recs-list'>")
    html.append("<li><strong>نبود انعطاف در کاتالوگ برای رژیم‌های غیر گوشتی (گیاه‌خواری و وگان):</strong> تمام ۲۵ برنامه کاتالوگ (ECO, IRN, GYM, FAST, PREM) بر مبنای غذاهای گوشتی و مرغ تدوین شده‌اند. هنگامی که کاربر گیاه‌خوار یا وگان است، این غذاها حذف شده و سیستم به جای انتخاب تمپلیت جایگزین، با خطای کرش کنترل‌نشده <code>Scheduled Meal Catalogue template is unavailable</code> متوقف می‌شود.</li>")
    html.append("<li><strong>عدم تطابق کف هزینه تمپلیت‌ها با بودجه‌های اقتصادی (Budget Infeasibility):</strong> حداقل هزینه هفتگی یک سبد غذایی تولیدشده توسط موتور حدود ۳ تا ۳.۵ میلیون تومان است (معادل ۱۲ تا ۱۵ میلیون تومان در ماه). برای کاربرانی که بودجه ماهانه کمتر از این رقم دارند، موتور قبل از تلاش برای جایگزینی پروتئین‌های ارزان‌تر مستقیماً خطای <code>STRICT_BUDGET_EXCEEDED</code> یا <code>FLEXIBLE_BUDGET_CAP_EXCEEDED</code> می‌دهد.</li>")
    html.append("<li><strong>عدم اعتبارسنجی واحد قیمت در ورودی‌های دستی (Unit Conversion Vulnerability):</strong> در صورت ورود قیمت بر اساس <code>TOMAN_PER_UNIT</code> برای اقلامی که در جدول <code>PRICE_MASS_BASES</code> ثبت نشده‌اند (نظیر آناناس)، کل پایپ‌لاین موتور به دلیل بروز <code>PriceMassConversionMissingError</code> کرش می‌کند و هیچ برنامه‌ای برای هیچ کاربری ساخته نمی‌شود.</li>")
    html.append("<li><strong>انسداد سخت در هدف «آمادگی جسمانی» (improve_fitness):</strong> در حالی که در فرانت‌اند و مدل پروفایل کاربر گزینه آمادگی جسمانی وجود دارد، ماژول علمی <code>scientific.py</code> برای این هدف خطای <code>GoalReselectionRequiredError</code> پرتاب می‌کند که نشان‌دهنده ناهماهنگی بین لایه قرارداد کاربر و محاسبات علمی است.</li>")
    html.append("<li><strong>توقف کامل کاربران دارای منع ایمنی به جای ایجاد پیش‌نویس مشروط:</strong> کاربرانی که باردار، شیرده یا دارای سوابق خاص هستند، به صورت سخت مسدود می‌شوند (<code>safety_blocked</code>) و هیچ پلن پیشنهادی حتی برای بازبینی پزشک تولید نمی‌شود.</li>")
    html.append("</ol>")

    # Prioritized Roadmap
    html.append("<h2 class='section-title'>۳. پیشنهاد اولویت اصلاح (Repair Priority Roadmap)</h2>")
    html.append("<ol class='recs-list'>")
    html.append("<li><strong>اولویت ۱ (فوری): پیاده‌سازی Template Fallback / Substitution:</strong> در تابع <code>_build_scheduled_days</code>، چنانچه تمپلیت وعده زمان‌بندی‌شده به دلیل آلرژی یا رژیم در دسترس نبود، موتور باید از بین تمپلیت‌های مجاز همان دسته‌بندی (مثلاً ناهار گیاهی) مناسب‌ترین را جایگزین کند نه اینکه <code>ValueError</code> پرتاب نماید.</li>")
    html.append("<li><strong>اولویت ۲: غنی‌سازی کاتالوگ با برنامه‌های گیاه‌خواری (VEG) و فوق‌اقتصادی (ULTRA-ECO):</strong> حداقل ۲ تا ۳ برنامه هفتگی اختصاصی فاقد گوشت و مرغ با تمرکز بر تخم‌مرغ، حبوبات و لبنیات و همچنین تمپلیت‌های با هزینه هفتگی زیر ۱.۵ میلیون تومان اضافه شود.</li>")
    html.append("<li><strong>اولویت ۳: پشتیبانی از هدف improve_fitness در فرمول‌های علمی:</strong> افزودن ضرایب کالری و ماکرو برای آمادگی جسمانی در <code>scientific.py</code> (با ضریب تغییر وزن ۱.۰ و پروتئین پایه).</li>")
    html.append("<li><strong>اولویت ۴: اعتبارسنجی لایه قیمت‌گذاری دستی (Price Override Guard):</strong> در روت ادمین استعلام قیمت، اجازه ثبت واحد <code>TOMAN_PER_UNIT</code> به کالاهایی که تبدیل جرمی تأییدشده ندارند داده نشود.</li>")
    html.append("<li><strong>اولویت ۵: مکانیزم همگرایی کالری (Calorie Rescaling):</strong> افزودن یک مرحله تعدیل مقیاس نهایی برای پر کردن فاصله کالری هدف بدون برهم‌زدن نسبت ماکروها.</li>")
    html.append("</ol>")

    html.append("<div class='page-break'></div>")

    # Detailed 100 Profiles Section
    html.append("<h2 class='section-title'>۴. نتایج و گزارش تفصیلی به ازای تک‌تک ۱۰۰ کاربر</h2>")

    for rec in records:
        spec = rec.spec
        bmi = round(spec.weight_kg / ((spec.height_cm / 100) ** 2), 1)
        is_success = rec.outcome == "success"

        border_class = "success-border" if is_success else "fail-border"
        badge_html = "<span class='badge badge-success'>✅ برنامه با موفقیت ساخته شد</span>" if is_success else "<span class='badge badge-fail'>❌ برنامه ساخته نشد</span>"

        html.append(f"<div class='profile-card {border_class} avoid-break'>")
        html.append("<div class='profile-header'>")
        html.append(f"<div class='profile-title'>{spec.name} (شناسه تستی #{spec.index})</div>")
        html.append(f"<div>{badge_html}</div>")
        html.append("</div>")

        # Profile attributes grid
        ex_str = f"{FA_EXERCISE_TYPE.get(spec.exercise_type or '', 'تمرین')}، {spec.days_per_week} روز در هفته، {spec.minutes_per_session} دقیقه ({FA_INTENSITY.get(spec.intensity or '', '')})" if spec.trains else "بدون تمرین"
        restr_list = []
        if spec.allergies:
            restr_list.append(f"آلرژی: {', '.join(spec.allergies)}")
        if spec.intolerances:
            restr_list.append(f"عدم تحمل: {', '.join(spec.intolerances)}")
        if spec.disliked_foods:
            restr_list.append(f"غذاهای نامطلوب: {', '.join(spec.disliked_foods)}")
        if spec.refused_foods:
            restr_list.append(f"ردشده: {', '.join(spec.refused_foods)}")
        restr_str = " | ".join(restr_list) if restr_list else "ندارد"

        safety_str = "سالم"
        if spec.safety_flags["pregnant"]:
            safety_str = "بارداری"
        elif spec.safety_flags["breastfeeding"]:
            safety_str = "شیردهی"
        elif spec.safety_flags["eating_disorder_diagnosed"]:
            safety_str = "سابقه اختلال خوردن"
        elif spec.medical_conditions:
            safety_str = "، ".join(spec.medical_conditions)

        target_kcal_str = f"{int(rec.target_calories)} کیلوکالری" if rec.target_calories else "محاسبه نشد"
        target_protein_str = f"{int(rec.target_protein)} گرم" if rec.target_protein else "محاسبه نشد"
        budget_str = f"{spec.monthly_budget_irr // 10:,} تومان/ماه ({FA_BUDGET_STYLE.get(spec.budget_style, spec.budget_style)})"

        html.append("<div class='info-grid'>")
        html.append(f"<div class='info-item'><strong>سن و جنسیت:</strong> {spec.age} سال ({FA_SEX.get(spec.sex, spec.sex)})</div>")
        html.append(f"<div class='info-item'><strong>قد و وزن:</strong> {spec.height_cm} سانتی‌متر | {spec.weight_kg} کیلوگرم (BMI: {bmi})</div>")
        html.append(f"<div class='info-item'><strong>هدف فیتنس:</strong> {FA_GOAL.get(spec.fitness_goal, spec.fitness_goal)}</div>")
        html.append(f"<div class='info-item'><strong>فعالیت روزمره:</strong> {FA_ACTIVITY.get(spec.daily_activity_level, spec.daily_activity_level)}</div>")
        html.append(f"<div class='info-item' style='grid-column: span 2;'><strong>ورزش:</strong> {ex_str}</div>")
        html.append(f"<div class='info-item'><strong>کالری هدف:</strong> {target_kcal_str}</div>")
        html.append(f"<div class='info-item'><strong>پروتئین هدف:</strong> {target_protein_str}</div>")
        html.append(f"<div class='info-item'><strong>الگوی تغذیه:</strong> {FA_DIETARY_PATTERN.get(spec.dietary_pattern, spec.dietary_pattern)}</div>")
        html.append(f"<div class='info-item'><strong>بودجه ماهانه:</strong> {budget_str}</div>")
        html.append(f"<div class='info-item'><strong>تعداد وعده‌ها:</strong> {spec.meals_per_day} اصلی + {spec.snacks_per_day} میان‌وعده</div>")
        html.append(f"<div class='info-item'><strong>وضعیت سلامت:</strong> {safety_str}</div>")
        html.append(f"<div class='info-item' style='grid-column: span 3;'><strong>محدودیت‌ها و ترجیحات:</strong> {restr_str}</div>")
        html.append("</div>")

        # Result Body
        if is_success:
            cost_toman = rec.calculated_weekly_cost_irr // 10 if rec.calculated_weekly_cost_irr else 0
            html.append(f"<div style='font-size: 7.8pt; color: #059669; font-weight: bold; margin-bottom: 4px;'>هزینه هفتگی محقق‌شده: {cost_toman:,} تومان (بودجه مجاز هفتگی: {rec.weekly_budget_irr // 10:,} تومان)</div>")
            html.append("<div class='plan-box'>")
            for day in rec.days:
                meals_desc = []
                for m in day.meals:
                    f_parts = [f"{f.name_fa} ({int(f.grams)} گرم)" for f in m.foods]
                    f_str = "، ".join(f_parts) if f_parts else "وعده آزاد"
                    meals_desc.append(f"<strong>{m.name_fa}:</strong> {f_str}")

                meals_html = " | ".join(meals_desc)
                day_summary = f"کالری: {int(day.calories)} | پروتئین: {int(day.protein)}g | هزینه: {day.cost_irr // 10:,} تومان"

                html.append("<div class='day-row'>")
                html.append(f"<span class='day-summary-tag'>{day_summary}</span>")
                html.append(f"<div class='day-title'>📅 {day.day_name}:</div>")
                html.append(f"<div class='meal-inline'>{meals_html}</div>")
                html.append("</div>")
            html.append("</div>")
        else:
            html.append("<div class='fail-box'>")
            reasons_code_spans = " ".join([f"<span class='fail-reason-code'>{rc}</span>" for rc in rec.reason_codes])
            html.append(f"<div class='fail-title'>نتیجه: {FA_OUTCOME.get(rec.outcome, rec.outcome)} | کد خطا: {reasons_code_spans}</div>")
            html.append(f"<div class='cause-block'><strong>🔍 علت اصلی شکست:</strong> {rec.root_cause}</div>")
            html.append(f"<div class='sol-block'><strong>💡 راهکار پیشنهادی برای موتور:</strong> {rec.solution}</div>")
            html.append("</div>")

        html.append("</div>")

    html.append("</body></html>")
    return "\n".join(html)


def export_json(
    records: list[AuditRecord],
    summary: dict[str, Any],
    filepath: str,
    *,
    profile_seed: int,
) -> None:
    catalogue_version = next(
        (
            str(record.diagnostics["catalogue_version"])
            for record in records
            if "catalogue_version" in record.diagnostics
        ),
        "unknown",
    )
    data = {
        "metadata": {
            "title": "Fitsho Nutrition Generation Audit",
            "cohort": summary.get("cohort", "development"),
            "profile_count": len(records),
            "audit_schema_version": AUDIT_SCHEMA_VERSION,
            "git_commit": _git_commit(),
            "planner_version": PLANNER_VERSION,
            "planner_policy_version": PLANNER_POLICY_VERSION,
            "random_seed": profile_seed,
            "profile_generation_seed": profile_seed,
            "catalogue_version": catalogue_version,
            "holdout_definition_version": FROZEN_HOLDOUT_DEFINITION_VERSION,
            "holdout_profile_seed": HOLDOUT_PROFILE_SEED,
            "metadata_timestamp": datetime.now().astimezone().isoformat(),
            "database": DB_URL,
        },
        "summary": summary,
        "records": [asdict(r) for r in records],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"Audit JSON saved to {filepath}")


def render_pdf(html_content: str, output_filepath: str) -> None:
    print(f"Compiling PDF with WeasyPrint to {output_filepath}...")
    font_config = weasyprint.text.fonts.FontConfiguration()
    doc = weasyprint.HTML(string=html_content)
    doc.write_pdf(output_filepath, font_config=font_config)
    print(f"PDF generated successfully ({os.path.getsize(output_filepath):,} bytes)")


class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_server_in_background(directory: str, port: int = 8008) -> threading.Thread:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            # Silent logging
            pass

    def run_server() -> None:
        with ReuseTCPServer(("0.0.0.0", port), Handler) as httpd:
            httpd.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic nutrition generation audit.")
    parser.add_argument(
        "--cohort",
        choices=("development", "holdout", "stress"),
        default="development",
    )
    args = parser.parse_args()
    seed = 20260903 if args.cohort == "development" else HOLDOUT_PROFILE_SEED
    count = 100 if args.cohort == "development" else 200 if args.cohort == "holdout" else 300
    profiles = generate_100_profiles(seed=seed, count=count)
    records = run_audit(profiles, profile_seed=seed)
    summary = build_summary(records)
    summary["cohort"] = args.cohort

    # Output paths
    reports_dir = Path("/home/mohammad/project/fitsho/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    stem = f"fitsho_nutrition_{args.cohort}_audit"
    json_path = reports_dir / f"{stem}.json"
    pdf_path = reports_dir / f"{stem}.pdf"
    html_path = reports_dir / f"{stem}.html"

    # Also copy to frontend/public for easy access
    frontend_public = Path("/home/mohammad/project/fitsho/frontend/public")

    export_json(records, summary, str(json_path), profile_seed=seed)

    html_content = generate_html(records, summary, profile_seed=seed)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    render_pdf(html_content, str(pdf_path))

    # Copy to frontend/public
    if frontend_public.exists():
        import shutil
        shutil.copy(pdf_path, frontend_public / "fitsho_nutrition_engine_100_profiles_audit.pdf")

    print("\n" + "=" * 60)
    print(f"FITSHO NUTRITION {args.cohort.upper()} AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total Profiles: {summary['total']}")
    print(f"Success Count: {summary['success_count']}")
    print(f"Failure Count: {summary['failure_count']}")
    print(f"Success Rate: {summary['success_rate']}%")
    print("\nTop 5 Failure Reasons:")
    for code, count in summary["top_reasons"][:5]:
        print(f" - {code}: {count} ({FA_REASONS.get(code, '')})")
    print(f"\nPDF Path: {pdf_path}")
    print(f"JSON Path: {json_path}")
    print(f"Acceptance gates: {summary['acceptance']}")
    print("=" * 60)
    if not all(summary["acceptance"].values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
