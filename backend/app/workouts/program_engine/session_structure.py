from dataclasses import dataclass, replace

from app.exercises.enums import Difficulty, ExerciseType, MuscleFocus, MuscleGroup
from app.workouts.program_engine.duration_policy import (
    calculate_cardio_addon_minutes,
    calculate_total_session_minutes_from_exercises,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.exercise_semantics import (
    is_leg_extension_primer,
    is_pull_up_family,
    is_push_up_family,
    is_squat_family,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    ProgrammedExercise,
    WorkoutDay,
)
from app.workouts.program_engine.session_coherence import (
    SessionCoherence,
    hierarchy_for_focus,
)
from app.workouts.program_engine.session_targets import english_session_title_for_targets
from app.workouts.program_engine.supplemental_policy import (
    SUPPLEMENTAL_MUSCLES,
    is_core_or_supplemental_exercise,
    is_main_resistance_exercise,
    main_exercise_count,
    supplemental_reason_codes,
)

_PUSH_UP_OPENER = "push_up"
_PULL_UP_OPENER = "pull_up"


@dataclass(frozen=True)
class _ExerciseUnit:
    exercises: tuple[ProgrammedExercise, ...]

    @property
    def muscles(self) -> tuple[MuscleGroup, ...]:
        return tuple(
            item.primary_muscle for item in self.exercises if item.primary_muscle is not None
        )

    @property
    def identifier(self) -> tuple[str, ...]:
        return tuple(sorted(str(item.exercise_id) for item in self.exercises))

    @property
    def original_order(self) -> int:
        return min(item.order for item in self.exercises)

    @property
    def is_core_or_supplemental(self) -> bool:
        return all(is_core_or_supplemental_exercise(item) for item in self.exercises)


def finalize_session_structure(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    policy = PriorityAllocationPolicy.for_request(request, ruleset)
    finalized: list[WorkoutDay] = []
    for day in days:
        block = _strict_block(day)
        original_units = _exercise_units(day.exercises)
        units = sorted(
            original_units,
            key=lambda unit: _unit_sort_key(
                unit,
                original_units,
                block,
                request,
                request.primary_goal,
                policy,
            ),
        )
        flat_exercises = tuple(item for unit in units for item in unit.exercises)

        compound_seen = False
        recalculated: list[ProgrammedExercise] = []
        for index, item in enumerate(flat_exercises, start=1):
            warmup_sets = 0
            if not compound_seen and item.exercise_type is ExerciseType.COMPOUND:
                compound_seen = True
                warmup_sets = (
                    ruleset.strength_compound_warmup_sets
                    if request.primary_goal is Goal.STRENGTH
                    else ruleset.first_compound_warmup_sets
                )
            if item.warmup_sets != warmup_sets:
                est_mins = estimate_exercise_minutes(
                    item.sets, item.rest_seconds, warmup_sets, ruleset
                )
                recalculated.append(
                    replace(item, order=index, warmup_sets=warmup_sets, estimated_minutes=est_mins)
                )
            else:
                recalculated.append(replace(item, order=index))

        exercises = tuple(recalculated)
        estimated_duration = calculate_total_session_minutes_from_exercises(
            exercises,
            ruleset.general_warmup_minutes,
            calculate_cardio_addon_minutes(day) or 0,
        )

        finalized.append(
            replace(
                day,
                exercises=exercises,
                title=main_session_title(day.day_index, exercises),
                estimated_duration_minutes=estimated_duration,
            )
        )
    return tuple(finalized)


def main_session_title(
    day_index: int,
    exercises: tuple[ProgrammedExercise, ...],
) -> str:
    targets = tuple(
        dict.fromkeys(
            item.primary_muscle
            for item in exercises
            if item.primary_muscle is not None
            and not is_core_or_supplemental_exercise(item)
        )
    )
    return english_session_title_for_targets(day_index, targets)


def session_structure_errors(
    day: WorkoutDay,
    goal: Goal,
    request: ProgramGenerationRequest | NormalizedProgramRequest | None = None,
) -> tuple[str, ...]:
    errors: list[str] = []
    if tuple(item.order for item in day.exercises) != tuple(range(1, len(day.exercises) + 1)):
        errors.append("SESSION_EXERCISE_ORDER_INVALID")

    supplemental_seen = False
    supplemental_count = 0
    for item in day.exercises:
        if is_core_or_supplemental_exercise(item):
            supplemental_seen = True
            supplemental_count += 1
        elif supplemental_seen:
            errors.append("SUPPLEMENTAL_WORK_NOT_AT_SESSION_END")
    if supplemental_count > 2:
        errors.append("SUPPLEMENTAL_EXERCISE_LIMIT_EXCEEDED")

    block = _strict_block(day)
    units = _exercise_units(day.exercises)
    errors.extend(_semantic_ordering_errors(units, request))
    previous_block = -1
    phases_by_block: dict[int, int] = {}
    previous_phase = -1
    for unit in units:
        if unit.is_core_or_supplemental:
            continue
        phase = _role_phase(unit, goal)
        if any(is_push_up_family(item) or is_pull_up_family(item) for item in unit.exercises):
            phase = 0
        elif _has_safe_leg_extension_primer(units, request) and any(
            is_leg_extension_primer(item) for item in unit.exercises
        ):
            phase = 0
        if block is None:
            if phase < previous_phase:
                errors.append("EXERCISE_TYPE_SEQUENCE_INVALID")
            previous_phase = max(previous_phase, phase)
            continue
        block_rank = _unit_block_rank(unit, block)
        if block_rank < previous_block:
            errors.append("STRICT_MUSCLE_BLOCK_ORDER_INVALID")
        previous_block = max(previous_block, block_rank)
        prior_phase = phases_by_block.get(block_rank, -1)
        if phase < prior_phase:
            errors.append("EXERCISE_TYPE_SEQUENCE_INVALID")
        phases_by_block[block_rank] = max(prior_phase, phase)

    if goal is Goal.STRENGTH:
        main_units = tuple(
            unit
            for unit in units
            if not unit.is_core_or_supplemental
        )
        if block is None:
            opener_units = main_units
        else:
            first_block_rank = min(
                (_unit_block_rank(unit, block) for unit in main_units),
                default=len(block),
            )
            opener_units = tuple(
                unit for unit in main_units if _unit_block_rank(unit, block) == first_block_rank
            )
        non_opener_units = tuple(
            unit for unit in opener_units if not _is_required_semantic_opener(unit, units, request)
        )
        if any(
            _contains_reason(unit, "STRENGTH_PRIMARY_COMPOUND") for unit in non_opener_units
        ) and (
            not non_opener_units
            or not _contains_reason(non_opener_units[0], "STRENGTH_PRIMARY_COMPOUND")
        ):
            errors.append("STRENGTH_PRIMARY_NOT_FIRST")
    return tuple(dict.fromkeys(errors))


def _exercise_units(
    exercises: tuple[ProgrammedExercise, ...],
) -> tuple[_ExerciseUnit, ...]:
    emitted: set[str] = set()
    units: list[_ExerciseUnit] = []
    for item in exercises:
        group = item.superset_group
        if group is None:
            units.append(_ExerciseUnit((item,)))
            continue
        if group in emitted:
            continue
        emitted.add(group)
        members = tuple(
            sorted(
                (member for member in exercises if member.superset_group == group),
                key=lambda member: (member.order, str(member.exercise_id)),
            )
        )
        units.append(_ExerciseUnit(members))
    return tuple(units)


def _unit_sort_key(
    unit: _ExerciseUnit,
    all_units: tuple[_ExerciseUnit, ...],
    block: tuple[frozenset[MuscleGroup], ...] | None,
    request: NormalizedProgramRequest,
    goal: Goal,
    policy: PriorityAllocationPolicy,
) -> tuple[object, ...]:
    supplemental = unit.is_core_or_supplemental
    main_muscles = tuple(
        item.primary_muscle
        for item in unit.exercises
        if item.primary_muscle is not None
        and not is_core_or_supplemental_exercise(item)
    )
    priority = min(
        (policy.precedence_key(muscle) for muscle in main_muscles),
        default=(4, 0, ""),
    )
    if priority[0] >= 3:
        priority = (3, 0, "")
    return (
        1 if supplemental else 0,
        _semantic_order_rank(unit, all_units, request),
        _unit_block_rank(unit, block) if block is not None else 0,
        _role_phase(unit, goal),
        priority,
        unit.original_order,
        unit.identifier,
    )


def _semantic_order_rank(
    unit: _ExerciseUnit,
    all_units: tuple[_ExerciseUnit, ...],
    request: NormalizedProgramRequest,
) -> int:
    opener_family = _semantic_opener_family(all_units, request)
    if opener_family in _semantic_opener_families(unit):
        return 0
    has_safe_primer = any(
        is_leg_extension_primer(item) and _ordering_eligible(item, request)
        for candidate_unit in all_units
        for item in candidate_unit.exercises
    )
    has_squat = any(
        is_squat_family(item) for candidate_unit in all_units for item in candidate_unit.exercises
    )
    if (
        has_safe_primer
        and has_squat
        and any(is_leg_extension_primer(item) for item in unit.exercises)
    ):
        return 1
    return 2


def _has_safe_leg_extension_primer(
    units: tuple[_ExerciseUnit, ...],
    request: NormalizedProgramRequest | ProgramGenerationRequest | None,
) -> bool:
    has_squat = any(is_squat_family(item) for unit in units for item in unit.exercises)
    return has_squat and any(
        is_leg_extension_primer(item) and _ordering_eligible(item, request)
        for unit in units
        for item in unit.exercises
    )


def _is_required_semantic_opener(
    unit: _ExerciseUnit,
    all_units: tuple[_ExerciseUnit, ...],
    request: ProgramGenerationRequest | NormalizedProgramRequest | None,
) -> bool:
    return (
        _semantic_opener_family(all_units, request) in _semantic_opener_families(unit)
        or (
            _has_safe_leg_extension_primer(all_units, request)
            and any(is_leg_extension_primer(item) for item in unit.exercises)
        )
    )


def _semantic_opener_families(unit: _ExerciseUnit) -> frozenset[str]:
    families: set[str] = set()
    if any(is_push_up_family(item) for item in unit.exercises):
        families.add(_PUSH_UP_OPENER)
    if any(is_pull_up_family(item) for item in unit.exercises):
        families.add(_PULL_UP_OPENER)
    return frozenset(families)


def _semantic_opener_family(
    units: tuple[_ExerciseUnit, ...],
    request: ProgramGenerationRequest | NormalizedProgramRequest | None,
) -> str | None:
    family_units = {
        family: tuple(unit for unit in units if family in _semantic_opener_families(unit))
        for family in (_PUSH_UP_OPENER, _PULL_UP_OPENER)
    }
    available = tuple(family for family, candidates in family_units.items() if candidates)
    if len(available) <= 1:
        return available[0] if available else None

    strength_primary = tuple(
        family
        for family in available
        if any(_contains_reason(unit, "STRENGTH_PRIMARY_COMPOUND") for unit in family_units[family])
    )
    if len(strength_primary) == 1:
        return strength_primary[0]

    priority_families = _priority_opener_families(request)
    prioritized = tuple(family for family in available if family in priority_families)
    if len(prioritized) == 1:
        return prioritized[0]

    def construction_key(family: str) -> tuple[object, ...]:
        return min((unit.original_order, unit.identifier) for unit in family_units[family])

    return min(available, key=construction_key)


def _priority_opener_families(
    request: ProgramGenerationRequest | NormalizedProgramRequest | None,
) -> frozenset[str]:
    source = getattr(request, "source", request)
    priorities = getattr(source, "priority_muscles", ()) if source is not None else ()
    families: set[str] = set()
    if MuscleGroup.CHEST in priorities:
        families.add(_PUSH_UP_OPENER)
    if MuscleGroup.BACK in priorities:
        families.add(_PULL_UP_OPENER)
    return frozenset(families)


def _session_has_meaningful_muscle(units: tuple[_ExerciseUnit, ...], muscle: MuscleGroup) -> bool:
    return any(
        is_main_resistance_exercise(item)
        and (
            item.primary_muscle is muscle
            or muscle in item.secondary_muscles
            or (
                muscle is MuscleGroup.CHEST
                and item.muscle_focus
                in {
                    MuscleFocus.GENERAL_CHEST,
                    MuscleFocus.UPPER_CHEST,
                    MuscleFocus.MID_CHEST,
                    MuscleFocus.LOWER_CHEST,
                }
            )
        )
        for unit in units
        for item in unit.exercises
    )


def _session_has_meaningful_back(units: tuple[_ExerciseUnit, ...]) -> bool:
    return any(
        is_main_resistance_exercise(item)
        and (
            item.primary_muscle is MuscleGroup.BACK
            or MuscleGroup.BACK in item.secondary_muscles
            or item.muscle_focus
            in {
                MuscleFocus.GENERAL_BACK,
                MuscleFocus.LATS,
                MuscleFocus.LOWER_BACK,
                MuscleFocus.MID_BACK_RHOMBOIDS,
                MuscleFocus.UPPER_BACK,
            }
        )
        for unit in units
        for item in unit.exercises
    )


def _ordering_eligible(
    item: ProgrammedExercise,
    request: NormalizedProgramRequest | ProgramGenerationRequest | None,
) -> bool:
    if request is None:
        return True
    normalized = (
        request if isinstance(request, NormalizedProgramRequest) else normalize_request(request)
    )
    candidate = ExerciseCandidate(
        id=item.exercise_id,
        name=item.exercise_name,
        primary_muscle=item.primary_muscle,
        secondary_muscles=item.secondary_muscles,
        movement_pattern=item.movement_pattern,
        exercise_type=item.exercise_type,
        equipment=item.equipment,
        difficulty=Difficulty.BEGINNER,
        muscle_focus=item.muscle_focus,
        caution_tags=item.caution_tags,
        is_active=item.is_active,
        is_programmable=item.is_programmable,
        needs_review=item.needs_review,
        laterality=item.laterality,
        body_position=item.body_position,
        stability_demand=item.stability_demand,
        impact_level=item.impact_level,
        axial_loading_level=item.axial_loading_level,
        range_of_motion_profile=item.range_of_motion_profile,
        substitution_group=item.substitution_group,
        prescription_mode=item.prescription_mode,
        duration_min_seconds=item.duration_min_seconds,
        duration_max_seconds=item.duration_max_seconds,
    )
    return candidate in filter_eligible_exercises(normalized, (candidate,)).eligible


def _semantic_ordering_errors(
    units: tuple[_ExerciseUnit, ...],
    request: ProgramGenerationRequest | NormalizedProgramRequest | None,
) -> list[str]:
    main_units = tuple(
        unit for unit in units if not unit.is_core_or_supplemental
    )
    if not main_units:
        return []
    errors: list[str] = []
    push_up_required = _session_has_meaningful_muscle(units, MuscleGroup.CHEST) and any(
        is_push_up_family(item) for unit in main_units for item in unit.exercises
    )
    pull_up_required = _session_has_meaningful_back(units) and any(
        is_pull_up_family(item) for unit in main_units for item in unit.exercises
    )
    if push_up_required and pull_up_required:
        opener_family = _semantic_opener_family(units, request)
        opener_index = next(
            (
                index
                for index, unit in enumerate(main_units)
                if opener_family in _semantic_opener_families(unit)
            ),
            None,
        )
        if opener_index not in {None, 0}:
            opener_error = (
                "PUSH_UP_OPENER_ORDER_INVALID"
                if opener_family == _PUSH_UP_OPENER
                else "PULL_UP_OPENER_ORDER_INVALID"
            )
            errors.append(opener_error)
    elif push_up_required:
        push_index = next(
            (
                index
                for index, unit in enumerate(main_units)
                if any(is_push_up_family(item) for item in unit.exercises)
            ),
            None,
        )
        if push_index is not None and push_index != 0:
            errors.append("PUSH_UP_OPENER_ORDER_INVALID")
    elif pull_up_required:
        pull_index = next(
            (
                index
                for index, unit in enumerate(main_units)
                if any(is_pull_up_family(item) for item in unit.exercises)
            ),
            None,
        )
        if pull_index is not None and pull_index != 0:
            errors.append("PULL_UP_OPENER_ORDER_INVALID")
    primer_indices = [
        index
        for index, unit in enumerate(main_units)
        if any(
            is_leg_extension_primer(item) and _ordering_eligible(item, request)
            for item in unit.exercises
        )
    ]
    squat_indices = [
        index
        for index, unit in enumerate(main_units)
        if any(is_squat_family(item) for item in unit.exercises)
    ]
    if primer_indices and squat_indices and max(primer_indices) >= min(squat_indices):
        errors.append("LEG_EXTENSION_PRIMER_ORDER_INVALID")
    return errors


def _role_phase(unit: _ExerciseUnit, goal: Goal) -> int:
    if goal is Goal.STRENGTH:
        if _contains_reason(unit, "STRENGTH_PRIMARY_COMPOUND"):
            return 0
        if _contains_reason(unit, "PRIMARY_WORKING_COMPOUND"):
            return 1
        if _contains_reason(unit, "STRENGTH_SECONDARY_COMPOUND") or any(
            item.exercise_type is ExerciseType.COMPOUND for item in unit.exercises
        ):
            return 2
        return 3
    if _contains_reason(unit, "PRIMARY_WORKING_COMPOUND"):
        return 0
    if any(item.exercise_type is ExerciseType.COMPOUND for item in unit.exercises):
        return 1
    return 2


def _contains_reason(unit: _ExerciseUnit, reason: str) -> bool:
    return any(reason in item.reason_codes for item in unit.exercises)


def _unit_block_rank(
    unit: _ExerciseUnit,
    block: tuple[frozenset[MuscleGroup], ...] | None,
) -> int:
    if block is None:
        return 0
    ranks = tuple(
        index
        for item in unit.exercises
        if not is_core_or_supplemental_exercise(item)
        for muscle in (item.primary_muscle,)
        if muscle is not None
        for index, muscles in enumerate(block)
        if muscle in muscles
    )
    return min(ranks, default=len(block))


def _strict_block(day: WorkoutDay) -> tuple[frozenset[MuscleGroup], ...] | None:
    focus = (
        day.template_structure_focus
        if day.focus.startswith("template_reference")
        else day.focus
    )
    if not hierarchy_for_focus(focus):
        return None
    coherence = SessionCoherence.from_workout_day(day)
    if not coherence.allowed_direct_muscles:
        return None
    return coherence.ordered_blocks()


__all__ = [
    "SUPPLEMENTAL_MUSCLES",
    "finalize_session_structure",
    "main_exercise_count",
    "main_session_title",
    "session_structure_errors",
    "supplemental_reason_codes",
]
