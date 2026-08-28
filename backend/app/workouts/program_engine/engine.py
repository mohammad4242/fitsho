from collections import Counter
from dataclasses import replace

from app.exercises.enums import MovementPattern, MuscleGroup
from app.profile.enums import ExperienceLevel
from app.profile.training_compatibility import (
    SUPPORTED_RESISTANCE_TRAINING_DAYS,
    ResistanceTrainingDayStatus,
    resistance_training_day_status,
)
from app.workouts.program_engine.body_analysis import (
    applicable_body_analysis_influence,
    body_analysis_priority_muscles,
    body_analysis_provenance,
    body_analysis_trace,
)
from app.workouts.program_engine.cardio import add_cardio
from app.workouts.program_engine.coach_quality import build_coach_quality_metrics
from app.workouts.program_engine.duration_capacity import (
    SessionCapacity,
    build_session_capacity,
)
from app.workouts.program_engine.effective_volume import (
    calculate_effective_volume,
    complete_tracked_metrics,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import GenerationErrorCode, SafetyStatus, SplitType
from app.workouts.program_engine.final_gate import evaluate_final_program
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
    SessionDraft,
    SplitPlan,
    TemplateReference,
    ValidationReport,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.session_builder import SessionConstructionError, build_sessions
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.session_structure import finalize_session_structure
from app.workouts.program_engine.split_selector import (
    classify_template_region,
    rank_availability_aware_fallbacks,
    rank_split_candidates,
)
from app.workouts.program_engine.substitution_observability import (
    aggregate_substitution_observability,
    substitution_decision_summaries,
)
from app.workouts.program_engine.template_selector import (
    TemplateRankingResult,
    select_template_reference_result,
)
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
from app.workouts.program_engine.weekly_coverage import (
    assess_weekly_coverage,
    build_coverage_availability_evidence,
)
from app.workouts.program_engine.weekly_distribution import redistribute_weekly_exercises


def generate_program(
    request: ProgramGenerationRequest,
    exercise_catalog: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    reference_templates: tuple[TemplateReference, ...] = (),
) -> ProgramGenerationResult:
    training_day_error = _training_day_error(request, ruleset)
    if training_day_error is not None:
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.UNSUPPORTED_RESISTANCE_TRAINING_DAYS,
            errors=(training_day_error,),
        )
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
    session_capacity = build_session_capacity(
        normalized,
        eligibility.eligible,
        ruleset,
    )
    template_selection = select_template_reference_result(
        normalized,
        eligibility.eligible,
        reference_templates,
        ruleset,
        session_capacity=session_capacity,
    )
    template_selection_trace = (template_selection.decision_trace(),)
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
            decision_trace=template_selection_trace,
        )
    previous_volume = derive_previous_volume_baseline(normalized.source.recent_training_history)
    rejected_by_id = {item.exercise_id: item.reason_codes for item in eligibility.rejected}
    rejected_slot_candidates = tuple(
        (candidate, rejected_by_id[candidate.id])
        for candidate in exercise_catalog
        if candidate.id in rejected_by_id
    )
    coverage_availability_evidence = build_coverage_availability_evidence(
        eligibility.eligible,
        rejected_slot_candidates,
    )
    template_rejection_trace: tuple[dict[str, object], ...] = template_selection_trace
    validation_failed = False
    for ranking in template_selection.candidates:
        reference = ranking.template
        try:
            reference_build = build_template_sessions(
                normalized,
                reference,
                eligibility.eligible,
                ruleset,
                session_capacity=session_capacity,
                exercise_catalog=exercise_catalog,
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
                session_capacity=session_capacity,
                template_selection_trace=template_rejection_trace,
                coverage_availability_evidence=coverage_availability_evidence,
            )
            if reference_result.is_success:
                return _append_successful_template_attempt(
                    reference_result,
                    _template_attempt_trace(ranking, status="succeeded"),
                )
            validation_failed = validation_failed or (
                reference_result.error_code is GenerationErrorCode.PROGRAM_VALIDATION_FAILED
            )
            rejection_category = _template_rejection_category(reference_result.errors)
            rejection = {
                "stage": "template_reference",
                "rank": ranking.rank,
                "selected": reference.slug,
                "status": "rejected",
                "hard_eligibility": (
                    "days",
                    "training_level",
                    "core_slots_resolvable",
                ),
                "goal_used_for_exclusion": False,
                "score": ranking.decision_trace()["score"],
                "feasibility": ranking.feasibility.decision_trace(),
                "rejection_category": rejection_category,
                "reason_codes": reference_result.errors,
                "decision_trace": reference_result.decision_trace[len(template_rejection_trace) :],
            }
            template_rejection_trace += (
                rejection,
                _template_attempt_trace(
                    ranking,
                    status="rejected",
                    rejection_category=rejection_category,
                    reason_codes=reference_result.errors,
                ),
            )
        except TemplateConstructionError as exc:
            reason_codes = ("INITIAL_TEMPLATE_REJECTED_UNFILLABLE", *exc.reason_codes)
            rejection_category = _template_rejection_category(reason_codes)
            rejection = {
                "stage": "template_reference",
                "rank": ranking.rank,
                "selected": reference.slug,
                "status": "rejected",
                "hard_eligibility": (
                    "days",
                    "training_level",
                    "core_slots_resolvable",
                ),
                "goal_used_for_exclusion": False,
                "score": ranking.decision_trace()["score"],
                "feasibility": ranking.feasibility.decision_trace(),
                "rejection_category": rejection_category,
                "reason_codes": reason_codes,
            }
            template_rejection_trace += (
                rejection,
                _template_attempt_trace(
                    ranking,
                    status="rejected",
                    rejection_category=rejection_category,
                    reason_codes=reason_codes,
                ),
            )
    if template_selection.candidates:
        template_rejection_trace += (
            {
                "stage": "template_recovery",
                "status": "exhausted",
                "attempted_count": len(template_selection.candidates),
                "candidate_count": len(template_selection.candidates),
                "reason_codes": ("TEMPLATE_ALTERNATIVES_EXHAUSTED",),
            },
        )
    requested_days = normalized.resistance_training_days
    ranked_splits = rank_split_candidates(
        normalized,
        ruleset,
        exercises=eligibility.eligible,
        session_capacity=session_capacity,
    )
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
            session_capacity=session_capacity,
            rejected_splits=tuple(rejected_splits),
            template_rejection_trace=template_rejection_trace,
            rejected_slot_candidates=rejected_slot_candidates,
            coverage_availability_evidence=coverage_availability_evidence,
        )
        if result.is_success:
            return result
        validation_failed = validation_failed or (
            result.error_code is GenerationErrorCode.PROGRAM_VALIDATION_FAILED
        )
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
    dynamic_splits = rank_availability_aware_fallbacks(
        normalized,
        eligibility.eligible,
        ruleset,
        weekdays=weekdays_fallback,
        excluded_layouts=frozenset(candidate.day_focuses for candidate in exact_day_splits),
        session_capacity=session_capacity,
    )
    for fallback_split in dynamic_splits:
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
            session_capacity=session_capacity,
            rejected_splits=tuple(rejected_splits),
            template_rejection_trace=template_rejection_trace,
            rejected_slot_candidates=rejected_slot_candidates,
            coverage_availability_evidence=coverage_availability_evidence,
        )
        if result.is_success:
            return result
        validation_failed = validation_failed or (
            result.error_code is GenerationErrorCode.PROGRAM_VALIDATION_FAILED
        )
        collected_errors.extend(result.errors)
        rejected_splits.append(
            {
                "split": fallback_split.split_type.value,
                "day_focuses": fallback_split.day_focuses,
                "status": "rejected",
                "reason_codes": result.errors,
                "decision_trace": result.decision_trace,
            }
        )
    errors = (
        "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",
        "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED",
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
        *tuple(dict.fromkeys(collected_errors)),
    )
    return ProgramGenerationResult(
        program=None,
        error_code=(
            GenerationErrorCode.PROGRAM_VALIDATION_FAILED
            if validation_failed
            else GenerationErrorCode.UNSATISFIED_CONSTRAINT
        ),
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


def _template_rejection_category(reason_codes: tuple[str, ...]) -> str:
    joined = " ".join(reason_codes)
    if any(marker in joined for marker in ("CORE_SLOT", "REQUIRED_CORE")):
        return "CORE_SLOT_UNRESOLVED"
    if any(marker in joined for marker in ("SAFETY", "EQUIPMENT", "NO_ELIGIBLE")):
        return "SAFETY_EQUIPMENT_INCOMPATIBILITY"
    if "PRIORITY_HARD_MINIMUM" in joined:
        return "HARD_PRIORITY_MINIMUM_FAILURE"
    if any(marker in joined for marker in ("DURATION", "RECOVERY")):
        return "DURATION_RECOVERY_HARD_IMPOSSIBILITY"
    if any(
        marker in joined
        for marker in (
            "VALIDATION",
            "REQUIRED_MOVEMENT",
            "WEEKLY_MUSCLE_VOLUME",
            "PER_SESSION_MUSCLE_VOLUME",
            "REQUESTED_TRAINING_DAYS",
        )
    ):
        return "VALIDATION_FAILURE"
    return "ADAPTATION_EXHAUSTED"


def _template_attempt_trace(
    ranking: TemplateRankingResult,
    *,
    status: str,
    rejection_category: str | None = None,
    reason_codes: tuple[str, ...] = ("TEMPLATE_ATTEMPT_SUCCEEDED",),
) -> dict[str, object]:
    return {
        "stage": "template_attempt",
        "rank": ranking.rank,
        "slug": ranking.template.slug,
        "score": ranking.decision_trace()["score"],
        "feasibility": ranking.feasibility.decision_trace(),
        "scoring_reason_codes": ranking.reason_codes,
        "status": status,
        "rejection_category": rejection_category,
        "reason_codes": reason_codes,
    }


def _append_successful_template_attempt(
    result: ProgramGenerationResult,
    attempt_trace: dict[str, object],
) -> ProgramGenerationResult:
    if result.program is None:
        return result
    coach_index = next(
        (
            index
            for index, entry in enumerate(result.program.decision_trace)
            if entry.get("stage") == "final_construction"
        ),
        len(result.program.decision_trace),
    )
    final_trace = (
        result.program.decision_trace[:coach_index]
        + (attempt_trace,)
        + result.program.decision_trace[coach_index:]
    )
    report = replace(result.program.validation_report, decision_trace=final_trace)
    program = replace(
        result.program,
        validation_report=report,
        decision_trace=final_trace,
    )
    return replace(result, program=program, decision_trace=final_trace)


def _training_day_error(
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> str | None:
    requested_days = request.available_training_days
    if requested_days > SUPPORTED_RESISTANCE_TRAINING_DAYS[-1]:
        return "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"
    if requested_days < SUPPORTED_RESISTANCE_TRAINING_DAYS[0]:
        return None
    if requested_days > ruleset.max_resistance_days:
        return "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"
    experience_level = ExperienceLevel(request.training_experience.value)
    if (
        resistance_training_day_status(experience_level, requested_days)
        is ResistanceTrainingDayStatus.UNSUPPORTED
    ):
        return "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"
    return None


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
    session_capacity: SessionCapacity,
    rejected_splits: tuple[dict[str, object], ...],
    template_rejection_trace: tuple[dict[str, object], ...],
    rejected_slot_candidates: tuple[tuple[ExerciseCandidate, tuple[str, ...]], ...],
    coverage_availability_evidence: dict[str, object],
) -> ProgramGenerationResult:
    volume = plan_weekly_volume(
        normalized,
        split,
        ruleset,
        previous_volume=previous_volume,
        session_capacity=session_capacity,
    )
    try:
        drafts = build_sessions(
            normalized,
            split,
            volume,
            eligible,
            ruleset,
            rejected_slot_candidates=rejected_slot_candidates,
            session_capacity=session_capacity,
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
                "candidate_rejection_reasons": exc.rejection_reasons,
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
    substitution_decisions = [
        decision for draft in drafts for decision in draft.substitution_decisions
    ]
    days = prescribe_sessions(
        normalized,
        drafts,
        volume,
        ruleset,
    )
    days, repair_reasons = repair_weekly_volume(
        days,
        normalized,
        volume,
        ruleset,
        candidates=eligible,
        substitution_decisions=substitution_decisions,
    )
    days_before_duration_repair = days
    days, duration_repair_reasons = repair_session_durations(
        days,
        normalized,
        eligible,
        ruleset,
        volume=volume,
        session_capacity=session_capacity,
    )
    split, days, recovery_repair_reasons = repair_recovery_weekdays(split, days, ruleset)
    days = finalize_session_structure(days, normalized, ruleset)
    weekly_distribution = redistribute_weekly_exercises(days, normalized, ruleset)
    days = weekly_distribution.days
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
    structured_relaxed_groups = _structured_relaxed_pattern_groups(
        normalized,
        eligible,
        rejected_slot_candidates,
    )
    causal_structured_relaxed_groups = tuple(
        dict.fromkeys(
            group
            for draft in drafts
            if "REQUIRED_SLOT_RELAXED_FOR_STRUCTURED_LIMITATION" in draft.reason_codes
            for group in draft.relaxed_required_pattern_groups
        )
    )
    relaxed_groups = tuple(dict.fromkeys((*relaxed_groups, *structured_relaxed_groups)))
    relaxed_slots = tuple(
        dict.fromkeys(
            (group, target)
            for draft in drafts
            for group, target in zip(
                draft.relaxed_required_pattern_groups,
                draft.relaxed_required_target_muscles,
                strict=True,
            )
        )
    )
    substitution_metrics = aggregate_substitution_observability(substitution_decisions)
    metrics = {
        **_volume_metrics(
            days,
            volume,
            previous_volume,
            ruleset,
            request=normalized,
            relaxed_required_pattern_groups=relaxed_groups,
            relaxed_required_slots=relaxed_slots,
            repair_reason_codes=tuple(dict.fromkeys((*repair_reasons, *duration_repair_reasons))),
        ),
        **substitution_metrics,
        "weekly_distribution": weekly_distribution.metrics,
    }
    weekly_coverage = assess_weekly_coverage(
        days,
        metrics,
        ruleset=ruleset,
        availability_evidence=coverage_availability_evidence,
    )
    metrics["weekly_coverage"] = weekly_coverage.metrics
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
                *(
                    ("REQUIRED_PATTERN_RELAXED_FOR_STRUCTURED_LIMITATION",)
                    if causal_structured_relaxed_groups
                    else ()
                ),
                *(
                    ("PROGRAM_REBALANCED_TOWARD_SAFE_LOWER_BODY",)
                    if _has_structured_lower_body_rebalance(drafts, days)
                    else ()
                ),
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
        _duration_capacity_trace(session_capacity),
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
        _duration_repair_trace(
            session_capacity,
            days_before_duration_repair,
            days,
            duration_repair_reasons,
        ),
        {
            "stage": "session_structure",
            "status": "finalized",
            "reason_codes": ("FINAL_SESSION_SEQUENCE_APPLIED",),
        },
        {
            "stage": "weekly_coverage",
            "status": weekly_coverage.metrics["status"],
            "reason_codes": weekly_coverage.metrics["reason_codes"],
            "missing_patterns": weekly_coverage.metrics["missing_patterns"],
            "missing_major_muscles": weekly_coverage.metrics["missing_major_muscles"],
        },
        {
            "stage": "substitution_observability",
            "metrics": substitution_metrics,
            "decisions": substitution_decision_summaries(substitution_decisions),
        },
    )
    empty_report = ValidationReport(
        errors=(),
        warnings=(),
        assumptions=normalized.assumptions,
        metrics=metrics,
        decision_trace=trace,
    )
    days = add_cardio(normalized, days, cardio_eligible, ruleset)
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
    return _finalize_program(
        program,
        request,
        ruleset,
        safety_status=safety_status,
        rejected=rejected,
        trace=trace,
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
    session_capacity: SessionCapacity,
    template_selection_trace: tuple[dict[str, object], ...],
    coverage_availability_evidence: dict[str, object],
) -> ProgramGenerationResult:
    reference_focuses = tuple(_reference_split_focus(draft) for draft in build.drafts)
    split = SplitPlan(
        split_type=reference.split_type,
        day_focuses=reference_focuses,
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
        session_capacity=session_capacity,
    )
    substitution_decisions = [
        decision for draft in build.drafts for decision in draft.substitution_decisions
    ]
    days = prescribe_sessions(
        normalized,
        build.drafts,
        volume,
        ruleset,
    )
    days = apply_template_intent(days, build, ruleset)
    days, repair_reasons = repair_weekly_volume(
        days,
        normalized,
        volume,
        ruleset,
        candidates=eligible,
        allow_soft_exercise_additions=False,
        preserve_template_core_structure=True,
        substitution_decisions=substitution_decisions,
    )
    days_before_duration_repair = days
    days, duration_repair_reasons = repair_session_durations(
        days,
        normalized,
        eligible,
        ruleset,
        volume=volume,
        prefer_acceptable_volume_for_minimum_fill=True,
        session_capacity=session_capacity,
    )
    split, days, recovery_repair_reasons = repair_recovery_weekdays(split, days, ruleset)
    days = finalize_session_structure(days, normalized, ruleset)
    weekly_distribution = redistribute_weekly_exercises(
        days,
        normalized,
        ruleset,
        preserve_template_core_structure=True,
    )
    days = weekly_distribution.days
    substitution_metrics = aggregate_substitution_observability(substitution_decisions)
    metrics = {
        **_volume_metrics(
            days,
            volume,
            previous_volume,
            ruleset,
            request=normalized,
            reference_template=reference.slug,
            repair_reason_codes=tuple(dict.fromkeys((*repair_reasons, *duration_repair_reasons))),
        ),
        **substitution_metrics,
        "weekly_distribution": weekly_distribution.metrics,
    }
    weekly_coverage = assess_weekly_coverage(
        days,
        metrics,
        ruleset=ruleset,
        availability_evidence=coverage_availability_evidence,
        full_body_claim=reference.split_type is SplitType.FULL_BODY,
    )
    metrics["weekly_coverage"] = weekly_coverage.metrics
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
    trace: tuple[dict[str, object], ...] = template_selection_trace + (
        {"stage": "normalization", "assumptions": normalized.assumptions},
        {"stage": "safety", "status": safety_status.value, "reasons": safety_reasons},
        {
            "stage": "eligibility",
            "eligible_count": len(eligible),
            "rejected_count": len(rejected),
        },
        _duration_capacity_trace(session_capacity),
        *((body_trace,) if body_trace is not None else ()),
        {
            "stage": "template_reference",
            "selected": reference.slug,
            "status": "adapted",
            "hard_eligibility": (
                "days",
                "training_level",
                "core_slots_resolvable",
            ),
            "goal_used_for_exclusion": False,
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
        _duration_repair_trace(
            session_capacity,
            days_before_duration_repair,
            days,
            duration_repair_reasons,
        ),
        {
            "stage": "session_structure",
            "status": "finalized",
            "reason_codes": ("FINAL_SESSION_SEQUENCE_APPLIED",),
        },
        {
            "stage": "weekly_coverage",
            "status": weekly_coverage.metrics["status"],
            "reason_codes": weekly_coverage.metrics["reason_codes"],
            "missing_patterns": weekly_coverage.metrics["missing_patterns"],
            "missing_major_muscles": weekly_coverage.metrics["missing_major_muscles"],
        },
        {
            "stage": "substitution_observability",
            "metrics": substitution_metrics,
            "decisions": substitution_decision_summaries(substitution_decisions),
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
    explicit_priority_muscles = normalized.source.priority_muscles
    body_priority_muscles = body_analysis_priority_muscles(normalized, ruleset)
    targets_by_muscle = {target.muscle: target for target in volume.targets}
    unmet_priority_errors: list[str] = []
    for muscle in sorted(explicit_priority_muscles, key=lambda item: item.value):
        target = targets_by_muscle.get(muscle)
        if target is None:
            continue
        direct_value = direct[muscle.value]
        if target.direct_minimum_required and direct_value < target.minimum_direct_sets:
            unmet_priority_errors.append(
                f"TEMPLATE_PRIORITY_HARD_MINIMUM_UNSATISFIED:{muscle.value}"
            )
    if unmet_priority_errors:
        errors = tuple(unmet_priority_errors)
        return ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
            errors=errors,
            safety_status=safety_status,
            rejected_candidates=rejected,
            decision_trace=trace,
        )
    soft_priority_shortfalls = tuple(
        f"TEMPLATE_PRIORITY_PREFERRED_TARGET_PARTIAL:{muscle.value}"
        for muscle in sorted(
            explicit_priority_muscles | body_priority_muscles,
            key=lambda item: item.value,
        )
        if (target := targets_by_muscle.get(muscle))
        and (
            direct[muscle.value] < target.target_sets
            or effective_volume.effective_sets_by_muscle.get(muscle.value, 0)
            < target.effective_target_sets
        )
    )
    if soft_priority_shortfalls:
        trace += (
            {
                "stage": "template_priority_adaptation",
                "status": "constrained",
                "reason_codes": soft_priority_shortfalls,
            },
        )
    days = add_cardio(normalized, days, cardio_eligible, ruleset)
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
    return _finalize_program(
        program,
        request,
        ruleset,
        safety_status=safety_status,
        rejected=rejected,
        trace=trace,
    )


def _reference_split_focus(draft: SessionDraft) -> str:
    targets = set(draft.template_target_muscles)
    region = classify_template_region(targets)
    if region is not None:
        return region
    return draft.focus


def _structured_relaxed_pattern_groups(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    rejected_slot_candidates: tuple[tuple[ExerciseCandidate, tuple[str, ...]], ...],
) -> tuple[tuple[MovementPattern, ...], ...]:
    if not request.source.blocked_caution_tags:
        return ()
    required_groups = (
        frozenset({MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH}),
        frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}),
        frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}),
        frozenset({MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}),
    )
    eligible_patterns = {item.movement_pattern for item in eligible}
    blocked_pattern_groups = []
    for group in required_groups:
        if eligible_patterns.intersection(group):
            continue
        if any(
            item.movement_pattern in group and "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG" in reasons
            for item, reasons in rejected_slot_candidates
        ):
            blocked_pattern_groups.append(tuple(sorted(group, key=lambda item: item.value)))
    return tuple(blocked_pattern_groups)


