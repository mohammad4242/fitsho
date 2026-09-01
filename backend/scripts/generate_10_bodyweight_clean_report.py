from __future__ import annotations

import os
import random
import shutil
from datetime import date
from typing import Any
from uuid import UUID

import weasyprint
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
import app.main
from app.exercises.models import Exercise
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingLocation,
)
from app.training_templates.engine_reference import load_template_references
from app.workouts.program_engine.enums import (
    PhysicalJobDemand,
    RecoveryRating,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.service import WorkoutGenerationService
import sys
from pathlib import Path

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_1000_profiles_audit_report import (
    FA_TRANSLATIONS,
    PERSIAN_FIRST_NAMES_FEMALE,
    PERSIAN_FIRST_NAMES_MALE,
    PERSIAN_LAST_NAMES,
    ProfileSpec,
    build_pdf_html,
    evaluate_single_profile,
)


def generate_10_clean_bodyweight_profiles(seed: int = 42) -> list[ProfileSpec]:
    rng = random.Random(seed)
    today = date(2026, 9, 2)

    profiles: list[ProfileSpec] = []
    levels = [ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER]
    days_choices = [2, 3, 4]
    durations = [30, 45, 60]
    goals = [
        FitnessGoal.BUILD_MUSCLE,
        FitnessGoal.FAT_LOSS,
        FitnessGoal.BODY_RECOMPOSITION,
        FitnessGoal.IMPROVE_FITNESS,
        FitnessGoal.LOSE_WEIGHT,
    ]

    for i in range(1, 11):
        sex = Sex.MALE if (i % 2 == 1) else Sex.FEMALE
        first_name = rng.choice(
            PERSIAN_FIRST_NAMES_MALE if sex == Sex.MALE else PERSIAN_FIRST_NAMES_FEMALE
        )
        last_name = rng.choice(PERSIAN_LAST_NAMES)
        name = f"{first_name} {last_name}"

        exp_level = levels[(i - 1) % len(levels)]
        training_age_months = 0 if exp_level == ExperienceLevel.FIRST_MONTH else rng.randint(1, 5)
        training_days = days_choices[(i - 1) % len(days_choices)]
        session_duration = durations[(i - 1) % len(durations)]
        goal = goals[(i - 1) % len(goals)]

        age = 19 + (i * 3 + rng.randint(0, 3)) % 25
        birth_date = date(today.year - age, ((i * 3) % 12) + 1, ((i * 5) % 27) + 1)

        if sex == Sex.MALE:
            height_cm = rng.randint(170, 188)
            weight_kg = round(rng.uniform(66.0, 92.0), 1)
        else:
            height_cm = rng.randint(156, 172)
            weight_kg = round(rng.uniform(50.0, 72.0), 1)

        profiles.append(
            ProfileSpec(
                index=i,
                name=name,
                sex=sex,
                birth_date=birth_date,
                age=age,
                height_cm=height_cm,
                weight_kg=weight_kg,
                fitness_goal=goal,
                experience_level=exp_level,
                training_age_months=training_age_months,
                training_days_per_week=training_days,
                session_duration_minutes=session_duration,
                training_location=TrainingLocation.HOME,
                home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
                priority_muscle=None,
                training_cautions=[],  # Clean - no injuries
                plan_duration_weeks=6,
                sleep_quality=RecoveryRating.GOOD,
                stress_level=RecoveryRating.AVERAGE,
                physical_job_demand=PhysicalJobDemand.LOW,
            )
        )

    return profiles


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)

    profiles = generate_10_clean_bodyweight_profiles()
    print(f"Generated {len(profiles)} clean bodyweight profiles (no cautions, first_month & beginner, 2-4 days).")

    results: list[dict[str, Any]] = []

    with Session(engine) as session:
        exercises_list = session.scalars(select(Exercise)).all()
        exercise_map = {ex.id: ex for ex in exercises_list}

        service = WorkoutGenerationService(session, settings=None)
        catalog = service._load_catalog()
        references = load_template_references(session)

        for p in profiles:
            res = evaluate_single_profile(
                p,
                catalog,
                references,
                exercise_map,
                ruleset=RULESET,
                db=session,
            )
            results.append(res)
            status = res["status"]
            slug = res.get("template_slug")
            print(f"Profile #{p.index:02d} ({p.experience_level.value}, {p.training_days_per_week}d): {status} -> {slug}")

    successes = sum(1 for r in results if r["status"] == "SUCCESS")
    print(f"\nResult: {successes}/10 succeeded!")

    html_content = build_pdf_html(results)
    pdf_path = "/home/mohammad/project/fitsho/fitsho_10_bodyweight_clean_report.pdf"
    print(f"Rendering PDF to {pdf_path}...")
    weasyprint.HTML(string=html_content).write_pdf(pdf_path)

    shutil.copy2(pdf_path, "/home/mohammad/project/fitsho/frontend/public/fitsho_10_bodyweight_clean_report.pdf")
    html_path = "/home/mohammad/project/fitsho/frontend/public/fitsho_10_bodyweight_clean_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Saved PDF to {pdf_path}")
    print("Available at: http://localhost:8080/fitsho_10_bodyweight_clean_report.pdf")
    print("Available at: http://localhost:8000/fitsho_10_bodyweight_clean_report.pdf")


if __name__ == "__main__":
    main()
