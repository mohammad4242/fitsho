from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import weasyprint
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
import app.main  # Ensure all SQLAlchemy models and relationships are registered
from app.workout_reviews.models import WorkoutPlanReview  # Ensure models loaded
from app.exercises.enums import Equipment, ExerciseCautionTag, MuscleGroup
from app.exercises.models import Exercise
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.profile.training_compatibility import (
    UnsupportedResistanceTrainingCombinationError,
    require_supported_resistance_training_days,
)
from app.profile.training_focus import USER_SELECTABLE_PRIORITY_MUSCLES
from app.training_templates.engine_reference import load_template_references
from app.workouts.candidate_selector import caution_tags_for_training_cautions
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    ActivityLevel,
    BalanceAbility,
    Goal,
    ImpactLimit,
    LoadLimit,
    MedicalClearanceStatus,
    PhysicalJobDemand,
    RecoveryRating,
    TrainingExperience,
)
from app.workouts.program_engine.equipment import resolve_available_equipment
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    RecentTrainingHistory,
    WorkoutProgram,
)
from app.workouts.program_engine.volume_policy import session_hard_volume_cap
from app.workouts.service import WorkoutGenerationService

FA_TRANSLATIONS = {
    "male": "مرد",
    "female": "زن",
    "first_month": "ماه اول (تازه‌کار)",
    "beginner": "مبتدی",
    "intermediate": "متوسط",
    "advanced": "پیشرفته",
    "lose_weight": "کاهش وزن",
    "gain_weight": "افزایش وزن",
    "fat_loss": "چربی‌سوزی",
    "build_muscle": "عضله‌سازی و هایپرتروفی",
    "body_recomposition": "ترکیب بدنی (ریکامپ)",
    "strength": "افزایش قدرت بیشینه",
    "improve_fitness": "آمادگی جسمانی عمومی",
    "maintain_weight": "تثبیت وزن",
    "gym": "باشگاه ورزشی (تجهیزات کامل)",
    "home": "منزل",
    "bodyweight_only": "فقط وزن بدن (بدون تجهیزات)",
    "dumbbells_available": "دمبل خانگی + وزن بدن",
    "chest": "سینه",
    "back": "پشت و زیربغل",
    "shoulders": "سرشانه",
    "biceps": "جلو بازو",
    "triceps": "پشت بازو",
    "glutes": "باسن (سرینی)",
    "quadriceps": "چهارسر ران",
    "hamstrings": "همسترینگ",
    "calves": "ساق پا",
    "lower_back": "آسیب کمر (ستون فقرات کمری)",
    "knee": "آسیب زانو",
    "shoulder": "آسیب شانه",
    "neck": "محدودیت گردن",
    "wrist": "محدودیت مچ دست",
    "full_body": "فول بادی (Full Body)",
    "full_body_ab": "فول بادی متناوب (Full Body A/B)",
    "full_body_abc": "فول بادی سه روزه (Full Body A/B/C)",
    "upper_lower": "بالاتنه / پایین‌تنه (Upper/Lower)",
    "upper_lower_full": "بالاتنه / پایین‌تنه + فول بادی",
    "upper_lower_specialization": "بالاتنه / پایین‌تنه تخصصی (Specialization)",
    "push_pull_legs": "پوش / پول / لگز (PPL)",
    "push_pull_legs_upper_lower": "PPL + بالاتنه / پایین‌تنه (۵ روزه)",
    "push_pull_legs_x2": "PPL دو بار در هفته (۶ روزه)",
    "body_part_rotation": "چرخش بخش‌های بدن (Body Part Rotation)",
    "dynamic_fallback": "اسپلیت پویا (Dynamic Split)",
}

PERSIAN_FIRST_NAMES_MALE = [
    "علی", "محمد", "امیرحسین", "رضا", "حسین", "مهدی", "سجاد", "آرمین", "سینا", "نیما",
    "کامران", "فرزاد", "بهنام", "نوید", "فرهاد", "سهراب", "داریوش", "کسری", "شایان", "مانی",
    "پوریا", "آرش", "سامان", "میلاد", "پیمان", "احسان", "مسعود", "امید", "شهاب", "پویا",
]

PERSIAN_FIRST_NAMES_FEMALE = [
    "سارا", "مریم", "زهرا", "فاطمه", "شیدا", "بهاره", "پروانه", "سوگند", "طناز", "یاسمین",
    "آیدا", "طاهره", "مونا", "الهام", "نگار", "رویا", "مهسا", "ساناز", "نسیم", "نیلوفر",
    "صبا", "گلناز", "پریناز", "یلدا", "ترانه", "ستاره", "سیمین", "مینا", "سمیرا", "غزاله",
]

PERSIAN_LAST_NAMES = [
    "احمدی", "رضایی", "کاظمی", "مرادی", "حسینی", "محمدی", "کریمی", "موسوی", "جعفری", "قاسمی",
    "نوری", "صبوری", "محمودی", "سلطانی", "زمانی", "ابراهیمی", "فراهانی", "یوسفی", "راد", "جلالی",
    "فتوحی", "معتمدی", "صادقی", "داوودی", "رستگار", "افشار", "اکبری", "قادری", "انصاری", "طاهری",
    "حیدری", "نجفی", "بیات", "شریفی", "فرهادی", "جمشیدی", "صالحی", "باقری", "مظفری", "خسروی",
]


@dataclass
class ProfileSpec:
    index: int
    name: str
    sex: Sex
    birth_date: date
    age: int
    height_cm: int
    weight_kg: float
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_age_months: int
    training_days_per_week: int
    session_duration_minutes: int
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None
    priority_muscle: MuscleGroup | None
    training_cautions: list[TrainingCaution]
    plan_duration_weeks: int
    sleep_quality: RecoveryRating
    stress_level: RecoveryRating
    physical_job_demand: PhysicalJobDemand


