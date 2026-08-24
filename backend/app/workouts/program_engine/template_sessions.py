from collections import Counter
from dataclasses import dataclass, replace
from uuid import UUID

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_capacity import SessionCapacity
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.replacement_ranker import rank_replacement_exercises
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
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    template_slot_allowed_patterns,
)
from app.workouts.program_engine.supplemental_policy import (
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
) -> TemplateSessionBuild:
    eligible_by_id = {candidate.id: candidate for candidate in eligible}
    used: Counter[object] = Counter()
    reserved: Counter[UUID] = Counter(
        slot.exercise_id
        for day in template.days
        for slot in day.slots
        if slot.exercise_id is not None
    )
    drafts: list[SessionDraft] = []
    resolutions: list[TemplateSlotResolution] = []
    build_reasons: list[str] = []
    complementary_replacements: set[UUID] = set()
    deliberate_redundancies: set[UUID] = set()
    repeated_core_substitutions: set[tuple[int, UUID]] = set()
    repeated_targeted_accessories: set[tuple[int, UUID]] = set()
    preserved_template_occurrences: Counter[UUID] = Counter()
    weekly_direct_sessions: Counter[MuscleGroup] = Counter()
    for index, reference_day in enumerate(template.days, start=1):
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
            capacity = max(capacity, ruleset.minimum_exercises_per_session)
        planned_minimum = min(ruleset.minimum_exercises_per_session, capacity)
        if planned_minimum < ruleset.minimum_exercises_per_session:
            build_reasons.append("DURATION_PLANNED_REDUCED_EXERCISE_COUNT")
        selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]] = []
        for slot in reference_day.slots:
            if slot.exercise_id is not None:
                reserved[slot.exercise_id] -= 1
            candidate = (
                eligible_by_id.get(slot.exercise_id) if slot.exercise_id is not None else None
            )
            if candidate is not None and not _template_slot_is_compatible(candidate, slot, index):
                build_reasons.append("TEMPLATE_SLOT_SEMANTIC_MISMATCH")
                candidate = None
            repeated_explicit_slot = (
                candidate is not None
                and bool(used[candidate.id])
                and all(selected_candidate.id != candidate.id for selected_candidate, _ in selected)
            )
            if candidate is None or (used[candidate.id] and not repeated_explicit_slot):
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
            if candidate is None:
                if slot.adaptation_priority == "core":
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

        _add_targeted_accessories(
            request,
            selected,
            reference_day,
            eligible,
            used,
            reserved,
            planned_minimum,
            ruleset,
            repeated_targeted_accessories,
        )
        while (
            sum(is_supplemental_muscle(candidate.primary_muscle) for candidate, _slot in selected)
            > 1
            or len(selected) > capacity
        ):
            removable = next(
                (
                    position
                    for position in range(len(selected) - 1, -1, -1)
                    if is_supplemental_muscle(selected[position][0].primary_muscle)
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
            if is_supplemental_muscle(removed.primary_muscle):
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
            or len(selected) > ruleset.max_exercises_per_session
        ):
            raise TemplateConstructionError(
                "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
                f"TEMPLATE_DAY:{index}",
            )

        reasons: dict[UUID, tuple[str, ...]] = {}
        substitutions: dict[UUID, tuple[UUID, ...]] = {}
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
            )
            if preserved and is_template_slot:
                preserved_template_occurrences[candidate.id] += 1
            substitutions[candidate.id] = tuple(
                alternative.id
                for alternative in rank_replacement_exercises(
                    request,
                    candidate,
                    eligible,
                    limit=ruleset.substitution_limit,
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
                )
            )
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
                reason_codes=tuple(dict.fromkeys(build_reasons)),
            )
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

    # Explicit user priority (rank 3) trumps template core
    if isinstance(muscle_rank, int) and muscle_rank >= 3:
        return 70

    template_priority = template_adaptation_priority(exercise)
    if template_priority == "core":
        return 60

    if isinstance(muscle_rank, int) and muscle_rank > 0:
        return 50 + muscle_rank
    if template_priority == "accessory":
        return 20
    if template_priority == "optional":
        return 0
    return 10


