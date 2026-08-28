from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import Enum
from html import escape
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import weasyprint
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import get_settings
from app.exercises.enums import PrescriptionMode
from app.main import create_app
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    ProductMode,
    Sex,
    TrainingCaution,
    TrainingIntensity,
    TrainingLocation,
    WorkoutGenerationMethod,
)
from app.profile.models import BodyMeasurement, UserProfile, UserProfileTrainingCaution
from app.profile.service import get_profile
from app.training_templates.engine_reference import load_template_references
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.router import to_plan_response
from app.workouts.schemas import (
    WorkoutDayResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanResponse,
)
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
BATCH2_USER_NAMESPACE = uuid5(NAMESPACE_URL, "fitsho-e2e-workout-engine-batch2")


def batch2_user_id(profile_number: int) -> UUID:
    """Return the stable, profile-isolated identity used by the deterministic harness."""
    return uuid5(BATCH2_USER_NAMESPACE, f"profile:{profile_number}")


def fa_num(val: object) -> str:
    if val is None:
        return "—"
    return str(val).translate(_PERSIAN_DIGITS)


def _json_ready(value: object) -> object:
    """Return a detached, JSON-compatible copy of engine evidence."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Mapping):
        return {str(_json_ready(key)): _json_ready(item) for key, item in value.items()}
    return value


def _evidence_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    ready = _json_ready(value)
    return ready if isinstance(ready, dict) else {}


def project_batch2_results(results: list[tuple[dict, dict]]) -> dict[str, object]:
    """Project raw Batch2 outcomes into one detached report model."""
    details = []
    for profile, raw in results:
        success = bool(raw.get("success"))
        final_gate = _evidence_mapping(raw.get("final_gate"))
        coverage = _evidence_mapping(raw.get("weekly_coverage"))
        distribution = _evidence_mapping(raw.get("weekly_distribution"))
        gate_status = final_gate.get("status")
        status = (
            "failure"
            if not success
            else "constrained"
            if gate_status == "accepted_with_constraints"
            else "success"
        )
        details.append(
            {
                "profile_number": profile.get("num"),
                "profile_name": profile.get("name"),
                "status": status,
                "success": success,
                "error_code": _json_ready(raw.get("error_code")),
                "errors": list(_json_ready(raw.get("errors") or ())),
                "safety_status": _json_ready(raw.get("safety_status")),
                "final_gate": final_gate,
                "weekly_coverage": coverage,
                "weekly_distribution": distribution,
                "requested_day_count": _json_ready(raw.get("requested_day_count")),
                "actual_day_count": _json_ready(raw.get("actual_day_count")),
                "per_day": list(_json_ready(raw.get("per_day") or ())),
            }
        )

    summary = {
        "total": len(details),
        "success": sum(item["success"] is True for item in details),
        "failure": sum(item["status"] == "failure" for item in details),
        "constrained": sum(item["status"] == "constrained" for item in details),
    }
    return {"summary": summary, "details": details}


GOAL_FA = {
    FitnessGoal.BUILD_MUSCLE: "عضله‌سازی (هایپرتروفی)",
    FitnessGoal.FAT_LOSS: "چربی‌سوزی و کاهش درصد چربی",
    FitnessGoal.LOSE_WEIGHT: "کاهش وزن کلی",
    FitnessGoal.GAIN_WEIGHT: "افزایش وزن و حجم عضلانی",
    FitnessGoal.BODY_RECOMPOSITION: "بازترکیب بدنی (ریکامپ)",
    FitnessGoal.STRENGTH: "افزایش قدرت و رکوردها",
}

LEVEL_FA = {
    ExperienceLevel.FIRST_MONTH: "ماه اول (تازه‌کار)",
    ExperienceLevel.BEGINNER: "مبتدی",
    ExperienceLevel.INTERMEDIATE: "متوسط",
    ExperienceLevel.ADVANCED: "پیشرفته",
}

SEX_FA = {
    Sex.MALE: "مرد (آقا)",
    Sex.FEMALE: "زن (خانم)",
}

LOCATION_FA = {
    TrainingLocation.GYM: "باشگاه بدنسازی",
    TrainingLocation.HOME: "خانه (منزل)",
}

HOME_SETUP_FA = {
    HomeTrainingSetup.BODYWEIGHT_ONLY: "فقط وزن بدن (بدون تجهیزات)",
    HomeTrainingSetup.DUMBBELLS_AVAILABLE: "دمبل‌های متغیر خانگی",
}

INTENSITY_FA = {
    TrainingIntensity.LIGHT: "سبک",
    TrainingIntensity.MODERATE: "متوسط",
    TrainingIntensity.VIGOROUS: "پرشدت و سنگین",
}

CAUTION_FA = {
    TrainingCaution.LOWER_BACK: "احتیاط پایین کمر (ستون فقرات کمری)",
    TrainingCaution.KNEE: "احتیاط زانو (مفصل و تاندون کشکک)",
    TrainingCaution.SHOULDER: "احتیاط مفصل شانه (روتاتور کاف)",
    TrainingCaution.WRIST: "احتیاط مچ دست (فشار مستقیم محوری)",
    TrainingCaution.NECK: "احتیاط گردن (ستون فقرات گردنی)",
    TrainingCaution.OTHER: "سایر محدودیت‌ها",
}

MUSCLE_FA = {
    "chest": "سینه",
    "back": "زیربغل و پشت",
    "shoulders": "سرشانه",
    "biceps": "جلو بازو",
    "triceps": "پشت بازو",
    "glutes": "باسن (سرینی)",
    "quadriceps": "چهارسر ران",
    "hamstrings": "پشت پا (همسترینگ)",
    "calves": "ساق پا",
    "abs": "شکم و میان‌تنه",
    "forearms": "ساعد",
    "traps": "کول (تراپزیوس)",
}

GUIDANCE_FA = {
    "Select a load that preserves the target RIR": "انتخاب وزنه‌ای متناسب با RIR هدف",
    "Use a moderate load with strict form": "استفاده از وزنه متوسط با فرم صحیح و کنترل‌شده",
    "Explosive concentric and controlled eccentric": (
        "اجرای انفجاری در فاز مثبت و کنترل‌شده در فاز منفی"
    ),
}

PROGRESSION_FA = {
    "double_progression_v1": "پیشرفت دوگانه (تکرار سپس وزنه)",
    "linear_progression": "پیشرفت خطی بار تمرینی",
    "repetition_progression": "پیشرفت مبتنی بر افزایش تکرار",
    "dynamic_double_progression": "پیشرفت دوگانه پویا",
}

TEST_PROFILES_BATCH2 = [
    {
        "num": 1,
        "name": "آرش قنبری",
        "sex": Sex.MALE,
        "birth_date": date(2003, 5, 18),
        "height_cm": 179,
        "weight_kg": 71.0,
        "shoulder_cm": 110.0,
        "waist_cm": 78.0,
        "hip_cm": 94.0,
        "fitness_goal": FitnessGoal.BUILD_MUSCLE,
        "experience_level": ExperienceLevel.BEGINNER,
        "training_age_months": 5,
        "training_days_per_week": 2,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 60,
        "plan_duration_weeks": 6,
        "training_intensity": TrainingIntensity.MODERATE,
        "cautions": [],
        "limitations_text": None,
        "priority_muscles": ["chest", "triceps"],
    },
    {
        "num": 2,
        "name": "زینب حسینی",
        "sex": Sex.FEMALE,
        "birth_date": date(1993, 10, 12),
        "height_cm": 163,
        "weight_kg": 74.0,
        "shoulder_cm": 99.0,
        "waist_cm": 82.0,
        "hip_cm": 106.0,
        "fitness_goal": FitnessGoal.FAT_LOSS,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 22,
        "training_days_per_week": 4,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 45,
        "plan_duration_weeks": 8,
        "training_intensity": TrainingIntensity.MODERATE,
        "cautions": [TrainingCaution.LOWER_BACK],
        "limitations_text": None,
        "priority_muscles": ["glutes", "quadriceps"],
    },
    {
        "num": 3,
        "name": "حمید فلاحی",
        "sex": Sex.MALE,
        "birth_date": date(1987, 2, 28),
        "height_cm": 185,
        "weight_kg": 91.0,
        "shoulder_cm": 120.0,
        "waist_cm": 89.0,
        "hip_cm": 101.0,
        "fitness_goal": FitnessGoal.STRENGTH,
        "experience_level": ExperienceLevel.ADVANCED,
        "training_age_months": 72,
        "training_days_per_week": 4,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 90,
        "plan_duration_weeks": 8,
        "training_intensity": TrainingIntensity.VIGOROUS,
        "cautions": [],
        "limitations_text": None,
        "priority_muscles": ["chest", "back"],
    },
    {
        "num": 4,
        "name": "سپیده کریمی",
        "sex": Sex.FEMALE,
        "birth_date": date(1997, 8, 4),
        "height_cm": 172,
        "weight_kg": 63.5,
        "shoulder_cm": 101.0,
        "waist_cm": 69.0,
        "hip_cm": 97.0,
        "fitness_goal": FitnessGoal.BODY_RECOMPOSITION,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 16,
        "training_days_per_week": 3,
        "training_location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "session_duration_minutes": 60,
        "plan_duration_weeks": 6,
        "training_intensity": TrainingIntensity.MODERATE,
        "cautions": [],
        "limitations_text": None,
        "priority_muscles": ["shoulders", "glutes"],
    },
    {
        "num": 5,
        "name": "متین نوری",
        "sex": Sex.MALE,
        "birth_date": date(2007, 9, 14),
        "height_cm": 180,
        "weight_kg": 60.0,
        "shoulder_cm": 104.0,
        "waist_cm": 70.0,
        "hip_cm": 88.0,
        "fitness_goal": FitnessGoal.GAIN_WEIGHT,
        "experience_level": ExperienceLevel.FIRST_MONTH,
        "training_age_months": 0,
        "training_days_per_week": 3,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 45,
        "plan_duration_weeks": 4,
        "training_intensity": TrainingIntensity.LIGHT,
        "cautions": [],
        "limitations_text": None,
        "priority_muscles": [],
    },
    {
        "num": 6,
        "name": "بهناز راد",
        "sex": Sex.FEMALE,
        "birth_date": date(1984, 4, 20),
        "height_cm": 160,
        "weight_kg": 58.0,
        "shoulder_cm": 93.0,
        "waist_cm": 71.0,
        "hip_cm": 95.0,
        "fitness_goal": FitnessGoal.LOSE_WEIGHT,
        "experience_level": ExperienceLevel.BEGINNER,
        "training_age_months": 3,
        "training_days_per_week": 2,
        "training_location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.BODYWEIGHT_ONLY,
        "session_duration_minutes": 45,
        "plan_duration_weeks": 4,
        "training_intensity": TrainingIntensity.LIGHT,
        "cautions": [],
        "limitations_text": None,
        "priority_muscles": [],
    },
    {
        "num": 7,
        "name": "بهمن شریفی",
        "sex": Sex.MALE,
        "birth_date": date(1978, 12, 10),
        "height_cm": 174,
        "weight_kg": 86.0,
        "shoulder_cm": 116.0,
        "waist_cm": 95.0,
        "hip_cm": 100.0,
        "fitness_goal": FitnessGoal.FAT_LOSS,
        "experience_level": ExperienceLevel.BEGINNER,
        "training_age_months": 6,
        "training_days_per_week": 3,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 45,
        "plan_duration_weeks": 6,
        "training_intensity": TrainingIntensity.MODERATE,
        "cautions": [TrainingCaution.SHOULDER],
        "limitations_text": None,
        "priority_muscles": ["back", "abs"],
    },
    {
        "num": 8,
        "name": "هدیه امینی",
        "sex": Sex.FEMALE,
        "birth_date": date(2001, 11, 22),
        "height_cm": 167,
        "weight_kg": 54.0,
        "shoulder_cm": 95.0,
        "waist_cm": 65.0,
        "hip_cm": 91.0,
        "fitness_goal": FitnessGoal.BUILD_MUSCLE,
        "experience_level": ExperienceLevel.ADVANCED,
        "training_age_months": 40,
        "training_days_per_week": 5,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 75,
        "plan_duration_weeks": 8,
        "training_intensity": TrainingIntensity.VIGOROUS,
        "cautions": [],
        "limitations_text": None,
        "priority_muscles": ["glutes", "hamstrings", "calves"],
    },
    {
        "num": 9,
        "name": "صابر رستمی",
        "sex": Sex.MALE,
        "birth_date": date(1990, 6, 15),
        "height_cm": 181,
        "weight_kg": 85.0,
        "shoulder_cm": 119.0,
        "waist_cm": 87.0,
        "hip_cm": 100.0,
        "fitness_goal": FitnessGoal.BODY_RECOMPOSITION,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 24,
        "training_days_per_week": 4,
        "training_location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "session_duration_minutes": 60,
        "plan_duration_weeks": 6,
        "training_intensity": TrainingIntensity.MODERATE,
        "cautions": [TrainingCaution.KNEE],
        "limitations_text": None,
        "priority_muscles": ["chest", "biceps"],
    },
    {
        "num": 10,
        "name": "پروانه صالحی",
        "sex": Sex.FEMALE,
        "birth_date": date(1971, 3, 8),
        "height_cm": 159,
        "weight_kg": 68.0,
        "shoulder_cm": 97.0,
        "waist_cm": 80.0,
        "hip_cm": 102.0,
        "fitness_goal": FitnessGoal.FAT_LOSS,
        "experience_level": ExperienceLevel.BEGINNER,
        "training_age_months": 1,
        "training_days_per_week": 3,
        "training_location": TrainingLocation.GYM,
        "home_setup": None,
        "session_duration_minutes": 45,
        "plan_duration_weeks": 4,
        "training_intensity": TrainingIntensity.LIGHT,
        "cautions": [],
        "limitations_text": "سابقه جراحی تاندون آشیل و درد پاشنه چپ",
        "priority_muscles": [],
    },
]


def _successful_result_evidence(program, requested_day_count: int) -> dict[str, object]:
    aggregate_metrics = program.aggregate_metrics
    final_gate = _evidence_mapping(aggregate_metrics.get("final_quality_gate"))
    weekly_coverage = _evidence_mapping(aggregate_metrics.get("weekly_coverage"))
    weekly_distribution = _evidence_mapping(aggregate_metrics.get("weekly_distribution"))
    if not final_gate.get("status"):
        raise RuntimeError("Successful Batch2 generation is missing final gate evidence")
    if not weekly_coverage:
        raise RuntimeError("Successful Batch2 generation is missing weekly coverage evidence")
    if not weekly_distribution:
        raise RuntimeError("Successful Batch2 generation is missing weekly distribution evidence")

    per_day = tuple(
        {
            "day_number": day.day_index,
            "exercise_count": len(day.exercises),
            "duration_minutes": day.estimated_duration_minutes,
        }
        for day in program.weekly_schedule
    )
    return {
        "final_gate": final_gate,
        "weekly_coverage": weekly_coverage,
        "weekly_distribution": weekly_distribution,
        "requested_day_count": requested_day_count,
        "actual_day_count": len(program.weekly_schedule),
        "per_day": per_day,
    }


def run_batch2_profiles():
    create_app()
    settings = get_settings()
    engine = create_engine(settings.database_url)

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    results = []

    try:
        svc = WorkoutGenerationService(
            session,
            settings=WorkoutGenerationSettings(
                provider_name="fitsho_domain",
                model_id="program_engine_v1",
                prompt_version="none",
                generation_policy_version="resistance_training_v1",
                catalog_programming_version="v1",
                max_repair_attempts=0,
                cooldown_seconds=0,
                max_candidates=200,
                max_request_bytes=200000,
                warmup_minutes=5,
                deterministic_fallback_enabled=True,
                generation_method="fitsho_coach",
            ),
        )
        refs = load_template_references(session)

        for p in TEST_PROFILES_BATCH2:
            t0 = time.perf_counter()
            user_id = batch2_user_id(p["num"])
            user = User(
                id=user_id,
                email=f"test_{user_id.hex[:8]}@example.com",
                password_hash="x",
                is_admin=False,
            )
            session.add(user)
            session.flush()

            profile = UserProfile(
                user_id=user_id,
                product_mode=ProductMode.TRAINING,
                display_name=p["name"],
                birth_date=p["birth_date"],
                sex=p["sex"],
                height_cm=p["height_cm"],
                fitness_goal=p["fitness_goal"],
                experience_level=p["experience_level"],
                training_age_months=p["training_age_months"],
                training_days_per_week=p["training_days_per_week"],
                training_location=p["training_location"],
                home_training_setup=p["home_setup"],
                session_duration_minutes=p["session_duration_minutes"],
                plan_duration_weeks=p["plan_duration_weeks"],
                training_intensity=p["training_intensity"],
                workout_generation_method=WorkoutGenerationMethod.FITSHO_COACH,
                priority_muscles=p["priority_muscles"] if p["priority_muscles"] else None,
                physical_limitations=p["limitations_text"],
                training_caution_items=[
                    UserProfileTrainingCaution(caution=c) for c in p["cautions"]
                ],
            )
            session.add(profile)
            session.flush()

            measurement = BodyMeasurement(
                user_id=user_id,
                weight_kg=Decimal(str(p["weight_kg"])),
                shoulder_circumference_cm=(
                    Decimal(str(p["shoulder_cm"])) if p["shoulder_cm"] else None
                ),
                waist_circumference_cm=Decimal(str(p["waist_cm"])) if p["waist_cm"] else None,
                hip_circumference_cm=Decimal(str(p["hip_cm"])) if p["hip_cm"] else None,
            )
            session.add(measurement)
            session.flush()

            sp = get_profile(session, user_id)
            req = svc._to_program_request(sp, None)
            catalog = svc._load_catalog(sp.profile.sex)
            catalog_hash = svc._catalog_hash(catalog)
            ref_hash = svc._template_reference_hash(refs)
            signature = svc._generation_signature(req, catalog_hash, ref_hash)

            res = generate_program(req, catalog, RULESET, reference_templates=refs)
            dur = time.perf_counter() - t0

            if res.is_success and res.program is not None:
                plan = svc._build_plan(
                    user_id=user_id,
                    signature=signature,
                    catalog_hash=catalog_hash,
                    catalog=catalog,
                    program=res.program,
                    previous=None,
                )
                session.add(plan)
                session.flush()
                plan_resp = to_plan_response(plan, db=session)
                res_obj = {
                    "success": True,
                    "plan": plan_resp,
                    "error_code": None,
                    "errors": (),
                    "safety_status": res.safety_status.value if res.safety_status else "clear",
                    "latency_sec": dur,
                    **_successful_result_evidence(res.program, req.available_training_days),
                }
            else:
                err_code = res.error_code.value if res.error_code else "UNKNOWN_ERROR"
                res_obj = {
                    "success": False,
                    "plan": None,
                    "error_code": err_code,
                    "errors": res.errors,
                    "safety_status": (res.safety_status.value if res.safety_status else "rejected"),
                    "latency_sec": dur,
                    "engine_error_code": err_code,
                    "engine_error_reasons": tuple(res.errors),
                }

            results.append((p, res_obj))
            status_label = "SUCCESS" if res_obj["success"] else f"FAILED ({res_obj['error_code']})"
            print(f"Profile {p['num']} ({p['name']}): {status_label} in {dur:.2f}s")

    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()

    return results


CSS = """
@page {
  size: A4;
  margin: 10mm 12mm 12mm 12mm;
  @bottom-center {
    content: "صفحه " counter(page) " از " counter(pages) " · گزارش تست سرتاسری موتور "
             "تمرینی فیت‌شو (سری دوم)";
    font-family: "Vazirmatn", "Noto Sans Arabic", "DejaVu Sans", sans-serif;
    font-size: 7.5pt;
    color: #718096;
  }
}
* { box-sizing: border-box; }
body {
  direction: rtl;
  text-align: right;
  font-family: "Vazirmatn", "Noto Sans Arabic", "DejaVu Sans", sans-serif;
  font-size: 8.5pt;
  line-height: 1.5;
  color: #1a202c;
  background-color: #ffffff;
}
.header {
  border-bottom: 2px solid #087d6c;
  padding-bottom: 3mm;
  margin-bottom: 4mm;
}
h1 {
  color: #087d6c;
  font-size: 16pt;
  margin: 0 0 1mm 0;
  font-weight: 800;
}
.subtitle {
  color: #4a5568;
  font-size: 8.5pt;
  margin: 0;
}
.summary-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-right: 4px solid #087d6c;
  border-radius: 4px;
  padding: 3mm 4mm;
  margin-bottom: 5mm;
}
.summary-title {
  font-weight: bold;
  font-size: 10pt;
  color: #1a202c;
  margin-bottom: 2mm;
}
.stats-grid {
  display: table;
  width: 100%;
  margin-bottom: 2mm;
}
.stat-col {
  display: table-cell;
  width: 25%;
  text-align: center;
  padding: 1.5mm;
  background: #edf2f7;
  border-radius: 4px;
  border: 1px solid #cbd5e0;
}
.stat-val {
  font-size: 13pt;
  font-weight: bold;
  color: #087d6c;
}
.stat-val.error {
  color: #c53030;
}
.stat-lbl {
  font-size: 7.5pt;
  color: #4a5568;
}
.analysis-list {
  margin: 1mm 0 0 0;
  padding-right: 3mm;
  font-size: 8pt;
  color: #2d3748;
}
.analysis-list li {
  margin-bottom: 0.8mm;
}

