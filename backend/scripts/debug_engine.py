import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import get_settings
import app.main
from app.auth.models import User
from app.profile.models import UserProfile, BodyMeasurement, UserProfileTrainingCaution
from app.profile.enums import (ExperienceLevel, FitnessGoal, TrainingLocation, HomeTrainingSetup, TrainingIntensity, Sex, WorkoutGenerationMethod, TrainingCaution, ProductMode)
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings

p = {
    "name": "دانیال نوری",
    "sex": Sex.MALE,
    "birth_date": date(1996, 8, 22),
    "height_cm": 182,
    "weight_kg": Decimal("84.0"),
    "goal": FitnessGoal.BUILD_MUSCLE,
    "level": ExperienceLevel.INTERMEDIATE,
    "training_age_months": 24,
    "days": 4,
    "location": TrainingLocation.GYM,
    "home_setup": None,
    "cautions": [],
    "duration": 75,
    "plan_weeks": 8,
}

engine_db = create_engine(get_settings().database_url)
conn = engine_db.connect()
db = Session(bind=conn)

service = WorkoutGenerationService(db, settings=WorkoutGenerationSettings(
    provider_name='fitsho_domain', model_id='program_engine_v1', prompt_version='none',
    generation_policy_version='resistance_training_v1', catalog_programming_version='v1',
    max_repair_attempts=0, cooldown_seconds=0, max_candidates=80, max_request_bytes=262144,
    warmup_minutes=5, deterministic_fallback_enabled=True, generation_method='fitsho_coach'
))

db.begin_nested()
user = User(id=uuid4(), email=f"{uuid4().hex[:8]}@debug.com", password_hash="hash")
db.add(user)
db.flush()
profile = UserProfile(
    user_id=user.id, product_mode=ProductMode.TRAINING, display_name=p["name"],
    birth_date=p["birth_date"], sex=p["sex"], height_cm=p["height_cm"],
    fitness_goal=p["goal"], experience_level=p["level"], training_age_months=p["training_age_months"],
    training_days_per_week=p["days"], training_location=p["location"], home_training_setup=p["home_setup"],
    priority_muscles=None, session_duration_minutes=p["duration"], training_intensity=TrainingIntensity.MODERATE,
    plan_duration_weeks=p["plan_weeks"], workout_generation_method=WorkoutGenerationMethod.FITSHO_COACH,
)
db.add(profile)
db.add(BodyMeasurement(
    user_id=user.id, weight_kg=p["weight_kg"], shoulder_circumference_cm=Decimal("94.0"),
    waist_circumference_cm=Decimal("88.0"), hip_circumference_cm=Decimal("108.0"),
))
db.flush()

from app.profile.service import get_profile
snapshot = get_profile(db, user.id)
norm = service._to_generation_profile(snapshot)

from app.workouts.program_engine.engine import generate_program
from app.training_templates.engine_reference import load_template_references
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.template_selector import eligible_template_references, _hard_rejection_reason_codes, build_session_capacity
import json

templates = load_template_references(db)
catalog = service._load_catalog(profile.sex)
eligible = catalog
eligible = catalog

print("Total templates loaded:", len(templates))
capacity = build_session_capacity(norm, eligible, RULESET)
print("Session Capacity:", capacity)
valid = eligible_template_references(norm, eligible, templates, ruleset=RULESET)
print("Eligible templates count:", len(valid))
for v in valid:
    print(v.slug)

for t in templates:
    if t.days_per_week == 4:
        reasons = _hard_rejection_reason_codes(norm, eligible, t, level="intermediate", ruleset=RULESET, session_capacity=capacity)
        if reasons:
            print(f"Rejected {t.slug} because {reasons}")

db.rollback()
conn.close()
