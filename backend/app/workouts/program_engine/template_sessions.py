from collections import Counter
from dataclasses import dataclass, replace
from typing import cast
from uuid import UUID

from app.exercises.enums import Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_capacity import SessionCapacity
from app.workouts.program_engine.duration_policy import get_session_exercise_count_policy
from app.workouts.program_engine.enums import TrainingExperience
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.exercise_semantics import (
    has_near_equivalent,
    is_primary_working_compound,
)
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    SessionDraft,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
    WorkoutDay,
)
from app.workouts.program_engine.session_coherence import SessionCoherence
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    template_slot_allowed_patterns,
)
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import SubstitutionCause
from app.workouts.program_engine.supplemental_policy import (
    is_core_or_supplemental_exercise,
    is_main_resistance_exercise,
    is_supplemental_muscle,
    main_exercise_count,
    supplemental_reason_codes,
)


@dataclass(frozen=True)
class TemplateSlotResolution:
    day_index: int
    requested_exercise_id: UUID | None
    selected_exercise_id: UUID
    adaptation_priority: str
    intensity_method: str
    superset_group: str | None
    original_prescription: tuple[int, int, int, int, int]
    is_template_slot: bool

    @property
    def preserved_exactly(self) -> bool:
        return self.is_template_slot and self.requested_exercise_id == self.selected_exercise_id


@dataclass(frozen=True)
class TemplateSessionBuild:
    drafts: tuple[SessionDraft, ...]
    titles: tuple[str, ...]
    resolutions: tuple[TemplateSlotResolution, ...]
    reason_codes: tuple[str, ...]

    def direct_exposure_counts(self) -> Counter[MuscleGroup]:
        counts: Counter[MuscleGroup] = Counter()
        for draft in self.drafts:
            counts.update(
                {
                    exercise.primary_muscle
                    for exercise in draft.exercises
                    if exercise.primary_muscle is not None
                }
            )
        return counts


class TemplateConstructionError(ValueError):
    def __init__(self, *reason_codes: str) -> None:
        self.reason_codes = tuple(reason_codes)
        super().__init__(";".join(self.reason_codes))


