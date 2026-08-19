from collections import Counter
from dataclasses import replace

from app.workouts.program_engine.body_analysis import (
    applicable_body_analysis_influence,
    body_analysis_provenance,
    body_analysis_trace,
)
from app.workouts.program_engine.cardio import add_cardio, cardio_reserve_minutes
from app.workouts.program_engine.effective_volume import (
    calculate_effective_volume,
    complete_tracked_metrics,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import GenerationErrorCode, SafetyStatus, SplitType
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.progression import deload_policy, double_progression_policy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import screen_safety
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    ProgramGenerationResult,
    RejectedCandidate,
    SplitPlan,
    TemplateReference,
    ValidationReport,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.session_builder import build_sessions
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.template_selector import select_template_reference
from app.workouts.program_engine.template_sessions import build_template_sessions
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_history import derive_previous_volume_baseline
from app.workouts.program_engine.volume_planner import (
    SECONDARY_MUSCLES,
    TRACKED_MUSCLES,
    plan_weekly_volume,
)
from app.workouts.program_engine.volume_repair import repair_weekly_volume


def generate_program(
    request: ProgramGenerationRequest,
    exercise_catalog: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    reference_templates: tuple[TemplateReference, ...] = (),
) -> ProgramGenerationResult:
    request = request.model_copy(
        update={
            "body_analysis_influence": applicable_body_analysis_influence(
                request.body_analysis_influence, ruleset
            )
        }
    )
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
    reference = select_template_reference(
        normalized, eligibility.eligible, reference_templates, ruleset
    )
    if reference is not None:
        reference_days = build_template_sessions(
            normalized, reference, eligibility.eligible, ruleset
        )
        if reference_days is not None:
            reference_result = _reference_program(
                request,
                normalized,
                safety.status,
                safety.reason_codes,
                eligibility.rejected,
                len(eligibility.eligible),
                reference,
                reference_days,
                ruleset,
            )
            if reference_result.is_success:
                return reference_result
    split = select_split(normalized, ruleset)
    volume = plan_weekly_volume(normalized, split, ruleset)
    previous_volume = derive_previous_volume_baseline(normalized.source.recent_training_history)
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
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises),
        ruleset,
    )
    direct = Counter(effective_volume.direct_sets_by_muscle)
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
                "effective_maximum_soft": target.maximum_soft
                + round(target.maximum_soft * ruleset.secondary_set_credit),
                "effective_maximum_hard": target.maximum_hard
                + round(target.maximum_hard * ruleset.secondary_set_credit),
                "effective_target_sets": target.effective_target_sets,
                "minimum_direct_sets": target.minimum_direct_sets,
            }
            for target in volume.targets
        },
        "weekly_direct_sets_by_muscle": complete_tracked_metrics(dict(direct)),
        "weekly_fractional_sets_by_muscle": complete_tracked_metrics(
            effective_volume.secondary_sets_by_muscle
        ),
        "weekly_effective_sets_by_muscle": complete_tracked_metrics(
            effective_volume.effective_sets_by_muscle
        ),
        "previous_volume_baseline": {
            "direct_sets_by_muscle": {
                muscle.value: sets
                for muscle, sets in previous_volume.direct_sets_by_muscle.items()
            },
            "effective_sets_by_muscle": {
                muscle.value: sets
                for muscle, sets in previous_volume.effective_sets_by_muscle.items()
            },
            "confidence": previous_volume.confidence,
            "source": previous_volume.source,
            "reason_codes": previous_volume.reason_codes,
        },
        "weekly_cardio_minutes": sum(
            day.cardio.duration_minutes for day in days if day.cardio is not None
        ),
        "estimated_weekly_duration": sum(day.estimated_duration_minutes for day in days),
        "hard_training_days": len(days),
        "recovery_days": ruleset.days_per_week - len(days),
    }
    body_trace = body_analysis_trace(normalized, ruleset)
    trace: tuple[dict[str, object], ...] = (
        {"stage": "normalization", "assumptions": normalized.assumptions},
        {"stage": "safety", "status": safety.status.value, "reasons": safety.reason_codes},
        {
            "stage": "eligibility",
            "eligible_count": len(eligibility.eligible),
            "rejected_count": len(eligibility.rejected),
        },
        *((body_trace,) if body_trace is not None else ()),
        {"stage": "split", "selected": split.split_type.value, "reasons": split.reason_codes},
        {
            "stage": "volume",
            "reasons": volume.reason_codes,
            "previous_volume_baseline": {
                "confidence": previous_volume.confidence,
                "source": previous_volume.source,
                "reason_codes": previous_volume.reason_codes,
            },
            "effective_targets": {
                target.muscle.value: target.effective_target_sets for target in volume.targets
            },
            "minimum_direct_targets": {
                target.muscle.value: target.minimum_direct_sets for target in volume.targets
            },
        },
        {
            "stage": "volume_repair",
            "reasons": repair_reasons,
            "weekly_direct_sets": dict(direct),
            "weekly_effective_sets": effective_volume.effective_sets_by_muscle,
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
        body_analysis_provenance=body_analysis_provenance(normalized),
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


def _reference_program(
    request: ProgramGenerationRequest,
    normalized: NormalizedProgramRequest,
    safety_status: SafetyStatus,
    safety_reasons: tuple[str, ...],
    rejected: tuple[RejectedCandidate, ...],
    eligible_count: int,
    reference: TemplateReference,
    days: tuple[WorkoutDay, ...],
    ruleset: ProgramRuleset,
) -> ProgramGenerationResult:
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises),
        ruleset,
    )
    direct = Counter(effective_volume.direct_sets_by_muscle)
    split = SplitPlan(
        split_type=SplitType.BODY_PART_ROTATION,
        day_focuses=tuple(day.focus for day in days),
        weekdays=tuple(day.weekday for day in days if day.weekday is not None),
        score=100,
        reason_codes=("TEMPLATE_REFERENCE_SELECTED",),
    )
    metrics: dict[str, object] = {
        "reference_template": reference.slug,
        "reference_max_sets_per_muscle_per_session": (
            ruleset.template_reference_max_sets_per_muscle_per_session[normalized.training_status]
        ),
        "planned_direct_sets_by_muscle": complete_tracked_metrics(dict(direct)),
        "volume_ranges_by_muscle": _reference_volume_ranges(direct, normalized, ruleset),
        "weekly_direct_sets_by_muscle": complete_tracked_metrics(dict(direct)),
        "weekly_fractional_sets_by_muscle": complete_tracked_metrics(
            effective_volume.secondary_sets_by_muscle
        ),
        "weekly_effective_sets_by_muscle": complete_tracked_metrics(
            effective_volume.effective_sets_by_muscle
        ),
        "weekly_cardio_minutes": 0,
        "estimated_weekly_duration": sum(day.estimated_duration_minutes for day in days),
        "hard_training_days": len(days),
        "recovery_days": ruleset.days_per_week - len(days),
    }
    body_trace = body_analysis_trace(normalized, ruleset)
    trace: tuple[dict[str, object], ...] = (
        {"stage": "normalization", "assumptions": normalized.assumptions},
        {"stage": "safety", "status": safety_status.value, "reasons": safety_reasons},
        {
            "stage": "eligibility",
            "eligible_count": eligible_count,
            "rejected_count": len(rejected),
        },
        *((body_trace,) if body_trace is not None else ()),
        {"stage": "template_reference", "selected": reference.slug},
    )
    program = WorkoutProgram(
        user_profile_snapshot=request.model_dump(mode="json"),
        engine_version=ruleset.engine_version,
        ruleset_version=ruleset.version,
        seed=normalized.seed,
        primary_goal=normalized.primary_goal,
        secondary_goal=request.secondary_goal_optional,
        training_status=normalized.training_status,
        safety_status=safety_status,
        assumptions=normalized.assumptions,
        warnings=(),
        duration_weeks=request.program_duration_weeks,
        split=split,
        weekly_schedule=days,
        progression_policy={
            **double_progression_policy(ruleset),
            "deload": deload_policy(ruleset),
        },
        validation_report=ValidationReport((), (), normalized.assumptions, metrics, trace),
        aggregate_metrics=metrics,
        decision_trace=trace,
        body_analysis_provenance=body_analysis_provenance(normalized),
    )
    report = validate_program(program, request, ruleset)
    if not report.is_valid:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.PROGRAM_VALIDATION_FAILED,
            errors=report.errors,
            safety_status=safety_status,
            rejected_candidates=rejected,
        )
    return ProgramGenerationResult(
        program=replace(program, validation_report=report, warnings=report.warnings),
        safety_status=safety_status,
        rejected_candidates=rejected,
    )


