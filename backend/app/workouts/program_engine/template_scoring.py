from dataclasses import dataclass, field

from app.profile.enums import Sex
from app.training_templates.tags import (
    LEGACY_UPPER_PRIORITY_TAG,
    TemplateFocusTag,
    priority_tag_for_muscle,
    priority_tags_for_muscles,
    regional_priority_tags_for_muscles,
)
from app.workouts.program_engine.body_analysis import eligible_body_analysis_priorities
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest, TemplateReference
from app.workouts.program_engine.supplemental_policy import SUPPLEMENTAL_MUSCLES


@dataclass(frozen=True)
class TemplateScoringPolicy:
    explicit_priority_exact: int = 100
    explicit_priority_lower_regional: int = 40
    explicit_priority_cap: int = 120
    body_analysis_clear_lag: int = 40
    body_analysis_mild_lag: int = 20
    body_analysis_cap: int = 40
    strength_bias_affinity: int = 25
    compound_focus_affinity: int = 10
    balanced_goal_affinity: int = 10
    goal_cap: int = 25
    female_glute_affinity: int = 20
    female_lower_affinity: int = 10
    male_chest_or_back_affinity: int = 20
    sex_cap: int = 20
    balanced_fallback: int = 5


DEFAULT_TEMPLATE_SCORING_POLICY = TemplateScoringPolicy()


@dataclass(frozen=True)
class TemplateScore:
    priority_score: int
    body_analysis_score: int
    goal_score: int
    sex_score: int
    fallback_score: int
    total: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "total",
            self.priority_score
            + self.body_analysis_score
            + self.goal_score
            + self.sex_score
            + self.fallback_score,
        )


@dataclass(frozen=True)
class TemplateScoringResult:
    score: TemplateScore
    reason_codes: tuple[str, ...]


def score_template_reference(
    request: NormalizedProgramRequest,
    template: TemplateReference,
    ruleset: ProgramRuleset,
    policy: TemplateScoringPolicy = DEFAULT_TEMPLATE_SCORING_POLICY,
) -> TemplateScore:
    return score_template_reference_result(request, template, ruleset, policy).score


def score_template_reference_result(
    request: NormalizedProgramRequest,
    template: TemplateReference,
    ruleset: ProgramRuleset,
    policy: TemplateScoringPolicy = DEFAULT_TEMPLATE_SCORING_POLICY,
) -> TemplateScoringResult:
    tags = frozenset(
        TemplateFocusTag(str(tag))
        for tag in template.focus_tags
        if str(tag) != LEGACY_UPPER_PRIORITY_TAG
    )
    priority_score, priority_reasons = _priority_score(request, tags, policy)
    body_analysis_score, body_analysis_reasons = _body_analysis_score(
        request, tags, ruleset, policy
    )
    goal_score, goal_reasons = _goal_score(request.primary_goal, tags, policy)
    sex_score, sex_reasons = _sex_score(request, tags, policy)
    fallback_score = policy.balanced_fallback if TemplateFocusTag.BALANCED in tags else 0
    fallback_reasons = ("BALANCED_FALLBACK",) if fallback_score else ()
    return TemplateScoringResult(
        score=TemplateScore(
            priority_score=priority_score,
            body_analysis_score=body_analysis_score,
            goal_score=goal_score,
            sex_score=sex_score,
            fallback_score=fallback_score,
        ),
        reason_codes=(
            *priority_reasons,
            *body_analysis_reasons,
            *goal_reasons,
            *sex_reasons,
            *fallback_reasons,
        ),
    )


def _priority_score(
    request: NormalizedProgramRequest,
    tags: frozenset[TemplateFocusTag],
    policy: TemplateScoringPolicy,
) -> tuple[int, tuple[str, ...]]:
    main_priorities = tuple(
        muscle for muscle in request.source.priority_muscles if muscle not in SUPPLEMENTAL_MUSCLES
    )
    exact_matches = priority_tags_for_muscles(main_priorities) & tags
    lower_regional_matches = regional_priority_tags_for_muscles(main_priorities) & tags
    score = min(
        policy.explicit_priority_cap,
        len(exact_matches) * policy.explicit_priority_exact
        + len(lower_regional_matches) * policy.explicit_priority_lower_regional,
        # regional_priority_tags_for_muscles contains lower-body mappings only;
        # upper-body selections have no regional priority credit.
    )
    reasons = (
        *(("EXPLICIT_PRIORITY_EXACT_MATCH",) if exact_matches else ()),
        *(
            ("EXPLICIT_PRIORITY_LOWER_REGIONAL_MATCH",)
            if lower_regional_matches
            else ()
        ),
    )
    return score, reasons