.user-card {
  border: 1px solid #cbd5e0;
  border-radius: 5px;
  margin-bottom: 5mm;
  page-break-inside: avoid;
  background: #ffffff;
}
.user-card.page-break {
  page-break-before: always;
}
.user-header {
  background: #f0fdf4;
  border-bottom: 1px solid #cbd5e0;
  padding: 2mm 3mm;
}
.user-header.failed {
  background: #fff5f5;
  border-bottom: 1px solid #fed7d7;
}
.user-title {
  font-size: 10pt;
  font-weight: bold;
  color: #065f46;
  margin: 0;
}
.user-title.failed {
  color: #9b2c2c;
}
.badge {
  display: inline-block;
  font-size: 7pt;
  font-weight: bold;
  padding: 1px 5px;
  border-radius: 9999px;
  margin-right: 2mm;
}
.badge.success {
  background: #def7ec;
  color: #03543f;
  border: 1px solid #84e1bc;
}
.badge.warning {
  background: #fef08a;
  color: #854d0e;
  border: 1px solid #fde047;
}
.badge.danger {
  background: #fde8e8;
  color: #9b1c1c;
  border: 1px solid #f8b4b4;
}

.profile-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 7.5pt;
  margin: 0;
}
.profile-table td {
  padding: 1.2mm 2.5mm;
  border-bottom: 1px solid #edf2f7;
}
.profile-table tr:nth-child(even) {
  background: #f8fafc;
}
.profile-table .label {
  width: 22%;
  color: #4a5568;
  font-weight: 600;
}
.profile-table .value {
  width: 28%;
  color: #1a202c;
}

