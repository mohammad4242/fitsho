from collections import Counter
from dataclasses import replace

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.body_analysis import (
    applicable_body_analysis_influence,
    body_analysis_priority_muscles,
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
from app.workouts.program_engine.recovery import repair_recovery_weekdays
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
    WeeklyVolumePlan,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.session_builder import (
    CORE_PATTERNS,
    HINGE_PATTERNS,
    KNEE_PATTERNS,
    PULL_PATTERNS,
    PUSH_PATTERNS,
    SessionConstructionError,
    build_sessions,
)
from app.workouts.program_engine.split_selector import rank_split_candidates
from app.workouts.program_engine.template_selector import select_template_reference
from app.workouts.program_engine.template_sessions import (
    TemplateConstructionError,
    TemplateSessionBuild,
    apply_template_intent,
    build_template_sessions,
    template_resolution_trace,
)
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_history import (
    PreviousVolumeBaseline,
    derive_previous_volume_baseline,
)
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from app.workouts.program_engine.volume_repair import repair_weekly_volume

_RECOVERABLE_PATTERN_GROUPS = (
    PUSH_PATTERNS,
    PULL_PATTERNS,
    KNEE_PATTERNS,
    HINGE_PATTERNS,
    CORE_PATTERNS,
)


def _recoverable_required_pattern_groups(
    catalog: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...],
    eligible: tuple[ExerciseCandidate, ...],
    rejected: tuple[RejectedCandidate, ...],
) -> tuple[frozenset[MovementPattern], ...]:
    """Find required groups absent only because hard constraints rejected them."""
    eligible_patterns = {item.movement_pattern for item in eligible}
    rejected_by_id = {item.exercise_id: item.reason_codes for item in rejected}
    recoverable: list[frozenset[MovementPattern]] = []
    for group in _RECOVERABLE_PATTERN_GROUPS:
        if any(pattern in eligible_patterns for pattern in group):
            continue
        if any(
            candidate.movement_pattern in group
            and any(
                reason.startswith("EXERCISE_REJECTED_")
                for reason in rejected_by_id.get(candidate.id, ())
            )
            for candidate in catalog
        ):
            recoverable.append(group)
    return tuple(recoverable)


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
    previous_volume = derive_previous_volume_baseline(normalized.source.recent_training_history)
    reserve = cardio_reserve_minutes(normalized, eligibility.cardio_eligible, ruleset)
    relaxable_required_pattern_groups = _recoverable_required_pattern_groups(
        exercise_catalog,
        eligibility.eligible,
        eligibility.rejected,
    )
    template_rejection_trace: tuple[dict[str, object], ...] = ()
    reference = select_template_reference(
        normalized, eligibility.eligible, reference_templates, ruleset
    )
    if reference is not None:
        try:
            reference_build = build_template_sessions(
                normalized, reference, eligibility.eligible, ruleset
            )
            reference_result = _reference_program(
                request,
                normalized,
                safety.status,
                safety.reason_codes,
                eligibility.rejected,
                eligibility.eligible,
                eligibility.cardio_eligible,
                reference,
                reference_build,
                ruleset,
                previous_volume=previous_volume,
                cardio_reserve=reserve,
            )
            if reference_result.is_success:
                return reference_result
            template_rejection_trace = (
                {
                    "stage": "template_reference",
                    "selected": reference.slug,
                    "status": "rejected",
                    "reason_codes": reference_result.errors,
                    "decision_trace": reference_result.decision_trace,
                },
            )
        except TemplateConstructionError as exc:
            template_rejection_trace = (
                {
                    "stage": "template_reference",
                    "selected": reference.slug,
                    "status": "rejected",
                    "reason_codes": (
                        "INITIAL_TEMPLATE_REJECTED_UNFILLABLE",
                        *exc.reason_codes,
                    ),
                },
            )
    rejected_splits: list[dict[str, object]] = []
    collected_errors: list[str] = []
    for attempt_index, candidate in enumerate(rank_split_candidates(normalized, ruleset)):
        split = candidate
        if attempt_index:
            split = replace(
                candidate,
                reason_codes=candidate.reason_codes
                + ("SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE",),
            )
        result = _program_for_split(
            request,
            normalized,
            safety.status,
            safety.reason_codes,
            eligibility.rejected,
            eligibility.eligible,
            eligibility.cardio_eligible,
            split,
            ruleset,
            previous_volume=previous_volume,
            cardio_reserve=reserve,
            rejected_splits=tuple(rejected_splits),
            template_rejection_trace=template_rejection_trace,
            relaxable_required_pattern_groups=relaxable_required_pattern_groups,
        )
        if result.is_success:
            return result
        collected_errors.extend(result.errors)
        rejected_attempt: dict[str, object] = {
            "split": split.split_type.value,
            "day_focuses": split.day_focuses,
            "status": "rejected",
            "reason_codes": result.errors,
        }
        if result.decision_trace:
            rejected_attempt["decision_trace"] = result.decision_trace
        rejected_splits.append(rejected_attempt)
    errors = (
        "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",
        *tuple(dict.fromkeys(collected_errors)),
    )
    return ProgramGenerationResult(
        program=None,
        error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
        errors=errors,
        safety_status=safety.status,
        rejected_candidates=eligibility.rejected,
        decision_trace=(
            {
                "stage": "construction_recovery",
                "status": "exhausted",
                "attempts": tuple(rejected_splits),
                "reason_codes": errors,
            },
        ),
    )


