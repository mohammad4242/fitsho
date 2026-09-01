from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
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
from app.training_templates.bodyweight_reference import load_bodyweight_template
from app.training_templates.engine_reference import TemplateReference, load_template_references
from app.workouts.bodyweight_routing import (
    BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED,
    BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED,
    BodyweightRoutingStatus,
    resolve_fixed_bodyweight_route,
)
from app.workouts.bodyweight_template_builder import (
    BodyweightTemplateBuildError,
    build_bodyweight_template_program,
)
from app.workouts.bodyweight_templates import (
    BodyweightProgramTemplate,
    get_bodyweight_template,
)
from app.workouts.candidate_selector import caution_tags_for_training_cautions
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
    get_session_exercise_count_policy,
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
    SafetyStatus,
    TrainingExperience,
)
from app.workouts.program_engine.equipment import resolve_available_equipment
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset
from app.workouts.program_engine.safety import screen_safety
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    RecentTrainingHistory,
    WorkoutProgram,
)
from app.workouts.program_engine.volume_policy import session_hard_volume_cap
from app.workouts.service import WorkoutGenerationService

BENCHMARK_SEED = 20260902

PERSIAN_FIRST_NAMES_MALE = [
    "علی", "محمد", "امیرحسین", "رضا", "حسین", "مهدی", "سجاد", "آرمین", "سینا", "نیما",
    "کامران", "فرزاد", "بهنام", "نوید", "فرهاد", "سهراب", "داریوش", "کسری", "شایان", "مانی",
    "پوریا", "آرش", "سامان", "میلاد", "پیمان", "احسان", "مسعود", "امید", "شهاب", "پویا",
    "کیوان", "بابک", "افشین", "یاشار", "سام", "بهرام", "کامبیز", "سیروس", "هومن", "بیژن",
]

PERSIAN_FIRST_NAMES_FEMALE = [
    "سارا", "مریم", "زهرا", "فاطمه", "شیدا", "بهاره", "پروانه", "سوگند", "طناز", "یاسمین",
    "آیدا", "طاهره", "مونا", "الهام", "نگار", "رویا", "مهسا", "ساناز", "نسیم", "نیلوفر",
    "صبا", "گلناز", "پریناز", "یلدا", "ترانه", "ستاره", "سیمین", "مینا", "سمیرا", "غزاله",
    "شیوا", "آتوسا", "دنیا", "سحر", "مرجان", "شادی", "کتایون", "پانته‌آ", "هستی", "نسترن",
]

PERSIAN_LAST_NAMES = [
    "احمدی", "رضایی", "کاظمی", "مرادی", "حسینی", "محمدی", "کریمی", "موسوی", "جعفری", "قاسمی",
    "نوری", "صبوری", "محمودی", "سلطانی", "زمانی", "ابراهیمی", "فراهانی", "یوسفی", "راد", "جلالی",
    "فتوحی", "معتمدی", "صادقی", "داوودی", "رستگار", "افشار", "اکبری", "قادری", "انصاری", "طاهری",
    "حیدری", "نجفی", "بیات", "شریفی", "فرهادی", "جمشیدی", "صالحی", "باقری", "مظفری", "خسروی",
    "امینی", "رحیمی", "یزدانی", "مقدم", "وفایی", "سعیدی", "عباسی", "صادقیان", "طالبی", "کمالی",
]

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
    "abs": "شکم",
    "obliques": "پهلو",
    "lower_back": "کمر (ستون فقرات کمری)",
    "knee": "زانو",
    "shoulder": "شانه",
    "neck": "گردن",
    "wrist": "مچ دست",
    "full_body": "فول بادی (Full Body)",
    "full_body_ab": "فول بادی متناوب (Full Body A/B)",
    "full_body_abc": "فول بادی سه روزه (Full Body A/B/C)",
    "full_body_four": "فول بادی ۴ روزه (Full Body 4-Day)",
    "upper_lower": "بالاتنه / پایین‌تنه (Upper/Lower)",
    "upper_lower_full": "بالاتنه / پایین‌تنه + فول بادی",
    "upper_lower_specialization": "بالاتنه / پایین‌تنه تخصصی (Specialization)",
    "push_pull_legs": "پوش / پول / لگز (PPL)",
    "push_pull_legs_upper_lower": "PPL + بالاتنه / پایین‌تنه (۵ روزه)",
    "push_pull_legs_x2": "PPL دو بار در هفته (۶ روزه)",
    "body_part_rotation": "چرخش بخش‌های بدن (Body Part Rotation)",
    "dynamic_fallback": "اسپلیت پویا (Dynamic Split)",
    "bodyweight_fixed_template": "تمپلیت ثابت وزن بدن (Fixed Bodyweight)",
    "program_engine": "موتور تمرینی هوشمند (Program Engine)",
    "compatibility_rejection": "رد سازگاری ورودی (Product Contract Rejection)",
    "safety_rejection": "رد غربالگری ایمنی و ارجاع پزشکی (Safety Rejection)",
}


