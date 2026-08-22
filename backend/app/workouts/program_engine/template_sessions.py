from collections import Counter
from dataclasses import dataclass, replace
from uuid import UUID

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.exercise_ranker import rank_exercises
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
from app.workouts.program_engine.slot_compatibility import evaluate_candidate_slot_compatibility


@dataclass(frozen=True)
class TemplateSlotResolution:
    day_index: int
    requested_exercise_id: UUID | None
    selected_exercise_id: UUID
    adaptation_priority: str
    intensity_method: str
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
    source_catalog: tuple[ExerciseCandidate, ...] | None = None,
) -> TemplateSessionBuild:
    eligible_by_id = {candidate.id: candidate for candidate in eligible}
    source_by_id = {
        candidate.id: candidate
        for candidate in (source_catalog if source_catalog is not None else eligible)
    }
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
    preserved_template_occurrences: Counter[UUID] = Counter()
    weekly_patterns: set[MovementPattern] = set()
    capacity = max(
        ruleset.minimum_exercises_per_session,
        min(
            ruleset.max_exercises_per_session,
            (request.source.session_duration_minutes - ruleset.general_warmup_minutes)
            // ruleset.minutes_per_exercise_slot,
        ),
    )
    for index, reference_day in enumerate(template.days, start=1):
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
                candidate = _rank_template_slot_candidates(
                    request,
                    slot,
                    index,
                    eligible,
                    used,
                    reserved,
                    ruleset,
                    original=source_by_id.get(slot.exercise_id),
                )
            if candidate is None:
                if slot.adaptation_priority == "core":
                    raise TemplateConstructionError(
                        "TEMPLATE_CORE_SLOT_UNRESOLVABLE",
                        f"TEMPLATE_DAY:{index}",
                        f"TEMPLATE_PATTERN:{slot.movement_pattern.value}",
                    )
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
            selected.append((candidate, slot))
            used[candidate.id] += 1
            weekly_patterns.add(candidate.movement_pattern)

        if index == len(template.days) and not weekly_patterns.intersection(
            {
                MovementPattern.CORE_ANTI_EXTENSION,
                MovementPattern.CORE_ANTI_ROTATION,
                MovementPattern.CORE_ANTI_LATERAL_FLEXION,
            }
        ):
            core = next(
                (
                    candidate
                    for candidate in eligible
                    if not used[candidate.id]
                    and not reserved[candidate.id]
                    and candidate.primary_muscle is MuscleGroup.ABS
                    and evaluate_candidate_slot_compatibility(
                        candidate,
                        allowed_patterns=frozenset(
                            {
                                MovementPattern.CORE_ANTI_EXTENSION,
                                MovementPattern.CORE_ANTI_ROTATION,
                                MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                            }
                        ),
                        target_muscles=frozenset({MuscleGroup.ABS}),
                        day_focus=f"template_reference_{index}",
                    ).compatible
                ),
                None,
            )
            if core is None:
                raise TemplateConstructionError("TEMPLATE_REQUIRED_CORE_UNAVAILABLE")
            selected.append((core, _engine_core_slot(core)))
            used[core.id] += 1
            build_reasons.append("TEMPLATE_REQUIRED_CORE_ADDED")

        _add_targeted_accessories(
            request,
            selected,
            reference_day,
            eligible,
            used,
            reserved,
            ruleset.minimum_exercises_per_session,
            ruleset,
        )
        while len(selected) > capacity:
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
            build_reasons.append("TEMPLATE_ACCESSORY_TRIMMED_FOR_TIME_LIMIT")
        if (
            not ruleset.minimum_exercises_per_session
            <= len(selected)
            <= (ruleset.max_exercises_per_session)
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
                *(("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",) if intentional_repeat else ()),
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
                    allowed_patterns=frozenset({slot.movement_pattern}),
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
            allowed_patterns=frozenset({slot.movement_pattern}),
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
) -> tuple[WorkoutDay, ...]:
    resolutions = {(item.day_index, item.selected_exercise_id): item for item in build.resolutions}
    personalized: list[WorkoutDay] = []
    for day, title in zip(days, build.titles, strict=True):
        exercises = []
        for exercise in day.exercises:
            resolution = resolutions[(day.day_index, exercise.exercise_id)]
            prescription = (
                exercise.sets,
                exercise.rep_min,
                exercise.rep_max,
                exercise.target_rir,
                exercise.rest_seconds,
            )
            changed = prescription != resolution.original_prescription
            exercises.append(
                replace(
                    exercise,
                    reason_codes=exercise.reason_codes
                    + (("TEMPLATE_PRESCRIPTION_PERSONALIZED",) if changed else ()),
                    notes=(
                        None
                        if resolution.intensity_method == "standard"
                        else resolution.intensity_method
                    ),
                )
            )
        personalized.append(replace(day, title=title, exercises=tuple(exercises)))
    return tuple(personalized)


def template_resolution_trace(
    build: TemplateSessionBuild,
    days: tuple[WorkoutDay, ...],
) -> dict[str, object]:
    programmed = {(day.day_index, item.exercise_id): item for day in days for item in day.exercises}
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
        "reason_codes": build.reason_codes,
    }


def _engine_core_slot(core: ExerciseCandidate) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=core.id,
        exercise_slug_hint="engine-required-core",
        target_muscles=(MuscleGroup.ABS,),
        movement_pattern=core.movement_pattern,
        intensity_method="standard",
        adaptation_priority="accessory",
        superset_group=None,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=45,
    )


def _add_targeted_accessories(
    request: NormalizedProgramRequest,
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
    reference_day: TemplateReferenceDay,
    eligible: tuple[ExerciseCandidate, ...],
    used: Counter[object],
    reserved: Counter[UUID],
    minimum_exercises: int,
    ruleset: ProgramRuleset,
) -> None:
    target_muscles = reference_day.focus
    while len(selected) < minimum_exercises:
        options = [
            item
            for item in eligible
            if not used[item.id]
            and not reserved[item.id]
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
        allowed_patterns=frozenset({slot.movement_pattern}),
        target_muscles=frozenset(slot.target_muscles),
        day_focus=f"template_reference_{day_index}",
    ).compatible