def build_template_sessions(
    request: NormalizedProgramRequest,
    template: TemplateReference,
    eligible: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    session_capacity: SessionCapacity | None = None,
    exercise_catalog: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...] | None = None,
) -> TemplateSessionBuild:
    eligible_by_id = {candidate.id: candidate for candidate in eligible}
    catalog_source = eligible if exercise_catalog is None else exercise_catalog
    catalog_by_id = {candidate.id: candidate for candidate in catalog_source}
    used: Counter[object] = Counter()
    reserved_ids = []
    for day in template.days:
        for slot in day.slots:
            if slot.exercise_id is not None:
                reserved_ids.append(slot.exercise_id)
            superset_exercise_id = getattr(slot, "superset_exercise_id", None)
            if superset_exercise_id is not None:
                reserved_ids.append(superset_exercise_id)
    reserved: Counter[UUID] = Counter(reserved_ids)
    drafts: list[SessionDraft] = []
    resolutions: list[TemplateSlotResolution] = []
    build_reasons: list[str] = []
    complementary_replacements: set[UUID] = set()
    deliberate_redundancies: set[UUID] = set()
    repeated_core_substitutions: set[tuple[int, UUID]] = set()
    repeated_targeted_accessories: set[tuple[int, UUID]] = set()
    repeated_level_resolutions: set[tuple[int, UUID]] = set()
    repeated_template_selections: set[tuple[int, UUID]] = set()
    substitutions_by_requested: dict[UUID, set[UUID]] = {}
    preserved_template_occurrences: Counter[UUID] = Counter()
    weekly_direct_sessions: Counter[MuscleGroup] = Counter()
    count_policy = get_session_exercise_count_policy(
        request.source.session_duration_minutes, ruleset
    )
    for index, reference_day in enumerate(template.days, start=1):
        coherence = SessionCoherence.from_template_reference_day(reference_day)
        required_slot_count = sum(
            slot.adaptation_priority == "core" for slot in reference_day.slots
        )
        capacity = (
            max(
                required_slot_count,
                min(
                    ruleset.max_exercises_per_session,
                    session_capacity.expected_exercise_count_capacity,
                ),
            )
            if session_capacity is not None
            else max(
                ruleset.minimum_exercises_per_session,
                min(
                    ruleset.max_exercises_per_session,
                    request.source.session_duration_minutes // ruleset.minutes_per_exercise_slot,
                ),
            )
        )
        capacity = max(1, capacity)
        short_session = request.source.session_duration_minutes <= ruleset.short_session_minutes
        if not short_session:
            capacity = max(capacity, count_policy.minimum_main_exercises)
        main_capacity = min(count_policy.maximum_main_exercises, capacity)
        planned_minimum = min(count_policy.minimum_main_exercises, main_capacity)
        planned_target = min(ruleset.preferred_main_exercises_per_session, main_capacity)
        if planned_minimum < count_policy.minimum_main_exercises:
            build_reasons.append("DURATION_PLANNED_REDUCED_EXERCISE_COUNT")
        selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]] = []

        expanded_slots = []
        for slot in reference_day.slots:
            if slot.intensity_method == "superset" and getattr(slot, "superset_exercise_id", None):
                group_id = (
                    slot.superset_group
                    or f"auto_{str(slot.exercise_id)[:8]}_{str(slot.superset_exercise_id)[:8]}"
                )
                from dataclasses import replace

                slot_first = replace(slot, superset_group=group_id)
                expanded_slots.append(slot_first)

                second_candidate = next(
                    (ex for ex in eligible if ex.id == slot.superset_exercise_id), None
                )
                if second_candidate:
                    second_muscles = cast(
                        tuple[MuscleGroup, ...], (second_candidate.primary_muscle,)
                    )
                    second_pattern = second_candidate.movement_pattern
                else:
                    second_muscles = slot.target_muscles
                    second_pattern = slot.movement_pattern

                slot_second = replace(
                    slot_first,
                    exercise_id=slot.superset_exercise_id,
                    exercise_slug_hint=cast(str, slot.superset_exercise_slug_hint),
                    target_muscles=second_muscles,
                    movement_pattern=second_pattern,
                    superset_exercise_id=None,
                    superset_exercise_slug_hint=None,
                )
                expanded_slots.append(slot_second)
            else:
                expanded_slots.append(slot)

        for slot in expanded_slots:
            if slot.exercise_id is not None:
                reserved[slot.exercise_id] -= 1
            original = catalog_by_id.get(slot.exercise_id) if slot.exercise_id is not None else None
            candidate = (
                eligible_by_id.get(slot.exercise_id) if slot.exercise_id is not None else None
            )
            if candidate is not None and not _template_slot_is_compatible(candidate, slot, index):
                build_reasons.append("TEMPLATE_SLOT_SEMANTIC_MISMATCH")
                candidate = None
            if candidate is not None:
                level_candidate = _level_appropriate_template_candidate(
                    request,
                    candidate,
                    slot,
                    index,
                    eligible,
                    selected,
                    used,
                    reserved,
                    ruleset,
                )
                if level_candidate.id != candidate.id:
                    candidate = level_candidate
                    build_reasons.append("TEMPLATE_LEVEL_PALETTE_RESOLUTION")
                    if used[candidate.id]:
                        repeated_level_resolutions.add((index, candidate.id))
            repeated_explicit_slot = (
                candidate is not None
                and bool(used[candidate.id])
                and all(selected_candidate.id != candidate.id for selected_candidate, _ in selected)
            )
            if repeated_explicit_slot and candidate is not None:
                repeated_template_selections.add((index, candidate.id))
            if slot.exercise_id is None:
                # A structural slot without a referenced exercise is initial construction.
                candidate = min(
                    (
                        item
                        for item in eligible
                        if not used[item.id]
                        and not reserved[item.id]
                        and _template_slot_is_compatible(item, slot, index)
                    ),
                    key=lambda item: str(item.id),
                    default=None,
                )
            elif candidate is None or (used[candidate.id] and not repeated_explicit_slot):
                candidate = (
                    _rank_template_slot_candidates(
                        request,
                        slot,
                        index,
                        eligible,
                        used,
                        reserved,
                        ruleset,
                        original=original,
                        excluded_ids=frozenset(
                            substitutions_by_requested.get(slot.exercise_id, set())
                        ),
                    )
                    if original is not None
                    else None
                )
            if candidate is None:
                if slot.adaptation_priority == "core":
                    if slot.exercise_id is None:
                        # Preserve existing construction fallback for reference-free core slots.
                        candidate = min(
                            (
                                item
                                for item in eligible
                                if all(
                                    selected_candidate.id != item.id
                                    for selected_candidate, _ in selected
                                )
                                and _template_slot_is_compatible(item, slot, index)
                            ),
                            key=lambda item: (used[item.id], str(item.id)),
                            default=None,
                        )
                    else:
                        candidate = (
                            _rank_template_slot_candidates(
                                request,
                                slot,
                                index,
                                eligible,
                                used,
                                reserved,
                                ruleset,
                                original=original,
                                allow_reuse=True,
                                selected_ids=frozenset(
                                    item.id for item, _selected_slot in selected
                                ),
                                excluded_ids=frozenset(
                                    substitutions_by_requested.get(slot.exercise_id, set())
                                ),
                            )
                            if original is not None
                            else None
                        )
                    if candidate is None:
                        raise TemplateConstructionError(
                            "TEMPLATE_CORE_SLOT_UNRESOLVABLE",
                            f"TEMPLATE_DAY:{index}",
                            f"TEMPLATE_PATTERN:{slot.movement_pattern.value}",
                        )
                    repeated_core_substitutions.add((index, candidate.id))
                    build_reasons.append("TEMPLATE_CORE_SUBSTITUTION_REPEATED_FOR_PROGRESSION")
                else:
                    build_reasons.append("TEMPLATE_OPTIONAL_SLOT_OMITTED_UNAVAILABLE")
                    continue
            if (
                not is_core_or_supplemental_exercise(candidate)
                and not coherence.allows_direct(candidate.primary_muscle)
            ):
                build_reasons.append("TEMPLATE_DIRECT_MUSCLE_OUT_OF_SCOPE")
                if slot.adaptation_priority == "core":
                    raise TemplateConstructionError(
                        "TEMPLATE_CORE_SLOT_OUT_OF_SCOPE",
                        f"TEMPLATE_DAY:{index}",
                    )
                continue
            semantic_duplicate = has_near_equivalent(
                candidate,
                (selected_candidate for selected_candidate, _selected_slot in selected),
            )
            if semantic_duplicate:
                complementary = _complementary_template_candidate(
                    request,
                    reference_day,
                    selected,
                    eligible,
                    used,
                    reserved,
                    ruleset,
                )
                if complementary is not None:
                    candidate = complementary
                    complementary_replacements.add(candidate.id)
                    build_reasons.append("TEMPLATE_REDUNDANCY_REPLACED_WITH_COMPLEMENTARY_ROLE")
                else:
                    build_reasons.append("TEMPLATE_SEMANTIC_DUPLICATE_OMITTED")
                    if slot.adaptation_priority == "core":
                        raise TemplateConstructionError(
                            "TEMPLATE_CORE_SEMANTIC_DUPLICATE_UNRESOLVABLE",
                            f"TEMPLATE_DAY:{index}",
                            f"TEMPLATE_PATTERN:{slot.movement_pattern.value}",
                        )
                    continue
            if _template_role_is_excessive(candidate, selected):
                complementary = _complementary_template_candidate(
                    request,
                    reference_day,
                    selected,
                    eligible,
                    used,
                    reserved,
                    ruleset,
                )
                if complementary is not None:
                    candidate = complementary
                    complementary_replacements.add(candidate.id)
                    build_reasons.append("TEMPLATE_REDUNDANCY_REPLACED_WITH_COMPLEMENTARY_ROLE")
                else:
                    deliberate_redundancies.add(candidate.id)
                    build_reasons.append("DELIBERATE_REDUNDANCY_FOR_TEMPLATE_STRUCTURE")
            if (
                is_main_resistance_exercise(candidate)
                and main_exercise_count(candidate for candidate, _slot in selected) >= main_capacity
            ):
                if slot.adaptation_priority == "core":
                    raise TemplateConstructionError(
                        "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
                        f"TEMPLATE_DAY:{index}",
                        "TEMPLATE_MAIN_COUNT_OUT_OF_RANGE",
                    )
                build_reasons.append("TEMPLATE_MAIN_COUNT_CAPPED_FOR_DURATION")
                continue
            selected_muscles = {item.primary_muscle for item, _selected_slot in selected}
            if (
                slot.adaptation_priority == "optional"
                and candidate.primary_muscle is not None
                and candidate.primary_muscle not in selected_muscles
                and weekly_direct_sessions[candidate.primary_muscle]
                >= _template_direct_frequency_cap(len(template.days), ruleset)
            ):
                build_reasons.append("TEMPLATE_OPTIONAL_SLOT_OMITTED_FOR_RECOVERY")
                continue
            selected.append((candidate, slot))
            used[candidate.id] += 1
            if slot.exercise_id is not None and candidate.id != slot.exercise_id:
                substitutions_by_requested.setdefault(slot.exercise_id, set()).add(candidate.id)

        accessory_fill_constrained = _add_targeted_accessories(
            request,
            selected,
            reference_day,
            eligible,
            used,
            reserved,
            planned_target,
            planned_minimum,
            ruleset,
            repeated_targeted_accessories,
        )
        if accessory_fill_constrained:
            build_reasons.append("TEMPLATE_SESSION_COUNT_CONSTRAINED_BY_SAFE_CAPACITY")
        while (
            sum(is_core_or_supplemental_exercise(candidate) for candidate, _slot in selected) > 2
            or main_exercise_count(candidate for candidate, _slot in selected) > main_capacity
        ):
            removable = next(
                (
                    position
                    for position in range(len(selected) - 1, -1, -1)
                    if is_core_or_supplemental_exercise(selected[position][0])
                ),
                None,
            )
            if removable is None:
                removable = next(
                    (
                        position
                        for priority in ("optional", "accessory")
                        for position in range(len(selected) - 1, -1, -1)
                        if selected[position][1].adaptation_priority == priority
                    ),
                    None,
                )
            if removable is None:
                raise TemplateConstructionError(
                    "TEMPLATE_CORE_STRUCTURE_EXCEEDS_SESSION_CAPACITY",
                    f"TEMPLATE_DAY:{index}",
                )
            removed, _ = selected.pop(removable)
            used[removed.id] -= 1
            if is_core_or_supplemental_exercise(removed):
                build_reasons.append("TEMPLATE_SUPPLEMENTAL_TRIMMED_FOR_CAPACITY")
            else:
                build_reasons.append("TEMPLATE_ACCESSORY_TRIMMED_FOR_TIME_LIMIT")
        weekly_direct_sessions.update(
            {
                candidate.primary_muscle
                for candidate, _slot in selected
                if candidate.primary_muscle is not None
            }
        )
        if (
            not planned_minimum <= main_exercise_count(candidate for candidate, _slot in selected)
            and not accessory_fill_constrained
            or main_exercise_count(candidate for candidate, _slot in selected) > main_capacity
        ):
            raise TemplateConstructionError(
                "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
                f"TEMPLATE_DAY:{index}",
            )

        reasons: dict[UUID, tuple[str, ...]] = {}
        substitutions: dict[UUID, tuple[UUID, ...]] = {}
        substitution_decisions = []
        exercises: list[ExerciseCandidate] = []
        for candidate, slot in selected:
            exercises.append(candidate)
            preserved = candidate.id == slot.exercise_id
            is_template_slot = slot.exercise_slug_hint not in {
                "engine-targeted-accessory",
                "engine-required-core",
            }
            intentional_repeat = (
                preserved
                and is_template_slot
                and bool(preserved_template_occurrences[candidate.id])
            )
            reasons[candidate.id] = (
                "TEMPLATE_REFERENCE_EXERCISE" if preserved else "TEMPLATE_SAFE_SUBSTITUTION",
                f"TEMPLATE_ADAPTATION_PRIORITY:{slot.adaptation_priority}",
                f"TEMPLATE_INTENSITY_METHOD:{slot.intensity_method}",
                *(
                    ("TEMPLATE_REDUNDANCY_REPLACED_WITH_COMPLEMENTARY_ROLE",)
                    if candidate.id in complementary_replacements
                    else ()
                ),
                *(
                    ("DELIBERATE_REDUNDANCY_FOR_TEMPLATE_STRUCTURE",)
                    if candidate.id in deliberate_redundancies
                    else ()
                ),
                *(
                    ("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",)
                    if intentional_repeat
                    or (index, candidate.id) in repeated_core_substitutions
                    or (index, candidate.id) in repeated_targeted_accessories
                    or (index, candidate.id) in repeated_level_resolutions
                    or (index, candidate.id) in repeated_template_selections
                    else ()
                ),
                *(
                    supplemental_reason_codes(
                        candidate.primary_muscle,
                        planned=candidate.primary_muscle in request.source.priority_muscles,
                    )
                    if candidate.primary_muscle is not None
                    and is_supplemental_muscle(candidate.primary_muscle)
                    else ()
                ),
                *(("PRIMARY_WORKING_COMPOUND",) if is_primary_working_compound(candidate) else ()),
            )
            if preserved and is_template_slot:
                preserved_template_occurrences[candidate.id] += 1
            decision = rank_substitutions(
                request,
                candidate,
                list(eligible),
                SubstitutionContext(
                    cause=SubstitutionCause.DISPLAY_ALTERNATIVE,
                    allowed_patterns=template_slot_allowed_patterns(
                        slot.movement_pattern, slot.target_muscles
                    ),
                    target_muscles=(
                        frozenset(slot.target_muscles)
                        if slot.target_muscles
                        else frozenset({candidate.primary_muscle})
                        if candidate.primary_muscle is not None
                        else None
                    ),
                    day_focus=f"template_reference_{index}",
                ),
                ruleset=ruleset,
                limit=ruleset.substitution_limit,
            )
            substitution_decisions.append(decision)
            substitutions[candidate.id] = decision.exercise_ids
            resolutions.append(
                TemplateSlotResolution(
                    day_index=index,
                    requested_exercise_id=slot.exercise_id,
                    selected_exercise_id=candidate.id,
                    adaptation_priority=slot.adaptation_priority,
                    intensity_method=slot.intensity_method,
                    superset_group=slot.superset_group,
                    original_prescription=(
                        slot.sets,
                        slot.rep_min,
                        slot.rep_max,
                        slot.target_rir,
                        slot.rest_seconds,
                    ),
                    is_template_slot=is_template_slot,
                )
            )
        drafts.append(
            SessionDraft(
                day_index=index,
                weekday=ruleset.default_weekdays[len(template.days)][index - 1],
                focus=f"template_reference_{index}",
                exercises=exercises,
                selection_reasons=reasons,
                substitutions=substitutions,
                substitution_decisions=tuple(substitution_decisions),
                reason_codes=tuple(dict.fromkeys(build_reasons)),
                template_target_muscles=reference_day.focus,
                template_structure_focus=reference_day.structure_focus,
            )
        )
    weekly_occurrences: Counter[UUID] = Counter()
    for draft in drafts:
        for candidate in draft.exercises:
            weekly_occurrences[candidate.id] += 1
            if weekly_occurrences[candidate.id] <= 1:
                continue
            current_reasons = draft.selection_reasons.get(candidate.id, ())
            if "CORE_MOVEMENT_REPEATED_FOR_PROGRESSION" not in current_reasons:
                draft.selection_reasons[candidate.id] = (
                    *current_reasons,
                    "CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",
                )

    return TemplateSessionBuild(
        drafts=tuple(drafts),
        titles=tuple(day.title for day in template.days),
        resolutions=tuple(resolutions),
        reason_codes=tuple(dict.fromkeys(build_reasons)),
    )


