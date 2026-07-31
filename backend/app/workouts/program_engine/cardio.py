from app.exercises.enums import ExerciseLabel
from app.workouts.program_engine.enums import CardioIntensity, Goal
from app.workouts.program_engine.schemas import (
    CardioPrescription,
    ExerciseCandidate,
    NormalizedProgramRequest,
    WorkoutDay,
)

CARDIO_MINUTES = 10


def cardio_reserve_minutes(
    request: NormalizedProgramRequest,
    exercises: tuple[ExerciseCandidate, ...],
) -> int:
    return CARDIO_MINUTES if _safe_cardio(exercises) else 0


def add_cardio(
    request: NormalizedProgramRequest,
    days: tuple[WorkoutDay, ...],
    exercises: tuple[ExerciseCandidate, ...],
) -> tuple[WorkoutDay, ...]:
    options = _safe_cardio(exercises)
    if not options or not days:
        return days
    modality = min(options, key=lambda item: (item.fatigue_cost, item.setup_cost, str(item.id)))
    target_days = 2 if request.primary_goal in {Goal.FAT_LOSS, Goal.BODY_RECOMPOSITION} else 1
    updated: list[WorkoutDay] = []
    assigned = 0
    for day in days:
        eligible_day = day.focus not in {"lower", "legs"} or len(days) == 1
        cardio = None
        if eligible_day and assigned < target_days:
            cardio = CardioPrescription(
                modality_exercise_id=modality.id,
                modality_name=modality.name,
                duration_minutes=CARDIO_MINUTES,
                intensity=CardioIntensity.MODERATE,
                reason_codes=(
                    "LOW_IMPACT_CARDIO_SELECTED",
                    "CARDIO_SCHEDULED_AFTER_RESISTANCE",
                ),
            )
            assigned += 1
        updated.append(
            WorkoutDay(
                day_index=day.day_index,
                weekday=day.weekday,
                title=day.title,
                focus=day.focus,
                estimated_duration_minutes=day.estimated_duration_minutes
                + (cardio.duration_minutes if cardio else 0),
                exercises=day.exercises,
                cardio=cardio,
            )
        )
    return tuple(updated)


def _safe_cardio(exercises: tuple[ExerciseCandidate, ...]) -> tuple[ExerciseCandidate, ...]:
    return tuple(item for item in exercises if ExerciseLabel.CARDIO in item.labels)

