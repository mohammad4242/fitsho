from types import SimpleNamespace

from app.workouts.program_engine import engine
from app.workouts.program_engine.enums import GenerationErrorCode, SplitType
from app.workouts.program_engine.program_selection import (
    COACH_QUALITY_V2_SCHEMA_VERSION,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgramGenerationResult, SplitPlan
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _split(split_type: SplitType, *focuses: str) -> SplitPlan:
    return SplitPlan(
        split_type=split_type,
        day_focuses=focuses,
        weekdays=tuple(range(len(focuses))),
        score=0,
        reason_codes=(),
    )


def _successful_result(split: SplitPlan, score: float) -> ProgramGenerationResult:
    quality = {
        "schema_version": COACH_QUALITY_V2_SCHEMA_VERSION,
        "critical_dimensions": {"volume": score},
        "coverage_state": "satisfied",
        "coverage_percentage": 100.0,
        "volume_floor": score,
        "volume_median": score,
        "explicit_priority_floor": score,
        "body_analysis_priority_floor": None,
        "recovery_margin": 100.0,
        "duration_fit": 100.0,
        "semantic_degradation": 0,
    }
    trace = (
        {
            "stage": "coach_quality",
            "metrics": {"selection_quality": quality},
        },
        {
            "stage": "final_quality_gate",
            "status": "accepted",
            "reason_codes": (),
            "constraint_reason_codes": (),
        },
    )
    program = SimpleNamespace(
        split=split,
        decision_trace=trace,
        validation_report=SimpleNamespace(errors=()),
    )
    return ProgramGenerationResult(program=program, decision_trace=trace)


def test_canonical_selection_does_not_return_the_first_success(monkeypatch) -> None:
    first = _split(SplitType.UPPER_LOWER, "upper", "lower", "upper", "lower")
    second = _split(
        SplitType.BODY_PART_ROTATION,
        "chest_triceps",
        "back_biceps",
        "legs",
        "shoulders_traps",
    )
    results = {
        first.split_type: _successful_result(first, 70.0),
        second.split_type: _successful_result(second, 95.0),
    }
    calls: list[SplitPlan] = []

    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: (first, second))

    def build(*args, **kwargs):
        split = args[7]
        calls.append(split)
        return results[split.split_type]

    monkeypatch.setattr(engine, "_program_for_split", build)

    result = engine.generate_program(
        request(available_training_days=4),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None
    assert result.program.split.split_type is second.split_type
    assert len(calls) == 2
    assert "SPLIT_CANDIDATE_EVALUATED_FOR_QUALITY" in calls[1].reason_codes
    assert "SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE" not in calls[1].reason_codes


def test_canonical_fallback_marker_requires_an_actual_previous_failure(monkeypatch) -> None:
    first = _split(SplitType.UPPER_LOWER, "upper", "lower", "upper", "lower")
    second = _split(
        SplitType.BODY_PART_ROTATION,
        "chest_triceps",
        "back_biceps",
        "legs",
        "shoulders_traps",
    )
    successful = _successful_result(second, 90.0)
    calls: list[SplitPlan] = []
    histories: list[tuple[dict[str, object], ...]] = []

    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: (first, second))

    def build(*args, **kwargs):
        split = args[7]
        calls.append(split)
        histories.append(kwargs["rejected_splits"])
        if split.split_type is first.split_type:
            return ProgramGenerationResult(
                program=None,
                error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
                errors=("FIRST_SPLIT_FAILED",),
            )
        return successful

    monkeypatch.setattr(engine, "_program_for_split", build)

    result = engine.generate_program(
        request(available_training_days=4),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None
    assert "SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE" in calls[1].reason_codes
    assert histories[1] == ()
