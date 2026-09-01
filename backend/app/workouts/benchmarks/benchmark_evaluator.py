from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

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
from app.workouts.benchmarks.cohort_generator import FA_TRANSLATIONS, ProfileSpec
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
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset
from app.workouts.program_engine.safety import screen_safety
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    RecentTrainingHistory,
    TemplateReference,
    WorkoutProgram,
)
from app.workouts.program_engine.volume_policy import session_hard_volume_cap


def profile_to_request(spec: ProfileSpec, user_id: UUID | None = None) -> ProgramGenerationRequest:
    if user_id is None:
        user_id = uuid4()

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

    return ProgramGenerationRequest(
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
        current_pain_or_red_flags=tuple(spec.current_pain_or_red_flags),
        medical_clearance_status=MedicalClearanceStatus.NOT_REQUIRED,
        reports_uncontrolled_medical_condition=spec.reports_uncontrolled_medical_condition,
        pregnancy_or_postpartum=spec.pregnancy_or_postpartum,
        sleep_quality=spec.sleep_quality,
        stress_level=spec.stress_level,
        physical_job_demand=spec.physical_job_demand,
        cardio_tolerance=ActivityLevel.MODERATE,
        recent_training_history=RecentTrainingHistory(),
        program_duration_weeks=spec.plan_duration_weeks,
        seed_optional=spec.seed + spec.profile_id,
    )


def analyze_program_engine_failure(result: Any, request: ProgramGenerationRequest) -> dict[str, Any]:
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
        elif "SESSION_EXERCISE_COUNT_OUT_OF_RANGE" in collected_reasons:
            root_cause = "SESSION_EXERCISE_COUNT_OUT_OF_RANGE"
            ex_policy = get_session_exercise_count_policy(request.session_duration_minutes)
            actual_val = "خارج از بازه استاندارد حرکات جلسه"
            limit_val = f"{ex_policy.minimum_main_exercises} الی {ex_policy.maximum_main_exercises} حرکت اصلی در هر جلسه"
            exact_description_fa = (
                f"تعداد حرکات اصلی تجویزشده در جلسه خارج از بازه مجاز تعیین‌شده برای مدت زمان "
                f"{request.session_duration_minutes} دقیقه‌ای است (حداقل {ex_policy.minimum_main_exercises} و حداکثر {ex_policy.maximum_main_exercises} حرکت)."
            )
            engine_repair_hint_fa = "بررسی پالیسی get_session_exercise_count_policy یا تنظیم منطق افزودن/حذف حرکات کمکی در session_duration.py."
            rule_file = "app/workouts/program_engine/duration_policy.py"
            rule_func = "get_session_exercise_count_policy()"
            failing_phase = "session_exercise_count_validation"
        elif "REQUIRED_SLOT_HARD_IMPOSSIBILITY" in collected_reasons or "SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT" in collected_reasons:
            root_cause = "REQUIRED_SLOT_HARD_IMPOSSIBILITY" if "REQUIRED_SLOT_HARD_IMPOSSIBILITY" in collected_reasons else "SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT"
            actual_val = "۰ حرکت منطبق با اسلات اجباری"
            limit_val = "حداقل ۱ حرکت ایمن و منطبق با تجهیزات"
            exact_description_fa = (
                "تمپلیت تمرینی جلسه دارای اسلات الزامی برای یک الگوی حرکتی خاص است، "
                "اما به دلیل تلاقی برچسب‌های آسیب یا تجهیزات محدود، هیچ تمرین مجازی در کاتالوگ برای پر کردن این اسلات وجود ندارد."
            )
            engine_repair_hint_fa = "انعطاف‌پذیر کردن اسلات‌های اجباری در session_builder.py هنگام تجهیزات خانگی/آسیب‌دیدگی یا گسترش کاتالوگ حرکات جایگزین."
            rule_file = "app/workouts/program_engine/session_builder.py"
            rule_func = "build_sessions()"
            failing_phase = "required_slot_resolution"
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
            non_generic = [
                r for r in collected_reasons
                if r not in ("PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED", "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED", "UNSATISFIED_CONSTRAINT")
            ]
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
            if r != root_cause and r not in secondary_causes and r not in (
                "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED", "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED"
            ):
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


