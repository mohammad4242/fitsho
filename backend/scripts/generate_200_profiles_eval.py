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


if __name__ == "__main__":
    results = evaluate_all_200_profiles()
    successes = sum(1 for r in results if r["status"] == "SUCCESS")
    failures = len(results) - successes
    print(f"\nCompleted evaluation of {len(results)} profiles:")
    print(f"  Successes: {successes} ({successes/len(results)*100:.1f}%)")
    print(f"  Failures:  {failures} ({failures/len(results)*100:.1f}%)")
