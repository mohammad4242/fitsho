from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
    under_target_message_fa,
)
from app.workouts.program_engine.enums import SplitType
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ValidationReport,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.session_duration import SessionDurationRepairEvidence
from app.workouts.program_engine.session_feasibility import (
    SESSION_COUNT_OUT_OF_RANGE_REASON,
    SessionCountStatus,
    SessionFeasibilityEvidence,
    assess_session_count,
)

FINAL_GATE_SCHEMA_VERSION = "final_quality_gate_v1"
_COUNT_OUT_OF_RANGE_CODE = SESSION_COUNT_OUT_OF_RANGE_REASON
_FULL_BODY_SPLITS = frozenset(item for item in SplitType if item.value.startswith("full_body"))
_DURATION_CODES = frozenset(
    "SESSION_DURATION_UNDER_TARGET SESSION_DURATION_TARGET_UNSATISFIED "
    "SESSION_DURATION_EXCEEDED SESSION_DURATION_OVER_TARGET".split()
)
_DURATION_SOFT_CODES = frozenset({"SESSION_DURATION_UNDER_TARGET"})
_DURATION_HARD_CODES = _DURATION_CODES - _DURATION_SOFT_CODES
_DURATION_CONSTRAINTS = frozenset(
    "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS "
    "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD "
    "VOLUME_REDUCED_FOR_DURATION_CAPACITY DURATION_PLANNED_REDUCED_EXERCISE_COUNT".split()
)
_DURATION_OUTCOME_CODES = _DURATION_CODES


class FinalGateStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_CONSTRAINTS = "accepted_with_constraints"
    REJECTED = "rejected"


@dataclass(frozen=True)
class FinalGateResult:
    status: FinalGateStatus
    reason_codes: tuple[str, ...]
    constraint_reason_codes: tuple[str, ...]
    metrics: dict[str, object]
    validation_report: ValidationReport
    schema_version: str = FINAL_GATE_SCHEMA_VERSION

    @property
    def is_accepted(self) -> bool:
        return self.status is not FinalGateStatus.REJECTED

    def decision_trace(self) -> dict[str, object]:
        return {
            "stage": "final_quality_gate",
            "schema_version": self.schema_version,
            "status": self.status.value,
            "reason_codes": self.reason_codes,
            "constraint_reason_codes": self.constraint_reason_codes,
            "metrics": self.metrics,
            "checks": self.metrics["checks"],
        }