def template_adaptation_priority(exercise: object) -> str | None:
    reason_codes = getattr(exercise, "reason_codes", ())
    for code in reason_codes:
        if isinstance(code, str) and code.startswith("TEMPLATE_ADAPTATION_PRIORITY:"):
            return code.partition(":")[2]
    return None


def template_intensity_method(exercise: object) -> str | None:
    reason_codes = getattr(exercise, "reason_codes", ())
    for code in reason_codes:
        if isinstance(code, str) and code.startswith("TEMPLATE_INTENSITY_METHOD:"):
            return code.partition(":")[2]
    return None


def template_removal_rank(exercise: object) -> int:
    return {
        "optional": 0,
        "accessory": 1,
        None: 2,
        "core": 3,
    }.get(template_adaptation_priority(exercise), 2)


def adaptation_preservation_rank(exercise: object, muscle_policy: object) -> int:
    """Rank work by product hierarchy; larger values are preserved longer."""

    primary_muscle = getattr(exercise, "primary_muscle", None)
    preservation_rank = getattr(muscle_policy, "preservation_rank", None)
    muscle_rank = preservation_rank(primary_muscle) if callable(preservation_rank) else 0

    method_bonus = 30 if template_intensity_method(exercise) in {"superset", "drop_set"} else 0

    # Explicit user priority (rank 3) trumps template core
    if isinstance(muscle_rank, int) and muscle_rank >= 3:
        return 70 + method_bonus

    template_priority = template_adaptation_priority(exercise)
    if template_priority == "core":
        return 60 + method_bonus

    if isinstance(muscle_rank, int) and muscle_rank > 0:
        return 50 + muscle_rank + method_bonus
    if template_priority == "accessory":
        return 20 + method_bonus
    if template_priority == "optional":
        return method_bonus
    return 10 + method_bonus


