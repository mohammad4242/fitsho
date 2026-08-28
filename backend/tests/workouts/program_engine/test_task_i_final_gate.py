from dataclasses import replace

from app.exercises.enums import Equipment, ExerciseCautionTag, MuscleGroup
from app.workouts.program_engine import engine
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import SplitType
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.weekly_coverage import assess_weekly_coverage
from tests.workouts.program_engine.golden_fixtures import full_catalog, request
from tests.workouts.program_engine.test_template_reference import _four_day_reference


def test_generated_program_contains_the_final_quality_gate_stage() -> None:
    result = generate_program(request(available_training_days=1), full_catalog(), RULESET)

    assert result.program is not None, result.errors
    gate_entries = [
        item for item in result.program.decision_trace if item.get("stage") == "final_quality_gate"
    ]
    assert len(gate_entries) == 1
    assert gate_entries[0]["schema_version"] == "final_quality_gate_v1"
    assert gate_entries[0]["status"] in {"accepted", "accepted_with_constraints"}
    assert result.program.aggregate_metrics["final_quality_gate"]["status"] in {
        "accepted",
        "accepted_with_constraints",
    }


def _gate(program, source):
    gate = getattr(engine, "evaluate_final_program", None)
    assert callable(gate), "final quality gate is not wired into the engine"
    report = validate_program(program, source, RULESET)
    return gate(program, source, report, RULESET)


def _program(source=None):
    source = source or request(available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    return result.program


def test_final_gate_rejects_each_hard_final_invariant() -> None:
    source = request(available_training_days=1)
    base = _program(source)
    day = base.weekly_schedule[0]

    underfilled = replace(
        base,
        weekly_schedule=(replace(day, exercises=day.exercises[:1]),),
    )
    overfilled = replace(
        base,
        weekly_schedule=(
            replace(
                day,
                estimated_duration_minutes=RULESET.general_warmup_minutes
                + source.session_duration_minutes
                + (day.cardio.duration_minutes if day.cardio else 0)
                + 11,
            ),
        ),
    )
    unavailable = replace(
        base,
        weekly_schedule=(
            replace(
                day,
                exercises=(replace(day.exercises[0], equipment=frozenset({Equipment.BARBELL})),),
            ),
        ),
    )
    caution_source = request(
        available_training_days=1,
        blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING],
    )
    cautioned = _program(caution_source)
    caution_day = cautioned.weekly_schedule[0]
    caution_program = replace(
        cautioned,
        weekly_schedule=(
            replace(
                caution_day,
                exercises=(
                    replace(
                        caution_day.exercises[0],
                        caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
                    ),
                    *caution_day.exercises[1:],
                ),
            ),
        ),
    )

    for candidate, expected in (
        (underfilled, "SESSION_EXERCISE_COUNT_OUT_OF_RANGE"),
        (overfilled, "SESSION_DURATION_EXCEEDED"),
        (unavailable, "UNAVAILABLE_EQUIPMENT_SELECTED"),
        (caution_program, "BLOCKED_CAUTION_TAG_SELECTED"),
    ):
        decision = _gate(candidate, caution_source if candidate is caution_program else source)
        assert decision.status == "rejected"
        assert expected in decision.reason_codes


def test_final_gate_rejects_semantics_recovery_day_count_and_coverage() -> None:
    source = request(available_training_days=2)
    base = _program(source)
    first, second = base.weekly_schedule
    semantic = replace(
        base,
        weekly_schedule=(replace(first, exercises=(first.exercises[0],) * 2), second),
    )
    recovery = replace(
        base,
        split=replace(base.split, weekdays=(0, 1)),
        weekly_schedule=(replace(first, weekday=0), replace(second, weekday=1)),
    )
    day_count = replace(base, weekly_schedule=(first,))
    coverage_days = tuple(
        replace(
            day,
            exercises=tuple(
                item
                for item in day.exercises
                if item.primary_muscle is not MuscleGroup.BACK
                and MuscleGroup.BACK not in item.secondary_muscles
            ),
        )
        for day in (first, second)
    )
    coverage_metrics = assess_weekly_coverage(
        coverage_days,
        base.aggregate_metrics,
        ruleset=RULESET,
        availability_evidence=base.aggregate_metrics["weekly_coverage"]["availability_evidence"],
        full_body_claim=True,
    ).metrics
    coverage = replace(
        base,
        weekly_schedule=coverage_days,
        aggregate_metrics={**base.aggregate_metrics, "weekly_coverage": coverage_metrics},
    )

    for candidate, expected in (
        (semantic, "UNJUSTIFIED_DUPLICATE_EXERCISE"),
        (recovery, "RECOVERY_SPACING_INVALID"),
        (day_count, "REQUESTED_TRAINING_DAYS_UNSATISFIED"),
        (coverage, "FULL_BODY_PATTERN_MISSING:pull"),
    ):
        decision = _gate(candidate, source)
        assert decision.status == "rejected"
        assert expected in decision.reason_codes


