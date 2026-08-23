from dataclasses import dataclass, replace
from uuid import UUID

from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    TemplateReference,
)
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    template_slot_allowed_patterns,
)
from app.workouts.program_engine.template_scoring import (
    TemplateScore,
    score_template_reference_result,
)


@dataclass(frozen=True)
class TemplateRankingResult:
    template: TemplateReference
    score: TemplateScore
    reason_codes: tuple[str, ...]
    feasibility: "TemplateFeasibility"
    rank: int = 0

    def decision_trace(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "slug": self.template.slug,
            "score": {
                "priority": self.score.priority_score,
                "body_analysis": self.score.body_analysis_score,
                "goal": self.score.goal_score,
                "sex": self.score.sex_score,
                "fallback": self.score.fallback_score,
                "total": self.score.total,
            },
            "feasibility": self.feasibility.decision_trace(),
            "reason_codes": self.reason_codes,
        }


@dataclass(frozen=True)
class TemplateFeasibility:
    total_slots: int
    core_slots: int
    resolvable_slots: int
    exact_slot_matches: int
    substitution_slots: int
    difficult_slots: int
    unresolved_non_core_slots: int
    hard_priority_slots_covered: int
    hard_priority_muscles_eligible: int
    hard_priority_muscles_requested: int

    @property
    def coverage_ratio(self) -> int:
        return round(self.resolvable_slots / self.total_slots * 1000) if self.total_slots else 0

    @property
    def exact_match_ratio(self) -> int:
        return round(self.exact_slot_matches / self.total_slots * 1000) if self.total_slots else 0

    @property
    def sort_key(self) -> tuple[int, ...]:
        return (
            self.coverage_ratio,
            self.hard_priority_slots_covered,
            self.hard_priority_muscles_eligible,
            self.exact_match_ratio,
            -self.unresolved_non_core_slots,
            -self.difficult_slots,
            -self.substitution_slots,
        )

    def decision_trace(self) -> dict[str, object]:
        return {
            "total_slots": self.total_slots,
            "core_slots": self.core_slots,
            "resolvable_slots": self.resolvable_slots,
            "coverage_percentage": round(self.coverage_ratio / 10, 1),
            "exact_slot_matches": self.exact_slot_matches,
            "exact_match_percentage": round(self.exact_match_ratio / 10, 1),
            "substitution_slots": self.substitution_slots,
            "difficult_slots": self.difficult_slots,
            "unresolved_non_core_slots": self.unresolved_non_core_slots,
            "hard_priority_slots_covered": self.hard_priority_slots_covered,
            "hard_priority_muscles_eligible": self.hard_priority_muscles_eligible,
            "hard_priority_muscles_requested": self.hard_priority_muscles_requested,
        }


@dataclass(frozen=True)
class HardRejectedTemplate:
    slug: str
    reason_codes: tuple[str, ...]

    def decision_trace(self) -> dict[str, object]:
        return {"slug": self.slug, "reason_codes": self.reason_codes}


@dataclass(frozen=True)
class TemplateTieBreak:
    score: int
    tied_slugs: tuple[str, ...]
    selected: str
    selected_by: str = "slug_descending"

    def decision_trace(self) -> dict[str, object]:
        return {
            "score": self.score,
            "tied_slugs": self.tied_slugs,
            "selected_by": self.selected_by,
            "selected": self.selected,
        }


@dataclass(frozen=True)
class TemplateSelectionResult:
    requested_days: int
    experience_level: str
    templates_considered: int
    hard_rejections: tuple[HardRejectedTemplate, ...]
    candidates: tuple[TemplateRankingResult, ...]
    selected: TemplateRankingResult | None
    tie_break: TemplateTieBreak | None

    def decision_trace(self) -> dict[str, object]:
        rejection_category = None
        if self.selected is None:
            has_days_level_candidate = any(
                "DAYS_MISMATCH" not in item.reason_codes
                and "EXPERIENCE_LEVEL_MISMATCH" not in item.reason_codes
                for item in self.hard_rejections
            )
            rejection_category = (
                "CORE_SLOT_UNRESOLVED" if has_days_level_candidate else "NO_DAYS_LEVEL_CANDIDATE"
            )
        return {
            "stage": "template_selection",
            "requested_days": self.requested_days,
            "experience_level": self.experience_level,
            "templates_considered": self.templates_considered,
            "hard_rejections": tuple(item.decision_trace() for item in self.hard_rejections),
            "candidates": tuple(item.decision_trace() for item in self.candidates),
            "selected": self.selected.template.slug if self.selected is not None else None,
            "rejection_category": rejection_category,
            "tie_break": self.tie_break.decision_trace() if self.tie_break is not None else None,
        }


