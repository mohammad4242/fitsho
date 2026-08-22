from __future__ import annotations

from app.exercises.enums import MuscleGroup
from app.training_templates.tags import priority_tag_for_muscle
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    BodyAnalysisPriority,
    NormalizedProgramRequest,
)

BODY_ANALYSIS_TRAINING_MAPPING_VERSION = "body_analysis_training_map_v2"

TEMPLATE_TAGS_BY_MUSCLE: dict[MuscleGroup, frozenset[str]] = {
    muscle: frozenset({tag}) if (tag := priority_tag_for_muscle(muscle)) else frozenset()
    for muscle in MuscleGroup
}


def eligible_body_analysis_priorities(
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[BodyAnalysisPriority, ...]:
    influence = request.source.body_analysis_influence
    if influence is None or influence.overall_confidence < ruleset.body_analysis_minimum_confidence:
        return ()
    return tuple(
        priority
        for priority in influence.priorities
        if priority.confidence >= ruleset.body_analysis_minimum_confidence
    )


def applicable_body_analysis_influence(
    influence: BodyAnalysisInfluence | None,
    ruleset: ProgramRuleset,
) -> BodyAnalysisInfluence | None:
    """Drops evidence that cannot safely influence any program decision."""

    if influence is None or influence.overall_confidence < ruleset.body_analysis_minimum_confidence:
        return None
    priorities = tuple(
        priority
        for priority in influence.priorities
        if priority.confidence >= ruleset.body_analysis_minimum_confidence
    )
    if not priorities:
        return None
    return influence.model_copy(update={"priorities": priorities})


def body_analysis_priority_muscles(
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> frozenset[MuscleGroup]:
    return frozenset(
        priority.muscle for priority in eligible_body_analysis_priorities(request, ruleset)
    )


def body_analysis_provenance(request: NormalizedProgramRequest) -> dict[str, object]:
    influence = request.source.body_analysis_influence
    if influence is None:
        return {}
    return {
        "analysis_id": str(influence.analysis_id),
        "result_version_id": str(influence.result_version_id),
        "analysis_revision": influence.analysis_revision,
        "schema_version": influence.schema_version,
        "source": influence.source,
        "provisional": influence.source != "fully_reviewed",
        "mapping_version": BODY_ANALYSIS_TRAINING_MAPPING_VERSION,
    }


def body_analysis_trace(
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> dict[str, object] | None:
    influence = request.source.body_analysis_influence
    if influence is None:
        return None
    priorities = eligible_body_analysis_priorities(request, ruleset)
    return {
        "stage": "body_analysis_influence",
        "analysis_id": str(influence.analysis_id),
        "result_version_id": str(influence.result_version_id),
        "source": influence.source,
        "provisional": influence.source != "fully_reviewed",
        "mapping_version": BODY_ANALYSIS_TRAINING_MAPPING_VERSION,
        "minimum_confidence": ruleset.body_analysis_minimum_confidence,
        "applied_muscles": sorted(item.muscle.value for item in priorities),
    }
