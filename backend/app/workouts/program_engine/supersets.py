from dataclasses import replace
from math import ceil
from typing import Protocol
from uuid import UUID

from app.exercises.enums import Equipment, ExerciseType, MuscleGroup
from app.workouts.program_engine.enums import LoadLimit
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest, ProgrammedExercise
from app.workouts.program_engine.supplemental_policy import is_supplemental_muscle

_LOWER_BODY_MUSCLES = frozenset(
    {
        MuscleGroup.GLUTES,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
    }
)
_UPPER_BODY_MUSCLES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
        MuscleGroup.TRAPS,
        MuscleGroup.FOREARMS,
    }
)


class SupersetExercise(Protocol):
    @property
    def exercise_id(self) -> UUID: ...

    @property
    def primary_muscle(self) -> MuscleGroup | None: ...

    @property
    def secondary_muscles(self) -> tuple[MuscleGroup, ...]: ...

    @property
    def equipment(self) -> frozenset[Equipment]: ...

    @property
    def exercise_type(self) -> ExerciseType: ...

    @property
    def axial_loading_level(self) -> LoadLimit: ...

    @property
    def reason_codes(self) -> tuple[str, ...]: ...


def apply_template_supersets(
    exercises: tuple[ProgrammedExercise, ...],
) -> tuple[tuple[ProgrammedExercise, ...], tuple[str, ...]]:
    """Preserve only complete, adjacent template pairs that pass the safety policy."""

    grouped: dict[str, list[int]] = {}
    for index, exercise in enumerate(exercises):
        if exercise.superset_group is not None:
            grouped.setdefault(exercise.superset_group, []).append(index)
    if not grouped:
        return exercises, ()
    updated = list(exercises)
    reasons: list[str] = []
    for group in sorted(grouped):
        indices = grouped[group]
        members = [updated[index] for index in indices]
        if all("SAFE_SUPERSET_APPLIED_FOR_DURATION" in item.reason_codes for item in members):
            continue
        is_valid = (
            len(indices) == 2
            and indices[1] == indices[0] + 1
            and safe_superset_category(members[0], members[1]) is not None
        )
        if not is_valid:
            for index in indices:
                exercise = updated[index]
                updated[index] = replace(
                    exercise,
                    superset_group=None,
                    reason_codes=tuple(
                        dict.fromkeys((*exercise.reason_codes, "TEMPLATE_SUPERSET_REJECTED_UNSAFE"))
                    ),
                )
            reasons.append("TEMPLATE_SUPERSET_REJECTED_UNSAFE")
            continue
        first_index, second_index = indices
        first = updated[first_index]
        second = updated[second_index]
        saving = _pair_saving_minutes(first, second)
        updated[first_index] = replace(
            first,
            reason_codes=tuple(
                dict.fromkeys((*first.reason_codes, "SAFE_TEMPLATE_SUPERSET_PRESERVED"))
            ),
        )
        updated[second_index] = replace(
            second,
            estimated_minutes=max(1, second.estimated_minutes - saving),
            reason_codes=tuple(
                dict.fromkeys(
                    (
                        *second.reason_codes,
                        "SAFE_TEMPLATE_SUPERSET_PRESERVED",
                        "SAFE_SUPERSET_DURATION_SAVING",
                    )
                )
            ),
        )
        reasons.append("SAFE_TEMPLATE_SUPERSET_PRESERVED")
    return tuple(updated), tuple(dict.fromkeys(reasons))