def _has_structured_lower_body_rebalance(
    drafts: tuple[SessionDraft, ...],
    days: tuple[WorkoutDay, ...],
) -> bool:
    days_by_index = {day.day_index: day for day in days}
    lower_body_muscles = frozenset(
        {
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.GLUTES,
            MuscleGroup.CALVES,
        }
    )
    for draft in drafts:
        if (
            "REQUIRED_SLOT_RELAXED_FOR_STRUCTURED_LIMITATION" not in draft.reason_codes
            or not draft.relaxed_required_pattern_groups
        ):
            continue
        day = days_by_index.get(draft.day_index)
        if day is None:
            continue
        if any(
            item.primary_muscle in lower_body_muscles
            and all(
                item.movement_pattern not in relaxed_group
                for relaxed_group in draft.relaxed_required_pattern_groups
            )
            for item in day.exercises
        ):
            return True
    return False


def _day_count_errors(actual: int, expected: int, *, stage: str) -> tuple[str, ...]:
    if actual == expected:
        return ()
    return (
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
        f"REQUESTED_TRAINING_DAYS_MISMATCH:expected={expected}:actual={actual}",
        f"DAY_COUNT_INVARIANT_FAILED:{stage}",
    )


def _attach_coach_quality_metrics(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutProgram, ValidationReport]:
    quality = build_coach_quality_metrics(program, request, report, ruleset)
    aggregate_metrics = {**program.aggregate_metrics, "coach_quality": quality}
    report = replace(report, metrics={**report.metrics, "coach_quality": quality})
    return replace(program, aggregate_metrics=aggregate_metrics), report


