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
            if candidate is None or used[candidate.id]:
                candidate = next(
                    (
                        item
                        for item in eligible
                        if not used[item.id]
                        and not reserved[item.id]
                        and item.movement_pattern is slot.movement_pattern
                        and item.primary_muscle in slot.target_muscles
                    ),
                    None,
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
                    and candidate.movement_pattern
                    in {
                        MovementPattern.CORE_ANTI_EXTENSION,
                        MovementPattern.CORE_ANTI_ROTATION,
                        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                    }
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
        if not ruleset.minimum_exercises_per_session <= len(selected) <= (
            ruleset.max_exercises_per_session
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
            reasons[candidate.id] = (
                "TEMPLATE_REFERENCE_EXERCISE" if preserved else "TEMPLATE_SAFE_SUBSTITUTION",
                f"TEMPLATE_ADAPTATION_PRIORITY:{slot.adaptation_priority}",
                f"TEMPLATE_INTENSITY_METHOD:{slot.intensity_method}",
            )
            substitutions[candidate.id] = tuple(
                alternative.id
                for alternative in rank_replacement_exercises(
                    request,
                    candidate,
                    eligible,
                    limit=ruleset.substitution_limit,
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
                    is_template_slot=slot.exercise_slug_hint
                    not in {"engine-targeted-accessory", "engine-required-core"},
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


def apply_template_intent(
    days: tuple[WorkoutDay, ...],
    build: TemplateSessionBuild,
) -> tuple[WorkoutDay, ...]:
    resolutions = {item.selected_exercise_id: item for item in build.resolutions}
    personalized: list[WorkoutDay] = []
    for day, title in zip(days, build.titles, strict=True):
        exercises = []
        for exercise in day.exercises:
            resolution = resolutions[exercise.exercise_id]
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
    programmed = {
        item.exercise_id: item for day in days for item in day.exercises
    }
    preserved = tuple(
        str(item.selected_exercise_id)
        for item in build.resolutions
        if item.preserved_exactly and item.selected_exercise_id in programmed
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
                programmed[item.selected_exercise_id].sets,
                programmed[item.selected_exercise_id].rep_min,
                programmed[item.selected_exercise_id].rep_max,
                programmed[item.selected_exercise_id].target_rir,
                programmed[item.selected_exercise_id].rest_seconds,
            ),
        }
        for item in build.resolutions
        if item.selected_exercise_id in programmed
        and (
            programmed[item.selected_exercise_id].sets,
            programmed[item.selected_exercise_id].rep_min,
            programmed[item.selected_exercise_id].rep_max,
            programmed[item.selected_exercise_id].target_rir,
            programmed[item.selected_exercise_id].rest_seconds,
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
        sets=2,
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
            and item.primary_muscle in target_muscles
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
                    sets=2,
                    rep_min=8,
                    rep_max=15,
                    target_rir=2,
                    rest_seconds=60,
                ),
            )
        )
        used[candidate.id] += 1
