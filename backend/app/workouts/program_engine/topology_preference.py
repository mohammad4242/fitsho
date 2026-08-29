from dataclasses import dataclass

from app.training_templates.tags import (
    PRIMARY_STRUCTURE_TAGS,
    TemplateFocusTag,
    priority_tag_for_muscle,
    priority_tags_for_muscles,
    regional_priority_tags_for_muscles,
)
from app.workouts.program_engine.body_analysis import eligible_body_analysis_priorities
from app.workouts.program_engine.enums import SplitType, TrainingStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest
from app.workouts.program_engine.supplemental_policy import SUPPLEMENTAL_MUSCLES


@dataclass(frozen=True)
class ProfessionalTopologyPreference:
    score: int
    reason_codes: tuple[str, ...]


def professional_topology_preference(
    request: NormalizedProgramRequest,
    split_type: SplitType,
    ruleset: ProgramRuleset,
    *,
    template_tags: frozenset[TemplateFocusTag] | None = None,
) -> ProfessionalTopologyPreference:
    if request.training_status not in {TrainingStatus.INTERMEDIATE, TrainingStatus.ADVANCED}:
        return ProfessionalTopologyPreference(0, ("PROFESSIONAL_TOPOLOGY_OUT_OF_SCOPE",))
    if request.resistance_training_days not in {4, 5, 6}:
        return ProfessionalTopologyPreference(0, ("PROFESSIONAL_TOPOLOGY_OUT_OF_SCOPE",))

    primary_tags = None if template_tags is None else template_tags & PRIMARY_STRUCTURE_TAGS
    if primary_tags is not None and not primary_tags:
        return ProfessionalTopologyPreference(0, ("PROFESSIONAL_TOPOLOGY_NO_PRIMARY_STRUCTURE",))
    structure = _structure_from_tags(primary_tags) if primary_tags is not None else split_type
    base_score = _base_score(structure, ruleset)
    if base_score == 0:
        return ProfessionalTopologyPreference(0, ("PROFESSIONAL_TOPOLOGY_GENERIC_STRUCTURE",))

    if (
        primary_tags is not None
        and TemplateFocusTag.SPECIALIZATION in template_tags
        and _specialization_matches(request, template_tags, ruleset)
    ):
        return ProfessionalTopologyPreference(
            ruleset.professional_matching_specialization_bonus,
            ("PROFESSIONAL_TOPOLOGY_MATCHING_SPECIALIZATION_PREFERENCE",),
        )
    return ProfessionalTopologyPreference(base_score, (f"PROFESSIONAL_TOPOLOGY_{base_score}",))


def _structure_from_tags(tags: frozenset[TemplateFocusTag]) -> SplitType:
    if TemplateFocusTag.PUSH_PULL_LEGS in tags:
        if TemplateFocusTag.UPPER_LOWER in tags:
            return SplitType.PUSH_PULL_LEGS_UPPER_LOWER
        return SplitType.PUSH_PULL_LEGS
    if TemplateFocusTag.UPPER_LOWER in tags:
        return SplitType.UPPER_LOWER
    if TemplateFocusTag.FULL_BODY in tags:
        return SplitType.FULL_BODY
    return SplitType.BODY_PART_ROTATION


def _base_score(split_type: SplitType, ruleset: ProgramRuleset) -> int:
    if split_type is SplitType.PUSH_PULL_LEGS_UPPER_LOWER:
        return ruleset.professional_hybrid_bonus
    if split_type in {SplitType.PUSH_PULL_LEGS, SplitType.PUSH_PULL_LEGS_X2}:
        return ruleset.professional_ppl_bonus
    if split_type is SplitType.BODY_PART_ROTATION:
        return ruleset.professional_body_part_bonus
    return 0


def _specialization_matches(
    request: NormalizedProgramRequest,
    tags: frozenset[TemplateFocusTag],
    ruleset: ProgramRuleset,
) -> bool:
    explicit = tuple(
        muscle
        for muscle in request.source.priority_muscles
        if muscle not in SUPPLEMENTAL_MUSCLES
    )
    if (
        priority_tags_for_muscles(explicit) & tags
        or regional_priority_tags_for_muscles(explicit) & tags
    ):
        return True
    for priority in eligible_body_analysis_priorities(request, ruleset):
        if priority.muscle in SUPPLEMENTAL_MUSCLES:
            continue
        tag = priority_tag_for_muscle(priority.muscle)
        if tag is not None and tag in tags:
            return True
    return False