def generate_100_diverse_profiles(seed: int = 20260901) -> list[ProfileSpec]:
    """Generates 100 diverse, realistic profiles covering all Fitsho profile options and constraints."""
    rng = random.Random(seed)
    today = date(2026, 9, 1)

    experience_levels = [
        ExperienceLevel.FIRST_MONTH,
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    ]
    goals = [
        FitnessGoal.BUILD_MUSCLE,
        FitnessGoal.FAT_LOSS,
        FitnessGoal.BODY_RECOMPOSITION,
        FitnessGoal.STRENGTH,
        FitnessGoal.LOSE_WEIGHT,
        FitnessGoal.GAIN_WEIGHT,
        FitnessGoal.IMPROVE_FITNESS,
    ]
    durations = [30, 45, 60, 75, 90]
    locations = [
        (TrainingLocation.GYM, None),
        (TrainingLocation.HOME, HomeTrainingSetup.BODYWEIGHT_ONLY),
        (TrainingLocation.HOME, HomeTrainingSetup.DUMBBELLS_AVAILABLE),
    ]
    caution_options: list[list[TrainingCaution]] = [
        [],
        [TrainingCaution.LOWER_BACK],
        [TrainingCaution.KNEE],
        [TrainingCaution.SHOULDER],
        [TrainingCaution.NECK],
        [TrainingCaution.WRIST],
        [TrainingCaution.KNEE, TrainingCaution.SHOULDER],
        [TrainingCaution.LOWER_BACK, TrainingCaution.KNEE],
    ]
    priority_options: list[MuscleGroup | None] = [None] + list(USER_SELECTABLE_PRIORITY_MUSCLES)

    profiles: list[ProfileSpec] = []

    for i in range(1, 101):
        sex = Sex.MALE if (i % 2 == 1) else Sex.FEMALE
        first_name = rng.choice(PERSIAN_FIRST_NAMES_MALE if sex == Sex.MALE else PERSIAN_FIRST_NAMES_FEMALE)
        last_name = rng.choice(PERSIAN_LAST_NAMES)
        name = f"{first_name} {last_name}"

        exp_level = experience_levels[(i - 1) % len(experience_levels)]
        if exp_level == ExperienceLevel.FIRST_MONTH:
            training_age_months = 0
            if i % 15 == 0:
                training_days = 5  # Intentional edge case to test validation
            else:
                training_days = rng.choice([2, 3, 4])
        elif exp_level == ExperienceLevel.BEGINNER:
            training_age_months = rng.randint(1, 6)
            if i % 20 == 0:
                training_days = 6  # Intentional edge case
            else:
                training_days = rng.choice([2, 3, 4])
        elif exp_level == ExperienceLevel.INTERMEDIATE:
            training_age_months = rng.randint(7, 36)
            training_days = rng.choice([2, 3, 4, 5, 6])
        else:  # ADVANCED
            training_age_months = rng.randint(37, 120)
            if i % 25 == 0:
                training_days = 2  # Intentional edge case for advanced
            else:
                training_days = rng.choice([3, 4, 5, 6])

        age = 20 + (i * 3 + rng.randint(0, 4)) % 45
        birth_year = today.year - age
        birth_month = (i % 12) + 1
        birth_day = (i % 27) + 1
        birth_date = date(birth_year, birth_month, birth_day)

        if sex == Sex.MALE:
            height_cm = rng.randint(168, 192)
            weight_kg = round(rng.uniform(64.0, 104.0), 1)
        else:
            height_cm = rng.randint(154, 176)
            weight_kg = round(rng.uniform(50.0, 84.0), 1)

        fitness_goal = goals[(i - 1) % len(goals)]
        loc, home_setup = locations[(i - 1) % len(locations)]
        session_duration = durations[(i - 1) % len(durations)]
        priority_muscle = priority_options[i % len(priority_options)]
        training_cautions = caution_options[i % len(caution_options)]
        plan_duration_weeks = rng.choice([4, 6, 8])

        sleep_quality = rng.choice([RecoveryRating.AVERAGE, RecoveryRating.GOOD, RecoveryRating.POOR])
        stress_level = rng.choice([RecoveryRating.AVERAGE, RecoveryRating.GOOD, RecoveryRating.POOR])
        physical_job_demand = rng.choice([PhysicalJobDemand.LOW, PhysicalJobDemand.MODERATE, PhysicalJobDemand.HIGH])

        profiles.append(
            ProfileSpec(
                index=i,
                name=name,
                sex=sex,
                birth_date=birth_date,
                age=age,
                height_cm=height_cm,
                weight_kg=weight_kg,
                fitness_goal=fitness_goal,
                experience_level=exp_level,
                training_age_months=training_age_months,
                training_days_per_week=training_days,
                session_duration_minutes=session_duration,
                training_location=loc,
                home_training_setup=home_setup,
                priority_muscle=priority_muscle,
                training_cautions=training_cautions,
                plan_duration_weeks=plan_duration_weeks,
                sleep_quality=sleep_quality,
                stress_level=stress_level,
                physical_job_demand=physical_job_demand,
            )
        )

    return profiles


def profile_to_request(spec: ProfileSpec, user_id: UUID) -> ProgramGenerationRequest:
    equipment = resolve_available_equipment(
        spec.training_location,
        spec.home_training_setup,
        None,
    )

    caution_tags = caution_tags_for_training_cautions(tuple(spec.training_cautions))

    goal_mapping = {
        FitnessGoal.FAT_LOSS: Goal.FAT_LOSS,
        FitnessGoal.BUILD_MUSCLE: Goal.HYPERTROPHY,
        FitnessGoal.BODY_RECOMPOSITION: Goal.BODY_RECOMPOSITION,
        FitnessGoal.STRENGTH: Goal.STRENGTH,
        FitnessGoal.IMPROVE_FITNESS: Goal.GENERAL_FITNESS,
        FitnessGoal.LOSE_WEIGHT: Goal.FAT_LOSS,
        FitnessGoal.GAIN_WEIGHT: Goal.HYPERTROPHY,
        FitnessGoal.MAINTAIN_WEIGHT: Goal.GENERAL_FITNESS,
    }

    req = ProgramGenerationRequest(
        user_id=user_id,
        age=spec.age,
        biological_sex_optional=spec.sex.value,
        height_cm=spec.height_cm,
        weight_kg=spec.weight_kg,
        primary_goal=goal_mapping[spec.fitness_goal],
        secondary_goal_optional=None,
        training_experience=TrainingExperience(spec.experience_level.value),
        training_age_months=spec.training_age_months,
        current_activity_level=ActivityLevel.MODERATE,
        available_training_days=spec.training_days_per_week,
        preferred_weekdays=(),
        session_duration_minutes=spec.session_duration_minutes,  # type: ignore[arg-type]
        available_equipment=equipment,
        training_location=spec.training_location,
        preferred_exercises=frozenset(),
        disliked_exercises=frozenset(),
        priority_muscles=frozenset({spec.priority_muscle} if spec.priority_muscle else set()),
        body_analysis_influence=None,
        injuries_and_limitations=(),
        blocked_exercises=frozenset(),
        blocked_movement_patterns=frozenset(),
        blocked_caution_tags=caution_tags,
        allowed_range_of_motion=frozenset(),
        impact_limit=ImpactLimit.HIGH,
        axial_load_limit=LoadLimit.HIGH,
        overhead_limit=LoadLimit.HIGH,
        balance_requirement=BalanceAbility.NORMAL,
        current_pain_or_red_flags=(),
        medical_clearance_status=MedicalClearanceStatus.NOT_REQUIRED,
        reports_uncontrolled_medical_condition=False,
        pregnancy_or_postpartum=False,
        sleep_quality=spec.sleep_quality,
        stress_level=spec.stress_level,
        physical_job_demand=spec.physical_job_demand,
        cardio_tolerance=ActivityLevel.MODERATE,
        recent_training_history=RecentTrainingHistory(),
        program_duration_weeks=spec.plan_duration_weeks,
        seed_optional=20260901 + spec.index,
    )
    return req