def _rank_template_slot_candidates(
    request: NormalizedProgramRequest,
    slot: TemplateReferenceSlot,
    day_index: int,
    eligible: tuple[ExerciseCandidate, ...],
    used: Counter[object],
    reserved: Counter[UUID],
    ruleset: ProgramRuleset,
    *,
    original: ExerciseCandidate,
    allow_reuse: bool = False,
    selected_ids: frozenset[UUID] = frozenset(),
    excluded_ids: frozenset[UUID] = frozenset(),
) -> ExerciseCandidate | None:
    options = tuple(
        item
        for item in eligible
        if (allow_reuse or (not used[item.id] and not reserved[item.id]))
        and item.id not in selected_ids
        and item.id not in excluded_ids
    )
    if not options:
        return None
    target_muscles = frozenset(slot.target_muscles)
    replacements = rank_substitutions(
        request,
        original,
        list(options),
        SubstitutionContext(
            cause=SubstitutionCause.TEMPLATE_RECOVERY,
            allowed_patterns=template_slot_allowed_patterns(
                slot.movement_pattern, slot.target_muscles
            ),
            target_muscles=target_muscles,
            day_focus=f"template_reference_{day_index}",
        ),
        ruleset=ruleset,
        limit=len(options),
    )
    return replacements.options[0].exercise if replacements.options else None