def evaluate_final_program(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> FinalGateResult:
    hard_validation_errors = tuple(
        code
        for code in report.errors
        if code not in _DURATION_SOFT_CODES and code != _COUNT_OUT_OF_RANGE_CODE
    )
    reasons = list(hard_validation_errors)
    constraints = [
        code
        for code in report.warnings
        if code not in _DURATION_OUTCOME_CODES and code != _COUNT_OUT_OF_RANGE_CODE
    ]
    checks: dict[str, object] = {
        "validation": {
            "status": "rejected" if hard_validation_errors else "passed",
            "reason_codes": hard_validation_errors,
            "warning_codes": report.warnings,
        },
        "duration": {"status": "passed", "reason_codes": (), "messages_fa": ()},
        "exercise_count": {"status": "passed", "reason_codes": ()},
        "coverage": {"status": "not_applicable", "reason_codes": ()},
        "recovery": {"status": "passed", "reason_codes": ()},
        "safety": {"status": "passed", "reason_codes": ()},
        "day_count": {"status": "passed", "reason_codes": ()},
    }

    duration_policy = get_session_duration_policy(request.session_duration_minutes)
    count_assessments = tuple(
        assess_session_count(
            day,
            requested_minutes=request.session_duration_minutes,
            ruleset=ruleset,
            evidence=_count_evidence_for_day(program, day),
        )
        for day in program.weekly_schedule
    )
    count_unproven_reasons = tuple(
        reason
        for assessment in count_assessments
        for reason in assessment.reason_codes
        if assessment.status is SessionCountStatus.UNPROVEN
    )
    constrained_count_reasons = tuple(
        reason
        for assessment in count_assessments
        for reason in assessment.reason_codes
        if assessment.status is SessionCountStatus.CONSTRAINED
    )
    if count_unproven_reasons:
        reasons.extend(count_unproven_reasons)
        checks["exercise_count"] = {
            "status": "rejected",
            "reason_codes": tuple(dict.fromkeys(count_unproven_reasons)),
        }
    elif constrained_count_reasons:
        constraints.extend(constrained_count_reasons)
        checks["exercise_count"] = {
            "status": "constrained",
            "reason_codes": tuple(dict.fromkeys(constrained_count_reasons)),
        }
    invariant_hard_duration_codes: list[str] = []
    for day in program.weekly_schedule:
        main_minutes = calculate_main_training_minutes(day)
        if duration_policy.exceeds_hard_maximum(main_minutes):
            invariant_hard_duration_codes.extend(
                (
                    "SESSION_DURATION_EXCEEDED",
                    "SESSION_DURATION_OVER_TARGET",
                    "SESSION_DURATION_TARGET_UNSATISFIED",
                )
            )
    under_target_messages = tuple(
        under_target_message_fa(calculate_main_training_minutes(day))
        for day in program.weekly_schedule
        if duration_policy.below_preferred_minimum(calculate_main_training_minutes(day))
    )
    soft_duration_codes = ("SESSION_DURATION_UNDER_TARGET",) if under_target_messages else ()
    hard_duration_codes = tuple(
        dict.fromkeys(
            code
            for code in (*report.errors, *report.warnings, *invariant_hard_duration_codes)
            if code in _DURATION_HARD_CODES
            and any(
                _duration_code_applies_to_day(code, day, request, ruleset)
                for day in program.weekly_schedule
            )
        )
    )
    duration_evidence_codes: set[str] = set()
    duration_evidence_complete = bool(hard_duration_codes)
    for duration_code in hard_duration_codes:
        affected_days = tuple(
            day
            for day in program.weekly_schedule
            if _duration_code_applies_to_day(duration_code, day, request, ruleset)
        )
        if not affected_days:
            duration_evidence_complete = False
            continue
        for day in affected_days:
            matching = _duration_evidence_for_day(program, day)
            if not any(
                _evidence_proves_duration_code(evidence, duration_code, day, request, ruleset)
                for evidence in matching
            ):
                duration_evidence_complete = False
                continue
            duration_evidence_codes.update(
                evidence_code
                for evidence in matching
                for evidence_code in evidence.reason_codes
                if evidence_code in _DURATION_CONSTRAINTS
            )
    duration_evidence = tuple(sorted(duration_evidence_codes))
    if hard_duration_codes:
        checks["duration"] = {
            "status": (
                "constrained"
                if (
                    duration_evidence
                    and duration_evidence_complete
                    and not hard_validation_errors
                    and not invariant_hard_duration_codes
                )
                else "rejected"
            ),
            "reason_codes": tuple(dict.fromkeys((*duration_evidence, *hard_duration_codes))),
            "messages_fa": under_target_messages,
        }
        if (
            hard_validation_errors
            or invariant_hard_duration_codes
            or not duration_evidence
            or not duration_evidence_complete
        ):
            reasons.extend(hard_duration_codes)
            if (
                not duration_evidence
                or not duration_evidence_complete
                or invariant_hard_duration_codes
            ):
                reasons.append("SESSION_DURATION_CONSTRAINT_UNEXPLAINED")
        else:
            constraints.extend(duration_evidence)
    elif soft_duration_codes:
        checks["duration"] = {
            "status": "warning",
            "reason_codes": soft_duration_codes,
            "messages_fa": under_target_messages,
        }

    coverage = _mapping(program.aggregate_metrics.get("weekly_coverage"))
    if program.split.split_type in _FULL_BODY_SPLITS or any(
        day.focus.startswith("full_body") for day in program.weekly_schedule
    ):
        if not coverage:
            reasons.append("WEEKLY_COVERAGE_EVIDENCE_MISSING")
            checks["coverage"] = {"status": "rejected", "reason_codes": reasons[-1:]}
        else:
            coverage_status = coverage.get("status")
            coverage_reasons = _string_values(coverage.get("reason_codes"))
            checks["coverage"] = {"status": coverage_status, "reason_codes": coverage_reasons}
            if coverage_status == "unsatisfied":
                reasons.extend((*coverage_reasons, "FULL_BODY_COVERAGE_UNSATISFIED"))
            elif coverage_status == "constrained":
                unavailable_patterns = tuple(
                    code.partition(":")[2]
                    for code in coverage_reasons
                    if code.startswith("FULL_BODY_PATTERN_UNAVAILABLE:")
                )
                if unavailable_patterns:
                    reasons.extend(
                        (
                            "REQUIRED_SLOT_HARD_IMPOSSIBILITY",
                            *(
                                f"REQUIRED_PATTERN_UNAVAILABLE:{item}"
                                for item in unavailable_patterns
                            ),
                        )
                    )
                elif _coverage_constraint_is_proven(coverage):
                    constraints.extend(coverage_reasons)
                else:
                    reasons.append("FULL_BODY_COVERAGE_CONSTRAINT_UNEXPLAINED")
            elif coverage_status != "satisfied":
                reasons.append("WEEKLY_COVERAGE_STATUS_UNEXPLAINED")

    expected_days = min(request.available_training_days, ruleset.max_resistance_days)
    if (
        len(program.weekly_schedule) != expected_days
        or len(program.split.day_focuses) != expected_days
    ):
        reasons.append("REQUESTED_TRAINING_DAYS_UNSATISFIED")
        checks["day_count"] = {"status": "rejected"}
    if "RECOVERY_SPACING_INVALID" in report.errors:
        reasons.append("RECOVERY_SPACING_INVALID")
        checks["recovery"] = {
            "status": "rejected",
            "reason_codes": ("RECOVERY_SPACING_INVALID",),
        }
    safety_errors = tuple(
        code
        for code in report.errors
        if code
        in {
            "SAFETY_STATUS_DISALLOWS_GENERATION",
            "BLOCKED_CAUTION_TAG_SELECTED",
            "UNAVAILABLE_EQUIPMENT_SELECTED",
        }
    )
    if safety_errors:
        reasons.extend(safety_errors)
        checks["safety"] = {"status": "rejected", "reason_codes": safety_errors}

    unique_reasons = tuple(dict.fromkeys(reasons))
    unique_constraints = tuple(dict.fromkeys(constraints))
    status = (
        FinalGateStatus.REJECTED
        if unique_reasons
        else FinalGateStatus.ACCEPTED_WITH_CONSTRAINTS
        if unique_constraints
        else FinalGateStatus.ACCEPTED
    )
    metrics: dict[str, object] = {
        "schema_version": FINAL_GATE_SCHEMA_VERSION,
        "status": status.value,
        "reason_codes": unique_reasons,
        "constraint_reason_codes": unique_constraints,
        "checks": checks,
    }
    return FinalGateResult(
        status=status,
        reason_codes=unique_reasons,
        constraint_reason_codes=unique_constraints,
        metrics=metrics,
        validation_report=report,
    )


def _coverage_constraint_is_proven(coverage: Mapping[str, object]) -> bool:
    reasons = set(_string_values(coverage.get("reason_codes"))) - {"FULL_BODY_COVERAGE_CONSTRAINED"}
    pattern_reasons = {
        reason.partition(":")[2]
        for reason in reasons
        if reason.startswith("FULL_BODY_PATTERN_UNAVAILABLE:")
    }
    muscle_reasons = {
        reason.partition(":")[2]
        for reason in reasons
        if reason.startswith("FULL_BODY_COVERAGE_UNAVAILABLE:")
    }
    expected = {
        *(f"FULL_BODY_PATTERN_UNAVAILABLE:{pattern}" for pattern in pattern_reasons),
        *(f"FULL_BODY_COVERAGE_UNAVAILABLE:{muscle}" for muscle in muscle_reasons),
    }
    if (
        not (pattern_reasons or muscle_reasons)
        or reasons != expected
        or pattern_reasons != set(_string_values(coverage.get("missing_patterns")))
        or muscle_reasons != set(_string_values(coverage.get("missing_major_muscles")))
    ):
        return False
    evidence = _mapping(coverage.get("availability_evidence"))
    return all(
        _mapping(_mapping(evidence.get(category)).get(name)).get("unavailable") is True
        for category, names in (("patterns", pattern_reasons), ("muscles", muscle_reasons))
        for name in names
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _duration_evidence_for_day(
    program: WorkoutProgram,
    day: WorkoutDay,
) -> tuple[SessionDurationRepairEvidence, ...]:
    matches: list[SessionDurationRepairEvidence] = []
    for entry in program.decision_trace:
        if entry.get("stage") != "session_duration":
            continue
        raw_evidence = entry.get("per_session_evidence")
        if not isinstance(raw_evidence, (tuple, list)):
            continue
        parsed = tuple(
            evidence
            for item in raw_evidence
            if (evidence := SessionDurationRepairEvidence.from_trace(item)) is not None
            and evidence.day_index == day.day_index
            and evidence.matches(day)
        )
        matches.extend(parsed)
    return tuple(matches) if len(matches) == 1 else ()


def _count_evidence_for_day(
    program: WorkoutProgram,
    day: WorkoutDay,
) -> SessionFeasibilityEvidence | None:
    matching = _duration_evidence_for_day(program, day)
    return matching[0].session_feasibility if len(matching) == 1 else None


def _evidence_proves_duration_code(
    evidence: SessionDurationRepairEvidence,
    duration_code: str,
    day: WorkoutDay,
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> bool:
    reasons = set(evidence.reason_codes)
    main_minutes = calculate_main_training_minutes(day)
    policy = get_session_duration_policy(request.session_duration_minutes)
    if duration_code in {
        "SESSION_DURATION_UNDER_TARGET",
    }:
        return duration_code in reasons and policy.below_preferred_minimum(main_minutes)
    if duration_code in {
        "SESSION_DURATION_EXCEEDED",
        "SESSION_DURATION_OVER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }:
        return duration_code in reasons and main_minutes > policy.maximum_minutes
    return False


def _duration_code_applies_to_day(
    duration_code: str,
    day: WorkoutDay,
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> bool:
    main_minutes = calculate_main_training_minutes(day)
    policy = get_session_duration_policy(request.session_duration_minutes)
    if duration_code == "SESSION_DURATION_UNDER_TARGET":
        return policy.below_preferred_minimum(main_minutes)
    if duration_code in {
        "SESSION_DURATION_EXCEEDED",
        "SESSION_DURATION_OVER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }:
        return main_minutes > policy.maximum_minutes
    return False