@dataclass
class ProfileSpec:
    profile_id: int
    seed: int
    name: str
    sex: Sex
    birth_date: date
    age: int
    height_cm: int
    weight_kg: float
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_age_months: int
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None
    resolved_equipment: list[str]
    training_days_per_week: int
    session_duration_minutes: int
    priority_muscle: MuscleGroup | None
    training_cautions: list[TrainingCaution]
    plan_duration_weeks: int
    sleep_quality: RecoveryRating = RecoveryRating.GOOD
    stress_level: RecoveryRating = RecoveryRating.AVERAGE
    physical_job_demand: PhysicalJobDemand = PhysicalJobDemand.LOW
    current_pain_or_red_flags: list[str] = field(default_factory=list)
    reports_uncontrolled_medical_condition: bool = False
    pregnancy_or_postpartum: bool = False
    is_deliberate_unsupported: bool = False
    deliberate_unsupported_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sex"] = self.sex.value
        d["birth_date"] = self.birth_date.isoformat()
        d["fitness_goal"] = self.fitness_goal.value
        d["experience_level"] = self.experience_level.value
        d["training_location"] = self.training_location.value
        d["home_training_setup"] = (
            self.home_training_setup.value if self.home_training_setup else None
        )
        d["priority_muscle"] = (
            self.priority_muscle.value if self.priority_muscle else None
        )
        d["training_cautions"] = [c.value for c in self.training_cautions]
        d["sleep_quality"] = self.sleep_quality.value
        d["stress_level"] = self.stress_level.value
        d["physical_job_demand"] = self.physical_job_demand.value
        return d