.plan-section {
  padding: 2.5mm 3mm;
}
.plan-heading {
  font-size: 8.5pt;
  font-weight: bold;
  color: #087d6c;
  margin-bottom: 1.5mm;
  border-bottom: 1px dashed #cbd5e0;
  padding-bottom: 0.8mm;
}
.evidence-box {
  background: #f8fafc;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  padding: 2mm 3mm;
  margin-bottom: 2mm;
  font-size: 7.2pt;
  line-height: 1.5;
}
.evidence-title {
  color: #087d6c;
  font-weight: bold;
  margin-bottom: 0.8mm;
}
.evidence-box code {
  direction: ltr;
  unicode-bidi: embed;
  color: #134e4a;
}
.evidence-days {
  margin: 0.8mm 0 0 0;
  padding-right: 3mm;
}

.day-box {
  background: #fbfdfc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 2mm;
  margin-bottom: 2mm;
  page-break-inside: avoid;
}
.day-title {
  font-size: 8.5pt;
  font-weight: bold;
  color: #0f766e;
  margin: 0 0 1.2mm 0;
}

.exercise-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 7.5pt;
}
.exercise-table th {
  background: #e6f4f1;
  color: #134e4a;
  padding: 1mm 1.8mm;
  font-weight: 700;
  border: 1px solid #ccede5;
  text-align: right;
}
.exercise-table td {
  padding: 1.2mm 1.8mm;
  border: 1px solid #e5e7eb;
  vertical-align: middle;
}
.exercise-table tr:nth-child(even) td {
  background: #fafafa;
}
.ex-num {
  text-align: center;
  font-weight: bold;
  color: #087d6c;
  width: 4%;
}
.ex-name {
  font-weight: 600;
  color: #1f2937;
  width: 42%;
}
.ex-meta {
  color: #374151;
  width: 26%;
}
.ex-rest {
  color: #4b5563;
  width: 14%;
  text-align: center;
}
.ex-rir {
  color: #087d6c;
  font-weight: 600;
  width: 14%;
  text-align: center;
}
.superset-tag {
  background: #fef3c7;
  color: #92400e;
  font-size: 6.5pt;
  padding: 1px 3px;
  border-radius: 2px;
  margin-right: 1mm;
}
.ex-note {
  font-size: 6.8pt;
  color: #6b7280;
  margin-top: 0.3mm;
}

