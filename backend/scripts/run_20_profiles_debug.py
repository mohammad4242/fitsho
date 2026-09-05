from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import weasyprint
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
from app.profile.schemas import ProfileCreate
from app.profile.training_compatibility import require_supported_resistance_training_days
from app.training_templates.engine_reference import load_template_references
from app.workout_reviews.models import WorkoutPlanReview  # Ensure models loaded
from app.workouts.candidate_selector import caution_tags_for_training_cautions
from app.workouts.service import WorkoutGenerationService, legacy_training_age_months
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
    get_session_exercise_count_policy,
)
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    ActivityLevel,
    BalanceAbility,
    GenerationErrorCode,
    Goal,
    ImpactLimit,
    LoadLimit,
    MedicalClearanceStatus,
    PhysicalJobDemand,
    RecoveryRating,
    RedFlag,
    SafetyStatus,
    TrainingExperience,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    Limitation,
    ProgramGenerationRequest,
    RecentTrainingHistory,
    TemplateReference,
    WorkoutProgram,
)
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.volume_policy import session_hard_volume_cap
from app.workouts.service import WorkoutGenerationService


FA_TRANSLATIONS = {
    "male": "مرد",
    "female": "زن",
    "first_month": "ماه اول (First Month)",
    "beginner": "مبتدی (Beginner)",
    "intermediate": "متوسط (Intermediate)",
    "advanced": "پیشرفته (Advanced)",
    "lose_weight": "کاهش وزن (Lose Weight)",
    "gain_weight": "افزایش وزن (Gain Weight)",
    "fat_loss": "چربی‌سوزی (Fat Loss)",
    "build_muscle": "عضله‌سازی (Build Muscle)",
    "body_recomposition": "ترکیب بدنی / ریکامپ (Recomposition)",
    "strength": "افزایش قدرت (Strength)",
    "improve_fitness": "آمادگی جسمانی عمومی (General Fitness)",
    "maintain_weight": "تثبیت وزن (Maintain Weight)",
    "gym": "باشگاه (Gym)",
    "home": "منزل (Home)",
    "bodyweight_only": "فقط وزن بدن (Bodyweight)",
    "dumbbells_available": "همراه با دمبل (Dumbbells)",
    "chest": "سینه (Chest)",
    "back": "پشت / زیربغل (Back)",
    "shoulders": "سرشانه (Shoulders)",
    "biceps": "جلو بازو (Biceps)",
    "triceps": "پشت بازو (Triceps)",
    "glutes": "باسن / باسن بزرگ (Glutes)",
    "quadriceps": "چهارسر ران (Quadriceps)",
    "hamstrings": "همسترینگ (Hamstrings)",
    "calves": "ساق پا (Calves)",
    "abs": "شکم (Abs)",
    "lower_back": "کمر / ستون فقرات کمری (Lower Back)",
    "knee": "زانو (Knee)",
    "shoulder": "شانه (Shoulders)",
    "neck": "گردن (Neck)",
    "wrist": "مچ دست (Wrist)",
    "other": "سایر (Other)",
    "full_body": "فول بادی (Full Body)",
    "full_body_ab": "فول بادی A/B",
    "full_body_abc": "فول بادی A/B/C",
    "upper_lower": "بالاتنه / پایین‌تنه (Upper/Lower)",
    "upper_lower_full": "بالاتنه / پایین‌تنه + فول بادی",
    "upper_lower_specialization": "بالاتنه / پایین‌تنه تخصصی",
    "push_pull_legs": "پوش / پول / لگز (PPL)",
    "push_pull_legs_upper_lower": "PPL + بالاتنه / پایین‌تنه (5 روزه)",
    "push_pull_legs_x2": "PPL دو بار در هفته (6 روزه)",
    "dynamic_fallback": "اسپلیت پویا (Dynamic Split)",
}


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