def generate_1000_profiles(seed: int = BENCHMARK_SEED) -> list[ProfileSpec]:
    rng = random.Random(seed)
    today = date(2026, 9, 2)

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
    priority_muscle_pool = list(USER_SELECTABLE_PRIORITY_MUSCLES)

    # Caution distribution: ~55% None, ~30% 1 caution, ~15% 2 cautions
    single_cautions = [
        TrainingCaution.LOWER_BACK,
        TrainingCaution.KNEE,
        TrainingCaution.SHOULDER,
        TrainingCaution.NECK,
        TrainingCaution.WRIST,
    ]
    double_caution_combos = [
        [TrainingCaution.LOWER_BACK, TrainingCaution.KNEE],
        [TrainingCaution.KNEE, TrainingCaution.SHOULDER],
        [TrainingCaution.SHOULDER, TrainingCaution.NECK],
        [TrainingCaution.WRIST, TrainingCaution.SHOULDER],
        [TrainingCaution.LOWER_BACK, TrainingCaution.NECK],
        [TrainingCaution.WRIST, TrainingCaution.LOWER_BACK],
    ]

    def sample_cautions() -> list[TrainingCaution]:
        roll = rng.random()
        if roll < 0.55:
            return []
        elif roll < 0.85:
            return [rng.choice(single_cautions)]
        else:
            return list(rng.choice(double_caution_combos))

    profiles: list[ProfileSpec] = []

    # Deliberate unsupported plan (70 profiles = 7.0%):
    # 1. 35 profiles: BODYWEIGHT_ONLY + INTERMEDIATE (20) / ADVANCED (15)
    # 2. 20 profiles: Unsupported days: FIRST_MONTH 5/6d (8), BEGINNER 5/6d (8), ADVANCED 2d (4)
    # 3. 15 profiles: Expected safety rejections: red flags/uncontrolled (8), pregnancy (7)
    # The remaining 930 profiles are 100% supported by Fitsho product rules!

    unsupported_indices = set(rng.sample(range(1, 1001), 70))
    unsupported_type_map: dict[int, str] = {}
    unsupported_list = sorted(list(unsupported_indices))

    for idx in unsupported_list[:20]:
        unsupported_type_map[idx] = "BW_INTERMEDIATE"
    for idx in unsupported_list[20:35]:
        unsupported_type_map[idx] = "BW_ADVANCED"
    for idx in unsupported_list[35:43]:
        unsupported_type_map[idx] = "FIRST_MONTH_BAD_DAYS"
    for idx in unsupported_list[43:51]:
        unsupported_type_map[idx] = "BEGINNER_BAD_DAYS"
    for idx in unsupported_list[51:55]:
        unsupported_type_map[idx] = "ADVANCED_BAD_DAYS"
    for idx in unsupported_list[55:59]:
        unsupported_type_map[idx] = "SAFETY_RED_FLAGS"
    for idx in unsupported_list[59:63]:
        unsupported_type_map[idx] = "SAFETY_UNCONTROLLED"
    for idx in unsupported_list[63:70]:
        unsupported_type_map[idx] = "SAFETY_PREGNANCY"

    experience_options = [
        ExperienceLevel.FIRST_MONTH,
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    ]

    for profile_id in range(1, 1001):
        # Independent draws for demographics
        sex = Sex.MALE if rng.random() < 0.50 else Sex.FEMALE
        first_name = rng.choice(
            PERSIAN_FIRST_NAMES_MALE if sex is Sex.MALE else PERSIAN_FIRST_NAMES_FEMALE
        )
        last_name = rng.choice(PERSIAN_LAST_NAMES)
        name = f"{first_name} {last_name}"

        age = rng.randint(18, 62)
        birth_year = today.year - age
        birth_month = rng.randint(1, 12)
        birth_day = rng.randint(1, 28)
        birth_date = date(birth_year, birth_month, birth_day)

        if sex is Sex.MALE:
            height_cm = rng.randint(165, 195)
            weight_kg = round(rng.uniform(62.0, 108.0), 1)
        else:
            height_cm = rng.randint(152, 178)
            weight_kg = round(rng.uniform(48.0, 88.0), 1)

        fitness_goal = rng.choice(goals)
        session_duration = rng.choice(durations)
        plan_duration = rng.choice([4, 6, 8])

        # Priority muscle: 40% None, 60% one selectable muscle
        if rng.random() < 0.40:
            priority_muscle = None
        else:
            priority_muscle = rng.choice(priority_muscle_pool)

        training_cautions = sample_cautions()

        sleep_quality = rng.choice(
            [RecoveryRating.AVERAGE, RecoveryRating.GOOD, RecoveryRating.POOR]
        )
        stress_level = rng.choice(
            [RecoveryRating.AVERAGE, RecoveryRating.GOOD, RecoveryRating.POOR]
        )
        physical_job_demand = rng.choice(
            [PhysicalJobDemand.LOW, PhysicalJobDemand.MODERATE, PhysicalJobDemand.HIGH]
        )

        current_pain_or_red_flags: list[str] = []
        reports_uncontrolled_medical_condition = False
        pregnancy_or_postpartum = False
        is_deliberate_unsupported = False
        deliberate_unsupported_reason = None

        if profile_id in unsupported_type_map:
            is_deliberate_unsupported = True
            subtype = unsupported_type_map[profile_id]

            if subtype == "BW_INTERMEDIATE":
                exp_level = ExperienceLevel.INTERMEDIATE
                training_age_months = rng.randint(7, 36)
                training_location = TrainingLocation.HOME
                home_setup = HomeTrainingSetup.BODYWEIGHT_ONLY
                training_days = rng.choice([2, 3, 4])
                deliberate_unsupported_reason = "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED"

            elif subtype == "BW_ADVANCED":
                exp_level = ExperienceLevel.ADVANCED
                training_age_months = rng.randint(37, 100)
                training_location = TrainingLocation.HOME
                home_setup = HomeTrainingSetup.BODYWEIGHT_ONLY
                training_days = rng.choice([3, 4, 5])
                deliberate_unsupported_reason = "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED"

            elif subtype == "FIRST_MONTH_BAD_DAYS":
                exp_level = ExperienceLevel.FIRST_MONTH
                training_age_months = 0
                training_location = rng.choice(
                    [TrainingLocation.GYM, TrainingLocation.HOME]
                )
                home_setup = (
                    rng.choice(
                        [
                            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
                            HomeTrainingSetup.BODYWEIGHT_ONLY,
                        ]
                    )
                    if training_location is TrainingLocation.HOME
                    else None
                )
                training_days = rng.choice([5, 6])
                deliberate_unsupported_reason = "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"

            elif subtype == "BEGINNER_BAD_DAYS":
                exp_level = ExperienceLevel.BEGINNER
                training_age_months = rng.randint(1, 6)
                training_location = rng.choice(
                    [TrainingLocation.GYM, TrainingLocation.HOME]
                )
                home_setup = (
                    rng.choice(
                        [
                            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
                            HomeTrainingSetup.BODYWEIGHT_ONLY,
                        ]
                    )
                    if training_location is TrainingLocation.HOME
                    else None
                )
                training_days = rng.choice([5, 6])
                deliberate_unsupported_reason = "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"

            elif subtype == "ADVANCED_BAD_DAYS":
                exp_level = ExperienceLevel.ADVANCED
                training_age_months = rng.randint(37, 100)
                training_location = rng.choice(
                    [TrainingLocation.GYM, TrainingLocation.HOME]
                )
                home_setup = (
                    HomeTrainingSetup.DUMBBELLS_AVAILABLE
                    if training_location is TrainingLocation.HOME
                    else None
                )
                training_days = 2
                deliberate_unsupported_reason = "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"

            elif subtype == "SAFETY_RED_FLAGS":
                exp_level = rng.choice(experience_options)
                training_age_months = _sample_training_age(exp_level, rng)
                training_location, home_setup = _sample_supported_location(
                    exp_level, rng
                )
                training_days = _sample_supported_days(
                    exp_level, training_location, home_setup, rng
                )
                current_pain_or_red_flags = ["chest_pain"]
                deliberate_unsupported_reason = "EXPECTED_SAFETY_REJECTION"

            elif subtype == "SAFETY_UNCONTROLLED":
                exp_level = rng.choice(experience_options)
                training_age_months = _sample_training_age(exp_level, rng)
                training_location, home_setup = _sample_supported_location(
                    exp_level, rng
                )
                training_days = _sample_supported_days(
                    exp_level, training_location, home_setup, rng
                )
                reports_uncontrolled_medical_condition = True
                deliberate_unsupported_reason = "EXPECTED_SAFETY_REJECTION"

            elif subtype == "SAFETY_PREGNANCY":
                sex = Sex.FEMALE
                first_name = rng.choice(PERSIAN_FIRST_NAMES_FEMALE)
                name = f"{first_name} {last_name}"
                exp_level = rng.choice(experience_options)
                training_age_months = _sample_training_age(exp_level, rng)
                training_location, home_setup = _sample_supported_location(
                    exp_level, rng
                )
                training_days = _sample_supported_days(
                    exp_level, training_location, home_setup, rng
                )
                pregnancy_or_postpartum = True
                deliberate_unsupported_reason = "EXPECTED_SAFETY_REJECTION"

        else:
            # Fully supported profile
            exp_level = rng.choice(experience_options)
            training_age_months = _sample_training_age(exp_level, rng)
            training_location, home_setup = _sample_supported_location(exp_level, rng)
            training_days = _sample_supported_days(
                exp_level, training_location, home_setup, rng
            )

        equipment_set = resolve_available_equipment(
            training_location, home_setup, None
        )
        resolved_equipment = sorted([item.value for item in equipment_set])

        profiles.append(
            ProfileSpec(
                profile_id=profile_id,
                seed=seed,
                name=name,
                sex=sex,
                birth_date=birth_date,
                age=age,
                height_cm=height_cm,
                weight_kg=weight_kg,
                fitness_goal=fitness_goal,
                experience_level=exp_level,
                training_age_months=training_age_months,
                training_location=training_location,
                home_training_setup=home_setup,
                resolved_equipment=resolved_equipment,
                training_days_per_week=training_days,
                session_duration_minutes=session_duration,
                priority_muscle=priority_muscle,
                training_cautions=training_cautions,
                plan_duration_weeks=plan_duration,
                sleep_quality=sleep_quality,
                stress_level=stress_level,
                physical_job_demand=physical_job_demand,
                current_pain_or_red_flags=current_pain_or_red_flags,
                reports_uncontrolled_medical_condition=reports_uncontrolled_medical_condition,
                pregnancy_or_postpartum=pregnancy_or_postpartum,
                is_deliberate_unsupported=is_deliberate_unsupported,
                deliberate_unsupported_reason=deliberate_unsupported_reason,
            )
        )

    return profiles