def _finalize_program(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
    *,
    safety_status: SafetyStatus,
    rejected: tuple[RejectedCandidate, ...],
    trace: tuple[dict[str, object], ...],
) -> ProgramGenerationResult:
    report = validate_program(program, request, ruleset)
    program, report = _attach_coach_quality_metrics(program, request, report, ruleset)
    quality_metrics = program.aggregate_metrics["coach_quality"]
    construction_status = "succeeded" if report.is_valid else "rejected"
    construction_reason_codes = (
        ("FINAL_CONSTRUCTION_SUCCEEDED",) if report.is_valid else report.errors
    )
    pre_gate_trace = trace + (
        {
            "stage": "final_construction",
            "status": construction_status,
            "reason_codes": construction_reason_codes,
        },
        {"stage": "coach_quality", "metrics": quality_metrics},
    )
    report = replace(report, decision_trace=pre_gate_trace)
    program = replace(
        program,
        validation_report=report,
        warnings=report.warnings,
        decision_trace=pre_gate_trace,
    )
    gate = evaluate_final_program(program, request, report, ruleset)
    final_trace = pre_gate_trace + (gate.decision_trace(),)
    if not gate.is_accepted:
        error_code = (
            GenerationErrorCode.PROGRAM_VALIDATION_FAILED
            if gate.validation_report.errors
            else GenerationErrorCode.UNSATISFIED_CONSTRAINT
        )
        return ProgramGenerationResult(
            program=None,
            error_code=error_code,
            errors=gate.reason_codes,
            safety_status=safety_status,
            rejected_candidates=rejected,
            decision_trace=final_trace,
        )

    warnings = tuple(
        dict.fromkeys((*gate.validation_report.warnings, *gate.constraint_reason_codes))
    )
    final_metrics = {
        **gate.validation_report.metrics,
        "final_quality_gate": gate.metrics,
    }
    final_report = replace(
        gate.validation_report,
        warnings=warnings,
        metrics=final_metrics,
        decision_trace=final_trace,
    )
    final_program = replace(
        program,
        validation_report=final_report,
        aggregate_metrics={**program.aggregate_metrics, "final_quality_gate": gate.metrics},
        warnings=warnings,
        decision_trace=final_trace,
    )
    return ProgramGenerationResult(
        program=final_program,
        safety_status=safety_status,
        rejected_candidates=rejected,
        decision_trace=final_trace,
    )


