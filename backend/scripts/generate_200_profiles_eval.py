from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

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
    "first_month": "ماه اول",
    "beginner": "مبتدی",
    "intermediate": "متوسط",
    "advanced": "پیشرفته",
    "lose_weight": "کاهش وزن",
    "gain_weight": "افزایش وزن",
    "fat_loss": "چربی‌سوزی",
    "build_muscle": "عضله‌سازی",
    "body_recomposition": "ترکیب بدنی (ریکامپ)",
    "strength": "افزایش قدرت",
    "improve_fitness": "آمادگی جسمانی عمومی",
    "maintain_weight": "تثبیت وزن",
    "gym": "باشگاه ورزشی",
    "home": "منزل",
    "bodyweight_only": "فقط وزن بدن",
    "dumbbells_available": "همراه با دمبل",
    "chest": "سینه",
    "back": "پشت / زیربغل",
    "shoulders": "سرشانه",
    "biceps": "جلو بازو",
    "triceps": "پشت بازو",
    "glutes": "باسن",
    "quadriceps": "چهارسر ران",
    "hamstrings": "همسترینگ",
    "calves": "ساق پا",
    "lower_back": "کمر (ستون فقرات)",
    "knee": "زانو",
    "shoulder": "شانه",
    "neck": "گردن",
    "wrist": "مچ دست",
    "other": "سایر",
    "full_body": "فول بادی (Full Body)",
    "full_body_ab": "فول بادی A/B",
    "full_body_abc": "فول بادی A/B/C",
    "upper_lower": "بالاتنه / پایین‌تنه (Upper/Lower)",
    "upper_lower_full": "بالاتنه / پایین‌تنه + فول بادی",
    "upper_lower_specialization": "بالاتنه / پایین‌تنه تخصصی",
    "push_pull_legs": "پوش / پول / لگز (PPL)",
    "push_pull_legs_upper_lower": "PPL + بالاتنه / پایین‌تنه (۵ روزه)",
    "push_pull_legs_x2": "PPL دو بار در هفته (۶ روزه)",
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