def _program_for_split(
    request: ProgramGenerationRequest,
    normalized: NormalizedProgramRequest,
    safety_status: SafetyStatus,
    safety_reasons: tuple[str, ...],
    rejected: tuple[RejectedCandidate, ...],
    eligible: tuple[ExerciseCandidate, ...],
    cardio_eligible: tuple[ExerciseCandidate, ...],
    split: SplitPlan,
    ruleset: ProgramRuleset,
    *,
    previous_volume: PreviousVolumeBaseline,
    cardio_reserve: int,
    rejected_splits: tuple[dict[str, object], ...],
    template_rejection_trace: tuple[dict[str, object], ...],
    relaxable_required_pattern_groups: tuple[frozenset[MovementPattern], ...],
) -> ProgramGenerationResult:
    volume = plan_weekly_volume(normalized, split, ruleset, previous_volume=previous_volume)
    try:
        drafts = build_sessions(
            normalized,
            split,
            volume,
            eligible,
            ruleset,
            relaxable_required_pattern_groups=relaxable_required_pattern_groups,
        )
    except SessionConstructionError as exc:
        construction_trace: tuple[dict[str, object], ...] = template_rejection_trace + (
            {
                "stage": "session_construction",
                "status": "rejected",
                "split": split.split_type.value,
                "day_index": exc.day_index,
                "focus": exc.focus,
                "required_patterns": exc.patterns,
                "required_target_muscle": exc.target_muscle,
                "reason_codes": exc.reason_codes,
            },
        )
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN,
            errors=exc.reason_codes,
            safety_status=safety_status,
            rejected_candidates=rejected,
            decision_trace=construction_trace,
        )
    days = prescribe_sessions(
        normalized,
        drafts,
        volume,
        ruleset,
        cardio_reserve_minutes=cardio_reserve,
    )
    days, repair_reasons = repair_weekly_volume(
        days,
        normalized,
        volume,
        ruleset,
        candidates=eligible,
        cardio_reserve_minutes=cardio_reserve,
    )
    days = add_cardio(normalized, days, cardio_eligible, ruleset)
    split, days, recovery_repair_reasons = repair_recovery_weekdays(split, days, ruleset)
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises),
        ruleset,
    )
    direct = Counter(effective_volume.direct_sets_by_muscle)
    relaxed_groups = tuple(
        dict.fromkeys(group for draft in drafts for group in draft.relaxed_required_pattern_groups)
    )
    metrics = _volume_metrics(
        days,
        volume,
        previous_volume,
        ruleset,
        relaxed_required_pattern_groups=relaxed_groups,
    )
    body_trace = body_analysis_trace(normalized, ruleset)
    session_reasons = tuple(
        dict.fromkeys(reason for draft in drafts for reason in draft.reason_codes)
    )
    recovery_reasons = tuple(
        dict.fromkeys(
            (
                *(("SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE",) if rejected_splits else ()),
                *session_reasons,
                *recovery_repair_reasons,
            )
        )
    )
    trace: tuple[dict[str, object], ...] = template_rejection_trace + (
        {"stage": "normalization", "assumptions": normalized.assumptions},
        {"stage": "safety", "status": safety_status.value, "reasons": safety_reasons},
        {
            "stage": "eligibility",
            "eligible_count": len(eligible),
            "rejected_count": len(rejected),
        },
        *((body_trace,) if body_trace is not None else ()),
        {
            "stage": "construction_recovery",
            "status": "recovered" if recovery_reasons else "not_required",
            "selected_split": split.split_type.value,
            "rejected_splits": rejected_splits,
            "reason_codes": recovery_reasons,
            "session_reasons": tuple(
                {
                    "day_index": draft.day_index,
                    "focus": draft.focus,
                    "reason_codes": draft.reason_codes,
                }
                for draft in drafts
                if draft.reason_codes
            ),
        },
        {"stage": "split", "selected": split.split_type.value, "reasons": split.reason_codes},
        _volume_decision_trace(volume, previous_volume),
        {
            "stage": "volume_repair",
            "reasons": tuple(dict.fromkeys((*repair_reasons, *recovery_repair_reasons))),
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
            safety_status=safety_status,
            rejected_candidates=rejected,
            decision_trace=trace,
        )
    final_trace = trace + (
        {
            "stage": "final_construction",
            "status": "succeeded",
            "reason_codes": ("FINAL_CONSTRUCTION_SUCCEEDED",),
        },
    )
    report = replace(report, decision_trace=final_trace)
    program = replace(
        program,
        validation_report=report,
        warnings=report.warnings,
        decision_trace=final_trace,
    )
    return ProgramGenerationResult(
        program=program,
        safety_status=safety_status,
        rejected_candidates=rejected,
        decision_trace=final_trace,
    )


def _reference_program(
    request: ProgramGenerationRequest,
    normalized: NormalizedProgramRequest,
    safety_status: SafetyStatus,
    safety_reasons: tuple[str, ...],
    rejected: tuple[RejectedCandidate, ...],
    eligible: tuple[ExerciseCandidate, ...],
    cardio_eligible: tuple[ExerciseCandidate, ...],
    reference: TemplateReference,
    build: TemplateSessionBuild,
    ruleset: ProgramRuleset,
    *,
    previous_volume: PreviousVolumeBaseline,
    cardio_reserve: int,
) -> ProgramGenerationResult:
    split = SplitPlan(
        split_type=SplitType.BODY_PART_ROTATION,
        day_focuses=tuple(draft.focus for draft in build.drafts),
        weekdays=tuple(draft.weekday for draft in build.drafts if draft.weekday is not None),
        score=100,
        reason_codes=("TEMPLATE_REFERENCE_SELECTED",),
    )
    volume = plan_weekly_volume(
        normalized,
        split,
        ruleset,
        previous_volume=previous_volume,
        direct_exposure_counts=build.direct_exposure_counts(),
    )
    days = prescribe_sessions(
        normalized,
        build.drafts,
        volume,
        ruleset,
        cardio_reserve_minutes=cardio_reserve,
    )
    days = apply_template_intent(days, build)
    days, repair_reasons = repair_weekly_volume(
        days,
        normalized,
        volume,
        ruleset,
        candidates=eligible,
        cardio_reserve_minutes=cardio_reserve,
    )
    days = add_cardio(normalized, days, cardio_eligible, ruleset)
    split, days, recovery_repair_reasons = repair_recovery_weekdays(split, days, ruleset)
    metrics = _volume_metrics(
        days,
        volume,
        previous_volume,
        ruleset,
        reference_template=reference.slug,
    )
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises), ruleset
    )
    direct = Counter(effective_volume.direct_sets_by_muscle)
    body_trace = body_analysis_trace(normalized, ruleset)
    trace: tuple[dict[str, object], ...] = (
        {"stage": "normalization", "assumptions": normalized.assumptions},
        {"stage": "safety", "status": safety_status.value, "reasons": safety_reasons},
        {
            "stage": "eligibility",
            "eligible_count": len(eligible),
            "rejected_count": len(rejected),
        },
        *((body_trace,) if body_trace is not None else ()),
        {
            "stage": "template_reference",
            "selected": reference.slug,
            "status": "adapted",
            "focus_tags": reference.focus_tags,
            "intensity_methods": reference.intensity_methods,
        },
        template_resolution_trace(build, days),
        _volume_decision_trace(volume, previous_volume),
        {
            "stage": "volume_repair",
            "reasons": tuple(dict.fromkeys((*repair_reasons, *recovery_repair_reasons))),
            "weekly_direct_sets": dict(direct),
            "weekly_effective_sets": effective_volume.effective_sets_by_muscle,
        },
    )
    priority_muscles = normalized.source.priority_muscles | body_analysis_priority_muscles(
        normalized, ruleset
    )
    unmet_priorities = tuple(
        muscle
        for muscle in sorted(priority_muscles, key=lambda item: item.value)
        if direct[muscle.value] < volume.minimum_direct_sets_for(muscle)
        or effective_volume.effective_sets_by_muscle.get(muscle.value, 0)
        < volume.effective_target_for(muscle)
    )
    if unmet_priorities:
        errors = tuple(
            f"TEMPLATE_PRIORITY_VOLUME_UNSATISFIED:{muscle.value}" for muscle in unmet_priorities
        )
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
            errors=errors,
            safety_status=safety_status,
            rejected_candidates=rejected,
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
            decision_trace=trace,
        )
    final_trace = trace + (
        {
            "stage": "final_construction",
            "status": "succeeded",
            "reason_codes": ("FINAL_CONSTRUCTION_SUCCEEDED",),
        },
    )
    report = replace(report, decision_trace=final_trace)
    return ProgramGenerationResult(
        program=replace(
            program,
            validation_report=report,
            warnings=report.warnings,
            decision_trace=final_trace,
        ),
        safety_status=safety_status,
        rejected_candidates=rejected,
        decision_trace=final_trace,
    )