def _duration_capacity_trace(capacity: SessionCapacity) -> dict[str, object]:
    return {
        "stage": "duration_capacity",
        "requested_workout_minutes": capacity.requested_workout_minutes,
        "target_total_minutes": capacity.target_total_minutes,
        "minimum_workout_minutes": capacity.minimum_workout_minutes,
        "maximum_workout_minutes": capacity.maximum_workout_minutes,
        "resistance_work_budget_minutes": capacity.resistance_work_budget_minutes,
        "minimum_resistance_work_minutes": capacity.minimum_resistance_work_minutes,
        "maximum_resistance_work_minutes": capacity.maximum_resistance_work_minutes,
        "expected_exercise_count_capacity": capacity.expected_exercise_count_capacity,
        "expected_working_set_capacity": capacity.expected_working_set_capacity,
        "reason_codes": ("DURATION_CAPACITY_PLANNED_BEFORE_CONSTRUCTION",),
    }


def _duration_repair_trace(
    capacity: SessionCapacity,
    before: tuple[WorkoutDay, ...],
    after: tuple[WorkoutDay, ...],
    reason_codes: tuple[str, ...],
) -> dict[str, object]:
    repair_applied = "SESSION_DURATION_REPAIR_APPLIED" in reason_codes
    duration_deltas = tuple(
        abs(updated.estimated_duration_minutes - original.estimated_duration_minutes)
        for original, updated in zip(before, after, strict=True)
    )
    exercise_deltas = tuple(
        abs(len(updated.exercises) - len(original.exercises))
        for original, updated in zip(before, after, strict=True)
    )
    if not repair_applied:
        classification = "not_needed"
    elif max(duration_deltas, default=0) <= 10 and max(exercise_deltas, default=0) <= 1:
        classification = "minor"
    else:
        classification = "major"
    unavoidable_constraints = tuple(
        code for code in reason_codes if "CONSTRAINED" in code or "EXTENDED" in code
    )
    return {
        "stage": "session_duration",
        "status": "repaired" if repair_applied else "validated",
        "planned_resistance_work_budget_minutes": capacity.resistance_work_budget_minutes,
        "planned_exercise_capacity": capacity.expected_exercise_count_capacity,
        "planned_set_capacity": capacity.expected_working_set_capacity,
        "estimated_duration_before_late_repair": tuple(
            day.estimated_duration_minutes for day in before
        ),
        "estimated_duration_after_late_repair": tuple(
            day.estimated_duration_minutes for day in after
        ),
        "repair_classification": classification,
        "unavoidable_duration_constraints": unavoidable_constraints,
        "reason_codes": reason_codes,
    }