def analyze_failure(result: Any, request: ProgramGenerationRequest) -> dict[str, Any]:
    error_code = result.error_code.value if (result and result.error_code) else "UNKNOWN_ERROR"
    errors = list(result.errors) if result else []
    trace = (result.decision_trace or ()) if result else ()

    root_cause = "UNSATISFIED_CONSTRAINT"
    secondary_causes: list[str] = []
    rule_file = "app/workouts/program_engine/engine.py"
    rule_func = "generate_program()"
    actual_val = "N/A"
    limit_val = "N/A"
    failing_phase = "construction_recovery"
    exact_description_fa = "محدودیت‌های متقاطع در پروفایل، مانع از ساخت چیدمان برنامه پایدار شد."
    engine_repair_hint_fa = "بررسی کاندیداهای تمرینی، زمان‌بندی جلسات و قوانین جایگزینی حرکات در شرایط سخت."

    construction_recovery = None
    for step in trace:
        stage = step.get("stage")
        if stage == "construction_recovery":
            construction_recovery = step
        elif stage == "safety" and step.get("status") not in ("clear", "clear_with_modifications"):
            root_cause = "PROGRAM_REJECTED_SAFETY_STATUS"
            rule_file = "app/workouts/program_engine/safety.py"
            rule_func = "screen_safety()"
            actual_val = step.get("status")
            limit_val = "CLEAR / CLEAR_WITH_MODIFICATIONS"
            failing_phase = "safety_screening"
            exact_description_fa = f"موتور به دلیل تشخیص وضعیت پرخطر پزشکی ({step.get('status')}) مجوز ادامه تولید را لغو کرد."
            engine_repair_hint_fa = "بررسی متد screen_safety و اضافه کردن استثنا یا نیازمندی تاییدیه پزشکی برای کاربر."
        elif stage == "eligibility" and step.get("eligible_count", 0) == 0:
            root_cause = "INSUFFICIENT_ELIGIBLE_EXERCISES"
            rule_file = "app/workouts/program_engine/eligibility.py"
            rule_func = "filter_eligible_exercises()"
            actual_val = "۰ حرکت واجد شرایط"
            limit_val = "حداقل ۱ حرکت"
            failing_phase = "exercise_eligibility"
            exact_description_fa = "کاتالوگ تمرینات فاقد حرکات ایمن و قابل‌اجرا با توجه به تداخل آسیب‌ها و تجهیزات است."
            engine_repair_hint_fa = "توسعه کاتالوگ حرکات بدون تجهیزات / حرکات با دمبل که با برچسب‌های آسیب انتخاب‌شده تداخل نداشته باشند."

    if root_cause == "UNSATISFIED_CONSTRAINT" and construction_recovery:
        attempts = construction_recovery.get("attempts", ())
        collected_reasons = []
        for attempt in attempts:
            attempt_reasons = attempt.get("reason_codes", ())
            collected_reasons.extend(attempt_reasons)

        duration_policy = get_session_duration_policy(request.session_duration_minutes)
        if "SESSION_DURATION_EXCEEDED" in collected_reasons or "SESSION_DURATION_OVER_TARGET" in collected_reasons:
            root_cause = "SESSION_DURATION_EXCEEDED"
            actual_val = f"> {duration_policy.maximum_minutes} دقیقه"
            limit_val = f"{duration_policy.minimum_minutes} الی {duration_policy.maximum_minutes} دقیقه"
            exact_description_fa = (
                f"مدت زمان جلسات از سقف مجاز ({duration_policy.maximum_minutes} دقیقه) فراتر رفت "
                f"و موتور پس از تلاش برای کاهش ست‌ها، نتوانست زمان جلسه را در بازه مجاز حفظ کند."
            )
            engine_repair_hint_fa = "تنظیم دقیق‌تر فاز هرس (prune) ست‌ها یا تمرین‌های فرعی در session_duration.py."
            rule_file = "app/workouts/program_engine/session_duration.py"
            rule_func = "repair_session_durations()"
            failing_phase = "session_duration_repair_and_validation"
        elif "SEMANTIC_OPENER_CONFLICT" in collected_reasons:
            root_cause = "SEMANTIC_OPENER_CONFLICT"
            actual_val = "تداخل حرکت آغازین با الگوهای جلسه"
            limit_val = "سازگاری الگوی آغازین"
            exact_description_fa = (
                "حرکت آغازین انتخاب‌شده برای جلسه با الگوهای اصلی یا تمرینات اولویت‌دار بعدی "
                "تداخل ترتیبی و خستگی ساختاری ایجاد کرده و قوانین ترتیب‌بندی حرکات را نقض می‌کند."
            )
            engine_repair_hint_fa = "بررسی رتبه‌بندی حرکات آغازین در session_builder.py و اصلاح ترتیب انتخاب حرکات کامپاند."
            rule_file = "app/workouts/program_engine/session_builder.py"
            rule_func = "order_session_exercises()"
            failing_phase = "session_exercise_sequencing"
        elif any("FULL_BODY_COVERAGE_MISSING" in str(r) for r in collected_reasons):
            missing_cause = next(r for r in collected_reasons if "FULL_BODY_COVERAGE_MISSING" in str(r))
            root_cause = missing_cause
            muscle_name = missing_cause.split(":")[-1] if ":" in missing_cause else "نامشخص"
            actual_val = f"عدم پوشش عضله {FA_TRANSLATIONS.get(muscle_name, muscle_name)}"
            limit_val = "پوشش تمام گروه‌های عضلانی اصلی فول‌بادی"
            exact_description_fa = (
                f"در ساختار فول‌بادی، به دلیل محدودیت تجهیزات یا آسیب‌های تعیین‌شده، "
                f"امکان انتخاب هیچ تمرین ایمنی برای عضله '{FA_TRANSLATIONS.get(muscle_name, muscle_name)}' وجود نداشت."
            )
            engine_repair_hint_fa = "تعریف حرکات جایگزین بدون نیاز به تجهیزات برای این عضله یا مجاز کردن جایگزینی عضله همکار در شرایط اضطرار."
            rule_file = "app/workouts/program_engine/rulesets/resistance_training_v1.py"
            rule_func = "verify_full_body_coverage()"
            failing_phase = "full_body_pattern_validation"
        elif "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" in collected_reasons:
            root_cause = "PER_SESSION_MUSCLE_VOLUME_EXCEEDED"
            cap = session_hard_volume_cap(request.training_age_months)
            actual_val = f"> {cap} ست در هر عضله/جلسه"
            limit_val = f"حداکثر {cap} ست مستقیم"
            exact_description_fa = f"حجم ست‌های مستقیم برای یک عضله از سقف مجاز سابقه تمرینی کاربر ({cap} ست) تجاوز کرد."
            engine_repair_hint_fa = "تنظیم سقف ست‌های کاندیداها یا توزیع بهتر ست‌ها بین جلسات مختلف هفته."
            rule_file = "app/workouts/program_engine/validation.py"
            rule_func = "validate_program()"
            failing_phase = "session_volume_validation"
        elif "NO_SAFE_EXERCISE_FOR_PATTERN" in collected_reasons or any("NO_SAFE_EXERCISE" in str(r) for r in collected_reasons):
            root_cause = "NO_SAFE_EXERCISE_FOR_PATTERN"
            actual_val = "عدم وجود حرکت مجاز"
            limit_val = "حداقل ۱ حرکت ایمن"
            exact_description_fa = "تلاقی آسیب‌های بدنی و تجهیزات باعث شد هیچ حرکت استانداردی برای الگوی حرکتی جلسه باقی نماند."
            engine_repair_hint_fa = "توسعه کاتالوگ حرکات با وسایل سبک یا اصلاح برچسب‌های احتیاط در دیتابیس."
            rule_file = "app/workouts/program_engine/session_builder.py"
            rule_func = "build_sessions()"
            failing_phase = "session_construction"
        elif "REQUESTED_TRAINING_DAYS_UNSATISFIED" in collected_reasons:
            root_cause = "REQUESTED_TRAINING_DAYS_UNSATISFIED"
            actual_val = f"اسپلیت {request.available_training_days} روزه"
            limit_val = f"{request.available_training_days} روز در هفته"
            exact_description_fa = f"موتور الگوی تقسیم معتبری برای چیدمان {request.available_training_days} روز تمرین در هفته با این شرایط نیافت."
            engine_repair_hint_fa = "افزودن تمپلیت‌ها یا الگوهای اسپلیت جدید برای این تعداد روز در split_selector.py."
            rule_file = "app/workouts/program_engine/split_selector.py"
            rule_func = "rank_split_candidates()"
            failing_phase = "split_selection"
        else:
            non_generic = [r for r in collected_reasons if r not in ("PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED", "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED", "UNSATISFIED_CONSTRAINT")]
            if non_generic:
                root_cause = non_generic[0]
                actual_val = root_cause
                limit_val = "ضابطه طراحی برنامه"
                exact_description_fa = f"موتور در ارزیابی نهایی برنامه را به دلیل قانون '{root_cause}' رد کرد."
                engine_repair_hint_fa = f"بررسی متد اعتبارسنجی مرتبط با {root_cause} در validation.py."
                rule_file = "app/workouts/program_engine/validation.py"
                rule_func = "validate_program()"
                failing_phase = "validation_phase"

        for r in collected_reasons:
            if r != root_cause and r not in secondary_causes and r not in ("PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED", "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED"):
                secondary_causes.append(r)

    return {
        "final_error_code": error_code,
        "all_errors": errors,
        "root_cause": root_cause,
        "secondary_causes": secondary_causes,
        "rule_file": rule_file,
        "rule_func": rule_func,
        "actual_val": actual_val,
        "limit_val": limit_val,
        "failing_phase": failing_phase,
        "exact_description_fa": exact_description_fa,
        "engine_repair_hint_fa": engine_repair_hint_fa,
    }


