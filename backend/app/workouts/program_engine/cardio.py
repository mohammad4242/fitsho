from app.exercises.enums import ExerciseLabel
from app.workouts.program_engine.enums import CardioIntensity, Goal
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    CardioPrescription,
    ExerciseCandidate,
    NormalizedProgramRequest,
    WorkoutDay,
)


def cardio_reserve_minutes(
    request: NormalizedProgramRequest,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> int:
    return ruleset.cardio_start_minutes if _safe_cardio(exercises) else 0


def add_cardio(
    request: NormalizedProgramRequest,
    days: tuple[WorkoutDay, ...],
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    options = _safe_cardio(exercises)
    if not options or not days:
        return days
    modality = min(options, key=lambda item: (item.fatigue_cost, item.setup_cost, str(item.id)))
    target_days = (
        ruleset.fat_loss_cardio_days
        if request.primary_goal in {Goal.FAT_LOSS, Goal.BODY_RECOMPOSITION}
        else ruleset.maintenance_cardio_days
    )
    updated: list[WorkoutDay] = []
    assigned = 0
    for day in days:
        available_cardio_minutes = min(
            ruleset.cardio_start_minutes,
            request.source.session_duration_minutes
            + ruleset.duration_tolerance_minutes
            - day.estimated_duration_minutes,
        )
        eligible_day = (
            day.focus not in {"lower", "legs"} or len(days) == 1
        ) and available_cardio_minutes >= ruleset.minimum_cardio_minutes
        cardio = None
        if eligible_day and assigned < target_days:
            cardio = CardioPrescription(
                modality_exercise_id=modality.id,
                modality_name=modality.name,
                duration_minutes=available_cardio_minutes,
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