def _volume_metrics(
    days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan,
    previous_volume: PreviousVolumeBaseline,
    ruleset: ProgramRuleset,
    *,
    request: NormalizedProgramRequest,
    reference_template: str | None = None,
    relaxed_required_pattern_groups: tuple[tuple[MovementPattern, ...], ...] = (),
    relaxed_required_slots: tuple[tuple[tuple[MovementPattern, ...], MuscleGroup | None], ...] = (),
    repair_reason_codes: tuple[str, ...] = (),
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
            target.muscle.value: _volume_range_metric(
                target,
                direct.get(target.muscle.value, 0),
                effective_volume.effective_sets_by_muscle.get(target.muscle.value, 0.0),
                days,
                repair_reason_codes,
            )
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
            ruleset,
        ),
    }
    if reference_template is not None:
        metrics["reference_template"] = reference_template
    if relaxed_required_pattern_groups:
        relaxed_group_values = tuple(
            tuple(pattern.value for pattern in group) for group in relaxed_required_pattern_groups
        )
        metrics["relaxed_required_pattern_groups"] = relaxed_group_values
        metrics["relaxed_required_slots"] = tuple(
            {
                "patterns": tuple(pattern.value for pattern in group),
                "target_muscle": target.value if target is not None else None,
            }
            for group, target in relaxed_required_slots
        )
        target_values: set[str] = set()
        pattern_muscles: dict[frozenset[MovementPattern], tuple[MuscleGroup, ...]] = {
            frozenset({MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH}): (
                MuscleGroup.CHEST,
                MuscleGroup.SHOULDERS,
                MuscleGroup.TRICEPS,
            ),
            frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}): (
                MuscleGroup.BACK,
                MuscleGroup.BICEPS,
            ),
            frozenset(
                {MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}
            ): (MuscleGroup.QUADRICEPS,),
            frozenset({MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}): (
                MuscleGroup.HAMSTRINGS,
                MuscleGroup.GLUTES,
            ),
            frozenset(
                {
                    MovementPattern.CORE_ANTI_EXTENSION,
                    MovementPattern.CORE_ANTI_ROTATION,
                    MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                }
            ): (MuscleGroup.ABS,),
        }
        for group, target in relaxed_required_slots:
            if target is None:
                target_values.update(
                    muscle.value for muscle in pattern_muscles.get(frozenset(group), ())
                )
        if target_values:
            metrics["unavailable_muscle_coverage"] = tuple(sorted(target_values))
            ranges = metrics["volume_ranges_by_muscle"]
            if isinstance(ranges, dict):
                for muscle in target_values:
                    values = ranges.get(muscle)
                    if not isinstance(values, dict):
                        continue
                    values["status"] = "constrained"
                    values["constraint_reason_codes"] = tuple(
                        dict.fromkeys(
                            (
                                *_string_sequence(values.get("constraint_reason_codes")),
                                "VOLUME_CONSTRAINED_BY_SAFETY_OR_EQUIPMENT",
                            )
                        )
                    )

    return metrics