def analyze_bodyweight_template_failure(error: BodyweightTemplateBuildError) -> dict[str, Any]:
    code = error.code
    template_slug = error.template_slug
    exercise_slug = error.exercise_slug or "نامشخص"
    reasons = list(error.rejection_reason_codes)

    if code == "BODYWEIGHT_PULL_UP_BAR_REQUIRED":
        exact_description_fa = (
            f"تمپلیت ثابت '{template_slug}' برای حرکت '{exercise_slug}' نیازمند میله بارفیکس است "
            f"اما این وسیله در تجهیزات کاربر وجود ندارد."
        )
        hint = "اطمینان از وجود تجهیزات میله بارفیکس در پروفایل کاربر برای اجرای حرکات کششی عمودی."
        failing_phase = "bodyweight_equipment_check"
    elif code == "BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE":
        reasons_str = "، ".join(reasons) if reasons else "تداخل با محدودیت‌های پزشکی"
        exact_description_fa = (
            f"حرکت '{exercise_slug}' در تمپلیت ثابت '{template_slug}' با محدودیت‌ها و آسیب‌های کاربر "
            f"تداخل دارد ({reasons_str}) و حرکت جایگزین بدون نقض ساختار ثابت قابل تامین نیست."
        )
        hint = "بررسی علت تداخل آسیب یا ارائه تمپلیت سازگار بدون آسیب برای تمرینات خانگی."
        failing_phase = "bodyweight_exercise_eligibility"
    elif code == "PROGRAM_REJECTED_SAFETY_STATUS":
        exact_description_fa = f"تمپلیت ثابت '{template_slug}' به دلیل تشخیص ریسک پزشکی کاربر متوقف شد."
        hint = "بررسی غربالگری پزشکی و ارجاع کاربر به پزشک متخصص."
        failing_phase = "safety_screening"
    else:
        exact_description_fa = f"تمپلیت ثابت '{template_slug}' با خطای '{code}' مواجه شد."
        hint = "بررسی قوانین ساخت تمپلیت ثابت وزن بدن در bodyweight_template_builder.py."
        failing_phase = "bodyweight_template_build"

    return {
        "final_error_code": code,
        "all_errors": reasons or [code],
        "root_cause": code,
        "secondary_causes": [r for r in reasons if r != code],
        "rule_file": "app/workouts/bodyweight_template_builder.py",
        "rule_func": "build_bodyweight_template_program()",
        "actual_val": f"حرکت {exercise_slug}",
        "limit_val": "انطباق کامل با کاتالوگ و شرایط پزشکی",
        "failing_phase": failing_phase,
        "exact_description_fa": exact_description_fa,
        "engine_repair_hint_fa": hint,
    }