def _level_appropriate_template_candidate(
    request: NormalizedProgramRequest,
    original: ExerciseCandidate,
    slot: TemplateReferenceSlot,
    day_index: int,
    eligible: tuple[ExerciseCandidate, ...],
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
    used: Counter[object],
    reserved: Counter[UUID],
    ruleset: ProgramRuleset,
) -> ExerciseCandidate:
    # Core/supplemental template slots are anatomical or accessory work, not
    # main-resistance opportunities. Preserve the explicit candidate even when
    # level adaptation would otherwise prefer a higher-ranked main exercise.
    if is_core_or_supplemental_exercise(original):
        return original
    if (
        request.source.training_experience is TrainingExperience.INTERMEDIATE
        and not original.equipment.intersection({Equipment.MACHINE, Equipment.CABLE})
    ):
        return original
    options = [
        item
        for item in eligible
        if _template_slot_is_compatible(item, slot, day_index)
        and (item.id == original.id or (not used[item.id] and not reserved[item.id]))
    ]
    if len(options) <= 1:
        return original
    equipment_use: Counter[object] = Counter(
        equipment for candidate, _selected_slot in selected for equipment in candidate.equipment
    )
    ranked = rank_exercises(
        request,
        options,
        ruleset,
        needed_muscle=slot.target_muscles[0] if slot.target_muscles else None,
    )
    diversity_weight = (
        6
        if request.source.training_experience
        in {TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED}
        else 0
    )
    ranked_selection = min(
        ranked,
        key=lambda item: (
            -(
                item.score
                - diversity_weight
                * sum(equipment_use[equipment] for equipment in item.exercise.equipment)
            ),
            str(item.exercise.id),
        ),
    )
    if request.source.training_experience in {
        TrainingExperience.FIRST_MONTH,
        TrainingExperience.BEGINNER,
        TrainingExperience.ADVANCED,
    }:
        original_rank = next(item for item in ranked if item.exercise.id == original.id)
        if ranked_selection.score <= original_rank.score:
            return original
    return ranked_selection.exercise