def _rank_template_slot_candidates(
    request: NormalizedProgramRequest,
    slot: TemplateReferenceSlot,
    day_index: int,
    eligible: tuple[ExerciseCandidate, ...],
    used: Counter[object],
    reserved: Counter[UUID],
    ruleset: ProgramRuleset,
    *,
    original: ExerciseCandidate | None,
) -> ExerciseCandidate | None:
    options = tuple(
        item
        for item in eligible
        if not used[item.id]
        and not reserved[item.id]
        and _template_slot_is_compatible(item, slot, day_index)
    )
    if not options:
        return None
    target_muscles = frozenset(slot.target_muscles)
    if original is not None:
        replacements = rank_replacement_exercises(
            request,
            original,
            options,
            limit=len(options),
            allowed_patterns=template_slot_allowed_patterns(
                slot.movement_pattern, slot.target_muscles
            ),
            target_muscles=target_muscles,
            day_focus=f"template_reference_{day_index}",
        )
        if replacements:
            return replacements[0]
    needed_muscle = slot.target_muscles[0] if len(slot.target_muscles) == 1 else None
    ranked = rank_exercises(request, options, ruleset, needed_muscle=needed_muscle)
    return ranked[0].exercise if ranked else None


def _template_role_is_excessive(
    candidate: ExerciseCandidate,
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
) -> bool:
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
    if focus.intersection({MuscleGroup.CHEST, MuscleGroup.TRICEPS}):
        focus.add(MuscleGroup.SHOULDERS)
    if focus.intersection({MuscleGroup.BACK, MuscleGroup.BICEPS}):
        focus.update({MuscleGroup.SHOULDERS, MuscleGroup.TRAPS})
    options = [
        item
        for item in eligible
        if not used[item.id]
        and not reserved[item.id]
        and evaluate_candidate_slot_compatibility(
            item,
            allowed_patterns=frozenset(MovementPattern) - {MovementPattern.OTHER},
            target_muscles=frozenset(focus),
            day_focus=f"template_reference_{reference_day.day_number}",
        ).compatible
        and not _template_role_is_excessive(item, selected)
    ]
    if not options:
        return None
    return rank_exercises(request, options, ruleset)[0].exercise


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
            if (
                resolution.adaptation_priority == "core"
                and exercise.exercise_type is ExerciseType.COMPOUND
            ):
                rest_seconds = max(
                    rest_seconds,
                    ruleset.minimum_rest_seconds + ruleset.duration_repair_rest_increment_seconds,
                )
            prescription = (
                exercise.sets,
                exercise.rep_min,
                exercise.rep_max,
                exercise.target_rir,
                rest_seconds,
            )
            changed = prescription != resolution.original_prescription
            exercises.append(
                replace(
                    exercise,
                    rest_seconds=rest_seconds,
                    estimated_minutes=estimate_exercise_minutes(
                        exercise.sets,
                        rest_seconds,
                        exercise.warmup_sets,
                        ruleset,
                    ),
                    reason_codes=exercise.reason_codes
                    + (("TEMPLATE_PRESCRIPTION_PERSONALIZED",) if changed else ())
                    + (
                        ("TEMPLATE_CORE_REST_FLOOR_PRESERVED",)
                        if rest_seconds > exercise.rest_seconds
                        else ()
                    ),
                    notes=(
                        None
                        if resolution.intensity_method == "standard"
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
    ruleset: ProgramRuleset,
    repeated_targeted_accessories: set[tuple[int, UUID]],
) -> None:
    target_muscles = reference_day.focus
    while main_exercise_count(candidate for candidate, _slot in selected) < minimum_exercises:
        options = [
            item
            for item in eligible
            if not used[item.id]
            and not reserved[item.id]
            and not is_supplemental_muscle(item.primary_muscle)
            and evaluate_candidate_slot_compatibility(
                item,
                allowed_patterns=frozenset(MovementPattern) - {MovementPattern.OTHER},
                target_muscles=frozenset(target_muscles),
                day_focus=f"template_reference_{reference_day.day_number}",
            ).compatible
        ]
        if not options:
            selected_ids = {candidate.id for candidate, _slot in selected}
            options = [
                item
                for item in eligible
                if item.id not in selected_ids
                and not reserved[item.id]
                and not is_supplemental_muscle(item.primary_muscle)
                and evaluate_candidate_slot_compatibility(
                    item,
                    allowed_patterns=frozenset(MovementPattern) - {MovementPattern.OTHER},
                    target_muscles=frozenset(target_muscles),
                    day_focus=f"template_reference_{reference_day.day_number}",
                ).compatible
            ]
            if not options:
                return
        candidate = rank_exercises(request, options, ruleset)[0].exercise
        if used[candidate.id]:
            repeated_targeted_accessories.add((reference_day.day_number, candidate.id))
        selected.append(
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
                    sets=3,
                    rep_min=8,
                    rep_max=15,
                    target_rir=2,
                    rest_seconds=60,
                ),
            )
        )
        used[candidate.id] += 1


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