def _sample_training_age(exp_level: ExperienceLevel, rng: random.Random) -> int:
    if exp_level is ExperienceLevel.FIRST_MONTH:
        return 0
    elif exp_level is ExperienceLevel.BEGINNER:
        return rng.randint(1, 6)
    elif exp_level is ExperienceLevel.INTERMEDIATE:
        return rng.randint(7, 36)
    else:
        return rng.randint(37, 120)


def _sample_supported_location(
    exp_level: ExperienceLevel, rng: random.Random
) -> tuple[TrainingLocation, HomeTrainingSetup | None]:
    if exp_level in (ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER):
        roll = rng.random()
        if roll < 0.40:
            return TrainingLocation.GYM, None
        elif roll < 0.70:
            return TrainingLocation.HOME, HomeTrainingSetup.DUMBBELLS_AVAILABLE
        else:
            return TrainingLocation.HOME, HomeTrainingSetup.BODYWEIGHT_ONLY
    else:
        if rng.random() < 0.55:
            return TrainingLocation.GYM, None
        else:
            return TrainingLocation.HOME, HomeTrainingSetup.DUMBBELLS_AVAILABLE


def _sample_supported_days(
    exp_level: ExperienceLevel,
    location: TrainingLocation,
    home_setup: HomeTrainingSetup | None,
    rng: random.Random,
) -> int:
    if (
        location is TrainingLocation.HOME
        and home_setup is HomeTrainingSetup.BODYWEIGHT_ONLY
    ):
        return rng.choice([2, 3, 4])

    if exp_level is ExperienceLevel.FIRST_MONTH:
        return rng.choices([2, 3, 4], weights=[45, 45, 10])[0]
    elif exp_level is ExperienceLevel.BEGINNER:
        return rng.choices([2, 3, 4], weights=[40, 45, 15])[0]
    elif exp_level is ExperienceLevel.INTERMEDIATE:
        return rng.choices([2, 3, 4, 5, 6], weights=[10, 30, 35, 20, 5])[0]
    else:
        return rng.choices([3, 4, 5, 6], weights=[15, 40, 30, 15])[0]