def _template_role_is_excessive(
    candidate: ExerciseCandidate,
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
) -> bool:
    if has_near_equivalent(
        candidate,
        (selected_candidate for selected_candidate, _selected_slot in selected),
    ):
        return True
    role_count = sum(
        item.primary_muscle is candidate.primary_muscle
        and item.movement_pattern is candidate.movement_pattern
        for item, _slot in selected
    )
    role_limit = 1 if candidate.movement_pattern is MovementPattern.SHRUG else 2
    return role_count >= role_limit


def _complementary_template_candidate(
    request: NormalizedProgramRequest,
    reference_day: TemplateReferenceDay,
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
    eligible: tuple[ExerciseCandidate, ...],
    used: Counter[object],
    reserved: Counter[UUID],
    ruleset: ProgramRuleset,
) -> ExerciseCandidate | None:
    focus = set(reference_day.focus)
    coherence = SessionCoherence.from_template_reference_day(reference_day)
    options = [
        item
        for item in eligible
        if not used[item.id]
        and not reserved[item.id]
        and item.primary_muscle in focus
        and evaluate_candidate_slot_compatibility(
            item,
            allowed_patterns=frozenset(MovementPattern) - {MovementPattern.OTHER},
            target_muscles=frozenset(focus),
            day_focus=f"template_reference_{reference_day.day_number}",
        ).compatible
        and not has_near_equivalent(
            item,
            (selected_candidate for selected_candidate, _selected_slot in selected),
        )
        and not _template_role_is_excessive(item, selected)
    ]
    if not options:
        return None
    ranked = rank_exercises(request, options, ruleset)
    return min(
        ranked,
        key=lambda item: (
            *coherence.placement_rank(
                item.exercise.primary_muscle,
                existing_exposure=any(
                    selected_item.primary_muscle is item.exercise.primary_muscle
                    for selected_item, _slot in selected
                ),
            ),
            -item.score,
            str(item.exercise.id),
        ),
    ).exercise


