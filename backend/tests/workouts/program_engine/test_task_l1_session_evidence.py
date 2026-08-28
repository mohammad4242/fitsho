import os
import subprocess
import sys
from dataclasses import replace

from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.final_gate import evaluate_final_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport
from app.workouts.program_engine.session_duration import SessionDurationRepairEvidence
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request
from tests.workouts.program_engine.test_template_reference import (
    _four_day_reference,
    template_request,
)


def _program(days: int = 2):
    result = generate_program(request(available_training_days=days), full_catalog(), RULESET)
    assert result.program is not None, result.errors
    return result.program


def _duration_trace(program, evidence):
    return tuple(
        {**entry, "per_session_evidence": evidence}
        if entry.get("stage") == "session_duration"
        else entry
        for entry in program.decision_trace
    )


def test_duration_evidence_is_emitted_for_dynamic_and_template_programs() -> None:
    template_result = generate_program(
        template_request(available_training_days=4),
        full_catalog(),
        RULESET,
        reference_templates=(_four_day_reference(),),
    )
    for program in (_program(), template_result.program):
        assert program is not None
        entry = next(item for item in program.decision_trace if item["stage"] == "session_duration")
        evidence = entry["per_session_evidence"]
        assert len(evidence) == len(program.weekly_schedule)
        assert {item["day_index"] for item in evidence} == {
            day.day_index for day in program.weekly_schedule
        }


def test_duration_constraint_cannot_cross_excuse_another_day() -> None:
    program = _program()
    first, second = program.weekly_schedule
    first_evidence = SessionDurationRepairEvidence.from_day(
        first,
        ("SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",),
    )
    shortened = replace(
        second,
        exercises=second.exercises[:1],
        estimated_duration_minutes=(
            second.exercises[0].estimated_minutes + RULESET.general_warmup_minutes
        ),
    )
    altered = replace(
        program,
        weekly_schedule=(first, shortened),
        decision_trace=_duration_trace(program, (first_evidence.as_trace(),)),
    )

    report = validate_program(altered, request(available_training_days=2), RULESET)

    assert "SESSION_DURATION_UNDER_TARGET" in report.errors


def test_duration_evidence_must_match_the_exact_day_fingerprint() -> None:
    program = _program()
    day = program.weekly_schedule[0]
    evidence = SessionDurationRepairEvidence.from_day(
        day,
        ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
    )
    changed = replace(
        day,
        exercises=(replace(day.exercises[0], sets=day.exercises[0].sets - 1), *day.exercises[1:]),
    )

    assert evidence.matches(day)
    assert not evidence.matches(changed)


def test_final_gate_rejects_stale_duration_evidence() -> None:
    program = _program(1)
    day = program.weekly_schedule[0]
    evidence = SessionDurationRepairEvidence.from_day(
        day,
        (
            "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
            "SESSION_DURATION_UNDER_TARGET",
        ),
    )
    stale_day = replace(day, estimated_duration_minutes=day.estimated_duration_minutes + 1)
    stale = replace(
        program,
        weekly_schedule=(stale_day,),
        decision_trace=_duration_trace(program, (evidence.as_trace(),)),
    )
    report = ValidationReport(
        errors=(),
        warnings=("SESSION_DURATION_UNDER_TARGET",),
        assumptions=stale.assumptions,
        metrics=stale.aggregate_metrics,
        decision_trace=stale.decision_trace,
    )

    decision = evaluate_final_program(stale, request(available_training_days=1), report, RULESET)

    assert decision.status.value == "rejected"
    assert "SESSION_DURATION_CONSTRAINT_UNEXPLAINED" in decision.reason_codes