def evaluate_100_profiles() -> list[dict[str, Any]]:
    print("Loading settings and initializing session...")
    settings = get_settings()
    engine = create_engine(settings.database_url)

    profiles = generate_100_diverse_profiles()
    print(f"Generated {len(profiles)} diverse test profiles.")

    results: list[dict[str, Any]] = []

    with Session(engine) as session:
        exercises_list = session.scalars(select(Exercise)).all()
        exercise_map = {ex.id: ex for ex in exercises_list}

        service = WorkoutGenerationService(session, settings=None)
        catalog = service._load_catalog()
        references = load_template_references(session)
        print(f"Loaded {len(catalog)} exercises and {len(references)} templates.")

        for p in profiles:
            user_uuid = uuid4()

            # First verify compatibility rule
            try:
                require_supported_resistance_training_days(
                    p.experience_level,
                    p.training_days_per_week,
                )
                compatibility_error = None
            except UnsupportedResistanceTrainingCombinationError as err:
                compatibility_error = str(err)

            if compatibility_error:
                failure_info = {
                    "final_error_code": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
                    "all_errors": [compatibility_error],
                    "root_cause": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
                    "secondary_causes": [],
                    "rule_file": "app/profile/training_compatibility.py",
                    "rule_func": "require_supported_resistance_training_days()",
                    "actual_val": f"{p.experience_level.value} با {p.training_days_per_week} روز در هفته",
                    "limit_val": "تطابق با ماتریس مجاز تمرین مقاومتی فیتشو",
                    "failing_phase": "input_compatibility_validation",
                    "exact_description_fa": (
                        f"سطح سابقه '{FA_TRANSLATIONS.get(p.experience_level.value, p.experience_level.value)}' با "
                        f"{p.training_days_per_week} روز تمرین در هفته سازگار نیست. "
                        f"طبق قوانین پزشکی و فیزیولوژیک فیتشو، برای پیشگیری از بیش‌تمرینی و آسیب، تعداد روزهای انتخابی نامعتبر است."
                    ),
                    "engine_repair_hint_fa": "رد سریع در فرم ورود اطلاعات کاربر یا پیشنهاد اتوماتیک روزهای سازگار با سطح تجربه.",
                }
                results.append({
                    "profile": p,
                    "status": "FAILED",
                    "split": None,
                    "split_fa": None,
                    "days_count": 0,
                    "days": [],
                    "weekly_direct_volume": {},
                    "weekly_effective_volume": {},
                    "warnings": [],
                    "final_gate_status": "rejected",
                    "failure_info": failure_info,
                })
                print(f"Profile #{p.index:03d} [{p.name}]: FAILED -> {failure_info['root_cause']}")
                continue

            req = profile_to_request(p, user_uuid)

            try:
                gen_result = generate_program(
                    req,
                    catalog,
                    RULESET,
                    reference_templates=references,
                )
            except Exception as e:
                print(f"Profile #{p.index:03d} Exception: {e}")
                gen_result = None

            if gen_result and gen_result.is_success and gen_result.program:
                prog: WorkoutProgram = gen_result.program
                days_data = []
                for day in prog.weekly_schedule:
                    main_mins = calculate_main_training_minutes(day)
                    ex_list = []
                    for it in day.exercises:
                        ex_db = exercise_map.get(it.exercise_id)
                        name_fa = ex_db.name_fa if ex_db and ex_db.name_fa else it.name
                        name_en = ex_db.name_en if ex_db and ex_db.name_en else it.name
                        ex_list.append({
                            "order": it.order,
                            "name_fa": name_fa,
                            "name_en": name_en,
                            "sets": it.sets,
                            "prescription_mode": it.prescription_mode.value if hasattr(it.prescription_mode, "value") else str(it.prescription_mode),
                            "rep_min": it.rep_min,
                            "rep_max": it.rep_max,
                            "rest_seconds": it.rest_seconds,
                            "rir": it.target_rir,
                            "primary_muscle": it.primary_muscle.value if it.primary_muscle else "-",
                            "primary_muscle_fa": FA_TRANSLATIONS.get(it.primary_muscle.value, it.primary_muscle.value) if it.primary_muscle else "-",
                            "estimated_minutes": it.estimated_minutes,
                        })
                    days_data.append({
                        "day_index": day.day_index,
                        "title": day.title,
                        "focus": day.focus,
                        "estimated_duration_minutes": day.estimated_duration_minutes,
                        "main_training_minutes": main_mins,
                        "exercises": ex_list,
                    })

                direct_vol = prog.aggregate_metrics.get("weekly_direct_sets_by_muscle", {})
                effective_vol = prog.aggregate_metrics.get("weekly_effective_sets_by_muscle", {})
                final_gate = prog.aggregate_metrics.get("final_quality_gate", {})
                gate_status = final_gate.get("status", "accepted")

                results.append({
                    "profile": p,
                    "status": "SUCCESS",
                    "split": prog.split.split_type.value,
                    "split_fa": FA_TRANSLATIONS.get(prog.split.split_type.value, prog.split.split_type.value),
                    "days_count": len(prog.weekly_schedule),
                    "days": days_data,
                    "weekly_direct_volume": direct_vol,
                    "weekly_effective_volume": effective_vol,
                    "warnings": list(prog.warnings),
                    "final_gate_status": gate_status,
                    "failure_info": None,
                })
                print(f"Profile #{p.index:03d} [{p.name}]: SUCCESS -> {prog.split.split_type.value} ({len(prog.weekly_schedule)} days)")
            else:
                failure_info = analyze_failure(gen_result, req) if gen_result else {
                    "final_error_code": "CRASH_EXCEPTION",
                    "all_errors": ["ENGINE_CRASH"],
                    "root_cause": "ENGINE_CRASH",
                    "secondary_causes": [],
                    "rule_file": "engine.py",
                    "rule_func": "generate_program()",
                    "actual_val": "Crash",
                    "limit_val": "Clean execution",
                    "failing_phase": "exception",
                    "exact_description_fa": "خطای سیستمی رخ داد و برنامه تمرینی ساخته نشد.",
                    "engine_repair_hint_fa": "بررسی لاگ‌های سیستمی و خطاهای مدیریت‌نشده در engine.py.",
                }
                results.append({
                    "profile": p,
                    "status": "FAILED",
                    "split": None,
                    "split_fa": None,
                    "days_count": 0,
                    "days": [],
                    "weekly_direct_volume": {},
                    "weekly_effective_volume": {},
                    "warnings": [],
                    "final_gate_status": "rejected",
                    "failure_info": failure_info,
                })
                print(f"Profile #{p.index:03d} [{p.name}]: FAILED -> {failure_info['root_cause']}")

    return results