def apply_template_intent(
    days: tuple[WorkoutDay, ...],
    build: TemplateSessionBuild,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    resolutions = {(item.day_index, item.selected_exercise_id): item for item in build.resolutions}
    personalized: list[WorkoutDay] = []
    for day, title in zip(days, build.titles, strict=True):
        exercises = []
        for exercise in day.exercises:
            resolution = resolutions[(day.day_index, exercise.exercise_id)]
            rest_seconds = exercise.rest_seconds
            rep_min = exercise.rep_min
            rep_max = exercise.rep_max
            target_rir = exercise.target_rir
            method_reasons: tuple[str, ...] = ()
            if (
                resolution.adaptation_priority == "core"
                and exercise.exercise_type is ExerciseType.COMPOUND
            ):
                rest_seconds = max(
                    rest_seconds,
                    ruleset.minimum_rest_seconds + ruleset.duration_repair_rest_increment_seconds,
                )
            if (
                resolution.intensity_method == "drop_set"
                and exercise.exercise_type is ExerciseType.ISOLATION
                and rep_min is not None
                and rep_max is not None
                and target_rir is not None
            ):
                rep_min = max(rep_min, 10)
                rep_max = max(rep_max, 15)
                target_rir = min(target_rir, 1)
                rest_seconds = min(rest_seconds, 75)
                method_reasons = ("SAFE_TEMPLATE_DROP_SET_APPLIED",)
            prescription = (
                exercise.sets,
                rep_min,
                rep_max,
                target_rir,
                rest_seconds,
            )
            changed = prescription != resolution.original_prescription
            exercises.append(
                replace(
                    exercise,
                    rep_min=rep_min,
                    rep_max=rep_max,
                    target_rir=target_rir,
                    rest_seconds=rest_seconds,
                    estimated_minutes=estimate_exercise_minutes(
                        exercise.sets,
                        rest_seconds,
                        exercise.warmup_sets,
                        ruleset,
                    ),
                    reason_codes=exercise.reason_codes
                    + method_reasons
                    + (("TEMPLATE_PRESCRIPTION_PERSONALIZED",) if changed else ())
                    + (
                        ("TEMPLATE_CORE_REST_FLOOR_PRESERVED",)
                        if rest_seconds > exercise.rest_seconds
                        else ()
                    ),
                    notes=(
                        "drop_set:last_working_set_reduce_load_20_to_30_percent"
                        if method_reasons
                        else None
                        if resolution.intensity_method in {"standard", "drop_set"}
                        else resolution.intensity_method
                    ),
                    superset_group=resolution.superset_group,
                )
            )
        personalized.append(replace(day, title=title, exercises=tuple(exercises)))
    return tuple(personalized)


def template_resolution_trace(
    build: TemplateSessionBuild,
    days: tuple[WorkoutDay, ...],
) -> dict[str, object]:
    programmed = {(day.day_index, item.exercise_id): item for day in days for item in day.exercises}
    template_slots = tuple(item for item in build.resolutions if item.is_template_slot)
    retained_template_slots = tuple(
        item for item in template_slots if (item.day_index, item.selected_exercise_id) in programmed
    )
    core_slots = tuple(item for item in template_slots if item.adaptation_priority == "core")
    retained_core_slots = tuple(
        item for item in core_slots if (item.day_index, item.selected_exercise_id) in programmed
    )
    preserved = tuple(
        str(item.selected_exercise_id)
        for item in build.resolutions
        if item.preserved_exactly and (item.day_index, item.selected_exercise_id) in programmed
    )
    substitutions = tuple(
        {
            "requested_exercise_id": (
                str(item.requested_exercise_id) if item.requested_exercise_id is not None else None
            ),
            "selected_exercise_id": str(item.selected_exercise_id),
            "day_index": item.day_index,
        }
        for item in build.resolutions
        if item.is_template_slot
        and item.requested_exercise_id is not None
        and not item.preserved_exactly
        and (item.day_index, item.selected_exercise_id) in programmed
    )
    prescription_changes = tuple(
        {
            "exercise_id": str(item.selected_exercise_id),
            "day_index": item.day_index,
            "adaptation_priority": item.adaptation_priority,
            "intensity_method": item.intensity_method,
            "before": item.original_prescription,
            "after": (
                programmed[(item.day_index, item.selected_exercise_id)].sets,
                programmed[(item.day_index, item.selected_exercise_id)].rep_min,
                programmed[(item.day_index, item.selected_exercise_id)].rep_max,
                programmed[(item.day_index, item.selected_exercise_id)].target_rir,
                programmed[(item.day_index, item.selected_exercise_id)].rest_seconds,
            ),
        }
        for item in build.resolutions
        if (item.day_index, item.selected_exercise_id) in programmed
        and (
            programmed[(item.day_index, item.selected_exercise_id)].sets,
            programmed[(item.day_index, item.selected_exercise_id)].rep_min,
            programmed[(item.day_index, item.selected_exercise_id)].rep_max,
            programmed[(item.day_index, item.selected_exercise_id)].target_rir,
            programmed[(item.day_index, item.selected_exercise_id)].rest_seconds,
        )
        != item.original_prescription
    )
    return {
        "stage": "template_adaptation",
        "preserved_exercise_ids": preserved,
        "substitutions": substitutions,
        "prescription_changes": prescription_changes,
        "template_slot_count": len(template_slots),
        "retained_template_slot_count": len(retained_template_slots),
        "core_slot_count": len(core_slots),
        "retained_core_slot_count": len(retained_core_slots),
        "reason_codes": build.reason_codes,
    }


def _add_targeted_accessories(
    request: NormalizedProgramRequest,
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
    reference_day: TemplateReferenceDay,
    eligible: tuple[ExerciseCandidate, ...],
    used: Counter[object],
    reserved: Counter[UUID],
    minimum_exercises: int,
    required_minimum: int,
    ruleset: ProgramRuleset,
    repeated_targeted_accessories: set[tuple[int, UUID]],
) -> bool:
    target_muscles = reference_day.focus
    coherence = SessionCoherence.from_template_reference_day(reference_day)
    while main_exercise_count(candidate for candidate, _slot in selected) < minimum_exercises:
        options = [
            item
            for item in eligible
            if not used[item.id]
            and not reserved[item.id]
            and item.is_active
            and item.is_programmable
            and not item.needs_review
            and is_main_resistance_exercise(item)
            and item.primary_muscle in target_muscles
            and (
                main_exercise_count(candidate for candidate, _slot in selected) < required_minimum
                or not _template_role_is_excessive(item, selected)
            )
            and evaluate_candidate_slot_compatibility(
                item,
                allowed_patterns=frozenset(MovementPattern) - {MovementPattern.OTHER},
                target_muscles=frozenset(target_muscles),
                day_focus=f"template_reference_{reference_day.day_number}",
            ).compatible
            and (
                not has_near_equivalent(
                    item,
                    (selected_candidate for selected_candidate, _selected_slot in selected),
                )
            )
        ]
        if not options:
            return True
        ranked = rank_exercises(request, options, ruleset)
        candidate = min(
            ranked,
            key=lambda item: (
                *coherence.placement_rank(
                    item.exercise.primary_muscle,
                    existing_exposure=any(
                        selected_item.primary_muscle is item.exercise.primary_muscle
                        for selected_item, _slot in selected
                    ),
                ),
                -item.score,
                str(item.exercise.id),
            ),
        ).exercise
        if used[candidate.id]:
            repeated_targeted_accessories.add((reference_day.day_number, candidate.id))
        supplemental_start = next(
            (
                position
                for position, (item, _slot) in enumerate(selected)
                if is_supplemental_muscle(item.primary_muscle)
            ),
            len(selected),
        )
        selected.insert(
            supplemental_start,
            (
                candidate,
                TemplateReferenceSlot(
                    exercise_id=candidate.id,
                    exercise_slug_hint="engine-targeted-accessory",
                    target_muscles=target_muscles,
                    movement_pattern=candidate.movement_pattern,
                    intensity_method="standard",
                    adaptation_priority="accessory",
                    superset_group=None,
                    superset_exercise_id=None,
                    superset_exercise_slug_hint=None,
                    sets=3,
                    rep_min=8,
                    rep_max=15,
                    target_rir=2,
                    rest_seconds=60,
                ),
            ),
        )
        used[candidate.id] += 1
    return False


def _template_slot_is_compatible(
    candidate: ExerciseCandidate,
    slot: TemplateReferenceSlot,
    day_index: int,
) -> bool:
    return evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=template_slot_allowed_patterns(slot.movement_pattern, slot.target_muscles),
        target_muscles=frozenset(slot.target_muscles),
        day_focus=f"template_reference_{day_index}",
    ).compatible


def _template_direct_frequency_cap(
    training_days: int,
    ruleset: ProgramRuleset,
) -> int:
    if training_days <= 4:
        return ruleset.maximum_direct_sessions_per_muscle_per_week
    return ruleset.maximum_direct_sessions_per_muscle_per_week + (training_days - 4)