.error-card {
  background: #fffafa;
  border: 1px solid #fed7d7;
  border-radius: 4px;
  padding: 2mm 3mm;
  margin: 2mm 3mm 3mm 3mm;
}
.error-title {
  color: #c53030;
  font-weight: bold;
  font-size: 8.5pt;
  margin: 0 0 0.8mm 0;
}
.error-desc {
  color: #742a2a;
  font-size: 7.5pt;
  margin: 0;
  line-height: 1.4;
}
"""


def translate_note_item(text: str) -> str:
    for eng, farsi in GUIDANCE_FA.items():
        if eng in text:
            text = text.replace(eng, farsi)
    for eng, farsi in PROGRESSION_FA.items():
        if eng in text:
            text = text.replace(eng, farsi)
    return text


def render_exercise_row(idx: int, item: WorkoutPlanExerciseResponse) -> str:
    ex = item.exercise
    name_fa = ex.name_fa if (ex.name_fa and ex.name_fa.strip()) else ex.name_en

    if item.prescription_mode == PrescriptionMode.REPS:
        meta = f"{fa_num(item.sets)} ست × {fa_num(item.reps_min)} تا {fa_num(item.reps_max)} تکرار"
    else:
        meta = (
            f"{fa_num(item.sets)} ست × {fa_num(item.duration_min_seconds)} تا "
            f"{fa_num(item.duration_max_seconds)} ثانیه"
        )

    rest = f"{fa_num(item.rest_seconds)} ثانیه"
    rir = f"RIR {fa_num(item.rir)}" if item.rir is not None else "—"

    superset_html = ""
    if item.superset_group:
        superset_html = (
            f'<span class="superset-tag">سوپرست {escape(str(item.superset_group))}</span> '
        )

    notes = []
    if item.warmup_sets:
        notes.append(f"{fa_num(item.warmup_sets)} ست گرم‌کردن")
    if item.load_guidance:
        notes.append(f"بارگذاری: {translate_note_item(item.load_guidance)}")
    if item.progression_rule:
        notes.append(f"پیشرفت: {translate_note_item(item.progression_rule)}")
    if item.notes_fa:
        notes.append(item.notes_fa)
    elif item.notes_en:
        notes.append(translate_note_item(item.notes_en))

    note_text = " · ".join(notes)
    note_html = f'<div class="ex-note">{escape(note_text)}</div>' if note_text else ""

    return f"""
    <tr>
      <td class="ex-num">{fa_num(idx)}</td>
      <td class="ex-name">{superset_html}{escape(name_fa)}{note_html}</td>
      <td class="ex-meta">{meta}</td>
      <td class="ex-rest">{rest}</td>
      <td class="ex-rir">{rir}</td>
    </tr>
    """


def render_day_block(day: WorkoutDayResponse) -> str:
    rows = "".join(render_exercise_row(i, ex) for i, ex in enumerate(day.exercises, start=1))
    title = (
        f"{escape(day.title_fa)} ({fa_num(len(day.exercises))} حرکت · تخمین زمان: "
        f"{fa_num(day.estimated_duration_minutes)} دقیقه)"
    )
    return f"""
    <div class="day-box">
      <div class="day-title">{title}</div>
      <table class="exercise-table">
        <thead>
          <tr>
            <th class="ex-num">#</th>
            <th class="ex-name">نام حرکت</th>
            <th class="ex-meta">ست × تکرار / مدت زمان</th>
            <th class="ex-rest">استراحت</th>
            <th class="ex-rir">شدت / RIR</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
    """


def _evidence_values(evidence: dict[str, object], key: str) -> tuple[str, ...]:
    value = evidence.get(key)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


def _render_engine_evidence(detail: dict[str, object]) -> str:
    final_gate = detail["final_gate"]
    coverage = detail["weekly_coverage"]
    distribution = detail["weekly_distribution"]
    if not isinstance(final_gate, dict):
        final_gate = {}
    if not isinstance(coverage, dict):
        coverage = {}
    if not isinstance(distribution, dict):
        distribution = {}

    gate_reasons = _evidence_values(final_gate, "reason_codes")
    gate_constraints = _evidence_values(final_gate, "constraint_reason_codes")
    coverage_reasons = _evidence_values(coverage, "reason_codes")
    coverage_missing_patterns = _evidence_values(coverage, "missing_patterns")
    coverage_missing_muscles = _evidence_values(coverage, "missing_major_muscles")
    distribution_reasons = _evidence_values(distribution, "reason_codes")
    day_rows = "".join(
        f"<li>روز {fa_num(day.get('day_number'))}: {fa_num(day.get('exercise_count'))} حرکت · "
        f"{fa_num(day.get('duration_minutes'))} دقیقه</li>"
        for day in detail["per_day"]
        if isinstance(day, dict)
    )

    def codes(values: tuple[str, ...]) -> str:
        return " · ".join(f"<code>{escape(value)}</code>" for value in values) or "—"

    return f"""
        <div class="evidence-box">
          <div class="evidence-title">شواهد نهایی موتور</div>
          <div>گیت نهایی: <code>{escape(str(final_gate.get("status", "—")))}</code> ·
          دلایل: {codes(gate_reasons)} · قیود: {codes(gate_constraints)}</div>
          <div>پوشش هفتگی: <code>{escape(str(coverage.get("status", "—")))}</code> ·
          دلایل: {codes(coverage_reasons)} · الگوهای پوشش‌داده‌نشده:
          {codes(coverage_missing_patterns)} · عضلات پوشش‌داده‌نشده:
          {codes(coverage_missing_muscles)}</div>
          <div>توزیع هفتگی: <code>{escape(str(distribution.get("status", "—")))}</code> ·
          دلایل: {codes(distribution_reasons)}</div>
          <div>روزهای درخواستی/واقعی: <code>{fa_num(detail.get("requested_day_count"))}</code> /
          <code>{fa_num(detail.get("actual_day_count"))}</code></div>
          <ul class="evidence-days">{day_rows}</ul>
        </div>
        """


def render_user_profile_card(
    p: dict, res: dict, index: int, detail: dict[str, object] | None = None
) -> str:
    if detail is None:
        projected = project_batch2_results([(p, res)])
        detail = projected["details"][0]
    age = calculate_age(p["birth_date"])
    sex_str = escape(SEX_FA.get(p["sex"], str(p["sex"].value)))
    goal_str = escape(GOAL_FA.get(p["fitness_goal"], str(p["fitness_goal"].value)))
    level_str = escape(LEVEL_FA.get(p["experience_level"], str(p["experience_level"].value)))
    loc_str = escape(LOCATION_FA.get(p["training_location"], str(p["training_location"].value)))

    if p["training_location"] == TrainingLocation.HOME:
        equip_str = escape(HOME_SETUP_FA.get(p["home_setup"], "تجهیزات خانگی"))
    else:
        equip_str = escape("باشگاه کامل (هالتر، دمبل، دستگاه، کابل)")

    cautions_list = [CAUTION_FA.get(c, c.value) for c in p["cautions"]]
    if p["limitations_text"]:
        cautions_list.append(f"توضیحات آسیب: {p['limitations_text']}")
    caution_str = escape("، ".join(cautions_list) if cautions_list else "بدون آسیب و محدودیت")

    prio_list = [MUSCLE_FA.get(m, m) for m in p["priority_muscles"]]
    prio_str = escape("، ".join(prio_list) if prio_list else "عضلات عمومی متعادل")

    measure_str = escape(
        f"دور شانه: {fa_num(p['shoulder_cm'])} cm · دور کمر: "
        f"{fa_num(p['waist_cm'])} cm · دور باسن: {fa_num(p['hip_cm'])} cm"
    )

    status = detail["status"]
    success = status != "failure"
    plan: WorkoutPlanResponse | None = res["plan"]

    if success and plan:
        gate = detail["final_gate"]
        gate_status = gate.get("status") if isinstance(gate, dict) else None
        if status == "constrained":
            badge_html = (
                f'<span class="badge warning">محدودشده · گیت نهایی: '
                f"{escape(str(gate_status or '—'))}</span>"
            )
        else:
            badge_html = (
                f'<span class="badge success">موفق · گیت نهایی: '
                f"{escape(str(gate_status or '—'))}</span>"
            )

        days_html = "".join(render_day_block(day) for day in plan.days)
        actual_day_count = detail.get("actual_day_count")
        plan_heading = (
            f"برنامه تمرینی تولیدشده توسط موتور ({fa_num(actual_day_count)} روز واقعی · "
            f"دوره {fa_num(plan.plan_duration_weeks)} هفته‌ای · نسخه موتور: "
            f"{escape(plan.engine_version)})"
        )
        plan_content = f"""
        <div class="plan-section">
          <div class="plan-heading">{plan_heading}</div>
          {_render_engine_evidence(detail)}
          {days_html}
        </div>
        """
        header_class = "user-header"
        title_class = "user-title"
    else:
        err_code = str(detail.get("error_code") or "ERROR")
        err_errors = tuple(str(error) for error in detail.get("errors", ()))
        errors_joined = " · ".join(escape(error) for error in err_errors) or "—"
        badge_html = f'<span class="badge danger">ناموفق · کد موتور: {escape(err_code)}</span>'
        err_desc = f"کد خطای موتور: {escape(err_code)} · دلایل دقیق موتور: {errors_joined}"

        plan_content = f"""
        <div class="error-card">
          <div class="error-title">علت و کد خطای موتور: {escape(err_code)}</div>
          <p class="error-desc">{err_desc}</p>
          <div style="font-size: 7pt; color: #9b2c2c; margin-top: 1.2mm;">
            <strong>کدهای تشخیصی موتور:</strong> {errors_joined}
          </div>
        </div>
        """
        header_class = "user-header failed"
        title_class = "user-title failed"

    page_break = " page-break" if index > 1 else ""
    height_weight = f"{fa_num(p['height_cm'])} سانتی‌متر · {fa_num(p['weight_kg'])} کیلوگرم"
    session_settings = (
        f"مدت {fa_num(p['session_duration_minutes'])} دقیقه · "
        f"دوره {fa_num(p['plan_duration_weeks'])} هفته"
    )
    intensity = escape(INTENSITY_FA.get(p["training_intensity"], "متوسط"))

    return f"""
    <section class="user-card{page_break}">
      <div class="{header_class}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2 class="{title_class}">کاربر شماره {fa_num(p["num"])}: {escape(str(p["name"]))}</h2>
          {badge_html}
        </div>
      </div>
      <table class="profile-table">
        <tr>
          <td class="label">سن و جنسیت:</td>
          <td class="value">{fa_num(age)} سال · {sex_str}</td>
          <td class="label">قد و وزن:</td>
          <td class="value">{height_weight}</td>
        </tr>
        <tr>
          <td class="label">هدف تمرینی:</td>
          <td class="value">{goal_str}</td>
          <td class="label">سطح و سابقه:</td>
          <td class="value">{level_str} ({fa_num(p["training_age_months"])} ماه سابقه)</td>
        </tr>
        <tr>
          <td class="label">روزهای تمرین:</td>
          <td class="value">{fa_num(p["training_days_per_week"])} روز در هفته</td>
          <td class="label">محیط تمرین:</td>
          <td class="value">{loc_str}</td>
        </tr>
        <tr>
          <td class="label">تجهیزات موجود:</td>
          <td class="value">{equip_str}</td>
          <td class="label">اندازه‌های بدنی:</td>
          <td class="value">{measure_str}</td>
        </tr>
        <tr>
          <td class="label">محدودیت و آسیب:</td>
          <td class="value">{caution_str}</td>
          <td class="label">عضلات اولویت‌دار:</td>
          <td class="value">{prio_str}</td>
        </tr>
        <tr>
          <td class="label">تنظیمات جلسه:</td>
          <td class="value">{session_settings}</td>
          <td class="label">شدت تمرین:</td>
          <td class="value">{intensity}</td>
        </tr>
      </table>
      {plan_content}
    </section>
    """


def calculate_age(bdate: date) -> int:
    today = date.today()
    return today.year - bdate.year - ((today.month, today.day) < (bdate.month, bdate.day))


def generate_html_report(results: list) -> str:
    projection = project_batch2_results(results)
    summary = projection["summary"]
    details = projection["details"]
    total_count = summary["total"]
    success_count = summary["success"]
    fail_count = summary["failure"]
    constrained_count = summary["constrained"]

    cards_html = "".join(
        render_user_profile_card(p, res, i, detail)
        for i, ((p, res), detail) in enumerate(zip(results, details, strict=True), start=1)
    )

    failure_codes = sorted(
        {
            str(detail["error_code"])
            for detail in details
            if detail["status"] == "failure" and detail["error_code"]
        }
    )
    failure_code_text = " · ".join(escape(code) for code in failure_codes) or "—"
    summary_observation = (
        f"تعداد کل پروفایل‌های اجراشده: <strong>{fa_num(total_count)}</strong> · "
        f"موفق: <strong>{fa_num(success_count)}</strong> · "
        f"ناموفق: <strong>{fa_num(fail_count)}</strong> · "
        f"محدودشده: <strong>{fa_num(constrained_count)}</strong>"
    )
    report_subtitle = (
        f"آزمون جامع عملکرد روی {fa_num(total_count)} پروفایل کاملاً جدید، متنوع و با "
        "ترکیب‌های تمرینی پیشرفته"
    )
    summary_title = f"خلاصه نتایج آزمون جامع موتور ({fa_num(total_count)} پروفایل جدید)"

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>گزارش تست سرتاسری موتور تمرینی فیت‌شو - سری دوم</title>
  <style>{CSS}</style>
</head>
<body>
  <header class="header">
    <div class="logo-title">
      <div>
        <h1>گزارش تست سرتاسری موتور تولید برنامه تمرینی فیت‌شو (سری دوم)</h1>
        <p class="subtitle">{report_subtitle}</p>
      </div>
    </div>
  </header>

  <section class="summary-box">
    <div class="summary-title">{summary_title}</div>
    <div class="stats-grid">
      <div class="stat-col">
        <div class="stat-val">{fa_num(total_count)}</div>
        <div class="stat-lbl">تعداد کل پروفایل‌های تست‌شده</div>
      </div>
      <div class="stat-col">
        <div class="stat-val">{fa_num(success_count)}</div>
        <div class="stat-lbl">برنامه‌های تولیدشده و پذیرفته‌شده</div>
      </div>
      <div class="stat-col">
        <div class="stat-val error">{fa_num(fail_count)}</div>
        <div class="stat-lbl">نتایج ناموفق موتور</div>
      </div>
      <div class="stat-col">
        <div class="stat-val">{fa_num(constrained_count)}</div>
        <div class="stat-lbl">تعداد برنامه‌های محدودشده</div>
      </div>
    </div>

    <div style="font-weight: bold; font-size: 8.5pt; color: #1a202c; margin-top: 2mm;">
      مشاهدات مبتنی بر خروجی واقعی موتور:
    </div>
    <ul class="analysis-list">
      <li>{summary_observation}</li>
      <li>کدهای خطای مشاهده‌شده در خروجی ناموفق: <code>{failure_code_text}</code></li>
      <li>هر کارت وضعیت گیت نهایی، پوشش هفتگی، توزیع هفتگی و شمارش روزهای
      درخواستی/واقعی خود را از همان رکورد خام نمایش می‌دهد.</li>
    </ul>
  </section>

  {cards_html}

</body>
</html>"""


def main():
    out_dir = Path("/home/mohammad/project/fitsho/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "workout_engine_10_profiles_batch2.pdf"

    print("Running 10 NEW test profiles against the live Fitsho engine...")
    results = run_batch2_profiles()

    print("Building Persian HTML report for Batch 2...")
    html_content = generate_html_report(results)

    print(f"Rendering PDF via WeasyPrint to {pdf_path}...")
    weasyprint.HTML(string=html_content).write_pdf(str(pdf_path))

    print(f"PDF successfully generated: {pdf_path} ({pdf_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