def _reference_volume_ranges(
    direct: Counter[str],
    normalized: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> dict[str, dict[str, int]]:
    ranges: dict[str, dict[str, int]] = {}
    for muscle, sets in direct.items():
        muscle_enum = next(
            (tracked for tracked in TRACKED_MUSCLES if tracked.value == muscle),
            None,
        )
        maximum = (
            ruleset.secondary_muscle_maximum_sets[normalized.training_status]
            if muscle_enum in SECONDARY_MUSCLES
            else ruleset.maximum_sets[normalized.training_status]
        )
        ranges[muscle] = {
            "minimum_soft": min(sets, maximum),
            "target_sets": min(sets, maximum),
            "maximum_soft": maximum,
            "maximum_hard": maximum,
            "effective_maximum_soft": maximum,
            "effective_maximum_hard": maximum,
            "effective_target_sets": min(sets, maximum),
            "minimum_direct_sets": 0,
        }
    for muscle in TRACKED_MUSCLES:
        maximum = (
            ruleset.secondary_muscle_maximum_sets[normalized.training_status]
            if muscle in SECONDARY_MUSCLES
            else ruleset.maximum_sets[normalized.training_status]
        )
        ranges.setdefault(
            muscle.value,
            {
                "minimum_soft": 0,
                "target_sets": 0,
                "maximum_soft": maximum,
                "maximum_hard": maximum,
                "effective_maximum_soft": maximum,
                "effective_maximum_hard": maximum,
                "effective_target_sets": 0,
                "minimum_direct_sets": 0,
            },
        )
    return ranges