def build_pdf_html(results: list[dict[str, Any]]) -> str:
    total = len(results)
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    failure_count = total - success_count
    success_rate = (success_count / total) * 100 if total > 0 else 0

    failures_by_code: dict[str, int] = {}
    failed_rules_counter: dict[str, int] = {}
    for r in results:
        if r["status"] == "FAILED" and r.get("failure_info"):
            finfo = r["failure_info"]
            code = finfo.get("final_error_code", "UNKNOWN")
            root = finfo.get("root_cause", "UNKNOWN")
            failures_by_code[code] = failures_by_code.get(code, 0) + 1
            failed_rules_counter[root] = failed_rules_counter.get(root, 0) + 1

    top_failed_rules = sorted(failed_rules_counter.items(), key=lambda x: x[1], reverse=True)

    css = """
    @page {
        size: A4 portrait;
        margin: 12mm 12mm 14mm 12mm;
        @bottom-left {
            content: "گزارش آزمون و عیب‌یابی ۱۰۰ پروفایل موتور تمرینی Fitsho";
            font-family: 'Vazirmatn', sans-serif;
            font-size: 7.5pt;
            color: #557069;
        }
        @bottom-right {
            content: "صفحه " counter(page) " از " counter(pages);
            font-family: 'Vazirmatn', sans-serif;
            font-size: 7.5pt;
            color: #557069;
        }
    }
    * { box-sizing: border-box; }
    body {
        font-family: 'Vazirmatn', 'DejaVu Sans', sans-serif;
        font-size: 8pt;
        line-height: 1.5;
        direction: rtl;
        text-align: right;
        color: #112824;
        background-color: #ffffff;
    }
    .header-box {
        background: linear-gradient(135deg, #074e43 0%, #0d6e5e 100%);
        color: #ffffff;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    .header-title {
        font-size: 15pt;
        font-weight: bold;
        margin: 0 0 4px 0;
    }
    .header-subtitle {
        font-size: 8.5pt;
        opacity: 0.92;
        margin: 0;
    }
    .summary-card {
        background: #f2f9f7;
        border: 1px solid #c2e2da;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 14px;
        page-break-inside: avoid;
    }
    .summary-stats {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 10px;
        border-bottom: 1px dashed #afd5cb;
        padding-bottom: 8px;
    }
    .stat-badge {
        display: inline-block;
        background: #ffffff;
        border: 1px solid #afd5cb;
        border-radius: 5px;
        padding: 4px 8px;
        font-size: 8pt;
    }
    .stat-badge strong {
        color: #0d6e5e;
    }
    .stat-badge.success strong {
        color: #097e44;
    }
    .stat-badge.error strong {
        color: #c92a2a;
    }
    .audit-box {
        background: #ffffff;
        border-right: 4px solid #0d6e5e;
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 8pt;
        line-height: 1.6;
        color: #203833;
    }
    .analytics-table-wrap {
        display: flex;
        gap: 12px;
        margin-top: 10px;
    }
    .analytics-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.5pt;
        margin-bottom: 0;
    }
    .analytics-table th {
        background: #e6f3ef;
        color: #085a4c;
        padding: 4px 8px;
        border: 1px solid #cbd5e1;
        font-weight: bold;
    }
    .analytics-table td {
        padding: 4px 8px;
        border: 1px solid #cbd5e1;
    }
    .user-section {
        page-break-inside: avoid;
        border: 1px solid #cee0dc;
        border-radius: 6px;
        margin-bottom: 12px;
        background: #ffffff;
        overflow: hidden;
    }
    .user-section.success-section {
        border-right: 5px solid #097e44;
    }
    .user-section.failed-section {
        border-right: 5px solid #c92a2a;
    }
    .user-header {
        background: #eef6f4;
        border-bottom: 1px solid #cee0dc;
        padding: 6px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .user-title {
        font-size: 9.5pt;
        font-weight: bold;
        color: #074e43;
        margin: 0;
    }
    .status-badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 7.5pt;
        font-weight: bold;
    }
    .status-badge.success {
        background: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
    }
    .status-badge.fail {
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
    }
    .profile-grid {
        padding: 8px 12px;
        background: #fbfdfc;
        border-bottom: 1px solid #e2ece9;
        font-size: 7.5pt;
    }
    .profile-row {
        display: flex;
        flex-wrap: wrap;
        margin-bottom: 3px;
    }
    .profile-row:last-child {
        margin-bottom: 0;
    }
    .profile-item {
        flex: 1 1 33.33%;
        margin-bottom: 2px;
    }
    .profile-label {
        color: #4a6862;
        font-weight: bold;
    }
    .profile-value {
        color: #112824;
    }
    .days-container {
        padding: 8px 12px;
    }
    .program-overview-bar {
        background: #f2f9f7;
        border: 1px solid #c2e2da;
        border-radius: 4px;
        padding: 5px 10px;
        margin-bottom: 8px;
        font-size: 7.8pt;
        color: #085a4c;
    }
    .day-block {
        margin-bottom: 8px;
        border: 1px solid #dce8e5;
        border-radius: 5px;
        overflow: hidden;
    }
    .day-block:last-child {
        margin-bottom: 0;
    }
    .day-title-bar {
        background: #eef6f4;
        padding: 4px 8px;
        border-bottom: 1px solid #dce8e5;
        font-size: 8pt;
        font-weight: bold;
        color: #085a4c;
        display: flex;
        justify-content: space-between;
    }
    .exercise-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.5pt;
    }
    .exercise-table th {
        background: #f6faf8;
        color: #3e5b56;
        text-align: right;
        padding: 3px 6px;
        border-bottom: 1px solid #dce8e5;
        font-weight: 600;
    }
    .exercise-table td {
        padding: 3px 6px;
        border-bottom: 1px solid #edf4f2;
        vertical-align: middle;
    }
    .exercise-table tr:last-child td {
        border-bottom: none;
    }
    .exercise-table tr:nth-child(even) {
        background-color: #fafcfb;
    }
    .ex-num {
        width: 20px;
        font-weight: bold;
        color: #0d6e5e;
        text-align: center;
    }
    .ex-name {
        font-weight: bold;
        color: #132a26;
    }
    .fail-detail-box {
        padding: 10px 14px;
        background: #fff8f8;
        border-top: 1px solid #fed7d7;
        font-size: 7.8pt;
    }
    .fail-header-line {
        font-size: 8.5pt;
        font-weight: bold;
        color: #991b1b;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
    }
    .fail-desc {
        background: #ffffff;
        border: 1px solid #fecaca;
        border-right: 3px solid #dc2626;
        border-radius: 4px;
        padding: 6px 10px;
        margin-bottom: 6px;
        color: #7f1d1d;
        line-height: 1.55;
    }
    .fail-meta-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px 8px;
        font-size: 7.2pt;
        background: #ffffff;
        border: 1px solid #f3e8e8;
        padding: 6px 8px;
        border-radius: 4px;
        margin-bottom: 6px;
    }
    .fail-meta-item span.lbl {
        color: #7f1d1d;
        font-weight: bold;
    }
    .fail-meta-item span.val {
        color: #334155;
    }
    .repair-hint {
        background: #fffbeb;
        border: 1px dashed #fcd34d;
        border-radius: 4px;
        padding: 5px 8px;
        color: #92400e;
        font-size: 7.2pt;
    }
    code {
        font-family: monospace;
        background: #f1f5f9;
        padding: 1px 3px;
        border-radius: 2px;
        font-size: 6.8pt;
        color: #0f172a;
    }
    </style>
    """

    html = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش جامع ارزیابی و عیب‌یابی ۱۰۰ پروفایل موتور تمرینی Fitsho</title>
