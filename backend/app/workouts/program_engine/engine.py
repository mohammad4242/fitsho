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
    eligible_body_analysis_priorities,
)
from app.workouts.program_engine.cardio import add_cardio
from app.workouts.program_engine.coach_quality import build_coach_quality_metrics
from app.workouts.program_engine.duration_capacity import (
    SessionCapacity,
    build_session_capacity,
)
from app.workouts.program_engine.duration_policy import (
    calculate_resistance_minutes,
)
from app.workouts.program_engine.effective_volume import (
    calculate_effective_volume,
    complete_tracked_metrics,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import GenerationErrorCode, SafetyStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.progression import deload_policy, double_progression_policy
from app.workouts.program_engine.recovery import recovery_spacing_is_valid, repair_recovery_weekdays
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
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.session_builder import SessionConstructionError, build_sessions
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.session_structure import finalize_session_structure
from app.workouts.program_engine.split_selector import (
    rank_availability_aware_fallbacks,
    rank_split_candidates,
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
    template_rejection_trace: tuple[dict[str, object], ...] = template_selection_trace
    for ranking in template_selection.candidates:
        reference = ranking.template
        try:
            reference_build = build_template_sessions(
                normalized,
                reference,
                eligibility.eligible,
                ruleset,
                session_capacity=session_capacity,
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
            )
            if reference_result.is_success:
                return _append_successful_template_attempt(
                    reference_result,
                    _template_attempt_trace(ranking, status="succeeded"),
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
        )
        if result.is_success:
            return result
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
    metrics = _volume_metrics(
        days,
        volume,
        previous_volume,
        ruleset,
        request=normalized,
        relaxed_required_pattern_groups=relaxed_groups,
        relaxed_required_slots=relaxed_slots,
        repair_reason_codes=tuple(dict.fromkeys((*repair_reasons, *duration_repair_reasons))),
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
    program, report = _attach_coach_quality_metrics(program, request, normalized, report, ruleset)
    quality_metrics = build_coach_quality_metrics(program, request, report, ruleset)
    final_trace = trace + (
        {
            "stage": "final_construction",
            "status": "succeeded",
            "reason_codes": ("FINAL_CONSTRUCTION_SUCCEEDED",),
        },
        {"stage": "coach_quality", "metrics": quality_metrics},
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
    session_capacity: SessionCapacity,
    template_selection_trace: tuple[dict[str, object], ...],
) -> ProgramGenerationResult:
    split = SplitPlan(
        split_type=reference.split_type,
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
        session_capacity=session_capacity,
    )
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
    metrics = _volume_metrics(
        days,
        volume,
        previous_volume,
        ruleset,
        request=normalized,
        reference_template=reference.slug,
        repair_reason_codes=tuple(dict.fromkeys((*repair_reasons, *duration_repair_reasons))),
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
    program, report = _attach_coach_quality_metrics(program, request, normalized, report, ruleset)
    quality_metrics = build_coach_quality_metrics(program, request, report, ruleset)
    final_trace = trace + (
        {
            "stage": "final_construction",
            "status": "succeeded",
            "reason_codes": ("FINAL_CONSTRUCTION_SUCCEEDED",),
        },
        {"stage": "coach_quality", "metrics": quality_metrics},
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


def _attach_coach_quality_metrics(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    normalized: NormalizedProgramRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutProgram, ValidationReport]:
    quality = _coach_quality_metrics(program, request, normalized, report, ruleset)
    aggregate_metrics = {**program.aggregate_metrics, "coach_quality": quality}
    report = replace(report, metrics={**report.metrics, "coach_quality": quality})
    return replace(program, aggregate_metrics=aggregate_metrics), report


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


def _coach_quality_metrics(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    normalized: NormalizedProgramRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> dict[str, object]:
    trace_reason_codes = {
        code
        for entry in program.decision_trace
        for key in ("reason_codes", "reasons")
        for code in _string_sequence(entry.get(key))
    }
    ranges = program.aggregate_metrics.get("volume_ranges_by_muscle", {})
    hard_volume_exceeded = isinstance(ranges, dict) and any(
        isinstance(values, dict)
        and float(values.get("actual_effective_volume", 0))
        > float(values.get("effective_maximum_hard", ruleset.maximum_sets[program.training_status]))
        for values in ranges.values()
    )
    volume_fit = (
        "failed"
        if hard_volume_exceeded or "WEEKLY_MUSCLE_VOLUME_EXCEEDED" in report.errors
        else "constrained"
        if "WEEKLY_VOLUME_CONSTRAINED" in report.warnings
        or "VOLUME_REPAIR_SOFT_TARGET_REDUCED" in trace_reason_codes
        else "fit"
    )
    resistance_budget = request.session_duration_minutes
    # resistance_time_budget_fit: did every session stay within the resistance budget (+tolerance)?
    session_resistance_minutes = [
        calculate_resistance_minutes(day, ruleset.general_warmup_minutes)
        for day in program.weekly_schedule
    ]
    overrun_minutes = [max(0, m - resistance_budget) for m in session_resistance_minutes]
    resistance_time_budget_fit = all(m <= resistance_budget for m in session_resistance_minutes)
    utilization = [round(m / max(1, resistance_budget), 3) for m in session_resistance_minutes]
    duration_fit = (
        "fit"
        if resistance_time_budget_fit
        else "constrained"
        if "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS" in trace_reason_codes
        else "failed"
    )
    duration_constrained_quality = bool(
        trace_reason_codes.intersection(
            {
                "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
                "DURATION_REDUCTION_VIOLATED_MINIMUM_EXERCISE_FLOOR",
            }
        )
    )
    late_repair_class = "not_needed"
    if "SESSION_DURATION_REPAIR_APPLIED" in trace_reason_codes:
        # classify based on the repair trace
        duration_trace = next(
            (e for e in program.decision_trace if e.get("stage") == "session_duration"),
            {},
        )
        rc = duration_trace.get("repair_classification", "minor")
        late_repair_class = rc if isinstance(rc, str) else "minor"

    recovery_fit = (
        "fit" if recovery_spacing_is_valid(program.weekly_schedule, ruleset) else "failed"
    )
    priority_metrics_raw = program.aggregate_metrics.get("priority_metrics", {})
    priority_metrics = priority_metrics_raw if isinstance(priority_metrics_raw, dict) else {}
    explicit_priorities = tuple(request.priority_muscles)
    body_priorities = tuple(
        item.muscle for item in eligible_body_analysis_priorities(normalized, ruleset)
    )

    def satisfaction(muscles: tuple[MuscleGroup, ...]) -> str:
        statuses: list[str] = []
        for muscle in muscles:
            metric = priority_metrics.get(muscle.value, {})
            if not isinstance(metric, dict):
                continue
            status = metric.get("status")
            if status in {"satisfied", "partial"}:
                statuses.append(status)
        if not statuses:
            return "not_applicable"
        return "satisfied" if all(status == "satisfied" for status in statuses) else "partial"

    constraint_codes = {
        code
        for code in trace_reason_codes
        if any(marker in code for marker in ("CONSTRAIN", "CAP", "LIMIT", "UNSATISFIED", "REPAIR"))
    }
    substitution_count = sum(
        "TEMPLATE_SAFE_SUBSTITUTION" in item.reason_codes
        for day in program.weekly_schedule
        for item in day.exercises
    )
    has_template = isinstance(program.aggregate_metrics.get("reference_template"), str)
    template_preservation = (
        "preserved"
        if has_template
        and any(
            any(code.startswith("TEMPLATE_") for code in item.reason_codes)
            for day in program.weekly_schedule
            for item in day.exercises
        )
        else "not_applicable"
    )
    return {
        "template_preservation": template_preservation,
        "priority_target_satisfaction": satisfaction(explicit_priorities),
        "body_analysis_target_satisfaction": satisfaction(body_priorities),
        "volume_fit": volume_fit,
        "duration_fit": duration_fit,
        "recovery_fit": recovery_fit,
        "substitution_count": substitution_count,
        "constraint_count": len(constraint_codes),
        "hard_validation_status": "passed" if report.is_valid else "failed",
        # Phase 11.9 duration metrics
        "resistance_time_budget_fit": resistance_time_budget_fit,
        "resistance_time_utilization": utilization,
        "resistance_time_overrun_minutes": overrun_minutes,
        "duration_constrained_quality": duration_constrained_quality,
        "late_duration_repair_class": late_repair_class,
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