def test_final_gate_cannot_cross_excuse_duration_constraint_between_days() -> None:
    program = _program()
    first, second = program.weekly_schedule
    short_first = replace(
        first,
        exercises=first.exercises[:1],
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + (first.cardio.duration_minutes if first.cardio else 0)
        + 1,
    )
    short_second = replace(
        second,
        exercises=second.exercises[:1],
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + (second.cardio.duration_minutes if second.cardio else 0)
        + 1,
    )
    first_evidence = SessionDurationRepairEvidence.from_day(
        short_first,
        ("SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD", "SESSION_DURATION_UNDER_TARGET"),
    )
    traced = replace(
        program,
        weekly_schedule=(short_first, short_second),
        aggregate_metrics={
            **program.aggregate_metrics,
            "weekly_distribution": {
                **program.aggregate_metrics["weekly_distribution"],
                "after_exercise_counts": (1, 1),
            },
        },
        decision_trace=_duration_trace(program, (first_evidence.as_trace(),)),
    )
    report = ValidationReport(
        errors=(),
        warnings=("SESSION_DURATION_UNDER_TARGET",),
        assumptions=traced.assumptions,
        metrics=traced.aggregate_metrics,
        decision_trace=traced.decision_trace,
    )

    decision = evaluate_final_program(traced, request(available_training_days=2), report, RULESET)

    assert decision.status.value == "rejected"
    assert "SESSION_DURATION_CONSTRAINT_UNEXPLAINED" in decision.reason_codes


def test_final_gate_duration_reason_order_is_deterministic() -> None:
    program = _program(1)
    day = program.weekly_schedule[0]
    day = replace(
        day,
        exercises=day.exercises[:1],
        estimated_duration_minutes=(
            day.exercises[0].estimated_minutes + RULESET.general_warmup_minutes
        ),
    )
    evidence = SessionDurationRepairEvidence.from_day(
        day,
        (
            "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
            "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
            "SESSION_DURATION_UNDER_TARGET",
            "SESSION_DURATION_TARGET_UNSATISFIED",
        ),
    )
    traced = replace(
        program,
        weekly_schedule=(day,),
        decision_trace=_duration_trace(program, (evidence.as_trace(),)),
    )
    report = ValidationReport(
        errors=(),
        warnings=("SESSION_DURATION_UNDER_TARGET",),
        assumptions=program.assumptions,
        metrics=program.aggregate_metrics,
        decision_trace=traced.decision_trace,
    )

    decision = evaluate_final_program(traced, request(available_training_days=1), report, RULESET)

    duration_reasons = tuple(
        code
        for code in decision.metrics["checks"]["duration"]["reason_codes"]
        if code
        in {
            "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
            "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
        }
    )
    assert duration_reasons == (
        "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
        "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
    )


def test_final_gate_duration_order_is_stable_across_pythonhashseed() -> None:
    script = """
from dataclasses import replace
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.final_gate import evaluate_final_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport
from app.workouts.program_engine.session_duration import SessionDurationRepairEvidence
from tests.workouts.program_engine.golden_fixtures import full_catalog, request

source = request(available_training_days=1)
result = generate_program(source, full_catalog(), RULESET)
assert result.program is not None
day = replace(
    result.program.weekly_schedule[0],
    exercises=result.program.weekly_schedule[0].exercises[:1],
    estimated_duration_minutes=8,
)
reasons = tuple(set((
    "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
    "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
    "SESSION_DURATION_UNDER_TARGET",
)))
evidence = SessionDurationRepairEvidence.from_day(day, reasons)
trace = tuple(
    {**entry, "per_session_evidence": (evidence.as_trace(),)}
    if entry.get("stage") == "session_duration" else entry
    for entry in result.program.decision_trace
)
program = replace(result.program, weekly_schedule=(day,), decision_trace=trace)
report = ValidationReport(
    errors=(), warnings=("SESSION_DURATION_UNDER_TARGET",),
    assumptions=program.assumptions, metrics=program.aggregate_metrics,
    decision_trace=program.decision_trace,
)
decision = evaluate_final_program(program, source, report, RULESET)
print(repr(decision.metrics["checks"]["duration"]["reason_codes"]))
"""
    outputs = []
    for seed in ("1", "2", "3", "4", "5"):
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        outputs.append(completed.stdout.strip().splitlines()[-1])

    assert outputs[0] == outputs[1]