<style>{css}</style>
</head>
<body>

<div class="header-box">
    <div class="header-title">گزارش آزمون و عیب‌یابی جامع موتور برنامه‌ریزی تمرین Fitsho</div>
    <div class="header-subtitle">ارزیابی ۱۰۰ پروفایل متنوع و واقعی، بررسی تفکیک روز و عضلات برنامه‌ها و تحلیل علل دقیق عدم ساخت برنامه | تاریخ: ۱۴۰۵/۰۶/۱۰ (2026-09-01)</div>
</div>

<div class="summary-card">
    <div class="summary-stats">
        <span class="stat-badge">تعداد کل پروفایل‌های ارزیابی‌شده: <strong>{total}</strong></span>
        <span class="stat-badge success">برنامه‌های با موفقیت تولیدشده: <strong>{success_count} ({success_rate:.1f}٪)</strong></span>
        <span class="stat-badge error">برنامه‌های رد شده با خطا: <strong>{failure_count} ({(100 - success_rate):.1f}٪)</strong></span>
        <span class="stat-badge">هدف ارزیابی: <strong>تحلیل عیب‌یابی و تعمیر قوانین موتور فیتشو</strong></span>
    </div>

    <div class="audit-box">
        <strong>خلاصه وضعیت عملکردی موتور و علل مسدود شدن برنامه‌ها (Engine Health & Diagnostic Audit):</strong><br>
        • <strong>برنامه‌های تولید شده:</strong> موتور در {success_count} مورد از ۱۰۰ پروفایل با رعایت سقف حجم ست‌ها، تطبیق دقیق مدت زمان جلسات و رعایت تمام محدودیت‌های پزشکی، موفق به چیدمان کامل حرکات در قالب اسپلیت‌های استاندارد (فول‌بادی، بالاتنه/پایین‌تنه، PPL و چرخش عضلانی) گردید.<br>
        • <strong>علت اصلی عدم تولید در {failure_count} پروفایل:</strong> کف زمان جلسه (<code>SESSION_DURATION_UNDER_TARGET</code>) اکنون فقط هشدار کیفیت است و علت رد برنامه نیست؛ علل رد در جدول خطاها بر اساس شواهد واقعی موتور گزارش شده‌اند.
    </div>

    <div class="analytics-table-wrap">
        <div style="flex: 1;">
            <table class="analytics-table">
                <thead>
                    <tr>
                        <th>کد خطای نهایی (Final Error Code)</th>
                        <th style="width: 50px; text-align: center;">تعداد</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td><code>{k}</code></td><td style='text-align: center; font-weight: bold;'>{v}</td></tr>" for k, v in failures_by_code.items())}
                </tbody>
            </table>
        </div>
        <div style="flex: 1;">
            <table class="analytics-table">
                <thead>
                    <tr>
                        <th>علت ریشه‌ای خطا (Root Cause)</th>
                        <th style="width: 50px; text-align: center;">تعداد</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td><code>{k}</code></td><td style='text-align: center; font-weight: bold;'>{v}</td></tr>" for k, v in top_failed_rules[:5])}
                </tbody>
            </table>
        </div>
    </div>