def generate_200_stratified_profiles(seed: int = 20260901) -> list[ProfileSpec]:
    """Generates 200 diverse, stratified profiles covering all Fitsho profile options.
    
    Stratification ensures:
    - Balanced gender distribution (Male, Female)
    - All experience levels (First Month, Beginner, Intermediate, Advanced)
    - All fitness goals (Lose Weight, Gain Weight, Fat Loss, Build Muscle, Recomp, Strength, General Fitness)
    - All locations and equipment setups (Gym, Home Bodyweight, Home Dumbbells)
    - All session durations (30, 45, 60, 75, 90, 120 mins)
    - Training days (2, 3, 4, 5, 6 days) with both supported combinations and intentional edge cases
    - Priority muscles coverage and diverse caution combinations
    """
    rng = random.Random(seed)
    today = date(2026, 9, 1)

    experience_levels = [
        ExperienceLevel.FIRST_MONTH,
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    ]
    goals = [
        FitnessGoal.FAT_LOSS,
        FitnessGoal.BUILD_MUSCLE,
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

    for i in range(1, 201):
        # Determine sex
        sex = Sex.MALE if (i % 2 == 1) else Sex.FEMALE
        first_name = rng.choice(PERSIAN_FIRST_NAMES_MALE if sex == Sex.MALE else PERSIAN_FIRST_NAMES_FEMALE)
        last_name = rng.choice(PERSIAN_LAST_NAMES)
        name = f"{first_name} {last_name} (پروفایل {i})"

        # Determine experience level systematically across all 4 tiers
        exp_level = experience_levels[(i - 1) % len(experience_levels)]
        if exp_level == ExperienceLevel.FIRST_MONTH:
            training_age_months = 0
            # First month usually 2-3 days, occasionally 4, or 5 (unsupported edge case)
            if i % 25 == 0:
                training_days = 5  # Intentional unsupported edge case to test validation
            else:
                training_days = rng.choice([2, 3, 4])
        elif exp_level == ExperienceLevel.BEGINNER:
            training_age_months = rng.randint(1, 6)
            if i % 30 == 0:
                training_days = 6  # Intentional unsupported edge case
            else:
                training_days = rng.choice([2, 3, 4])
        elif exp_level == ExperienceLevel.INTERMEDIATE:
            training_age_months = rng.randint(7, 36)
            training_days = rng.choice([2, 3, 4, 5, 6])
        else:  # ADVANCED
            training_age_months = rng.randint(37, 120)
            if i % 35 == 0:
                training_days = 2  # Intentional unsupported edge case for advanced
            else:
                training_days = rng.choice([3, 4, 5, 6])

        # Age distribution: 19 to 65
        age = 19 + (i * 3 + rng.randint(0, 5)) % 46
        birth_year = today.year - age
        birth_month = (i % 12) + 1
        birth_day = (i % 27) + 1
        birth_date = date(birth_year, birth_month, birth_day)

        # Height and weight
        if sex == Sex.MALE:
            height_cm = rng.randint(168, 194)
            weight_kg = round(rng.uniform(62.0, 108.0), 1)
        else:
            height_cm = rng.randint(152, 178)
            weight_kg = round(rng.uniform(48.0, 88.0), 1)

        # Goal distribution
        fitness_goal = goals[(i - 1) % len(goals)]

        # Location & equipment setup
        loc, home_setup = locations[(i - 1) % len(locations)]

        # Session duration
        session_duration = durations[(i - 1) % len(durations)]

        # Priority muscle
        priority_muscle = priority_options[i % len(priority_options)]

        # Cautions
        training_cautions = caution_options[i % len(caution_options)]

        # Plan duration
        plan_duration_weeks = rng.choice([4, 6, 8])

        # Recovery ratings
        sleep_quality = rng.choice([RecoveryRating.POOR, RecoveryRating.AVERAGE, RecoveryRating.GOOD])
        stress_level = rng.choice([RecoveryRating.POOR, RecoveryRating.AVERAGE, RecoveryRating.GOOD])
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
    exact_description_fa = "محدودیت‌های تعیین‌شده در پروفایل امکان چیدمان برنامه معتبر را مسدود کردند."

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
            exact_description_fa = f"رد صلاحیت ایمنی به دلیل وضعیت ریسک پزشکی ({step.get('status')})."
        elif stage == "eligibility" and step.get("eligible_count", 0) == 0:
            root_cause = "INSUFFICIENT_ELIGIBLE_EXERCISES"
            rule_file = "app/workouts/program_engine/eligibility.py"
            rule_func = "filter_eligible_exercises()"
            actual_val = "0 حرکت مجاز"
            limit_val = "حداقل ۱ حرکت مجاز"
            failing_phase = "exercise_eligibility"
            exact_description_fa = "عدم وجود تمرین‌های مجاز در دیتابیس به دلیل تقاطع تجهیزات و محدودیت‌های اعمال شده."

    if root_cause == "UNSATISFIED_CONSTRAINT" and construction_recovery:
        attempts = construction_recovery.get("attempts", ())
        collected_reasons = []
        for attempt in attempts:
            attempt_reasons = attempt.get("reason_codes", ())
            collected_reasons.extend(attempt_reasons)

        duration_policy = get_session_duration_policy(request.session_duration_minutes)
        if "SESSION_DURATION_UNDER_TARGET" in collected_reasons or "SESSION_DURATION_EXCEEDED" in collected_reasons or "SESSION_DURATION_OVER_TARGET" in collected_reasons:
            if "SESSION_DURATION_UNDER_TARGET" in collected_reasons:
                root_cause = "SESSION_DURATION_UNDER_TARGET"
                actual_val = f"< {duration_policy.minimum_minutes} دقیقه"
                limit_val = f"{duration_policy.minimum_minutes}–{duration_policy.maximum_minutes} دقیقه"
                exact_description_fa = f"مدت زمان جلسات کمتر از حداقل بازه مجاز ({duration_policy.minimum_minutes} دقیقه) است."
            else:
                root_cause = "SESSION_DURATION_EXCEEDED"
                actual_val = f"> {duration_policy.maximum_minutes} دقیقه"
                limit_val = f"{duration_policy.minimum_minutes}–{duration_policy.maximum_minutes} دقیقه"
                exact_description_fa = f"مدت زمان جلسات بیش از حداکثر بازه مجاز ({duration_policy.maximum_minutes} دقیقه) شد."
            rule_file = "app/workouts/program_engine/session_duration.py"
            rule_func = "repair_session_durations()"
            failing_phase = "session_duration_repair_and_validation"
        elif "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" in collected_reasons:
            root_cause = "PER_SESSION_MUSCLE_VOLUME_EXCEEDED"
            cap = session_hard_volume_cap(request.training_age_months)
            actual_val = f"> {cap} ست در هر عضله/جلسه"
            limit_val = f"حداکثر {cap} ست مستقیم"
            exact_description_fa = f"حجم ست‌های مستقیم در یک جلسه فراتر از سقف مجاز سابقه تمرینی ({cap} ست) قرار گرفت."
            rule_file = "app/workouts/program_engine/validation.py"
            rule_func = "validate_program()"
            failing_phase = "session_volume_validation"
        elif "NO_SAFE_EXERCISE_FOR_PATTERN" in collected_reasons or any("NO_SAFE_EXERCISE" in str(r) for r in collected_reasons):
            root_cause = "NO_SAFE_EXERCISE_FOR_PATTERN"
            actual_val = "الگوی حرکتی بدون حرکت جایگزین ایمن"
            limit_val = "وجود حداقل ۱ حرکت ایمن و قابل‌اجرا"
            exact_description_fa = "نبود تمرین ایمن برای یک الگوی حرکتی به دلیل تداخل محدودیت‌های آسیب و تجهیزات."
            rule_file = "app/workouts/program_engine/session_builder.py"
            rule_func = "build_sessions()"
            failing_phase = "session_construction"
        elif "REQUESTED_TRAINING_DAYS_UNSATISFIED" in collected_reasons:
            root_cause = "REQUESTED_TRAINING_DAYS_UNSATISFIED"
            actual_val = f"اسپلیت {request.available_training_days} روزه"
            limit_val = f"{request.available_training_days} روز در هفته"
            exact_description_fa = f"عدم امکان تطبیق الگوی تقسیم روزها (اسپلیت) با {request.available_training_days} روز درخواستی."
            rule_file = "app/workouts/program_engine/split_selector.py"
            rule_func = "rank_split_candidates()"
            failing_phase = "split_selection"
        else:
            non_generic = [r for r in collected_reasons if r not in ("PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED", "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED", "UNSATISFIED_CONSTRAINT")]
            if non_generic:
                root_cause = non_generic[0]
                actual_val = root_cause
                limit_val = "تطابق با ضوابط طراحی"
                exact_description_fa = f"خطای منطقی موتور در فاز ساخت برنامه ({root_cause})."
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
    }