def _volume_metrics(
    days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan,
    previous_volume: PreviousVolumeBaseline,
    ruleset: ProgramRuleset,
    *,
    reference_template: str | None = None,
    relaxed_required_pattern_groups: tuple[tuple[MovementPattern, ...], ...] = (),
) -> dict[str, object]:
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises), ruleset
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
                "minimum_effective_sets": target.minimum_effective_sets,
                "minimum_coverage_required": target.minimum_coverage_required,
                "direct_minimum_required": target.direct_minimum_required,
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
                muscle.value: sets for muscle, sets in previous_volume.direct_sets_by_muscle.items()
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
    if reference_template is not None:
        metrics["reference_template"] = reference_template
    if relaxed_required_pattern_groups:
        relaxed_group_values = tuple(
            tuple(pattern.value for pattern in group) for group in relaxed_required_pattern_groups
        )
        metrics["relaxed_required_pattern_groups"] = relaxed_group_values
        knee_group = tuple(
            pattern.value for pattern in sorted(KNEE_PATTERNS, key=lambda item: item.value)
        )
        if knee_group in relaxed_group_values:
            metrics["unavailable_muscle_coverage"] = (MuscleGroup.QUADRICEPS.value,)
    return metrics


def _volume_decision_trace(
    volume: WeeklyVolumePlan,
    previous_volume: PreviousVolumeBaseline,
) -> dict[str, object]:
    return {
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
        "minimum_effective_coverage": {
            target.muscle.value: target.minimum_effective_sets
            for target in volume.targets
            if target.minimum_coverage_required
        },
        "direct_minimum_required_muscles": tuple(
            target.muscle.value for target in volume.targets if target.direct_minimum_required
        ),
    }