def rank_template_references(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> tuple[TemplateRankingResult, ...]:
    scored = tuple(
        TemplateRankingResult(
            template,
            result.score,
            result.reason_codes,
            _template_feasibility(request, eligible, template),
        )
        for template in eligible_template_references(request, eligible, templates)
        for result in (score_template_reference_result(request, template, ruleset),)
    )
    ranked = tuple(
        sorted(
            scored,
            key=lambda item: (
                item.score.total,
                item.feasibility.sort_key,
                item.template.slug,
            ),
            reverse=True,
        )
    )
    return tuple(replace(item, rank=index) for index, item in enumerate(ranked, start=1))


def select_template_reference_result(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> TemplateSelectionResult:
    ranked = rank_template_references(request, eligible, templates, ruleset)
    selected = ranked[0] if ranked else None
    tie_break: TemplateTieBreak | None = None
    if selected is not None:
        tied = tuple(item for item in ranked if item.score.total == selected.score.total)
        if len(tied) > 1:
            feasibility_tied = all(
                item.feasibility.sort_key == selected.feasibility.sort_key for item in tied
            )
            tie_break = TemplateTieBreak(
                score=selected.score.total,
                tied_slugs=tuple(item.template.slug for item in tied),
                selected=selected.template.slug,
                selected_by=(
                    "slug_descending"
                    if feasibility_tied
                    else "feasibility_then_slug_descending"
                ),
            )
    rejected_items: list[HardRejectedTemplate] = []
    for template in templates:
        reason_codes = _hard_rejection_reason_codes(request, eligible, template)
        if reason_codes:
            rejected_items.append(HardRejectedTemplate(template.slug, reason_codes))
    rejected = tuple(sorted(rejected_items, key=lambda item: item.slug))
    return TemplateSelectionResult(
        requested_days=request.resistance_training_days,
        experience_level=_template_level(request),
        templates_considered=len(templates),
        hard_rejections=rejected,
        candidates=ranked,
        selected=selected,
        tie_break=tie_break,
    )


def select_template_reference(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> TemplateReference | None:
    result = select_template_reference_result(request, eligible, templates, ruleset)
    return result.selected.template if result.selected is not None else None


def eligible_template_references(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
) -> tuple[TemplateReference, ...]:
    """Return templates that pass structural hard eligibility.

    Goal remains available to downstream programming, but template metadata
    ``fitness_goal`` is intentionally not an exclusion criterion here.
    """
    level = _template_level(request)
    return tuple(
        template
        for template in templates
        if not _hard_rejection_reason_codes(request, eligible, template, level=level)
    )


def _hard_rejection_reason_codes(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    template: TemplateReference,
    *,
    level: str | None = None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if template.days_per_week != request.resistance_training_days:
        reasons.append("DAYS_MISMATCH")
    if template.training_level != (level or _template_level(request)):
        reasons.append("EXPERIENCE_LEVEL_MISMATCH")
    if not _core_slots_are_resolvable(
        template,
        eligible,
        {candidate.id for candidate in eligible},
    ):
        reasons.append("CORE_SLOT_UNRESOLVABLE")
    return tuple(reasons)


def _template_level(request: NormalizedProgramRequest) -> str:
    return request.source.training_experience.value


def _core_slots_are_resolvable(
    template: TemplateReference,
    eligible: tuple[ExerciseCandidate, ...],
    eligible_by_id: set[UUID],
) -> bool:
    for day in template.days:
        for slot in day.slots:
            if slot.adaptation_priority != "core":
                continue
            if slot.exercise_id in eligible_by_id:
                requested = next(item for item in eligible if item.id == slot.exercise_id)
                if evaluate_candidate_slot_compatibility(
                    requested,
                    allowed_patterns=template_slot_allowed_patterns(
                        slot.movement_pattern, slot.target_muscles
                    ),
                    target_muscles=frozenset(slot.target_muscles),
                    day_focus=f"template_reference_{day.day_number}",
                ).compatible:
                    continue
            if not any(
                evaluate_candidate_slot_compatibility(
                    candidate,
                    allowed_patterns=template_slot_allowed_patterns(
                        slot.movement_pattern, slot.target_muscles
                    ),
                    target_muscles=frozenset(slot.target_muscles),
                    day_focus=f"template_reference_{day.day_number}",
                ).compatible
                for candidate in eligible
            ):
                return False
    return True


def _template_feasibility(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    template: TemplateReference,
) -> TemplateFeasibility:
    eligible_by_id = {candidate.id: candidate for candidate in eligible}
    hard_priorities = request.source.priority_muscles
    total_slots = 0
    core_slots = 0
    resolvable_slots = 0
    exact_slot_matches = 0
    substitution_slots = 0
    difficult_slots = 0
    unresolved_non_core_slots = 0
    hard_priority_slots_covered = 0
    for day in template.days:
        for slot in day.slots:
            total_slots += 1
            core_slots += slot.adaptation_priority == "core"
            compatible = tuple(
                candidate
                for candidate in eligible
                if evaluate_candidate_slot_compatibility(
                    candidate,
                    allowed_patterns=template_slot_allowed_patterns(
                        slot.movement_pattern, slot.target_muscles
                    ),
                    target_muscles=frozenset(slot.target_muscles),
                    day_focus=f"template_reference_{day.day_number}",
                ).compatible
            )
            exact = eligible_by_id.get(slot.exercise_id) if slot.exercise_id is not None else None
            exact_is_compatible = exact is not None and exact in compatible
            if compatible:
                resolvable_slots += 1
                if exact_is_compatible:
                    exact_slot_matches += 1
                else:
                    substitution_slots += 1
                if len(compatible) == 1:
                    difficult_slots += 1
                if hard_priorities and any(
                    candidate.primary_muscle in hard_priorities for candidate in compatible
                ):
                    hard_priority_slots_covered += 1
            elif slot.adaptation_priority != "core":
                unresolved_non_core_slots += 1
    hard_priority_muscles_eligible = sum(
        any(candidate.primary_muscle is muscle for candidate in eligible)
        for muscle in hard_priorities
    )
    return TemplateFeasibility(
        total_slots=total_slots,
        core_slots=core_slots,
        resolvable_slots=resolvable_slots,
        exact_slot_matches=exact_slot_matches,
        substitution_slots=substitution_slots,
        difficult_slots=difficult_slots,
        unresolved_non_core_slots=unresolved_non_core_slots,
        hard_priority_slots_covered=hard_priority_slots_covered,
        hard_priority_muscles_eligible=hard_priority_muscles_eligible,
        hard_priority_muscles_requested=len(hard_priorities),
    )
