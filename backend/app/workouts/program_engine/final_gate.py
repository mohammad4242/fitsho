from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.workouts.program_engine.duration_policy import (
    calculate_resistance_minutes,
    effective_main_exercise_floor,
    get_session_duration_policy,
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
from app.workouts.program_engine.supplemental_policy import main_exercise_count

FINAL_GATE_SCHEMA_VERSION = "final_quality_gate_v1"
_FULL_BODY_SPLITS = frozenset(item for item in SplitType if item.value.startswith("full_body"))
_DURATION_CODES = frozenset(
    "SESSION_EXERCISE_COUNT_OUT_OF_RANGE SESSION_DURATION_UNDER_TARGET "
    "SESSION_DURATION_TARGET_UNSATISFIED SESSION_DURATION_EXCEEDED "
    "SESSION_DURATION_OVER_TARGET".split()
)
_DURATION_CONSTRAINTS = frozenset(
    "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS "
    "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE "
    "VOLUME_REDUCED_FOR_DURATION_CAPACITY DURATION_PLANNED_REDUCED_EXERCISE_COUNT".split()
)
_DURATION_OUTCOME_CODES = frozenset(_DURATION_CODES - {"SESSION_EXERCISE_COUNT_OUT_OF_RANGE"})


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
    reasons = list(report.errors)
    constraints = [code for code in report.warnings if code not in _DURATION_OUTCOME_CODES]
    checks: dict[str, object] = {
        "validation": {
            "status": "rejected" if report.errors else "passed",
            "reason_codes": report.errors,
            "warning_codes": report.warnings,
        },
        "duration": {"status": "passed", "reason_codes": ()},
        "coverage": {"status": "not_applicable", "reason_codes": ()},
        "distribution": {"status": "missing", "reason_codes": ()},
        "recovery": {"status": "passed", "reason_codes": ()},
        "safety": {"status": "passed", "reason_codes": ()},
        "day_count": {"status": "passed", "reason_codes": ()},
    }

    duration_codes = tuple(
        code for code in (*report.errors, *report.warnings) if code in _DURATION_CODES
    )
    duration_evidence_codes: set[str] = set()
    duration_evidence_complete = bool(duration_codes)
    for duration_code in duration_codes:
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
    if duration_codes:
        checks["duration"] = {
            "status": (
                "constrained"
                if duration_evidence and duration_evidence_complete and not report.errors
                else "rejected"
            ),
            "reason_codes": tuple(dict.fromkeys((*duration_evidence, *duration_codes))),
        }
        if report.errors or not duration_evidence or not duration_evidence_complete:
            reasons.extend(duration_codes)
            if not duration_evidence or not duration_evidence_complete:
                reasons.append("SESSION_DURATION_CONSTRAINT_UNEXPLAINED")
        else:
            constraints.extend(duration_evidence)

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
                if _coverage_constraint_is_proven(coverage):
                    constraints.extend(coverage_reasons)
                else:
                    reasons.append("FULL_BODY_COVERAGE_CONSTRAINT_UNEXPLAINED")
            elif coverage_status != "satisfied":
                reasons.append("WEEKLY_COVERAGE_STATUS_UNEXPLAINED")

    distribution = _mapping(program.aggregate_metrics.get("weekly_distribution"))
    distribution_reasons = _string_values(distribution.get("reason_codes"))
    checks["distribution"] = {
        "status": distribution.get("status", "missing"),
        "reason_codes": distribution_reasons,
    }
    actual_counts = tuple(len(day.exercises) for day in program.weekly_schedule)
    raw_after_counts = distribution.get("after_exercise_counts")
    after_counts = (
        tuple(raw_after_counts)
        if isinstance(raw_after_counts, (tuple, list))
        and all(isinstance(item, int) for item in raw_after_counts)
        else ()
    )
    if not distribution:
        reasons.append("WEEKLY_DISTRIBUTION_EVIDENCE_MISSING")
    elif not after_counts:
        reasons.append("WEEKLY_DISTRIBUTION_EVIDENCE_INCOMPLETE")
    elif after_counts != actual_counts:
        reasons.append("WEEKLY_DISTRIBUTION_METRICS_STALE")
    elif distribution.get("status") == "constrained":
        if distribution_reasons == ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",):
            constraints.extend(distribution_reasons)
        else:
            reasons.append("WEEKLY_DISTRIBUTION_CONSTRAINT_UNEXPLAINED")
    elif distribution.get("status") == "unsatisfied":
        reasons.append("WEEKLY_DISTRIBUTION_UNSATISFIED")
    elif distribution.get("status") == "applied":
        if "WEEKLY_REDISTRIBUTION_APPLIED" not in distribution_reasons:
            reasons.append("WEEKLY_DISTRIBUTION_STATUS_UNEXPLAINED")
    elif distribution.get("status") == "not_needed":
        if "WEEKLY_REDISTRIBUTION_ALREADY_BALANCED" not in distribution_reasons:
            reasons.append("WEEKLY_DISTRIBUTION_STATUS_UNEXPLAINED")
    else:
        reasons.append("WEEKLY_DISTRIBUTION_STATUS_UNEXPLAINED")

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


def _evidence_proves_duration_code(
    evidence: SessionDurationRepairEvidence,
    duration_code: str,
    day: WorkoutDay,
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> bool:
    reasons = set(evidence.reason_codes)
    workout_duration = calculate_resistance_minutes(day, ruleset.general_warmup_minutes)
    policy = get_session_duration_policy(request.session_duration_minutes)
    exercise_count = main_exercise_count(day.exercises)
    floor = effective_main_exercise_floor(request.session_duration_minutes, ruleset)
    if duration_code in {
        "SESSION_DURATION_UNDER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }:
        return (
            duration_code in reasons
            and workout_duration < policy.minimum_minutes
            and exercise_count < floor
        )
    if duration_code == "SESSION_EXERCISE_COUNT_OUT_OF_RANGE":
        return bool(
            exercise_count < ruleset.minimum_exercises_per_session
            and reasons.intersection(
                {
                    "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
                    "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
                    "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
                }
            )
        )
    if duration_code in {"SESSION_DURATION_EXCEEDED", "SESSION_DURATION_OVER_TARGET"}:
        return (
            "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" in reasons
            and workout_duration > policy.maximum_minutes
        )
    return False


def _duration_code_applies_to_day(
    duration_code: str,
    day: WorkoutDay,
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> bool:
    workout_duration = calculate_resistance_minutes(day, ruleset.general_warmup_minutes)
    policy = get_session_duration_policy(request.session_duration_minutes)
    exercise_count = main_exercise_count(day.exercises)
    floor = effective_main_exercise_floor(request.session_duration_minutes, ruleset)
    if duration_code in {
        "SESSION_DURATION_UNDER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }:
        return workout_duration < policy.minimum_minutes and exercise_count < floor
    if duration_code in {"SESSION_DURATION_EXCEEDED", "SESSION_DURATION_OVER_TARGET"}:
        return workout_duration > policy.maximum_minutes
    if duration_code == "SESSION_EXERCISE_COUNT_OUT_OF_RANGE":
        return exercise_count < ruleset.minimum_exercises_per_session
    return False