def define_20_diverse_profiles() -> list[ProfileSpec]:
    return [
        # Profile 1: Female, First Month, 2 days, 45 min, Home Bodyweight, Fat Loss
        ProfileSpec(
            index=1,
            name="سارا احمدی (پروفایل ۱)",
            sex=Sex.FEMALE,
            birth_date=date(2000, 4, 15),
            age=26,
            height_cm=164,
            weight_kg=68.0,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_age_months=0,
            training_days_per_week=2,
            session_duration_minutes=45,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            priority_muscle=None,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 2: Male, Beginner, 3 days, 60 min, Gym Full, Build Muscle, Chest priority
        ProfileSpec(
            index=2,
            name="علی رضایی (پروفایل ۲)",
            sex=Sex.MALE,
            birth_date=date(1998, 7, 20),
            age=28,
            height_cm=178,
            weight_kg=74.5,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.BEGINNER,
            training_age_months=4,
            training_days_per_week=3,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.CHEST,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 3: Female, Intermediate, 4 days, 60 min, Gym, Recomposition, Glutes priority, Knee caution
        ProfileSpec(
            index=3,
            name="مریم کاظمی (پروفایل ۳)",
            sex=Sex.FEMALE,
            birth_date=date(1994, 2, 10),
            age=32,
            height_cm=168,
            weight_kg=63.0,
            fitness_goal=FitnessGoal.BODY_RECOMPOSITION,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=18,
            training_days_per_week=4,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.GLUTES,
            training_cautions=[TrainingCaution.KNEE],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.MODERATE,
        ),
        # Profile 4: Male, Advanced, 5 days, 75 min, Gym, Strength, Back priority
        ProfileSpec(
            index=4,
            name="امیرحسین مرادی (پروفایل ۴)",
            sex=Sex.MALE,
            birth_date=date(1991, 11, 5),
            age=35,
            height_cm=183,
            weight_kg=88.0,
            fitness_goal=FitnessGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=60,
            training_days_per_week=5,
            session_duration_minutes=75,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.BACK,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 5: Female, Beginner, 3 days, 30 min (short session), Home Dumbbells, General Fitness
        ProfileSpec(
            index=5,
            name="زهرا حسینی (پروفایل ۵)",
            sex=Sex.FEMALE,
            birth_date=date(1999, 9, 12),
            age=27,
            height_cm=160,
            weight_kg=55.0,
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
            experience_level=ExperienceLevel.BEGINNER,
            training_age_months=3,
            training_days_per_week=3,
            session_duration_minutes=30,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            priority_muscle=None,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 6: Male, Intermediate, 6 days (high freq), 90 min (long session), Gym, Hypertrophy, Shoulders priority
        ProfileSpec(
            index=6,
            name="پویا نظری (پروفایل ۶)",
            sex=Sex.MALE,
            birth_date=date(1996, 5, 25),
            age=30,
            height_cm=180,
            weight_kg=82.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=24,
            training_days_per_week=6,
            session_duration_minutes=90,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.SHOULDERS,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 7: Female, Advanced, 4 days, 75 min, Gym, Build Muscle, Quadriceps priority, Lower back caution
        ProfileSpec(
            index=7,
            name="نیلوفر سعیدی (پروفایل ۷)",
            sex=Sex.FEMALE,
            birth_date=date(1990, 8, 14),
            age=36,
            height_cm=170,
            weight_kg=65.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=48,
            training_days_per_week=4,
            session_duration_minutes=75,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.QUADRICEPS,
            training_cautions=[TrainingCaution.LOWER_BACK],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 8: Male, First Month, 3 days, 45 min, Gym, Fat Loss, No priority, Knee + Shoulder cautions
        ProfileSpec(
            index=8,
            name="مهدی رستمی (پروفایل ۸)",
            sex=Sex.MALE,
            birth_date=date(1985, 3, 30),
            age=41,
            height_cm=175,
            weight_kg=92.0,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_age_months=0,
            training_days_per_week=3,
            session_duration_minutes=45,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=None,
            training_cautions=[TrainingCaution.KNEE, TrainingCaution.SHOULDER],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.POOR,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.HIGH,
        ),
        # Profile 9: Female, Intermediate, 5 days, 45 min, Gym, Fat Loss, Hamstrings priority
        ProfileSpec(
            index=9,
            name="الهام شریفی (پروفایل ۹)",
            sex=Sex.FEMALE,
            birth_date=date(1997, 1, 18),
            age=29,
            height_cm=166,
            weight_kg=59.0,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=15,
            training_days_per_week=5,
            session_duration_minutes=45,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.HAMSTRINGS,
            training_cautions=[],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 10: Male, Advanced, 6 days, 60 min, Gym, Hypertrophy, Biceps priority, Wrist caution
        ProfileSpec(
            index=10,
            name="سینا باقری (پروفایل ۱۰)",
            sex=Sex.MALE,
            birth_date=date(1993, 6, 22),
            age=33,
            height_cm=179,
            weight_kg=78.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=72,
            training_days_per_week=6,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.BICEPS,
            training_cautions=[TrainingCaution.WRIST],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 11: Female, Beginner, 2 days, 60 min, Home Dumbbells, Recomposition, Glutes priority
        ProfileSpec(
            index=11,
            name="فرشته طاهری (پروفایل ۱۱)",
            sex=Sex.FEMALE,
            birth_date=date(1995, 10, 8),
            age=31,
            height_cm=162,
            weight_kg=57.5,
            fitness_goal=FitnessGoal.BODY_RECOMPOSITION,
            experience_level=ExperienceLevel.BEGINNER,
            training_age_months=5,
            training_days_per_week=2,
            session_duration_minutes=60,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            priority_muscle=MuscleGroup.GLUTES,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 12: Male, Beginner, 4 days, 45 min, Gym, Strength, Triceps priority
        ProfileSpec(
            index=12,
            name="رضا کریمی (پروفایل ۱۲)",
            sex=Sex.MALE,
            birth_date=date(2001, 12, 3),
            age=25,
            height_cm=185,
            weight_kg=76.0,
            fitness_goal=FitnessGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
            training_age_months=6,
            training_days_per_week=4,
            session_duration_minutes=45,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.TRICEPS,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.MODERATE,
        ),
        # Profile 13: Female, First Month, 3 days, 60 min, Home Bodyweight, General Fitness, Neck caution
        ProfileSpec(
            index=13,
            name="سمیرا نوری (پروفایل ۱۳)",
            sex=Sex.FEMALE,
            birth_date=date(1988, 7, 19),
            age=38,
            height_cm=158,
            weight_kg=60.0,
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_age_months=0,
            training_days_per_week=3,
            session_duration_minutes=60,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            priority_muscle=None,
            training_cautions=[TrainingCaution.NECK],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.POOR,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 14: Male, Intermediate, 3 days, 90 min (long sessions), Gym, Build Muscle, Chest priority
        ProfileSpec(
            index=14,
            name="نوید صبوری (پروفایل ۱۴)",
            sex=Sex.MALE,
            birth_date=date(1992, 4, 11),
            age=34,
            height_cm=176,
            weight_kg=80.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=20,
            training_days_per_week=3,
            session_duration_minutes=90,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.CHEST,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 15: Female, Advanced, 3 days, 60 min, Gym, Strength, Back priority
        ProfileSpec(
            index=15,
            name="بهاره محمودی (پروفایل ۱۵)",
            sex=Sex.FEMALE,
            birth_date=date(1989, 9, 27),
            age=37,
            height_cm=172,
            weight_kg=68.0,
            fitness_goal=FitnessGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=54,
            training_days_per_week=3,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.BACK,
            training_cautions=[],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 16: Male, Advanced, 5 days, 60 min, Gym, Fat Loss, Calves priority, Lower back caution
        ProfileSpec(
            index=16,
            name="فرهاد سلطانی (پروفایل ۱۶)",
            sex=Sex.MALE,
            birth_date=date(1986, 12, 15),
            age=40,
            height_cm=181,
            weight_kg=86.0,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=84,
            training_days_per_week=5,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.CALVES,
            training_cautions=[TrainingCaution.LOWER_BACK],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.MODERATE,
        ),
        # Profile 17: Female, Intermediate, 4 days, 30 min (very tight duration), Gym, Recomposition, Shoulders priority
        ProfileSpec(
            index=17,
            name="مینا اسدی (پروفایل ۱۷)",
            sex=Sex.FEMALE,
            birth_date=date(1996, 3, 8),
            age=30,
            height_cm=165,
            weight_kg=61.0,
            fitness_goal=FitnessGoal.BODY_RECOMPOSITION,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=22,
            training_days_per_week=4,
            session_duration_minutes=30,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.SHOULDERS,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 18: Male, First Month, 4 days, 75 min (long for first month), Home Bodyweight, Fat Loss
        ProfileSpec(
            index=18,
            name="کامران کیانی (پروفایل ۱۸)",
            sex=Sex.MALE,
            birth_date=date(1997, 8, 29),
            age=29,
            height_cm=177,
            weight_kg=85.0,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_age_months=0,
            training_days_per_week=4,
            session_duration_minutes=75,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            priority_muscle=None,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.POOR,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 19: Female, Intermediate, 2 days, 75 min, Gym, General Fitness, Glutes priority, Knee + Shoulder cautions
        ProfileSpec(
            index=19,
            name="پروانه زمانی (پروفایل ۱۹)",
            sex=Sex.FEMALE,
            birth_date=date(1991, 5, 17),
            age=35,
            height_cm=167,
            weight_kg=64.0,
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=16,
            training_days_per_week=2,
            session_duration_minutes=75,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.GLUTES,
            training_cautions=[TrainingCaution.KNEE, TrainingCaution.SHOULDER],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 20: Male, Advanced, 6 days, 75 min, Gym, Build Muscle, Quadriceps priority
        ProfileSpec(
            index=20,
            name="داریوش قاسم‌پور (پروفایل ۲۰)",
            sex=Sex.MALE,
            birth_date=date(1990, 10, 31),
            age=36,
            height_cm=182,
            weight_kg=84.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=96,
            training_days_per_week=6,
            session_duration_minutes=75,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.QUADRICEPS,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 21: Male, Intermediate, 4 days, 60 min, Gym, Strength, Chest priority
        ProfileSpec(
            index=21,
            name="کسری ابراهیمی (پروفایل ۲۱)",
            sex=Sex.MALE,
            birth_date=date(1995, 3, 14),
            age=31,
            height_cm=180,
            weight_kg=79.0,
            fitness_goal=FitnessGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=20,
            training_days_per_week=4,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.CHEST,
            training_cautions=[],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 22: Female, Beginner, 3 days, 45 min, Home Dumbbells, Fat Loss, Glutes priority
        ProfileSpec(
            index=22,
            name="سوگند فراهانی (پروفایل ۲۲)",
            sex=Sex.FEMALE,
            birth_date=date(1998, 11, 23),
            age=27,
            height_cm=163,
            weight_kg=58.0,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.BEGINNER,
            training_age_months=4,
            training_days_per_week=3,
            session_duration_minutes=45,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            priority_muscle=MuscleGroup.GLUTES,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 23: Male, Advanced, 5 days, 90 min, Gym, Hypertrophy, Back priority
        ProfileSpec(
            index=23,
            name="سهراب یوسفی (پروفایل ۲۳)",
            sex=Sex.MALE,
            birth_date=date(1989, 4, 18),
            age=37,
            height_cm=186,
            weight_kg=90.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=60,
            training_days_per_week=5,
            session_duration_minutes=90,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.BACK,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 24: Female, Advanced, 4 days, 60 min, Gym, Recomposition, Shoulders priority, Knee caution
        ProfileSpec(
            index=24,
            name="طناز راد (پروفایل ۲۴)",
            sex=Sex.FEMALE,
            birth_date=date(1992, 8, 9),
            age=34,
            height_cm=169,
            weight_kg=62.0,
            fitness_goal=FitnessGoal.BODY_RECOMPOSITION,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=42,
            training_days_per_week=4,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.SHOULDERS,
            training_cautions=[TrainingCaution.KNEE],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.MODERATE,
        ),
        # Profile 25: Male, First Month, 2 days, 30 min, Gym, General Fitness
        ProfileSpec(
            index=25,
            name="کیوان جلالی (پروفایل ۲۵)",
            sex=Sex.MALE,
            birth_date=date(2002, 6, 25),
            age=24,
            height_cm=174,
            weight_kg=71.0,
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_age_months=0,
            training_days_per_week=2,
            session_duration_minutes=30,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=None,
            training_cautions=[],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 26: Female, Intermediate, 3 days, 75 min, Gym, Hypertrophy, Hamstrings priority
        ProfileSpec(
            index=26,
            name="یاسمین فتوحی (پروفایل ۲۶)",
            sex=Sex.FEMALE,
            birth_date=date(1996, 12, 1),
            age=29,
            height_cm=171,
            weight_kg=66.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=18,
            training_days_per_week=3,
            session_duration_minutes=75,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.HAMSTRINGS,
            training_cautions=[],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 27: Male, Intermediate, 5 days, 60 min, Gym, Build Muscle, Biceps priority
        ProfileSpec(
            index=27,
            name="شایان معتمدی (پروفایل ۲۷)",
            sex=Sex.MALE,
            birth_date=date(1994, 9, 15),
            age=32,
            height_cm=181,
            weight_kg=83.0,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=28,
            training_days_per_week=5,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.BICEPS,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 28: Female, First Month, 3 days, 45 min, Home Dumbbells, General Fitness, Lower back caution
        ProfileSpec(
            index=28,
            name="آیدا صادقی (پروفایل ۲۸)",
            sex=Sex.FEMALE,
            birth_date=date(1991, 1, 30),
            age=35,
            height_cm=159,
            weight_kg=56.0,
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_age_months=0,
            training_days_per_week=3,
            session_duration_minutes=45,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            priority_muscle=None,
            training_cautions=[TrainingCaution.LOWER_BACK],
            plan_duration_weeks=4,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 29: Male, Advanced, 6 days, 60 min, Gym, Strength, Triceps priority
        ProfileSpec(
            index=29,
            name="مانی داوودی (پروفایل ۲۹)",
            sex=Sex.MALE,
            birth_date=date(1987, 7, 7),
            age=39,
            height_cm=178,
            weight_kg=81.0,
            fitness_goal=FitnessGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            training_age_months=80,
            training_days_per_week=6,
            session_duration_minutes=60,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.TRICEPS,
            training_cautions=[],
            plan_duration_weeks=8,
            sleep_quality=RecoveryRating.GOOD,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
        # Profile 30: Female, Intermediate, 4 days, 45 min, Gym, Fat Loss, Quadriceps priority
        ProfileSpec(
            index=30,
            name="شیدا رستگار (پروفایل ۳۰)",
            sex=Sex.FEMALE,
            birth_date=date(1997, 5, 21),
            age=29,
            height_cm=167,
            weight_kg=60.5,
            fitness_goal=FitnessGoal.FAT_LOSS,
            experience_level=ExperienceLevel.INTERMEDIATE,
            training_age_months=14,
            training_days_per_week=4,
            session_duration_minutes=45,
            training_location=TrainingLocation.GYM,
            home_training_setup=None,
            priority_muscle=MuscleGroup.QUADRICEPS,
            training_cautions=[],
            plan_duration_weeks=6,
            sleep_quality=RecoveryRating.AVERAGE,
            stress_level=RecoveryRating.AVERAGE,
            physical_job_demand=PhysicalJobDemand.LOW,
        ),
    ]


from app.workouts.program_engine.equipment import resolve_available_equipment

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
        seed_optional=20260829 + spec.index,
    )
    return req


def analyze_failure(result: Any, request: ProgramGenerationRequest) -> dict[str, Any]:
    error_code = result.error_code.value if result.error_code else "UNKNOWN_ERROR"
    errors = list(result.errors)
    trace = result.decision_trace or ()

    root_cause = "UNSATISFIED_CONSTRAINT"
    secondary_causes: list[str] = []
    rule_file = "app/workouts/program_engine/engine.py"
    rule_func = "generate_program()"
    actual_val = "N/A"
    limit_val = "N/A"
    failing_phase = "construction_recovery"

    construction_recovery = None
    template_rejections = []
    for step in trace:
        stage = step.get("stage")
        if stage == "template_reference" and step.get("status") == "rejected":
            template_rejections.append(step)
        elif stage == "construction_recovery":
            construction_recovery = step
        elif stage == "safety" and step.get("status") not in ("clear", "clear_with_modifications"):
            root_cause = "PROGRAM_REJECTED_SAFETY_STATUS"
            rule_file = "app/workouts/program_engine/safety.py"
            rule_func = "screen_safety()"
            actual_val = step.get("status")
            limit_val = "CLEAR / CLEAR_WITH_MODIFICATIONS"
            failing_phase = "safety_screening"
        elif stage == "eligibility" and step.get("eligible_count", 0) == 0:
            root_cause = "INSUFFICIENT_ELIGIBLE_EXERCISES"
            rule_file = "app/workouts/program_engine/eligibility.py"
            rule_func = "filter_eligible_exercises()"
            actual_val = "0 eligible exercises"
            limit_val = "> 0 eligible exercises"
            failing_phase = "exercise_eligibility"

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
            else:
                root_cause = "SESSION_DURATION_EXCEEDED"
                actual_val = f"> {duration_policy.maximum_minutes} دقیقه"
                limit_val = f"{duration_policy.minimum_minutes}–{duration_policy.maximum_minutes} دقیقه"
            rule_file = "app/workouts/program_engine/validation.py / session_duration.py"
            rule_func = "validate_program() / repair_session_durations()"
            failing_phase = "session_duration_repair_and_validation"
        elif "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" in collected_reasons:
            root_cause = "PER_SESSION_MUSCLE_VOLUME_EXCEEDED"
            cap = session_hard_volume_cap(request.training_age_months)
            actual_val = f"> {cap} ست در هر عضله/جلسه"
            limit_val = f"حداکثر {cap} ست مستقیم"
            rule_file = "app/workouts/program_engine/validation.py"
            rule_func = "validate_program()"
            failing_phase = "session_volume_validation"
        elif "NO_SAFE_EXERCISE_FOR_PATTERN" in collected_reasons or any("NO_SAFE_EXERCISE" in str(r) for r in collected_reasons):
            root_cause = "NO_SAFE_EXERCISE_FOR_PATTERN"
            actual_val = "تداخل محدودیت تجهیزات یا احتیاط‌های پزشکی با الگوی حرکتی الزامی"
            limit_val = "وجود حداقل ۱ حرکت ایمن و قابل‌اجرا"
            rule_file = "app/workouts/program_engine/session_builder.py"
            rule_func = "build_sessions()"
            failing_phase = "session_construction"
        elif "REQUESTED_TRAINING_DAYS_UNSATISFIED" in collected_reasons:
            root_cause = "REQUESTED_TRAINING_DAYS_UNSATISFIED"
            actual_val = f"عدم امکان چینش ساختار {request.available_training_days} روزه با شرایط ورودی"
            limit_val = f"{request.available_training_days} روز در هفته"
            rule_file = "app/workouts/program_engine/split_selector.py"
            rule_func = "rank_split_candidates()"
            failing_phase = "split_selection"
        else:
            non_generic = [r for r in collected_reasons if r not in ("PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED", "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED", "UNSATISFIED_CONSTRAINT")]
            if non_generic:
                root_cause = non_generic[0]
                rule_file = "app/workouts/program_engine/validation.py"
                rule_func = "validate_program()"
                actual_val = root_cause
                limit_val = "تطابق با محدودیت"
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
        "decision_trace_summary": [
            {"stage": s.get("stage"), "status": s.get("status"), "reasons": s.get("reason_codes") or s.get("reasons")}
            for s in trace if isinstance(s, dict)
        ],
    }


def main() -> None:
    print("Initializing Fitsho 20-Profile Test...")
    settings = get_settings()
    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        exercises_list = session.scalars(select(Exercise)).all()
        exercise_map = {ex.id: ex for ex in exercises_list}

        service = WorkoutGenerationService(session, settings=None)
        catalog = service._load_catalog()
        references = load_template_references(session)
        print(f"Loaded {len(catalog)} exercise candidates and {len(references)} template references.")

        profiles = define_20_diverse_profiles()
        results = []

        for p in profiles:
            user_uuid = uuid4()
            req = profile_to_request(p, user_uuid)
            print(f"Testing Profile #{p.index}: {p.name} ({p.sex.value}, {p.experience_level.value}, {p.training_days_per_week}d, {p.session_duration_minutes}m, {p.training_location.value})...")

            try:
                gen_result = generate_program(
                    req,
                    catalog,
                    RULESET,
                    reference_templates=references,
                )
            except Exception as e:
                print(f"  Exception during generation: {e}")
                gen_result = None

            if gen_result and gen_result.is_success and gen_result.program:
                prog: WorkoutProgram = gen_result.program
                days_data = []
                for day in prog.weekly_schedule:
                    main_mins = calculate_main_training_minutes(day)
                    ex_list = []
                    for it in day.exercises:
                        ex_db = exercise_map.get(it.exercise_id)
                        name_fa = ex_db.name_fa if ex_db else it.name
                        name_en = ex_db.name_en if ex_db else it.name
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
                    "request": req,
                    "status": "SUCCESS",
                    "split": prog.split.split_type.value,
                    "split_fa": FA_TRANSLATIONS.get(prog.split.split_type.value, prog.split.split_type.value),
                    "days_count": len(prog.weekly_schedule),
                    "target_duration_minutes": p.session_duration_minutes,
                    "days": days_data,
                    "weekly_direct_volume": direct_vol,
                    "weekly_effective_volume": effective_vol,
                    "warnings": list(prog.warnings),
                    "final_gate_status": gate_status,
                    "failure_info": None,
                })
                print(f"  -> SUCCESS (Split: {prog.split.split_type.value}, Days: {len(prog.weekly_schedule)}, Gate: {gate_status})")
            else:
                failure_info = analyze_failure(gen_result, req) if gen_result else {
                    "final_error_code": "CRASH_EXCEPTION",
                    "all_errors": ["ENGINE_EXCEPTION"],
                    "root_cause": "ENGINE_EXCEPTION",
                    "secondary_causes": [],
                    "rule_file": "engine.py",
                    "rule_func": "generate_program()",
                    "actual_val": "Crash",
                    "limit_val": "Clean execution",
                    "failing_phase": "exception",
                    "decision_trace_summary": [],
                }
                results.append({
                    "profile": p,
                    "request": req,
                    "status": "FAILED",
                    "split": None,
                    "split_fa": None,
                    "days_count": 0,
                    "target_duration_minutes": p.session_duration_minutes,
                    "days": [],
                    "weekly_direct_volume": {},
                    "weekly_effective_volume": {},
                    "warnings": [],
                    "final_gate_status": "rejected",
                    "failure_info": failure_info,
                })
                print(f"  -> FAILED (Root cause: {failure_info['root_cause']})")

        os.makedirs("var/reports", exist_ok=True)
        with open("var/reports/20_profiles_debug_data.json", "w", encoding="utf-8") as f:
            serializable_results = []
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

                r_copy = dict(r)
                r_copy["profile"] = p_dict
                r_copy.pop("request", None)
                serializable_results.append(r_copy)
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)

        generate_pdf_report(results, "fitsho_20_random_profiles_debug_report.pdf")


def generate_pdf_report(results: list[dict[str, Any]], output_pdf_path: str) -> None:
    print(f"Generating Persian PDF report: {output_pdf_path}...")
    total = len(results)
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    failure_count = total - success_count
    success_rate = (success_count / total) * 100 if total > 0 else 0

    failures_by_code: dict[str, int] = {}
    failed_rules_counter: dict[str, int] = {}
    error_combinations: dict[str, int] = {}
    blocking_constraints_counter: dict[str, int] = {}

    for r in results:
        if r["status"] == "FAILED" and r["failure_info"]:
            code = r["failure_info"]["final_error_code"]
            failures_by_code[code] = failures_by_code.get(code, 0) + 1

            root = r["failure_info"]["root_cause"]
            failed_rules_counter[root] = failed_rules_counter.get(root, 0) + 1
            blocking_constraints_counter[root] = blocking_constraints_counter.get(root, 0) + 1

            combo = f"{root} + " + " & ".join(r["failure_info"]["secondary_causes"][:2]) if r["failure_info"]["secondary_causes"] else root
            error_combinations[combo] = error_combinations.get(combo, 0) + 1

    top_failed_rules = sorted(failed_rules_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    top_combos = sorted(error_combinations.items(), key=lambda x: x[1], reverse=True)[:5]
    top_blockers = sorted(blocking_constraints_counter.items(), key=lambda x: x[1], reverse=True)[:5]

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش جامع تست و دیباگ موتور برنامه تمرینی Fitsho</title>
<style>
@page {{
    size: A4 portrait;
    margin: 12mm 10mm 15mm 10mm;
    @bottom-right {{
        content: "صفحه " counter(page) " از " counter(pages);
        font-family: 'Noto Sans Arabic', sans-serif;
        font-size: 8pt;
        color: #64748b;
    }}
    @bottom-left {{
        content: "Fitsho Deterministic Workout Program Engine - 20 Profile Evaluation";
        font-family: sans-serif;
        font-size: 8pt;
        color: #94a3b8;
    }}
}}

body {{
    font-family: 'Noto Sans Arabic', 'Noto Kufi Arabic', sans-serif;
    font-size: 8.5pt;
    line-height: 1.45;
    color: #0f172a;
    direction: rtl;
}}

.header {{
    text-align: center;
    border-bottom: 2px solid #2563eb;
    padding-bottom: 8px;
    margin-bottom: 12px;
}}
.header h1 {{
    font-size: 16pt;
    margin: 0 0 4px 0;
    color: #1e3a8a;
}}
.header p {{
    margin: 0;
    font-size: 9pt;
    color: #475569;
}}

.stat-grid {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 14px;
    gap: 8px;
}}
.stat-card {{
    flex: 1;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px;
    text-align: center;
}}
.stat-card .val {{
    font-size: 14pt;
    font-weight: bold;
    color: #1e40af;
}}
.stat-card .lbl {{
    font-size: 7.5pt;
    color: #64748b;
}}

.badge-success {{
    background-color: #dcfce7;
    color: #166534;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 8pt;
    display: inline-block;
}}
.badge-fail {{
    background-color: #fee2e2;
    color: #991b1b;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 8pt;
    display: inline-block;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10px;
    font-size: 8pt;
}}
th, td {{
    border: 1px solid #cbd5e1;
    padding: 4px 6px;
    text-align: right;
}}
th {{
    background-color: #f1f5f9;
    color: #334155;
    font-weight: bold;
}}
tr:nth-child(even) {{
    background-color: #f8fafc;
}}

.profile-card {{
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px;
    margin-bottom: 12px;
    page-break-inside: avoid;
    background: #ffffff;
}}
.profile-card.success-card {{
    border-right: 4px solid #16a34a;
}}
.profile-card.fail-card {{
    border-right: 4px solid #dc2626;
}}

.profile-header {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin-bottom: 6px;
}}
.profile-title {{
    font-weight: bold;
    font-size: 10pt;
    color: #1e293b;
}}

.info-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
    font-size: 7.5pt;
    background: #f8fafc;
    padding: 6px;
    border-radius: 4px;
    margin-bottom: 6px;
}}
.info-item span.lbl {{
    color: #64748b;
}}
.info-item span.val {{
    font-weight: bold;
    color: #0f172a;
}}

.day-box {{
    background: #fafafa;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 5px;
    margin-top: 5px;
    margin-bottom: 5px;
}}
.day-title {{
    font-size: 8.5pt;
    font-weight: bold;
    color: #334155;
    margin-bottom: 4px;
}}

.fail-box {{
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 5px;
    padding: 8px;
    margin-top: 6px;
}}
.fail-box .title {{
    font-weight: bold;
    color: #991b1b;
    font-size: 9pt;
    margin-bottom: 4px;
}}
.fail-item {{
    margin-bottom: 3px;
    font-size: 8pt;
}}
.fail-label {{
    color: #7f1d1d;
    font-weight: bold;
}}

.page-break {{
    page-break-before: always;
}}
</style>
</head>
<body>

<div class="header">
    <h1>گزارش ارزیابی و دیباگ موتور برنامه تمرینی Fitsho</h1>
    <p>بررسی عملکرد موتور قطعی (Deterministic Engine) روی {total} پروفایل متنوع و واقعی | تاریخ تست: ۱۴۰۵/۰۶/۰۸ (2026-08-30)</p>
</div>

<div class="stat-grid">
    <div class="stat-card">
        <div class="val">{total}</div>
        <div class="lbl">کل پروفایل‌ها</div>
    </div>
    <div class="stat-card">
        <div class="val" style="color: #166534;">{success_count}</div>
        <div class="lbl">تولید موفق (Success)</div>
    </div>
    <div class="stat-card">
        <div class="val" style="color: #991b1b;">{failure_count}</div>
        <div class="lbl">توقف با خطا (Failure)</div>
    </div>
    <div class="stat-card">
        <div class="val">{success_rate:.1f}٪</div>
        <div class="lbl">نرخ موفقیت (Success Rate)</div>
    </div>
</div>

<h2 style="font-size: 11pt; color: #1e3a8a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-top: 10px;">خلاصه وضعیت خطاها و قوانین مسدودکننده (Failure Analytics)</h2>

<div style="display: flex; gap: 10px; margin-bottom: 12px;">
    <div style="flex: 1;">
        <h3 style="font-size: 9pt; color: #334155; margin-bottom: 4px;">توزیع بر اساس Error Code:</h3>
        <table>
            <thead><tr><th>کد خطا</th><th>تعداد</th></tr></thead>
            <tbody>
                {"".join(f"<tr><td><code>{k}</code></td><td style='text-align: center; font-weight: bold;'>{v}</td></tr>" for k, v in failures_by_code.items()) if failures_by_code else "<tr><td colspan='2'>هیچ خطایی ثبت نشد</td></tr>"}
            </tbody>
        </table>
    </div>
    <div style="flex: 1;">
        <h3 style="font-size: 9pt; color: #334155; margin-bottom: 4px;">پرتکرارترین قوانین Fail شده (Top Root Causes):</h3>
        <table>
            <thead><tr><th>نام قانون / Constraint</th><th>تعداد</th></tr></thead>
            <tbody>
                {"".join(f"<tr><td><code>{k}</code></td><td style='text-align: center; font-weight: bold;'>{v}</td></tr>" for k, v in top_failed_rules) if top_failed_rules else "<tr><td colspan='2'>-</td></tr>"}
            </tbody>
        </table>
    </div>
</div>

<h3 style="font-size: 9pt; color: #334155; margin-bottom: 4px;">جدول خلاصه دیباگ همه ۲۰ پروفایل (Debug Summary Table):</h3>
<table>
    <thead>
        <tr>
            <th style="width: 5%;">#</th>
            <th style="width: 14%;">نام پروفایل</th>
            <th style="width: 10%;">نتیجه</th>
            <th style="width: 25%;">علت اصلی (Root Cause)</th>
            <th style="width: 20%;">علل ثانویه (Secondary)</th>
            <th style="width: 16%;">فایل و تابع ناظر</th>
            <th style="width: 10%;">مقدار واقعی / حد مجاز</th>
        </tr>
    </thead>
    <tbody>
"""

    for r in results:
        p = r["profile"]
        res_badge = '<span class="badge-success">موفق</span>' if r["status"] == "SUCCESS" else '<span class="badge-fail">ناموفق</span>'
        if r["status"] == "SUCCESS":
            root_text = f"ساخت موفق: {r['split_fa']} ({r['days_count']} روزه)"
            sec_text = f"گیت نهایی: {r['final_gate_status']}"
            rule_text = "engine.py: generate_program()"
            val_text = f"{r['target_duration_minutes']} دقیقه"
        else:
            f_info = r["failure_info"]
            root_text = f"<code>{f_info['root_cause']}</code>"
            sec_text = ", ".join(f"<code>{s}</code>" for s in f_info["secondary_causes"][:2]) or "-"
            rule_text = f"<code>{f_info['rule_file'].split('/')[-1]}</code>"
            val_text = f"واقعی: {f_info['actual_val']}<br>مجاز: {f_info['limit_val']}"

        html += f"""
        <tr>
            <td style="text-align: center; font-weight: bold;">{p.index}</td>
            <td>{p.name}</td>
            <td style="text-align: center;">{res_badge}</td>
            <td>{root_text}</td>
            <td>{sec_text}</td>
            <td>{rule_text}</td>
            <td style="font-size: 7pt;">{val_text}</td>
        </tr>
        """

    html += """
    </tbody>
</table>

<div class="page-break"></div>
<h2 style="font-size: 13pt; color: #1e3a8a; border-bottom: 2px solid #2563eb; padding-bottom: 4px; margin-bottom: 12px;">جزئیات کامل و گزارش تک‌تک ۲۰ پروفایل</h2>
"""

    for r in results:
        p = r["profile"]
        is_succ = (r["status"] == "SUCCESS")
        card_class = "success-card" if is_succ else "fail-card"
        res_badge = '<span class="badge-success">موفق (SUCCESS)</span>' if is_succ else '<span class="badge-fail">ناموفق (FAILED)</span>'

        cautions_str = ", ".join(FA_TRANSLATIONS.get(c.value, c.value) for c in p.training_cautions) if p.training_cautions else "بدون محدودیت (سالم)"
        priority_str = FA_TRANSLATIONS.get(p.priority_muscle.value, p.priority_muscle.value) if p.priority_muscle else "ندارد (تعادل کل بدن)"
        loc_str = f"{FA_TRANSLATIONS.get(p.training_location.value, p.training_location.value)}"
        if p.home_training_setup:
            loc_str += f" - {FA_TRANSLATIONS.get(p.home_training_setup.value, p.home_training_setup.value)}"

        html += f"""
        <div class="profile-card {card_class}">
            <div class="profile-header">
                <div class="profile-title">پروفایل #{p.index}: {p.name}</div>
                <div>{res_badge}</div>
            </div>
            
            <div class="info-grid">
                <div class="info-item"><span class="lbl">جنسیت / سن:</span> <span class="val">{FA_TRANSLATIONS.get(p.sex.value, p.sex.value)} / {p.age} سال</span></div>
                <div class="info-item"><span class="lbl">قد / وزن:</span> <span class="val">{p.height_cm}cm / {p.weight_kg}kg</span></div>
                <div class="info-item"><span class="lbl">سطح تجربه:</span> <span class="val">{FA_TRANSLATIONS.get(p.experience_level.value, p.experience_level.value)} ({p.training_age_months} ماه)</span></div>
                <div class="info-item"><span class="lbl">هدف تمرینی:</span> <span class="val">{FA_TRANSLATIONS.get(p.fitness_goal.value, p.fitness_goal.value)}</span></div>
                <div class="info-item"><span class="lbl">روزهای تمرین:</span> <span class="val">{p.training_days_per_week} روز در هفته</span></div>
                <div class="info-item"><span class="lbl">مدت جلسه:</span> <span class="val">{p.session_duration_minutes} دقیقه</span></div>
                <div class="info-item"><span class="lbl">محل تمرین:</span> <span class="val">{loc_str}</span></div>
                <div class="info-item"><span class="lbl">اولویت عضلانی:</span> <span class="val">{priority_str}</span></div>
                <div class="info-item" style="grid-column: span 2;"><span class="lbl">محدودیت‌ها / احتیاط‌ها:</span> <span class="val">{cautions_str}</span></div>
                <div class="info-item" style="grid-column: span 2;"><span class="lbl">ریکاوری / خواب / استرس:</span> <span class="val">خواب: {p.sleep_quality.value} | استرس: {p.stress_level.value} | کار: {p.physical_job_demand.value}</span></div>
            </div>
        """

        if is_succ:
            vol_str = ", ".join(f"{FA_TRANSLATIONS.get(m, m)}: {s} ست" for m, s in r["weekly_direct_volume"].items() if s > 0)
            warns_str = ", ".join(f"<code>{w}</code>" for w in r["warnings"]) if r["warnings"] else "بدون اخطار"

            html += f"""
            <div style="font-size: 8pt; margin-bottom: 6px; background: #ecfdf5; padding: 6px; border-radius: 4px; border: 1px solid #a7f3d0;">
                <div><strong>اسپلیت انتخاب‌شده:</strong> {r['split_fa']} ({r['split']}) | <strong>تعداد روز:</strong> {r['days_count']} روز | <strong>وضعیت گیت نهایی:</strong> <code>{r['final_gate_status']}</code></div>
                <div style="margin-top: 2px;"><strong>حجم هفتگی مستقیم:</strong> {vol_str}</div>
                <div style="margin-top: 2px;"><strong>اخطارها و Constraints:</strong> {warns_str}</div>
            </div>
            """

            for day in r["days"]:
                html += f"""
                <div class="day-box">
                    <div class="day-title">جلسه {day['day_index']}: {day['title']} (تمرکز: {day['focus']}) — مدت کل: {day['estimated_duration_minutes']} دقیقه (مقاومتی خالص: {day['main_training_minutes']:.1f} دقیقه)</div>
                    <table style="margin-bottom: 0;">
                        <thead>
                            <tr>
                                <th style="width: 6%; text-align: center;">ترتیب</th>
                                <th style="width: 34%;">نام حرکت (فارسی)</th>
                                <th style="width: 25%;">نام انگلیسی</th>
                                <th style="width: 10%; text-align: center;">ست</th>
                                <th style="width: 15%; text-align: center;">تکرار / زمان</th>
                                <th style="width: 10%; text-align: center;">استراحت</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                for ex in day["exercises"]:
                    reps_txt = f"{ex['rep_min']}–{ex['rep_max']}" if ex['rep_min'] else "-"
                    html += f"""
                            <tr>
                                <td style="text-align: center; font-weight: bold;">{ex['order']}</td>
                                <td style="font-weight: bold; color: #1e3a8a;">{ex['name_fa']}</td>
                                <td style="color: #475569; font-size: 7pt;">{ex['name_en']}</td>
                                <td style="text-align: center;">{ex['sets']} ست</td>
                                <td style="text-align: center;">{reps_txt} (RIR: {ex['rir'] if ex['rir'] is not None else '-'})</td>
                                <td style="text-align: center;">{ex['rest_seconds']}s</td>
                            </tr>
                    """
                html += """
                        </tbody>
                    </table>
                </div>
                """
        else:
            fi = r["failure_info"]
            all_errs = ", ".join(f"<code>{e}</code>" for e in fi["all_errors"])
            sec_causes = ", ".join(f"<code>{s}</code>" for s in fi["secondary_causes"]) if fi["secondary_causes"] else "ندارد"

            html += f"""
            <div class="fail-box">
                <div class="title">گزارش علت توقف تولید برنامه (Failure Diagnostics):</div>
                <div class="fail-item"><span class="fail-label">کد خطای نهایی (Final Error Code):</span> <code>{fi['final_error_code']}</code></div>
                <div class="fail-item"><span class="fail-label">علت ریشه‌ای (Root Cause):</span> <strong style="color: #b91c1c; font-size: 9pt;"><code>{fi['root_cause']}</code></strong></div>
                <div class="fail-item"><span class="fail-label">موانع و خطاهای ثانویه (Secondary Blockers):</span> {sec_causes}</div>
                <div class="fail-item"><span class="fail-label">تمام خطاهای تجمیعی (Result Errors):</span> {all_errs}</div>
                <div class="fail-item"><span class="fail-label">اولین مرحله شکست (First Failing Phase):</span> <code>{fi['failing_phase']}</code></div>
                <div class="fail-item"><span class="fail-label">قانون و فایل ناظر:</span> <code>{fi['rule_file']}</code> -> <code>{fi['rule_func']}</code></div>
                <div class="fail-item"><span class="fail-label">مقدار ثبت‌شده (Actual):</span> {fi['actual_val']}</div>
                <div class="fail-item"><span class="fail-label">محدوده مجاز (Allowed/Hard Limit):</span> {fi['limit_val']}</div>
            </div>
            """

        html += "</div>"

    html += """
</body>
</html>
"""

    weasyprint.HTML(string=html).write_pdf(output_pdf_path)
    print(f"PDF generated successfully at: {output_pdf_path}")


if __name__ == "__main__":
    main()
