from collections.abc import Mapping, Sequence

from app.workouts.program_engine.duration_policy import calculate_resistance_minutes
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ValidationReport,
    WorkoutProgram,
)


def build_coach_quality_metrics(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> dict[str, object]:
    priority_metrics = _mapping(program.aggregate_metrics.get("priority_metrics"))
    explicit = frozenset(muscle.value for muscle in request.priority_muscles)
    body_analysis = frozenset(str(key) for key in priority_metrics) - explicit
    return {
        "template_preservation": _template_preservation(program.decision_trace),
        "priority_target_satisfaction": _target_satisfaction(priority_metrics, explicit),
        "body_analysis_target_satisfaction": _target_satisfaction(priority_metrics, body_analysis),
        "volume_fit": _volume_fit(program.aggregate_metrics),
        "duration_fit": _duration_fit(program, request, report, ruleset),
        "coverage_fit": metric_status(program.aggregate_metrics.get("weekly_coverage")),
        "recovery_fit": _ratio(
            1.0 if recovery_spacing_is_valid(program.weekly_schedule, ruleset) else 0.0,
            1.0,
        ),
        "substitution_count": _substitution_count(program.decision_trace),
        "constraint_count": len(report.warnings),
        "hard_validation_status": report.status.value,
    }


def _template_preservation(trace: Sequence[Mapping[str, object]]) -> dict[str, object]:
    entry = next((item for item in trace if item.get("stage") == "template_adaptation"), None)
    if entry is None:
        return _ratio(0.0, 0.0)
    return _ratio(
        _number(entry.get("retained_template_slot_count")),
        _number(entry.get("template_slot_count")),
    )


def _target_satisfaction(
    metrics: Mapping[str, object], muscles: frozenset[str]
) -> dict[str, object]:
    satisfied = 0.0
    total = 0.0
    for muscle in sorted(muscles):
        metric = _mapping(metrics.get(muscle))
        target = _number(metric.get("effective_target_sets"))
        actual = _number(metric.get("effective_sets"))
        if target <= 0:
            continue
        total += target
        satisfied += min(max(actual, 0.0), target)
    return _ratio(satisfied, total)


def _volume_fit(metrics: Mapping[str, object]) -> dict[str, object]:
    ranges = _mapping(metrics.get("volume_ranges_by_muscle"))
    satisfied = 0.0
    total = 0.0
    for muscle in sorted(str(key) for key in ranges):
        values = _mapping(ranges.get(muscle))
        actual = _number(values.get("actual_effective_volume"))
        minimum = _number(values.get("acceptable_minimum"))
        maximum = _number(values.get("acceptable_maximum"))
        total += 1
        if minimum <= actual <= maximum:
            satisfied += 1
    return _ratio(satisfied, total)


def _duration_fit(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> dict[str, object]:
    budget = request.session_duration_minutes
    satisfied = 0.0
    for day in program.weekly_schedule:
        workout_minutes = calculate_resistance_minutes(
            day,
            ruleset.general_warmup_minutes,
        )
        if workout_minutes <= budget:
            satisfied += 1
    return _ratio(satisfied, float(len(program.weekly_schedule)))


def _substitution_count(trace: Sequence[Mapping[str, object]]) -> int:
    entry = next((item for item in trace if item.get("stage") == "template_adaptation"), None)
    substitutions = entry.get("substitutions") if entry is not None else None
    return len(substitutions) if isinstance(substitutions, (tuple, list)) else 0


def _ratio(satisfied: float, total: float) -> dict[str, object]:
    return {
        "satisfied": round(satisfied, 1),
        "total": round(total, 1),
        "percentage": round(satisfied / total * 100, 1) if total > 0 else None,
    }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def metric_status(value: object) -> str:
    status = _mapping(value).get("status")
    return status if isinstance(status, str) else "not_applicable"


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
