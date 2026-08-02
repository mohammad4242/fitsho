from collections.abc import Iterable

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.schemas import ProgrammedExercise

ENGLISH_MUSCLE_NAMES: dict[MuscleGroup, str] = {
    MuscleGroup.CHEST: "Chest",
    MuscleGroup.BACK: "Back",
    MuscleGroup.SHOULDERS: "Shoulders",
    MuscleGroup.BICEPS: "Biceps",
    MuscleGroup.TRICEPS: "Triceps",
    MuscleGroup.TRAPS: "Traps",
    MuscleGroup.FOREARMS: "Forearms",
    MuscleGroup.NECK: "Neck",
    MuscleGroup.GLUTES: "Glutes",
    MuscleGroup.QUADRICEPS: "Quadriceps",
    MuscleGroup.HAMSTRINGS: "Hamstrings",
    MuscleGroup.ADDUCTORS: "Adductors",
    MuscleGroup.CALVES: "Calves",
    MuscleGroup.ABS: "Abs",
    MuscleGroup.OBLIQUES: "Obliques",
    MuscleGroup.LOWER_BACK: "Lower Back",
}

PERSIAN_MUSCLE_NAMES: dict[MuscleGroup, str] = {
    MuscleGroup.CHEST: "سینه",
    MuscleGroup.BACK: "زیربغل",
    MuscleGroup.SHOULDERS: "سرشانه",
    MuscleGroup.BICEPS: "جلو بازو",
    MuscleGroup.TRICEPS: "پشت بازو",
    MuscleGroup.TRAPS: "کول",
    MuscleGroup.FOREARMS: "ساعد",
    MuscleGroup.NECK: "گردن",
    MuscleGroup.GLUTES: "باسن",
    MuscleGroup.QUADRICEPS: "چهارسر",
    MuscleGroup.HAMSTRINGS: "پشت پا",
    MuscleGroup.ADDUCTORS: "داخل ران",
    MuscleGroup.CALVES: "ساق",
    MuscleGroup.ABS: "شکم",
    MuscleGroup.OBLIQUES: "پهلو",
    MuscleGroup.LOWER_BACK: "فیله",
}


def direct_target_muscles(
    exercises: Iterable[ProgrammedExercise],
) -> tuple[MuscleGroup, ...]:
    """Return ordered primary muscles only; secondary recruitment is never a title target."""
    return target_muscles_from_values(
        item.primary_muscle
        for item in exercises
        if item.counts_toward_volume and item.primary_muscle is not None
    )


def target_muscles_from_values(values: Iterable[object]) -> tuple[MuscleGroup, ...]:
    targets: list[MuscleGroup] = []
    for value in values:
        if isinstance(value, MuscleGroup):
            targets.append(value)
        elif isinstance(value, str):
            try:
                targets.append(MuscleGroup(value))
            except ValueError:
                continue
    return tuple(dict.fromkeys(targets))


def english_session_title(day_index: int, exercises: Iterable[ProgrammedExercise]) -> str:
    return english_session_title_for_targets(day_index, direct_target_muscles(exercises))


def persian_session_title(day_index: int, exercises: Iterable[ProgrammedExercise]) -> str:
    return persian_session_title_for_targets(day_index, direct_target_muscles(exercises))


def english_session_title_for_targets(day_index: int, targets: Iterable[MuscleGroup]) -> str:
    label = " + ".join(ENGLISH_MUSCLE_NAMES[muscle] for muscle in targets) or "Full Body"
    return f"Day {day_index}: {label}"


def persian_session_title_for_targets(day_index: int, targets: Iterable[MuscleGroup]) -> str:
    label = " + ".join(PERSIAN_MUSCLE_NAMES[muscle] for muscle in targets) or "تمام بدن"
    return f"روز {day_index}: {label}"