def test_final_gate_rejects_unexplained_distribution_and_accepts_proven_constraints() -> None:
    source = request(available_training_days=1)
    base = _program(source)
    distribution = base.aggregate_metrics["weekly_distribution"]
    unexplained_metrics = {
        **base.aggregate_metrics,
        "weekly_distribution": {
            **distribution,
            "status": "constrained",
            "reason_codes": (),
        },
    }
    unexplained = replace(base, aggregate_metrics=unexplained_metrics)
    rejected = _gate(unexplained, source)
    assert rejected.status == "rejected"
    assert "WEEKLY_DISTRIBUTION_CONSTRAINT_UNEXPLAINED" in rejected.reason_codes

    constrained_metrics = {
        **base.aggregate_metrics,
        "weekly_distribution": {
            **distribution,
            "status": "constrained",
            "reason_codes": ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",),
        },
    }
    constrained = replace(base, aggregate_metrics=constrained_metrics)
    accepted = _gate(constrained, source)
    assert accepted.status == "accepted_with_constraints"
    assert accepted.reason_codes == ()
    assert "WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE" in accepted.constraint_reason_codes


def test_final_gate_rejects_unexplained_duration_constraint() -> None:
    source = request(available_training_days=1)
    base = _program(source)
    report = ValidationReport(
        errors=(),
        warnings=("SESSION_DURATION_UNDER_TARGET",),
        assumptions=base.assumptions,
        metrics=base.aggregate_metrics,
        decision_trace=(),
    )

    decision = engine.evaluate_final_program(
        replace(base, decision_trace=()), source, report, RULESET
    )

    assert decision.status == "rejected"
    assert "SESSION_DURATION_CONSTRAINT_UNEXPLAINED" in decision.reason_codes
    assert "SESSION_DURATION_CONSTRAINT_UNEXPLAINED" not in decision.constraint_reason_codes
    assert "SESSION_DURATION_UNDER_TARGET" not in decision.constraint_reason_codes


def test_final_gate_rejects_failed_supported_upper_priority_topology() -> None:
    source = request(
        available_training_days=4,
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        priority_muscles=[MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS],
    )
    base = _program(source)
    assert base.split.split_type is SplitType.UPPER_LOWER_SPECIALIZATION
    lower_day = next(day for day in base.weekly_schedule if day.focus == "lower")
    upper_index = next(
        index for index, day in enumerate(base.weekly_schedule) if day.focus.startswith("upper")
    )
    altered_days = list(base.weekly_schedule)
    altered_days[upper_index] = replace(
        altered_days[upper_index],
        exercises=lower_day.exercises,
    )
    decision = _gate(replace(base, weekly_schedule=tuple(altered_days)), source)
    assert decision.status == "rejected"
    assert "UPPER_PRIORITY_TOPOLOGY_INVALID" in decision.reason_codes


def test_final_gate_accepts_valid_dynamic_template_fallback_and_repaired_outputs() -> None:
    reference = _four_day_reference()
    fallback_reference = replace(
        reference, slug="task-i-unadaptable", days=(reference.days[0],) * 4
    )
    source = request(
        available_training_days=4,
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        session_duration_minutes=60,
    )
    scenarios = (
        (request(available_training_days=1), ()),
        (source, (reference,)),
        (source, (fallback_reference,)),
        (request(available_training_days=4, session_duration_minutes=60), ()),
    )
    for scenario, templates in scenarios:
        result = generate_program(scenario, full_catalog(), RULESET, reference_templates=templates)
        assert result.program is not None, result.errors
        decision = _gate(result.program, scenario)
        assert decision.status in {"accepted", "accepted_with_constraints"}
        assert decision.schema_version == "final_quality_gate_v1"
        entries = [
            entry
            for entry in result.program.decision_trace
            if entry["stage"] == "final_quality_gate"
        ]
        assert len(entries) == 1
        assert entries[0]["schema_version"] == decision.schema_version

    repaired = generate_program(scenarios[-1][0], full_catalog(), RULESET)
    assert repaired.program is not None, repaired.errors
    assert repaired.program.aggregate_metrics["weekly_distribution"]["status"] == "constrained"
    assert (
        "WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE"
        in repaired.program.aggregate_metrics["final_quality_gate"]["constraint_reason_codes"]
    )