</div>

<h2 style="font-size: 10.5pt; color: #074e43; border-bottom: 2px solid #0d6e5e; padding-bottom: 4px; margin: 16px 0 10px 0;">
    کارنامه تفصیلی ۱۰۰ پروفایل کاربر به همراه برنامه تمرینی و علت دقیق خطاها
</h2>
"""

    for r in results:
        p: ProfileSpec = r["profile"]
        status = r["status"]
        is_success = (status == "SUCCESS")
        section_class = "success-section" if is_success else "failed-section"
        badge = '<span class="status-badge success">برنامه تمرینی با موفقیت صادر شد</span>' if is_success else '<span class="status-badge fail">برنامه صادر نشد (برخورد با خطا)</span>'

        sex_fa = FA_TRANSLATIONS.get(p.sex.value, p.sex.value)
        goal_fa = FA_TRANSLATIONS.get(p.fitness_goal.value, p.fitness_goal.value)
        level_fa = FA_TRANSLATIONS.get(p.experience_level.value, p.experience_level.value)
        loc_fa = FA_TRANSLATIONS.get(p.training_location.value, p.training_location.value)
        setup_fa = FA_TRANSLATIONS.get(p.home_training_setup.value, p.home_training_setup.value) if p.home_training_setup else "تجهیزات کامل باشگاه"
        pri_fa = FA_TRANSLATIONS.get(p.priority_muscle.value, p.priority_muscle.value) if p.priority_muscle else "بدون اولویت اختصاصی"
        cautions_fa = "، ".join(FA_TRANSLATIONS.get(c.value, c.value) for c in p.training_cautions) if p.training_cautions else "بدون آسیب یا محدودیت فیزیکی"

        # BMI calculation
        height_m = p.height_cm / 100.0
        bmi = round(p.weight_kg / (height_m * height_m), 1)

        html += f"""
<div class="user-section {section_class}">
    <div class="user-header">
        <span class="user-title">پروفایل #{p.index:03d}: {p.name}</span>
        {badge}
    </div>

    <div class="profile-grid">
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">سن و جنسیت:</span> <span class="profile-value">{p.age} سال · {sex_fa}</span></div>
            <div class="profile-item"><span class="profile-label">قد، وزن و BMI:</span> <span class="profile-value">{p.height_cm} cm · {p.weight_kg} kg (BMI: {bmi})</span></div>
            <div class="profile-item"><span class="profile-label">هدف تناسب اندام:</span> <span class="profile-value">{goal_fa}</span></div>
        </div>
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">سطح و سابقه تمرین:</span> <span class="profile-value">{level_fa} ({p.training_age_months} ماه سابقه)</span></div>
            <div class="profile-item"><span class="profile-label">برنامه هفتگی و مدت:</span> <span class="profile-value">{p.training_days_per_week} روز در هفته · {p.session_duration_minutes} دقیقه</span></div>
            <div class="profile-item"><span class="profile-label">محیط و تجهیزات:</span> <span class="profile-value">{loc_fa} · {setup_fa}</span></div>
        </div>
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">عضله دارای اولویت:</span> <span class="profile-value">{pri_fa}</span></div>
            <div class="profile-item"><span class="profile-label">طول دوره پیشنهادی:</span> <span class="profile-value">{p.plan_duration_weeks} هفته</span></div>
            <div class="profile-item"><span class="profile-label">آسیب‌ها و محدودیت‌ها:</span> <span class="profile-value">{cautions_fa}</span></div>
        </div>
    </div>
"""

        if is_success:
            split_fa = r.get("split_fa") or r.get("split")
            days_count = r.get("days_count", 0)
            html += f"""
    <div class="days-container">
        <div class="program-overview-bar">
            <strong>ساختار برنامه:</strong> اسپلیت <strong>{split_fa}</strong> | تعداد جلسات: <strong>{days_count} جلسه در هفته</strong> | طول دوره: <strong>{p.plan_duration_weeks} هفته</strong>
        </div>