def _volume_range_metric(
    target: VolumeTarget,
    actual_direct: int,
    actual_effective: float,
    days: tuple[WorkoutDay, ...],
    repair_reason_codes: tuple[str, ...],
) -> dict[str, object]:
    constraint_reasons = list(target.constraint_reason_codes)
    inside_range = target.acceptable_minimum <= actual_effective <= target.acceptable_maximum
    if not inside_range and set(repair_reason_codes).intersection(
        {
            "VOLUME_REPAIR_SOFT_TARGET_REDUCED",
            "VOLUME_REPAIR_HARD_MINIMUM_UNSATISFIED",
        }
    ):
        constraint_reasons.append("VOLUME_CONSTRAINED_BY_SESSION_FEASIBILITY")
    if not inside_range and any(
        "TEMPLATE_ADAPTATION_PRIORITY:core" in item.reason_codes
        and (item.primary_muscle is target.muscle or target.muscle in item.secondary_muscles)
        for day in days
        for item in day.exercises
    ):
        constraint_reasons.append("VOLUME_CONSTRAINED_BY_TEMPLATE_STRUCTURE")
    if actual_effective == target.preferred_target:
        status = "exact_target"
    elif inside_range:
        status = "within_flexible_range"
    elif constraint_reasons:
        status = "constrained"
    else:
        status = "outside_acceptable_range"
    return {
        "preferred_weekly_target": target.preferred_target,
        "acceptable_minimum": target.acceptable_minimum,
        "acceptable_maximum": target.acceptable_maximum,
        "actual_direct_volume": actual_direct,
        "actual_effective_volume": actual_effective,
        "status": status,
        "constraint_reason_codes": tuple(dict.fromkeys(constraint_reasons)),
        "minimum_soft": target.minimum_soft,
        "target_sets": target.target_sets,
        "maximum_soft": target.maximum_soft,
        "maximum_hard": target.maximum_hard,
        "effective_maximum_soft": target.acceptable_maximum,
        "effective_maximum_hard": target.maximum_hard,
        "effective_target_sets": target.effective_target_sets,
        "minimum_direct_sets": target.minimum_direct_sets,
        "minimum_effective_sets": target.minimum_effective_sets,
        "minimum_coverage_required": target.minimum_coverage_required,
        "direct_minimum_required": target.direct_minimum_required,
    }


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list, set, frozenset)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _priority_metrics(
    days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan,
    direct_sets: dict[str, int],
    effective_sets: dict[str, float],
    policy: PriorityAllocationPolicy,
    ruleset: ProgramRuleset,
) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {}
    for muscle in policy.priorities:
        session_indexes = tuple(
            day.day_index
            for day in days
            if any(item.primary_muscle is muscle for item in day.exercises)
        )
        direct = direct_sets.get(muscle.value, 0)
        effective = effective_sets.get(muscle.value, 0.0)
        target = volume.direct_sets_for(muscle)
        effective_target = volume.effective_target_for(muscle)
        target_available = target > 0 or effective_target > 0
        direct_satisfied = target_available and direct >= target
        effective_satisfied = target_available and effective >= effective_target
        useful_frequency = policy.useful_frequency(target, ruleset)
        frequency_satisfied = len(session_indexes) >= useful_frequency
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
        if frequency_satisfied and useful_frequency > 1:
            reason_codes.append("PRIORITY_FREQUENCY_INCREASED")
        else:
            reason_codes.append("PRIORITY_TARGET_CONSTRAINED")
        metrics[muscle.value] = {
            "direct_sets": direct,
            "effective_sets": effective,
            "target_sets": target,
            "effective_target_sets": effective_target,
            "preferred_frequency": useful_frequency,
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
