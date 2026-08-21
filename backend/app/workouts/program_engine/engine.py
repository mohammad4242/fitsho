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
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
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
    SHOULDER_PATTERNS,
    SessionConstructionError,
    build_sessions,
)
from app.workouts.program_engine.session_duration import repair_session_durations
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
    SHOULDER_PATTERNS,
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
    requested_days = normalized.resistance_training_days
    ranked_splits = rank_split_candidates(normalized, ruleset)
    exact_day_splits = tuple(
        candidate for candidate in ranked_splits if len(candidate.day_focuses) == requested_days
    )
    if not exact_day_splits:
        collected_errors: list[str] = [
            "REQUESTED_TRAINING_DAYS_UNSATISFIED",
            "NO_EXACT_DAY_SPLIT_AVAILABLE",
        ]
        rejected_splits: list[dict[str, object]] = []
    else:
        rejected_splits = []
        collected_errors = []
    for attempt_index, candidate in enumerate(exact_day_splits):
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

    weekdays_fallback = (
        exact_day_splits[0].weekdays if exact_day_splits else tuple(range(requested_days))
    )
    dynamic_focuses: tuple[str, ...]
    if requested_days == 1:
        dynamic_focuses = ("full_body",)
    elif requested_days == 2:
        dynamic_focuses = ("upper", "lower")
    elif requested_days == 3:
        dynamic_focuses = ("upper", "lower", "full_body")
    elif requested_days == 4:
        dynamic_focuses = ("upper", "lower", "upper", "lower")
    elif requested_days == 5:
        dynamic_focuses = ("upper", "lower", "push", "pull", "legs")
    else:
        dynamic_focuses = (
            ("push", "pull", "legs") * (requested_days // 3)
            + ("upper", "lower") * ((requested_days % 3) // 2)
            + ("full_body",) * (requested_days % 3 % 2)
        )

    fallback_split = SplitPlan(
        split_type=SplitType.DYNAMIC_FALLBACK,
        day_focuses=tuple(dynamic_focuses[:requested_days]),
        weekdays=weekdays_fallback,
        score=-1000,
        reason_codes=("DYNAMIC_EXACT_N_FALLBACK",),
    )
    result = _program_for_split(
        request,
        normalized,
        safety.status,
        safety.reason_codes,
        eligibility.rejected,
        eligibility.eligible,
        eligibility.cardio_eligible,
        fallback_split,
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
    errors = (
        "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",
        "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED",
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
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


def _rejected_split_recovery_reasons(
    rejected_splits: tuple[dict[str, object], ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for rejected_split in rejected_splits:
        decision_trace = rejected_split.get("decision_trace")
        if not isinstance(decision_trace, tuple):
            continue
        for entry in decision_trace:
            if not isinstance(entry, dict) or entry.get("stage") != "construction_recovery":
                continue
            reason_codes = entry.get("reason_codes")
            if isinstance(reason_codes, tuple):
                reasons.extend(code for code in reason_codes if isinstance(code, str))
    return tuple(dict.fromkeys(reasons))


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
    days, duration_repair_reasons = repair_session_durations(
        days, normalized, eligible, ruleset, volume=volume
    )
    split, days, recovery_repair_reasons = repair_recovery_weekdays(split, days, ruleset)
    day_count_errors = _day_count_errors(
        len(days), normalized.resistance_training_days, stage="dynamic_construction"
    )
    if day_count_errors:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
            errors=day_count_errors,
            safety_status=safety_status,
            rejected_candidates=rejected,
            decision_trace=template_rejection_trace
            + (
                {
                    "stage": "day_count_invariant",
                    "status": "rejected",
                    "expected_days": normalized.resistance_training_days,
                    "actual_days": len(days),
                    "split": split.split_type.value,
                    "reason_codes": day_count_errors,
                },
            ),
        )
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
        request=normalized,
        relaxed_required_pattern_groups=relaxed_groups,
        global_relaxable_groups=relaxable_required_pattern_groups,
    )
    body_trace = body_analysis_trace(normalized, ruleset)
    session_reasons = tuple(
        dict.fromkeys(reason for draft in drafts for reason in draft.reason_codes)
    )
    recovery_reasons = tuple(
        dict.fromkeys(
            (
                *(("SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE",) if rejected_splits else ()),
                *_rejected_split_recovery_reasons(rejected_splits),
                *session_reasons,
                *recovery_repair_reasons,
                *duration_repair_reasons,
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
        {
            "stage": "day_count_invariant",
            "status": "satisfied",
            "expected_days": normalized.resistance_training_days,
            "actual_days": len(days),
            "reason_codes": ("REQUESTED_TRAINING_DAYS_SATISFIED",),
        },
        {"stage": "split", "selected": split.split_type.value, "reasons": split.reason_codes},
        _volume_decision_trace(volume, previous_volume, normalized, ruleset),
        {
            "stage": "volume_repair",
            "reasons": tuple(dict.fromkeys((*repair_reasons, *recovery_repair_reasons))),
            "weekly_direct_sets": dict(direct),
            "weekly_effective_sets": effective_volume.effective_sets_by_muscle,
        },
        {
            "stage": "session_duration",
            "status": (
                "repaired"
                if "SESSION_DURATION_REPAIR_APPLIED" in duration_repair_reasons
                else "validated"
            ),
            "reason_codes": duration_repair_reasons,
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
        allow_soft_exercise_additions=False,
    )
    days = add_cardio(normalized, days, cardio_eligible, ruleset)
    days, duration_repair_reasons = repair_session_durations(
        days, normalized, eligible, ruleset, volume=volume
    )
    split, days, recovery_repair_reasons = repair_recovery_weekdays(split, days, ruleset)
    metrics = _volume_metrics(
        days,
        volume,
        previous_volume,
        ruleset,
        request=normalized,
        reference_template=reference.slug,
    )
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises), ruleset
    )
    direct = Counter(effective_volume.direct_sets_by_muscle)
    body_trace = body_analysis_trace(normalized, ruleset)
    day_count_errors = _day_count_errors(
        len(days), normalized.resistance_training_days, stage="template_construction"
    )
    day_count_trace: dict[str, object] = {
        "stage": "day_count_invariant",
        "status": "rejected" if day_count_errors else "satisfied",
        "expected_days": normalized.resistance_training_days,
        "actual_days": len(days),
        "split": split.split_type.value,
        "reason_codes": day_count_errors or ("REQUESTED_TRAINING_DAYS_SATISFIED",),
    }
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
        day_count_trace,
        _volume_decision_trace(volume, previous_volume, normalized, ruleset),
        {
            "stage": "volume_repair",
            "reasons": tuple(dict.fromkeys((*repair_reasons, *recovery_repair_reasons))),
            "weekly_direct_sets": dict(direct),
            "weekly_effective_sets": effective_volume.effective_sets_by_muscle,
        },
        {
            "stage": "session_duration",
            "status": (
                "repaired"
                if "SESSION_DURATION_REPAIR_APPLIED" in duration_repair_reasons
                else "validated"
            ),
            "reason_codes": duration_repair_reasons,
        },
    )
    if day_count_errors:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
            errors=day_count_errors,
            safety_status=safety_status,
            rejected_candidates=rejected,
            decision_trace=trace,
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


def _day_count_errors(actual: int, expected: int, *, stage: str) -> tuple[str, ...]:
    if actual == expected:
        return ()
    return (
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
        f"REQUESTED_TRAINING_DAYS_MISMATCH:expected={expected}:actual={actual}",
        f"DAY_COUNT_INVARIANT_FAILED:{stage}",
    )


def _volume_metrics(
    days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan,
    previous_volume: PreviousVolumeBaseline,
    ruleset: ProgramRuleset,
    *,
    request: NormalizedProgramRequest,
    reference_template: str | None = None,
    relaxed_required_pattern_groups: tuple[tuple[MovementPattern, ...], ...] = (),
    global_relaxable_groups: tuple[frozenset[MovementPattern], ...] = (),
) -> dict[str, object]:
    effective_volume = calculate_effective_volume(
        (item for day in days for item in day.exercises), ruleset
    )
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
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
        "priority_metrics": _priority_metrics(
            days,
            volume,
            effective_volume.direct_sets_by_muscle,
            effective_volume.effective_sets_by_muscle,
            priority_policy,
        ),
    }
    if reference_template is not None:
        metrics["reference_template"] = reference_template
    if relaxed_required_pattern_groups:
        relaxed_group_values = tuple(
            tuple(pattern.value for pattern in group) for group in relaxed_required_pattern_groups
        )
        metrics["relaxed_required_pattern_groups"] = relaxed_group_values

    if global_relaxable_groups:
        # Map each globally relaxable pattern group to the muscles whose coverage becomes
        # unavailable.
        # This prevents the validator from raising MINIMUM_MUSCLE_COVERAGE_UNSATISFIED
        # when the exercise pool simply cannot supply those movement patterns.
        _pattern_group_to_unavailable_muscles: dict[frozenset[MovementPattern], tuple[str, ...]] = {
            KNEE_PATTERNS: (MuscleGroup.QUADRICEPS.value,),
            PULL_PATTERNS: (MuscleGroup.BACK.value, MuscleGroup.BICEPS.value),
            PUSH_PATTERNS: (
                MuscleGroup.CHEST.value,
                MuscleGroup.SHOULDERS.value,
                MuscleGroup.TRICEPS.value,
            ),
            HINGE_PATTERNS: (MuscleGroup.HAMSTRINGS.value, MuscleGroup.GLUTES.value),
            CORE_PATTERNS: (MuscleGroup.ABS.value,),
            SHOULDER_PATTERNS: (MuscleGroup.SHOULDERS.value, MuscleGroup.TRAPS.value),
        }
        unavailable: list[str] = []
        for pattern_group, muscles in _pattern_group_to_unavailable_muscles.items():
            if pattern_group in global_relaxable_groups:
                unavailable.extend(muscles)
        if unavailable:
            metrics["unavailable_muscle_coverage"] = tuple(dict.fromkeys(unavailable))
    return metrics


def _priority_metrics(
    days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan,
    direct_sets: dict[str, int],
    effective_sets: dict[str, float],
    policy: PriorityAllocationPolicy,
) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {}
    for muscle in policy.priorities:
        session_indexes = tuple(
            day.day_index
            for day in days
            if any(
                item.primary_muscle is muscle and item.counts_toward_volume
                for item in day.exercises
            )
        )
        direct = direct_sets.get(muscle.value, 0)
        effective = effective_sets.get(muscle.value, 0.0)
        target = volume.direct_sets_for(muscle)
        effective_target = volume.effective_target_for(muscle)
        target_available = target > 0 or effective_target > 0
        direct_satisfied = target_available and direct >= volume.minimum_direct_sets_for(muscle)
        effective_satisfied = target_available and effective >= effective_target
        frequency_satisfied = len(session_indexes) >= policy.preferred_frequency
        status = (
            "satisfied"
            if direct_satisfied and effective_satisfied and frequency_satisfied
            else "partial"
        )
        reason_codes: list[str] = []
        if direct_satisfied and effective_satisfied:
            reason_codes.append("PRIORITY_VOLUME_INCREASED")
        else:
            reason_codes.append("PRIORITY_TARGET_PARTIALLY_SATISFIED")
        if frequency_satisfied and policy.preferred_frequency > 1:
            reason_codes.append("PRIORITY_FREQUENCY_INCREASED")
        else:
            reason_codes.append("PRIORITY_TARGET_CONSTRAINED")
        metrics[muscle.value] = {
            "direct_sets": direct,
            "effective_sets": effective,
            "target_sets": target,
            "effective_target_sets": effective_target,
            "preferred_frequency": policy.preferred_frequency,
            "session_frequency": len(session_indexes),
            "session_indexes": session_indexes,
            "distributed": frequency_satisfied,
            "status": status,
            "reason_codes": tuple(dict.fromkeys(reason_codes)),
        }
    return metrics


def _volume_decision_trace(
    volume: WeeklyVolumePlan,
    previous_volume: PreviousVolumeBaseline,
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> dict[str, object]:
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    return {
        "stage": "volume",
        "reasons": volume.reason_codes,
        "priority_muscles": tuple(muscle.value for muscle in priority_policy.priorities),
        "priority_preferred_frequency": priority_policy.preferred_frequency,
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
