from collections import Counter, defaultdict
from dataclasses import replace

from app.workouts.program_engine.cardio import add_cardio, cardio_reserve_minutes
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import GenerationErrorCode, SafetyStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.progression import deload_policy, double_progression_policy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import screen_safety
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgramGenerationRequest,
    ProgramGenerationResult,
    ValidationReport,
    WorkoutProgram,
)
from app.workouts.program_engine.session_builder import build_sessions
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from app.workouts.program_engine.volume_repair import repair_weekly_volume


def generate_program(
    request: ProgramGenerationRequest,
    exercise_catalog: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> ProgramGenerationResult:
    normalized = normalize_request(request, ruleset)
    safety = screen_safety(normalized)
    if safety.status not in {SafetyStatus.CLEAR, SafetyStatus.CLEAR_WITH_MODIFICATIONS}:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.PROGRAM_REJECTED_SAFETY_STATUS,
            errors=safety.reason_codes,
            safety_status=safety.status,
        )
    eligibility = filter_eligible_exercises(normalized, exercise_catalog)
    if not eligibility.eligible:
        missing_equipment = any(
            "EXERCISE_REJECTED_MISSING_EQUIPMENT" in item.reason_codes
            for item in eligibility.rejected
        )
        return ProgramGenerationResult(
            program=None,
            error_code=(
                GenerationErrorCode.NO_AVAILABLE_EQUIPMENT_MATCH
                if missing_equipment
                else GenerationErrorCode.INSUFFICIENT_ELIGIBLE_EXERCISES
            ),
            errors=("NO_ELIGIBLE_EXERCISES",),
            safety_status=safety.status,
            rejected_candidates=eligibility.rejected,
        )
    split = select_split(normalized, ruleset)
    volume = plan_weekly_volume(normalized, split, ruleset)
    try:
        drafts = build_sessions(normalized, split, volume, eligibility.eligible, ruleset)
    except ValueError as exc:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN,
            errors=(str(exc),),
            safety_status=safety.status,
            rejected_candidates=eligibility.rejected,
        )
    reserve = cardio_reserve_minutes(normalized, eligibility.eligible, ruleset)
    days = prescribe_sessions(
        normalized,
        drafts,
        volume,
        ruleset,
        cardio_reserve_minutes=reserve,
    )
    days = add_cardio(normalized, days, eligibility.eligible, ruleset)
    days, repair_reasons = repair_weekly_volume(days, normalized, volume, ruleset)
    direct: Counter[str] = Counter()
    fractional: defaultdict[str, float] = defaultdict(float)
    for day in days:
        for item in day.exercises:
            if item.primary_muscle is not None:
                direct[item.primary_muscle.value] += item.sets
            for muscle in item.secondary_muscles:
                fractional[muscle.value] += item.sets * ruleset.secondary_set_credit
    metrics: dict[str, object] = {
        "planned_direct_sets_by_muscle": {
            target.muscle.value: target.direct_sets for target in volume.targets
        },
        "volume_ranges_by_muscle": {
            target.muscle.value: {
                "minimum_soft": target.minimum_soft,
                "target_sets": target.target_sets,
                "maximum_soft": target.maximum_soft,
                "maximum_hard": target.maximum_hard,
            }
            for target in volume.targets
        },
        "weekly_direct_sets_by_muscle": dict(direct),
        "weekly_fractional_sets_by_muscle": dict(fractional),
        "weekly_cardio_minutes": sum(
            day.cardio.duration_minutes for day in days if day.cardio is not None
        ),
        "estimated_weekly_duration": sum(day.estimated_duration_minutes for day in days),
        "hard_training_days": len(days),
        "recovery_days": ruleset.days_per_week - len(days),
    }
    trace: tuple[dict[str, object], ...] = (
        {"stage": "normalization", "assumptions": normalized.assumptions},
        {"stage": "safety", "status": safety.status.value, "reasons": safety.reason_codes},
        {"stage": "split", "selected": split.split_type.value, "reasons": split.reason_codes},
        {"stage": "volume", "reasons": volume.reason_codes},
        {"stage": "volume_repair", "reasons": repair_reasons},
        {
            "stage": "eligibility",
            "eligible_count": len(eligibility.eligible),
            "rejected_count": len(eligibility.rejected),
        },
    )
    empty_report = ValidationReport(
        errors=(),
        warnings=(),
        assumptions=normalized.assumptions,
        metrics=metrics,
        decision_trace=trace,
    )
    program = WorkoutProgram(
        user_profile_snapshot=request.model_dump(mode="json"),
        engine_version=ruleset.engine_version,
        ruleset_version=ruleset.version,
        seed=normalized.seed,
        primary_goal=normalized.primary_goal,
        secondary_goal=request.secondary_goal_optional,
        training_status=normalized.training_status,
        safety_status=safety.status,
        assumptions=normalized.assumptions,
        warnings=(),
        duration_weeks=request.program_duration_weeks,
        split=split,
        weekly_schedule=days,
        progression_policy={
            **double_progression_policy(ruleset),
            "deload": deload_policy(ruleset),
        },
        validation_report=empty_report,
        aggregate_metrics=metrics,
        decision_trace=trace,
    )
    report = validate_program(program, request, ruleset)
    if not report.is_valid:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.PROGRAM_VALIDATION_FAILED,
            errors=report.errors,
            safety_status=safety.status,
            rejected_candidates=eligibility.rejected,
        )
    program = replace(program, validation_report=report, warnings=report.warnings)
    return ProgramGenerationResult(
        program=program,
        safety_status=safety.status,
        rejected_candidates=eligibility.rejected,
    )