def format_program_days(
    prog: WorkoutProgram,
    exercise_map: dict[UUID, Exercise],
) -> list[dict[str, Any]]:
    days_data = []
    for day in prog.weekly_schedule:
        main_mins = calculate_main_training_minutes(day)
        ex_list = []
        for it in day.exercises:
            ex_db = exercise_map.get(it.exercise_id)
            if ex_db is not None:
                name_fa = getattr(ex_db, "name_fa", None) or (ex_db.get("name_fa") if isinstance(ex_db, dict) else None) or it.exercise_name
                name_en = getattr(ex_db, "name_en", None) or (ex_db.get("name_en") if isinstance(ex_db, dict) else None) or it.exercise_name
            else:
                name_fa = it.exercise_name
                name_en = it.exercise_name
            ex_list.append({
                "order": it.order,
                "name_fa": name_fa,
                "name_en": name_en,
                "sets": it.sets,
                "prescription_mode": it.prescription_mode.value if hasattr(it.prescription_mode, "value") else str(it.prescription_mode),
                "rep_min": it.rep_min,
                "rep_max": it.rep_max,
                "duration_min_seconds": it.duration_min_seconds,
                "duration_max_seconds": it.duration_max_seconds,
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
    return days_data


def evaluate_single_profile(
    spec: ProfileSpec,
    catalog: tuple[ExerciseCandidate, ...],
    references: tuple[TemplateReference, ...],
    exercise_map: dict[UUID, Exercise],
    ruleset: ProgramRuleset = RULESET,
) -> dict[str, Any]:
    req = profile_to_request(spec)
    equipment = req.available_equipment

    # Stage 1: Safety Screening check
    normalized = normalize_request(req, ruleset)
    safety_assessment = screen_safety(normalized)
    if safety_assessment.status not in {SafetyStatus.CLEAR, SafetyStatus.CLEAR_WITH_MODIFICATIONS}:
        # Intentional product-level safety refusal prior to generation
        return {
            "profile_id": spec.profile_id,
            "seed": spec.seed,
            "profile": spec.to_dict(),
            "result_class": "UNSUPPORTED",
            "unsupported_subtype": "EXPECTED_SAFETY_REJECTION",
            "generation_path": "safety_rejection",
            "template_slug": None,
            "final_error_code": "PROGRAM_REJECTED_SAFETY_STATUS",
            "root_cause": "EXPECTED_SAFETY_REJECTION",
            "secondary_causes": list(safety_assessment.reason_codes),
            "safety_status": safety_assessment.status.value,
            "split_type": None,
            "days_count": 0,
            "exercise_count_per_day": [],
            "estimated_session_duration": [],
            "failure_info": {
                "final_error_code": "PROGRAM_REJECTED_SAFETY_STATUS",
                "all_errors": list(safety_assessment.reason_codes),
                "root_cause": "EXPECTED_SAFETY_REJECTION",
                "secondary_causes": [],
                "rule_file": "app/workouts/program_engine/safety.py",
                "rule_func": "screen_safety()",
                "actual_val": safety_assessment.status.value,
                "limit_val": "CLEAR / CLEAR_WITH_MODIFICATIONS",
                "failing_phase": "safety_screening",
                "exact_description_fa": f"ارجاع پزشکی به دلیل وضعیت ریسک پزشکی ({safety_assessment.status.value}) و رد پیش از صدور برنامه طبق قرارداد ایمنی فیتشو.",
                "engine_repair_hint_fa": "این حالت رفتار عمدی و مورد انتظار سیستم ایمنی است و نباید نقص موتور قلمداد شود.",
            },
            "program_days": [],
            "warnings": [],
        }

    # Stage 2: Fixed Bodyweight Route Decision
    bw_decision = resolve_fixed_bodyweight_route(
        spec.training_location,
        equipment,
        spec.experience_level,
        spec.training_days_per_week,
    )

    if bw_decision.is_bodyweight_route:
        generation_path = "bodyweight_fixed_template"

        if bw_decision.status is BodyweightRoutingStatus.UNSUPPORTED_LEVEL:
            return {
                "profile_id": spec.profile_id,
                "seed": spec.seed,
                "profile": spec.to_dict(),
                "result_class": "UNSUPPORTED",
                "unsupported_subtype": "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED",
                "generation_path": "compatibility_rejection",
                "template_slug": None,
                "final_error_code": bw_decision.error_code or BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED,
                "root_cause": "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED",
                "secondary_causes": [],
                "safety_status": safety_assessment.status.value,
                "split_type": None,
                "days_count": 0,
                "exercise_count_per_day": [],
                "estimated_session_duration": [],
                "failure_info": {
                    "final_error_code": bw_decision.error_code or BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED,
                    "all_errors": [bw_decision.error_code or BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED],
                    "root_cause": "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED",
                    "secondary_causes": [],
                    "rule_file": "app/workouts/bodyweight_routing.py",
                    "rule_func": "resolve_fixed_bodyweight_route()",
                    "actual_val": f"سطح سابقه {spec.experience_level.value}",
                    "limit_val": "تنها سطوح ماه اول و مبتدی برای تمرین فقط با وزن بدن",
                    "failing_phase": "bodyweight_route_screening",
                    "exact_description_fa": "تمرین با وزن بدن در منزل برای سطوح متوسط و پیشرفته در قرارداد محصول فیتشو پشتیبانی نمی‌شود.",
                    "engine_repair_hint_fa": "این رد عمدی و طبق قرارداد محصول است.",
                },
                "program_days": [],
                "warnings": [],
            }

        if bw_decision.status is BodyweightRoutingStatus.UNSUPPORTED_DAYS:
            return {
                "profile_id": spec.profile_id,
                "seed": spec.seed,
                "profile": spec.to_dict(),
                "result_class": "UNSUPPORTED",
                "unsupported_subtype": "BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED",
                "generation_path": "compatibility_rejection",
                "template_slug": None,
                "final_error_code": bw_decision.error_code or BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED,
                "root_cause": "BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED",
                "secondary_causes": [],
                "safety_status": safety_assessment.status.value,
                "split_type": None,
                "days_count": 0,
                "exercise_count_per_day": [],
                "estimated_session_duration": [],
                "failure_info": {
                    "final_error_code": bw_decision.error_code or BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED,
                    "all_errors": [bw_decision.error_code or BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED],
                    "root_cause": "BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED",
                    "secondary_causes": [],
                    "rule_file": "app/workouts/bodyweight_routing.py",
                    "rule_func": "resolve_fixed_bodyweight_route()",
                    "actual_val": f"{spec.training_days_per_week} روز در هفته",
                    "limit_val": "۲ الی ۴ روز برای تمپلیت‌های ثابت وزن بدن",
                    "failing_phase": "bodyweight_route_screening",
                    "exact_description_fa": f"تعداد روزهای درخواستی ({spec.training_days_per_week} روز) برای تمرین وزن بدن خارج از تمپلیت‌های ۲، ۳ و ۴ روزه است.",
                    "engine_repair_hint_fa": "این رد عمدی و طبق قرارداد محصول است.",
                },
                "program_days": [],
                "warnings": [],
            }

        # Fixed template resolution
        template = get_bodyweight_template(spec.experience_level, spec.training_days_per_week)
        if template is None:
            return {
                "profile_id": spec.profile_id,
                "seed": spec.seed,
                "profile": spec.to_dict(),
                "result_class": "FAILED",
                "unsupported_subtype": None,
                "generation_path": generation_path,
                "template_slug": bw_decision.template_slug,
                "final_error_code": "BODYWEIGHT_TEMPLATE_NOT_FOUND",
                "root_cause": "BODYWEIGHT_TEMPLATE_NOT_FOUND",
                "secondary_causes": [],
                "safety_status": safety_assessment.status.value,
                "split_type": None,
                "days_count": 0,
                "exercise_count_per_day": [],
                "estimated_session_duration": [],
                "failure_info": {
                    "final_error_code": "BODYWEIGHT_TEMPLATE_NOT_FOUND",
                    "all_errors": ["BODYWEIGHT_TEMPLATE_NOT_FOUND"],
                    "root_cause": "BODYWEIGHT_TEMPLATE_NOT_FOUND",
                    "secondary_causes": [],
                    "rule_file": "app/workouts/bodyweight_templates.py",
                    "rule_func": "get_bodyweight_template()",
                    "actual_val": f"{spec.experience_level.value}:{spec.training_days_per_week}d",
                    "limit_val": "تمپلیت معتبر",
                    "failing_phase": "template_lookup",
                    "exact_description_fa": "تمپلیت ثابت ثبت‌شده‌ای برای این ترکیب روز و سطح سابقه یافت نشد.",
                    "engine_repair_hint_fa": "ثبت تمپلیت ثابت مناسب در کاتالوگ.",
                },
                "program_days": [],
                "warnings": [],
            }

        try:
            program = build_bodyweight_template_program(
                request=req,
                experience_level=spec.experience_level,
                template=template,
                exercise_catalog=catalog,
                ruleset=ruleset,
            )
            days_data = format_program_days(program, exercise_map)
            ex_counts = [len(d["exercises"]) for d in days_data]
            durations = [d["estimated_duration_minutes"] for d in days_data]
            return {
                "profile_id": spec.profile_id,
                "seed": spec.seed,
                "profile": spec.to_dict(),
                "result_class": "SUCCESS",
                "unsupported_subtype": None,
                "generation_path": generation_path,
                "template_slug": template.slug,
                "final_error_code": None,
                "root_cause": None,
                "secondary_causes": [],
                "safety_status": safety_assessment.status.value,
                "split_type": template.split_type.value,
                "days_count": len(program.weekly_schedule),
                "exercise_count_per_day": ex_counts,
                "estimated_session_duration": durations,
                "failure_info": None,
                "program_days": days_data,
                "warnings": list(program.warnings),
            }
        except BodyweightTemplateBuildError as err:
            failure_info = analyze_bodyweight_template_failure(err)
            return {
                "profile_id": spec.profile_id,
                "seed": spec.seed,
                "profile": spec.to_dict(),
                "result_class": "FAILED",
                "unsupported_subtype": None,
                "generation_path": generation_path,
                "template_slug": template.slug,
                "final_error_code": failure_info["final_error_code"],
                "root_cause": failure_info["root_cause"],
                "secondary_causes": failure_info["secondary_causes"],
                "safety_status": safety_assessment.status.value,
                "split_type": template.split_type.value,
                "days_count": 0,
                "exercise_count_per_day": [],
                "estimated_session_duration": [],
                "failure_info": failure_info,
                "program_days": [],
                "warnings": [],
            }

    # Stage 3: Normal Program Engine Route
    generation_path = "program_engine"

    # Resistance training days compatibility check
    try:
        require_supported_resistance_training_days(
            spec.experience_level,
            spec.training_days_per_week,
        )
    except UnsupportedResistanceTrainingCombinationError as err:
        return {
            "profile_id": spec.profile_id,
            "seed": spec.seed,
            "profile": spec.to_dict(),
            "result_class": "UNSUPPORTED",
            "unsupported_subtype": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
            "generation_path": "compatibility_rejection",
            "template_slug": None,
            "final_error_code": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
            "root_cause": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
            "secondary_causes": [],
            "safety_status": safety_assessment.status.value,
            "split_type": None,
            "days_count": 0,
            "exercise_count_per_day": [],
            "estimated_session_duration": [],
            "failure_info": {
                "final_error_code": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
                "all_errors": [str(err)],
                "root_cause": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
                "secondary_causes": [],
                "rule_file": "app/profile/training_compatibility.py",
                "rule_func": "require_supported_resistance_training_days()",
                "actual_val": f"{spec.experience_level.value} با {spec.training_days_per_week} روز در هفته",
                "limit_val": "تطابق با ماتریس مجاز تمرین مقاومتی فیتشو",
                "failing_phase": "input_compatibility_validation",
                "exact_description_fa": f"سطح سابقه '{FA_TRANSLATIONS.get(spec.experience_level.value, spec.experience_level.value)}' با {spec.training_days_per_week} روز در هفته طبق ماتریس مجاز فیتشو ناسازگار است.",
                "engine_repair_hint_fa": "این رد عمدی و طبق قرارداد محصول است.",
            },
            "program_days": [],
            "warnings": [],
        }

    # Engine execution
    try:
        gen_result = generate_program(
            req,
            catalog,
            ruleset,
            reference_templates=references,
        )
    except Exception as e:
        return {
            "profile_id": spec.profile_id,
            "seed": spec.seed,
            "profile": spec.to_dict(),
            "result_class": "FAILED",
            "unsupported_subtype": None,
            "generation_path": generation_path,
            "template_slug": None,
            "final_error_code": "CRASH_EXCEPTION",
            "root_cause": "ENGINE_CRASH",
            "secondary_causes": [str(e)],
            "safety_status": safety_assessment.status.value,
            "split_type": None,
            "days_count": 0,
            "exercise_count_per_day": [],
            "estimated_session_duration": [],
            "failure_info": {
                "final_error_code": "CRASH_EXCEPTION",
                "all_errors": [str(e)],
                "root_cause": "ENGINE_CRASH",
                "secondary_causes": [],
                "rule_file": "engine.py",
                "rule_func": "generate_program()",
                "actual_val": "Crash",
                "limit_val": "Clean execution",
                "failing_phase": "exception",
                "exact_description_fa": f"خطای غیرمنتظره سیستمی رخ داد: {e}",
                "engine_repair_hint_fa": "بررسی باگ در engine.py.",
            },
            "program_days": [],
            "warnings": [],
        }

    if gen_result and gen_result.is_success and gen_result.program:
        prog: WorkoutProgram = gen_result.program
        days_data = format_program_days(prog, exercise_map)
        ex_counts = [len(d["exercises"]) for d in days_data]
        durations = [d["estimated_duration_minutes"] for d in days_data]
        return {
            "profile_id": spec.profile_id,
            "seed": spec.seed,
            "profile": spec.to_dict(),
            "result_class": "SUCCESS",
            "unsupported_subtype": None,
            "generation_path": generation_path,
            "template_slug": None,
            "final_error_code": None,
            "root_cause": None,
            "secondary_causes": [],
            "safety_status": safety_assessment.status.value,
            "split_type": prog.split.split_type.value,
            "days_count": len(prog.weekly_schedule),
            "exercise_count_per_day": ex_counts,
            "estimated_session_duration": durations,
            "failure_info": None,
            "program_days": days_data,
            "warnings": list(prog.warnings),
        }

    failure_info = analyze_program_engine_failure(gen_result, req)
    return {
        "profile_id": spec.profile_id,
        "seed": spec.seed,
        "profile": spec.to_dict(),
        "result_class": "FAILED",
        "unsupported_subtype": None,
        "generation_path": generation_path,
        "template_slug": None,
        "final_error_code": failure_info["final_error_code"],
        "root_cause": failure_info["root_cause"],
        "secondary_causes": failure_info["secondary_causes"],
        "safety_status": safety_assessment.status.value,
        "split_type": None,
        "days_count": 0,
        "exercise_count_per_day": [],
        "estimated_session_duration": [],
        "failure_info": failure_info,
        "program_days": [],
        "warnings": [],
    }