def evaluate_all_200_profiles() -> list[dict[str, Any]]:
    print("Loading settings and database session...")
    settings = get_settings()
    engine = create_engine(settings.database_url)

    profiles = generate_200_stratified_profiles()
    print(f"Generated {len(profiles)} stratified profiles.")

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
                    "actual_val": f"{p.experience_level.value} با {p.training_days_per_week} روز تمرین",
                    "limit_val": "تعداد روزهای مجاز طبق ماتریس سازگاری تمرین مقاومتی",
                    "failing_phase": "input_compatibility_validation",
                    "exact_description_fa": f"سطح سابقه {FA_TRANSLATIONS.get(p.experience_level.value, p.experience_level.value)} با {p.training_days_per_week} روز تمرین در هفته سازگار نیست و در قوانین فیتشو مجاز شمرده نمی‌شود.",
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
        margin: 10mm 10mm 12mm 10mm;
        @bottom-left {
            content: "Fitsho Workout Engine - 200 Profile Evaluation Report";
            font-family: 'Vazirmatn', 'Noto Sans Arabic', sans-serif;
            font-size: 7.5pt;
            color: #64748b;
        }
        @bottom-right {
            content: "صفحه " counter(page) " از " counter(pages);
            font-family: 'Vazirmatn', 'Noto Sans Arabic', sans-serif;
            font-size: 7.5pt;
            color: #64748b;
        }
    }
    * { box-sizing: border-box; }
    body {
        font-family: 'Vazirmatn', 'Noto Sans Arabic', 'DejaVu Sans', sans-serif;
        font-size: 8pt;
        line-height: 1.45;
        direction: rtl;
        text-align: right;
        color: #0f172a;
        background: #ffffff;
    }
    .header {
        text-align: center;
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%);
        color: #ffffff;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    .header h1 {
        font-size: 15pt;
        margin: 0 0 4px 0;
        font-weight: bold;
    }
    .header p {
        font-size: 8.5pt;
        margin: 0;
        opacity: 0.92;
    }
    .stats-row {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 12px;
    }
    .stat-card {
        flex: 1;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 5px;
        padding: 8px 6px;
        text-align: center;
    }
    .stat-val {
        font-size: 13pt;
        font-weight: bold;
        color: #1e40af;
    }
    .stat-lbl {
        font-size: 7pt;
        color: #64748b;
        margin-top: 2px;
    }
    .analytics-section {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 10px;
        margin-bottom: 14px;
        page-break-inside: avoid;
    }
    .analytics-title {
        font-size: 9.5pt;
        font-weight: bold;
        color: #1e3a8a;
        margin-bottom: 6px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.5pt;
        margin-bottom: 6px;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 3px 6px;
        text-align: right;
    }
    th {
        background: #e2e8f0;
        color: #334155;
        font-weight: bold;
    }
    .badge-success {
        background: #dcfce7;
        color: #166534;
        padding: 2px 6px;
        border-radius: 3px;
        font-weight: bold;
        font-size: 7pt;
        display: inline-block;
    }
    .badge-fail {
        background: #fee2e2;
        color: #991b1b;
        padding: 2px 6px;
        border-radius: 3px;
        font-weight: bold;
        font-size: 7pt;
        display: inline-block;
    }
    .profile-card {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        margin-bottom: 12px;
        background: #ffffff;
        page-break-inside: avoid;
        overflow: hidden;
    }
    .profile-card.success-card {
        border-right: 5px solid #16a34a;
    }
    .profile-card.fail-card {
        border-right: 5px solid #dc2626;
    }
    .card-header {
        background: #f8fafc;
        padding: 6px 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
    }
    .card-title {
        font-size: 9pt;
        font-weight: bold;
        color: #0f172a;
    }
    .grid-info {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 4px 8px;
        padding: 6px 10px;
        background: #ffffff;
        font-size: 7.2pt;
        border-bottom: 1px dashed #e2e8f0;
    }
    .info-item span.lbl {
        color: #64748b;
    }
    .info-item span.val {
        font-weight: bold;
        color: #0f172a;
    }
    .card-body {
        padding: 8px 10px;
    }
    .program-summary {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 4px;
        padding: 6px 8px;
        margin-bottom: 6px;
        font-size: 7.5pt;
    }
    .day-container {
        margin-top: 5px;
        background: #fafafa;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 5px 8px;
    }
    .day-header {
        font-weight: bold;
        font-size: 7.8pt;
        color: #1e3a8a;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
    }
    .ex-table {
        margin-top: 3px;
        margin-bottom: 0;
    }
    .ex-table th {
        background: #f1f5f9;
        font-size: 6.8pt;
        padding: 2px 4px;
    }
    .ex-table td {
        font-size: 6.8pt;
        padding: 2px 4px;
    }
    .fail-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 4px;
        padding: 8px 10px;
        font-size: 7.5pt;
    }
    .fail-title {
        color: #991b1b;
        font-weight: bold;
        font-size: 8.5pt;
        margin-bottom: 4px;
    }
    .fail-row {
        margin-bottom: 3px;
    }
    .fail-lbl {
        color: #7f1d1d;
        font-weight: bold;
    }
    code {
        font-family: monospace;
        background: #f1f5f9;
        padding: 1px 3px;
        border-radius: 2px;
        font-size: 7pt;
    }
    </style>
    """

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش جامع ۲۰۰ پروفایل موتور برنامه تمرینی Fitsho</title>
{css}
</head>
<body>

<div class="header">
    <h1>گزارش ارزیابی ۲۰۰ پروفایل در موتور تمرینی فیتشو (Fitsho Workout Engine)</h1>
    <p>بررسی خروجی و علل دقیق عدم ساخت برنامه بر روی ۲۰۰ پروفایل متنوع طبقه‌بندی‌شده | تاریخ ارزیابی: ۲۰۲۶-۰۹-۰۱</p>
</div>

<div class="stats-row">
    <div class="stat-card">
        <div class="stat-val">{total}</div>
        <div class="stat-lbl">کل پروفایل‌های تستی</div>
    </div>
    <div class="stat-card">
        <div class="stat-val" style="color: #166534;">{success_count}</div>
        <div class="stat-lbl">برنامه تولید شده (موفق)</div>
    </div>
    <div class="stat-card">
        <div class="stat-val" style="color: #991b1b;">{failure_count}</div>
        <div class="stat-lbl">عدم تولید برنامه (دارای خطا)</div>
    </div>
    <div class="stat-card">
        <div class="stat-val">{success_rate:.1f}٪</div>
        <div class="stat-lbl">نرخ موفقیت (Success Rate)</div>
    </div>
</div>

<div class="analytics-section">
    <div class="analytics-title">تحلیل و ریشه‌یابی آماری عدم تولید برنامه (Failure Root Causes Analytics)</div>
    <div style="display: flex; gap: 10px;">
        <div style="flex: 1;">
            <table>
                <thead>
                    <tr>
                        <th>کد وضعیت خطا</th>
                        <th style="width: 50px; text-align: center;">تعداد</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td><code>{k}</code></td><td style='text-align: center; font-weight: bold;'>{v}</td></tr>" for k, v in failures_by_code.items())}
                </tbody>
            </table>
        </div>
        <div style="flex: 1;">
            <table>
                <thead>
                    <tr>
                        <th>علت ریشه‌ای / محدودیت ناموفق</th>
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

<h2 style="font-size: 11pt; color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 3px; margin: 14px 0 10px 0;">
    فهرست و کارنامه تفصیلی ۲۰۰ پروفایل و برنامه‌های تخصیص‌یافته
</h2>
"""

    for r in results:
        p: ProfileSpec = r["profile"]
        status = r["status"]
        is_success = (status == "SUCCESS")
        card_class = "success-card" if is_success else "fail-card"
        badge = '<span class="badge-success">برنامه با موفقیت تولید شد</span>' if is_success else '<span class="badge-fail">برنامه تولید نشد</span>'

        sex_fa = FA_TRANSLATIONS.get(p.sex.value, p.sex.value)
        goal_fa = FA_TRANSLATIONS.get(p.fitness_goal.value, p.fitness_goal.value)
        level_fa = FA_TRANSLATIONS.get(p.experience_level.value, p.experience_level.value)
        loc_fa = FA_TRANSLATIONS.get(p.training_location.value, p.training_location.value)
        setup_fa = FA_TRANSLATIONS.get(p.home_training_setup.value, p.home_training_setup.value) if p.home_training_setup else "کامل باشگاه"
        pri_fa = FA_TRANSLATIONS.get(p.priority_muscle.value, p.priority_muscle.value) if p.priority_muscle else "ندارد"
        cautions_fa = ", ".join(FA_TRANSLATIONS.get(c.value, c.value) for c in p.training_cautions) if p.training_cautions else "بدون آسیب"

        html += f"""
<div class="profile-card {card_class}">
    <div class="card-header">
        <span class="card-title">پروفایل #{p.index:03d}: {p.name}</span>
        {badge}
    </div>
    <div class="grid-info">
        <div class="info-item"><span class="lbl">جنسیت و سن:</span> <span class="val">{sex_fa}، {p.age} سال</span></div>
        <div class="info-item"><span class="lbl">قد و وزن:</span> <span class="val">{p.height_cm}cm / {p.weight_kg}kg</span></div>
        <div class="info-item"><span class="lbl">هدف تمرینی:</span> <span class="val">{goal_fa}</span></div>
        <div class="info-item"><span class="lbl">سطح و سابقه:</span> <span class="val">{level_fa} ({p.training_age_months} ماه)</span></div>
        <div class="info-item"><span class="lbl">روزهای تمرین:</span> <span class="val">{p.training_days_per_week} روز در هفته</span></div>
        <div class="info-item"><span class="lbl">مدت زمان جلسه:</span> <span class="val">{p.session_duration_minutes} دقیقه</span></div>
        <div class="info-item"><span class="lbl">مکان و تجهیزات:</span> <span class="val">{loc_fa} ({setup_fa})</span></div>
        <div class="info-item"><span class="lbl">اولویت عضلانی:</span> <span class="val">{pri_fa}</span></div>
        <div class="info-item" style="grid-column: span 4;"><span class="lbl">محدودیت‌ها و آسیب‌ها:</span> <span class="val">{cautions_fa}</span></div>
    </div>
    <div class="card-body">
"""

        if is_success:
            split_fa = r.get("split_fa") or r.get("split")
            days_count = r.get("days_count", 0)
            html += f"""
        <div class="program-summary">
            <strong>ساختار برنامه:</strong> اسپلیت <strong>{split_fa}</strong> | تعداد جلسات: <strong>{days_count} جلسه در هفته</strong> | طول دوره: <strong>{p.plan_duration_weeks} هفته</strong>
        </div>
"""
            for day in r.get("days", []):
                d_idx = day.get("day_index")
                d_title = day.get("title")
                d_dur = day.get("estimated_duration_minutes")
                ex_list = day.get("exercises", [])

                html += f"""
        <div class="day-container">
            <div class="day-header">
                <span>جلسه {d_idx}: {d_title}</span>
                <span>زمان تخمینی: {d_dur} دقیقه ({len(ex_list)} حرکت)</span>
            </div>
            <table class="ex-table">
                <thead>
                    <tr>
                        <th style="width: 25px; text-align: center;">#</th>
                        <th>نام تمرین (فارسی / انگلیسی)</th>
                        <th style="width: 70px;">عضله هدف</th>
                        <th style="width: 45px; text-align: center;">ست</th>
                        <th style="width: 65px; text-align: center;">تکرار</th>
                        <th style="width: 45px; text-align: center;">RIR</th>
                        <th style="width: 55px; text-align: center;">استراحت</th>
                    </tr>
                </thead>
                <tbody>
"""
                for it in ex_list:
                    html += f"""
                    <tr>
                        <td style="text-align: center;">{it['order']}</td>
                        <td><strong>{it['name_fa']}</strong> <span style="color: #64748b; font-size: 6.2pt;">({it['name_en']})</span></td>
                        <td>{it['primary_muscle_fa']}</td>
                        <td style="text-align: center; font-weight: bold;">{it['sets']}</td>
                        <td style="text-align: center;">{it['rep_min']}-{it['rep_max']}</td>
                        <td style="text-align: center;">{it['rir']}</td>
                        <td style="text-align: center;">{it['rest_seconds']}ث</td>
                    </tr>
"""
                html += """
                </tbody>
            </table>
        </div>
"""
        else:
            finfo = r.get("failure_info", {})
            html += f"""
        <div class="fail-box">
            <div class="fail-title">علت دقیق عدم تولید برنامه: {finfo.get('root_cause')}</div>
            <div class="fail-row"><span class="fail-lbl">توضیح تفصیلی:</span> {finfo.get('exact_description_fa')}</div>
            <div class="fail-row"><span class="fail-lbl">فاز اجرایی شکست:</span> <code>{finfo.get('failing_phase')}</code></div>
            <div class="fail-row"><span class="fail-lbl">قانون و متد ناظر:</span> <code>{finfo.get('rule_file')} -> {finfo.get('rule_func')}</code></div>
            <div class="fail-row"><span class="fail-lbl">مقدار واقعی / حد مجاز:</span> {finfo.get('actual_val')} (حد مجاز: {finfo.get('limit_val')})</div>
        </div>
"""

        html += """
    </div>
</div>
"""

    html += """
</body>
</html>
"""
    return html


def main() -> None:
    import weasyprint

    results = evaluate_all_200_profiles()
    successes = sum(1 for r in results if r["status"] == "SUCCESS")
    failures = len(results) - successes
    print(f"\nEvaluation summary: {successes} succeeded, {failures} failed.")

    # Save JSON raw report
    os.makedirs("/home/mohammad/project/fitsho/var/reports", exist_ok=True)
    os.makedirs("/home/mohammad/project/fitsho/reports", exist_ok=True)

    json_path = "/home/mohammad/project/fitsho/var/reports/200_profiles_eval_data.json"
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
    print(f"Saved raw evaluation data to {json_path}")

    # Build HTML
    print("Building Persian HTML for 200 profiles...")
    html_content = build_pdf_html(results)
    html_path = "/home/mohammad/project/fitsho/reports/fitsho_200_profiles_eval_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML report saved to {html_path}")

    # Render PDF
    pdf_path = "/home/mohammad/project/fitsho/reports/fitsho_200_profiles_eval_report.pdf"
    print(f"Rendering PDF with WeasyPrint to {pdf_path} (this will render all 200 profile cards)...")
    weasyprint.HTML(string=html_content).write_pdf(pdf_path)
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"PDF generated successfully at {pdf_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()