def apply_duration_pressure_superset(
    exercises: tuple[ProgrammedExercise, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[tuple[ProgrammedExercise, ...], tuple[str, ...]]:
    """Apply one deterministic, visible, low-interference time-saving pair."""

    if any(item.superset_group is not None for item in exercises):
        return exercises, ()
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    options: list[tuple[tuple[object, ...], int, int]] = []
    for first_index, first in enumerate(exercises):
        for second_index in range(first_index + 1, len(exercises)):
            second = exercises[second_index]
            if is_supplemental_muscle(first.primary_muscle) or is_supplemental_muscle(
                second.primary_muscle
            ):
                continue
            category = safe_superset_category(first, second)
            if category is None:
                continue
            options.append(
                (
                    (
                        priority_policy.preservation_rank(first.primary_muscle)
                        + priority_policy.preservation_rank(second.primary_muscle),
                        category,
                        first.order,
                        second.order,
                        str(first.exercise_id),
                        str(second.exercise_id),
                    ),
                    first_index,
                    second_index,
                )
            )
    if not options:
        return exercises, ()
    _, first_index, second_index = min(options)
    ordered = list(exercises)
    second = ordered.pop(second_index)
    ordered.insert(first_index + 1, second)
    first = ordered[first_index]
    second = ordered[first_index + 1]
    group = f"superset-{first.order}-{second.order}"
    saving = _pair_saving_minutes(first, second)
    shared_reason = "SAFE_SUPERSET_APPLIED_FOR_DURATION"
    ordered[first_index] = replace(
        first,
        superset_group=group,
        reason_codes=tuple(dict.fromkeys((*first.reason_codes, shared_reason))),
    )
    ordered[first_index + 1] = replace(
        second,
        superset_group=group,
        estimated_minutes=max(1, second.estimated_minutes - saving),
        reason_codes=tuple(
            dict.fromkeys((*second.reason_codes, shared_reason, "SAFE_SUPERSET_DURATION_SAVING"))
        ),
    )
    return (
        tuple(replace(item, order=index + 1) for index, item in enumerate(ordered)),
        (shared_reason,),
    )


def safe_superset_category(
    first: SupersetExercise,
    second: SupersetExercise,
) -> int | None:
    if not _base_pair_is_safe(first, second):
        return None
    muscles = frozenset({first.primary_muscle, second.primary_muscle})
    if muscles == {MuscleGroup.BICEPS, MuscleGroup.TRICEPS} and _both_isolation(first, second):
        return 0
    if muscles == {MuscleGroup.CHEST, MuscleGroup.BACK} and _both_accessory(first, second):
        return 1
    if (
        first.exercise_type is ExerciseType.CORE
        and second.exercise_type is ExerciseType.ISOLATION
        and second.primary_muscle in _UPPER_BODY_MUSCLES
    ) or (
        second.exercise_type is ExerciseType.CORE
        and first.exercise_type is ExerciseType.ISOLATION
        and first.primary_muscle in _UPPER_BODY_MUSCLES
    ):
        return 2
    if _both_isolation(first, second) and not _muscles_interfere(first, second):
        return 3
    return None


def superset_structure_errors(
    exercises: tuple[ProgrammedExercise, ...],
) -> tuple[str, ...]:
    grouped: dict[str, list[int]] = {}
    for index, exercise in enumerate(exercises):
        if exercise.superset_group is not None:
            grouped.setdefault(exercise.superset_group, []).append(index)
    errors: list[str] = []
    for group in sorted(grouped):
        indices = grouped[group]
        if len(indices) != 2:
            errors.append("SUPERSET_GROUP_INVALID_SIZE")
            continue
        if indices[1] != indices[0] + 1:
            errors.append("SUPERSET_GROUP_NOT_ADJACENT")
            continue
        if safe_superset_category(exercises[indices[0]], exercises[indices[1]]) is None:
            errors.append("UNSAFE_SUPERSET_PAIR")
    return tuple(dict.fromkeys(errors))


def _base_pair_is_safe(first: SupersetExercise, second: SupersetExercise) -> bool:
    if first.exercise_id == second.exercise_id:
        return False
    if "STRENGTH_PRIMARY_COMPOUND" in first.reason_codes or (
        "STRENGTH_PRIMARY_COMPOUND" in second.reason_codes
    ):
        return False
    if first.primary_muscle is None or second.primary_muscle is None:
        return False
    if first.primary_muscle is second.primary_muscle:
        return False
    if _is_heavy_lower_compound(first) or _is_heavy_lower_compound(second):
        return False
    if not _equipment_transition_is_safe(first.equipment, second.equipment):
        return False
    return True


def _both_isolation(first: SupersetExercise, second: SupersetExercise) -> bool:
    return (
        first.exercise_type is ExerciseType.ISOLATION
        and second.exercise_type is ExerciseType.ISOLATION
    )


def _both_accessory(first: SupersetExercise, second: SupersetExercise) -> bool:
    return _is_accessory(first) and _is_accessory(second)


def _is_accessory(exercise: SupersetExercise) -> bool:
    return exercise.exercise_type is ExerciseType.ISOLATION or any(
        code
        in {
            "SESSION_SIZE_ACCESSORY",
            "TEMPLATE_ADAPTATION_PRIORITY:accessory",
            "TEMPLATE_ADAPTATION_PRIORITY:optional",
        }
        for code in exercise.reason_codes
    )


def _is_heavy_lower_compound(exercise: SupersetExercise) -> bool:
    return (
        exercise.exercise_type is ExerciseType.COMPOUND
        and exercise.primary_muscle in _LOWER_BODY_MUSCLES
        and exercise.axial_loading_level is LoadLimit.HIGH
    )


def _equipment_transition_is_safe(
    first: frozenset[Equipment], second: frozenset[Equipment]
) -> bool:
    if Equipment.BODYWEIGHT in first or Equipment.BODYWEIGHT in second:
        return True
    passive = {Equipment.BENCH}
    first_station = first.difference(passive)
    second_station = second.difference(passive)
    return bool(first_station.intersection(second_station))


def _muscles_interfere(first: SupersetExercise, second: SupersetExercise) -> bool:
    return bool(
        first.primary_muscle in second.secondary_muscles
        or second.primary_muscle in first.secondary_muscles
        or set(first.secondary_muscles).intersection(second.secondary_muscles)
    )


def _pair_saving_minutes(
    first: ProgrammedExercise,
    second: ProgrammedExercise,
) -> int:
    return max(
        1,
        ceil(
            min(first.sets - 1, second.sets - 1) * min(first.rest_seconds, second.rest_seconds) / 60
        ),
    )