def validate_dataset_sanity(profiles: list[ProfileSpec]) -> dict[str, Any]:
    total = len(profiles)
    if total != 1000:
        raise ValueError(f"Dataset sanity check failed: Expected 1000 profiles, got {total}")

    exp_loc: dict[str, Counter[str]] = defaultdict(Counter)
    exp_cautions: dict[str, Counter[int]] = defaultdict(Counter)
    loc_cautions: dict[str, Counter[int]] = defaultdict(Counter)
    exp_loc_cautions: dict[str, Counter[int]] = defaultdict(Counter)

    for p in profiles:
        exp = p.experience_level.value
        loc_str = (
            f"{p.training_location.value}_{p.home_training_setup.value}"
            if p.home_training_setup
            else p.training_location.value
        )
        c_count = len(p.training_cautions)
        exp_loc[exp][loc_str] += 1
        exp_cautions[exp][c_count] += 1
        loc_cautions[loc_str][c_count] += 1
        exp_loc_cautions[f"{exp}:{loc_str}"][c_count] += 1

    for group_name, counter in exp_cautions.items():
        total_group = sum(counter.values())
        if counter[0] == 0:
            raise ValueError(f"Sanity Check Failure: {group_name} has 0% healthy profiles!")
        if counter[0] == total_group:
            raise ValueError(f"Sanity Check Failure: {group_name} has 100% healthy (0 cautions) profiles!")
        if counter[1] == total_group or counter[2] == total_group:
            raise ValueError(f"Sanity Check Failure: {group_name} has 100% caution prevalence!")

    total_zero_caution = sum(1 for p in profiles if len(p.training_cautions) == 0)
    total_one_caution = sum(1 for p in profiles if len(p.training_cautions) == 1)
    total_two_caution = sum(1 for p in profiles if len(p.training_cautions) == 2)

    zero_pct = (total_zero_caution / total) * 100
    one_pct = (total_one_caution / total) * 100
    two_pct = (total_two_caution / total) * 100

    if not (45.0 <= zero_pct <= 65.0):
        raise ValueError(f"Sanity Check Failure: Zero-caution percentage out of realistic range: {zero_pct:.1f}%")
    if not (20.0 <= one_pct <= 40.0):
        raise ValueError(f"Sanity Check Failure: Single-caution percentage out of realistic range: {one_pct:.1f}%")
    if not (5.0 <= two_pct <= 25.0):
        raise ValueError(f"Sanity Check Failure: Two-caution percentage out of realistic range: {two_pct:.1f}%")

    return {
        "total": total,
        "zero_caution_count": total_zero_caution,
        "zero_caution_pct": zero_pct,
        "one_caution_count": total_one_caution,
        "one_caution_pct": one_pct,
        "two_caution_count": total_two_caution,
        "two_caution_pct": two_pct,
        "experience_x_location": {k: dict(v) for k, v in exp_loc.items()},
        "experience_x_caution_count": {k: dict(v) for k, v in exp_cautions.items()},
        "location_x_caution_count": {k: dict(v) for k, v in loc_cautions.items()},
        "exp_loc_x_caution_count": {k: dict(v) for k, v in exp_loc_cautions.items()},
    }