"""
            for day in r.get("days", []):
                d_idx = day.get("day_index")
                d_title = day.get("title")
                d_dur = day.get("estimated_duration_minutes") or day.get("main_training_minutes") or p.session_duration_minutes
                d_focus = day.get("focus") or "-"
                ex_list = day.get("exercises", [])

                html += f"""
        <div class="day-block">
            <div class="day-title-bar">
                <span>جلسه {d_idx}: {d_title} (تمرکز: {d_focus})</span>
                <span>زمان تخمینی: {d_dur} دقیقه · {len(ex_list)} حرکت تمرینی</span>
            </div>
            <table class="exercise-table">
                <thead>
                    <tr>
                        <th class="ex-num">#</th>
                        <th>نام تمرین (بانک اطلاعاتی فیتشو)</th>
                        <th style="width: 80px;">عضله هدف</th>
                        <th style="width: 100px;">ست × تکرار / زمان</th>
                        <th style="width: 60px; text-align: center;">استراحت</th>
                        <th style="width: 50px; text-align: center;">شدت (RIR)</th>
                    </tr>
                </thead>
                <tbody>
"""
                for it in ex_list:
                    if it["prescription_mode"] == "reps":
                        presc_str = f"{it['sets']} ست × {it['rep_min']}–{it['rep_max']} تکرار"
                    else:
                        presc_str = f"{it['sets']} ست × {it['rep_min']}–{it['rep_max']} ثانیه"

                    rir_str = f"RIR {it['rir']}" if it["rir"] is not None else "-"

                    html += f"""
                    <tr>
                        <td class="ex-num">{it['order']}</td>
                        <td class="ex-name">{it['name_fa']} <span style="color: #64748b; font-size: 6.2pt;">({it['name_en']})</span></td>
                        <td>{it['primary_muscle_fa']}</td>
                        <td>{presc_str}</td>
                        <td style="text-align: center;">{it['rest_seconds']} ثانیه</td>
                        <td style="text-align: center;">{rir_str}</td>
                    </tr>
"""
                html += """
                </tbody>
            </table>
        </div>
"""
            html += "    </div>"
        else:
            finfo = r.get("failure_info", {})
            html += f"""
    <div class="fail-detail-box">
        <div class="fail-header-line">
            <span>کد خطای موتور: <code>{finfo.get('root_cause')}</code></span>
            <span>کد خطا در API: <code>{finfo.get('final_error_code')}</code></span>
        </div>
        <div class="fail-desc">
            <strong>علت دقیق عدم امکان تولید برنامه:</strong><br>
            {finfo.get('exact_description_fa')}
        </div>
        <div class="fail-meta-grid">
            <div class="fail-meta-item"><span class="lbl">فاز اجرایی بروز خطا:</span> <span class="val"><code>{finfo.get('failing_phase')}</code></span></div>
            <div class="fail-meta-item"><span class="lbl">فایل قانون ناظر:</span> <span class="val"><code>{finfo.get('rule_file')}</code></span></div>
            <div class="fail-meta-item"><span class="lbl">تابع ناظر در موتور:</span> <span class="val"><code>{finfo.get('rule_func')}</code></span></div>
            <div class="fail-meta-item"><span class="lbl">مقدار محاسبه‌شده:</span> <span class="val">{finfo.get('actual_val')} (حد مجاز: {finfo.get('limit_val')})</span></div>
        </div>
        <div class="repair-hint">
            🔧 <strong>راهنمای تعمیر و ارتقای موتور (Engine Repair Guideline):</strong> {finfo.get('engine_repair_hint_fa')}
        </div>
    </div>
"""

        html += "</div>\n"

    html += """
</body>
</html>
"""
    return html


def main() -> None:
    results = evaluate_100_profiles()
    successes = sum(1 for r in results if r["status"] == "SUCCESS")
    failures = len(results) - successes
    print(f"\n100-profile evaluation complete: {successes} succeeded, {failures} failed.")

    os.makedirs("/home/mohammad/project/fitsho/var/reports", exist_ok=True)
    os.makedirs("/home/mohammad/project/fitsho/reports", exist_ok=True)

    # Save JSON data
    json_path = "/home/mohammad/project/fitsho/var/reports/100_profiles_audit_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json_data = []
        for r in results:
            p_dict = asdict(r["profile"])
            p_dict["birth_date"] = p_dict["birth_date"].isoformat()
            p_dict["sex"] = p_dict["sex"].value
            p_dict["fitness_goal"] = p_dict["fitness_goal"].value
            p_dict["experience_level"] = p_dict["experience_level"].value
            p_dict["training_location"] = p_dict["training_location"].value
            if p_dict["home_training_setup"]:
                p_dict["home_training_setup"] = p_dict["home_training_setup"].value
            if p_dict["priority_muscle"]:
                p_dict["priority_muscle"] = p_dict["priority_muscle"].value
            p_dict["training_cautions"] = [c.value for c in p_dict["training_cautions"]]
            p_dict["sleep_quality"] = p_dict["sleep_quality"].value
            p_dict["stress_level"] = p_dict["stress_level"].value
            p_dict["physical_job_demand"] = p_dict["physical_job_demand"].value

            r_clean = dict(r)
            r_clean["profile"] = p_dict
            json_data.append(r_clean)
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"Saved raw JSON audit data to {json_path}")

    # Build HTML
    print("Building high-fidelity Persian HTML report...")
    html_content = build_pdf_html(results)
    html_path = "/home/mohammad/project/fitsho/reports/fitsho_100_profiles_audit_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML saved to {html_path}")

    # Render PDF
    pdf_path = "/home/mohammad/project/fitsho/reports/fitsho_100_profiles_audit_report.pdf"
    print(f"Rendering PDF with WeasyPrint to {pdf_path}...")
    weasyprint.HTML(string=html_content).write_pdf(pdf_path)
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"PDF generated successfully at {pdf_path} ({size_mb:.2f} MB)")

    # Copy to root and public for easy download
    root_pdf = "/home/mohammad/project/fitsho/fitsho_100_profiles_audit_report.pdf"
    weasyprint.HTML(string=html_content).write_pdf(root_pdf)
    print(f"PDF also saved to {root_pdf}")


if __name__ == "__main__":
    main()