def _body_analysis_score(
    request: NormalizedProgramRequest,
    tags: frozenset[TemplateFocusTag],
    ruleset: ProgramRuleset,
    policy: TemplateScoringPolicy,
) -> tuple[int, tuple[str, ...]]:
    boost_by_tag: dict[TemplateFocusTag, int] = {}
    matched_classifications: set[str] = set()
    for priority in eligible_body_analysis_priorities(request, ruleset):
        if priority.muscle in SUPPLEMENTAL_MUSCLES:
            continue
        tag = priority_tag_for_muscle(priority.muscle)
        if tag is None or tag not in tags:
            continue
        boost = (
            policy.body_analysis_clear_lag
            if priority.classification == "clear_lag"
            else policy.body_analysis_mild_lag
        )
        boost_by_tag[tag] = max(boost_by_tag.get(tag, 0), boost)
        matched_classifications.add(priority.classification)
    score = min(policy.body_analysis_cap, sum(boost_by_tag.values()))
    reasons = (
        *(("BODY_ANALYSIS_CLEAR_LAG_MATCH",) if "clear_lag" in matched_classifications else ()),
        *(("BODY_ANALYSIS_MILD_LAG_MATCH",) if "mild_lag" in matched_classifications else ()),
    )
    return score, reasons


def _goal_score(
    goal: Goal,
    tags: frozenset[TemplateFocusTag],
    policy: TemplateScoringPolicy,
) -> tuple[int, tuple[str, ...]]:
    affinities: tuple[int, ...]
    reasons: tuple[str, ...]
    if goal is Goal.STRENGTH:
        affinities = (
            policy.strength_bias_affinity if TemplateFocusTag.STRENGTH_BIAS in tags else 0,
            policy.compound_focus_affinity if TemplateFocusTag.COMPOUND_FOCUS in tags else 0,
        )
        reasons = (
            *(("GOAL_STRENGTH_BIAS_MATCH",) if TemplateFocusTag.STRENGTH_BIAS in tags else ()),
            *(("GOAL_COMPOUND_FOCUS_MATCH",) if TemplateFocusTag.COMPOUND_FOCUS in tags else ()),
        )
    elif goal in {Goal.GENERAL_FITNESS, Goal.BODY_RECOMPOSITION}:
        affinities = (policy.balanced_goal_affinity if TemplateFocusTag.BALANCED in tags else 0,)
        reasons = ("GOAL_BALANCED_MATCH",) if TemplateFocusTag.BALANCED in tags else ()
    else:
        affinities = (0,)
        reasons = ()
    return min(policy.goal_cap, max(affinities)), reasons


def _sex_score(
    request: NormalizedProgramRequest,
    tags: frozenset[TemplateFocusTag],
    policy: TemplateScoringPolicy,
) -> tuple[int, tuple[str, ...]]:
    if request.source.priority_muscles:
        return 0, ("SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY",)
    sex_value = request.source.biological_sex_optional
    if sex_value is None:
        return 0, ()
    try:
        sex = Sex(sex_value)
    except ValueError:
        return 0, ()
    affinities: tuple[int, ...]
    reasons: tuple[str, ...]
    if sex is Sex.FEMALE:
        affinities = (
            policy.female_glute_affinity if TemplateFocusTag.GLUTE_PRIORITY in tags else 0,
            policy.female_lower_affinity if TemplateFocusTag.LOWER_PRIORITY in tags else 0,
        )
        reasons = (
            *(("SEX_PRIOR_GLUTE_MATCH",) if TemplateFocusTag.GLUTE_PRIORITY in tags else ()),
            *(("SEX_PRIOR_LOWER_MATCH",) if TemplateFocusTag.LOWER_PRIORITY in tags else ()),
        )
    elif sex is Sex.MALE:
        affinities = (
            policy.male_chest_or_back_affinity
            if tags & {TemplateFocusTag.CHEST_PRIORITY, TemplateFocusTag.BACK_PRIORITY}
            else 0,
        )
        reasons = (
            ("SEX_PRIOR_MUSCLE_MATCH",)
            if tags
            & {
                TemplateFocusTag.CHEST_PRIORITY,
                TemplateFocusTag.BACK_PRIORITY,
            }
            else ()
        )
    else:
        affinities = (0,)
        reasons = ()
    return min(policy.sex_cap, max(affinities)), reasons
