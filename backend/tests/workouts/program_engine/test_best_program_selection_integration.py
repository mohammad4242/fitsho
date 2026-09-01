from types import SimpleNamespace

from app.workouts.program_engine import engine
from app.workouts.program_engine.enums import GenerationErrorCode, SplitType
from app.workouts.program_engine.program_selection import (
    COACH_QUALITY_V2_SCHEMA_VERSION,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ProgramGenerationResult,
    SplitPlan,
    TemplateReference,
)
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
        aggregate_metrics={},
    )
    return ProgramGenerationResult(program=program, decision_trace=trace)


def _template(slug: str) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=4,
        supported_levels=("intermediate",),
        focus_tags=(),
        intensity_methods=(),
        days=(),
    )


def _template_ranking(template: TemplateReference, score: int, rank: int) -> SimpleNamespace:
    return SimpleNamespace(
        template=template,
        score=SimpleNamespace(total=score),
        reason_codes=(),
        feasibility=SimpleNamespace(decision_trace=lambda: {}),
        rank=rank,
        decision_trace=lambda: {"score": {"total": score}},
    )


def _template_result(template: TemplateReference, score: float) -> ProgramGenerationResult:
    quality_result = _successful_result(
        _split(SplitType.BODY_PART_ROTATION, "template"),
        score,
    )
    program = SimpleNamespace(
        split=quality_result.program.split,
        decision_trace=quality_result.program.decision_trace,
        validation_report=quality_result.program.validation_report,
        aggregate_metrics={"reference_template": template.slug},
    )
    return ProgramGenerationResult(program=program, decision_trace=program.decision_trace)


def _patch_template_candidates(monkeypatch, rankings, results) -> None:
    selection = SimpleNamespace(
        candidates=tuple(rankings),
        decision_trace=lambda: {
            "stage": "template_selection",
            "candidates": tuple(item.decision_trace() for item in rankings),
            "selected": rankings[0].template.slug if rankings else None,
        },
    )
    monkeypatch.setattr(
        engine, "select_template_reference_result", lambda *args, **kwargs: selection
    )
    monkeypatch.setattr(engine, "build_template_sessions", lambda *args, **kwargs: object())
    monkeypatch.setattr(engine, "_append_successful_template_attempt", lambda result, trace: result)
    monkeypatch.setattr(
        engine,
        "_reference_program",
        lambda *args, **kwargs: results[args[7].slug],
    )


def test_primary_pool_selects_canonical_when_final_quality_is_better(monkeypatch) -> None:
    template = _template("curated-template")
    ranking = _template_ranking(template, score=100, rank=1)
    canonical = _split(SplitType.UPPER_LOWER, "upper", "lower", "upper", "lower")
    _patch_template_candidates(
        monkeypatch, (ranking,), {template.slug: _template_result(template, 70)}
    )
    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: (canonical,))
    monkeypatch.setattr(
        engine, "_program_for_split", lambda *args, **kwargs: _successful_result(canonical, 95)
    )

    result = engine.generate_program(
        request(available_training_days=4),
        full_catalog(),
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None
    assert result.program.split.split_type is SplitType.UPPER_LOWER
    assert "reference_template" not in result.program.aggregate_metrics


def test_true_quality_tie_prefers_the_curated_template(monkeypatch) -> None:
    template = _template("curated-template")
    ranking = _template_ranking(template, score=10, rank=1)
    canonical = _split(SplitType.UPPER_LOWER, "upper", "lower", "upper", "lower")
    _patch_template_candidates(
        monkeypatch, (ranking,), {template.slug: _template_result(template, 90)}
    )
    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: (canonical,))
    monkeypatch.setattr(
        engine, "_program_for_split", lambda *args, **kwargs: _successful_result(canonical, 90)
    )

    result = engine.generate_program(
        request(available_training_days=4),
        full_catalog(),
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None
    assert result.program.aggregate_metrics["reference_template"] == template.slug


def test_template_final_quality_beats_a_higher_product_score(monkeypatch) -> None:
    high_product = _template("high-product-template")
    better_quality = _template("better-quality-template")
    rankings = (
        _template_ranking(high_product, score=100, rank=1),
        _template_ranking(better_quality, score=10, rank=2),
    )
    _patch_template_candidates(
        monkeypatch,
        rankings,
        {
            high_product.slug: _template_result(high_product, 70),
            better_quality.slug: _template_result(better_quality, 95),
        },
    )
    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: ())

    result = engine.generate_program(
        request(available_training_days=4),
        full_catalog(),
        RULESET,
        reference_templates=(high_product, better_quality),
    )

    assert result.program is not None
    assert result.program.aggregate_metrics["reference_template"] == better_quality.slug


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
    monkeypatch.setattr(engine, "_append_successful_template_attempt", lambda result, trace: result)

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
    monkeypatch.setattr(engine, "_append_successful_template_attempt", lambda result, trace: result)

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
