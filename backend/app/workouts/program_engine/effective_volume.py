from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import ProgrammedExercise
from app.workouts.program_engine.volume_planner import TRACKED_MUSCLES


@dataclass(frozen=True)
class EffectiveVolume:
    direct_sets_by_muscle: dict[str, int]
    secondary_sets_by_muscle: dict[str, float]
    effective_sets_by_muscle: dict[str, float]


def calculate_effective_volume(
    exercises: Iterable[ProgrammedExercise],
    ruleset: ProgramRuleset,
) -> EffectiveVolume:
    direct: Counter[str] = Counter()
    secondary: defaultdict[str, float] = defaultdict(float)
    effective: defaultdict[str, float] = defaultdict(float)

    for exercise in exercises:
        if not exercise.counts_toward_volume:
            continue
        credited_muscles: set[str] = set()
        if exercise.primary_muscle is not None:
            primary = exercise.primary_muscle.value
            direct[primary] += exercise.sets
            effective[primary] += exercise.sets * ruleset.primary_set_credit
            credited_muscles.add(primary)
        for muscle in exercise.secondary_muscles:
            secondary_muscle = muscle.value
            if secondary_muscle in credited_muscles:
                continue
            credited_muscles.add(secondary_muscle)
            credit = exercise.sets * ruleset.secondary_set_credit
            secondary[secondary_muscle] += credit
            effective[secondary_muscle] += credit

    return EffectiveVolume(
        direct_sets_by_muscle=dict(direct),
        secondary_sets_by_muscle=dict(secondary),
        effective_sets_by_muscle=dict(effective),
    )


def complete_tracked_metrics(values: dict[str, int | float]) -> dict[str, int | float]:
    complete = dict(values)
    for muscle in TRACKED_MUSCLES:
        complete.setdefault(muscle.value, 0)
    return complete
