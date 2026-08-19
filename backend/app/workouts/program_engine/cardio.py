from app.exercises.enums import ExerciseLabel
from app.workouts.program_engine.enums import (
    CardioIntensity,
    Goal,
    ImpactLimit,
    TrainingStatus,
)
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
    return ruleset.cardio_start_minutes if _safe_cardio(request, exercises, ruleset) else 0


def add_cardio(
    request: NormalizedProgramRequest,
    days: tuple[WorkoutDay, ...],
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    options = _safe_cardio(request, exercises, ruleset)
    if not options or not days:
        return days
    modality = min(options, key=lambda item: (_cardio_rank(request, item, ruleset), str(item.id)))
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
                    (
                        "LOW_IMPACT_CARDIO_SELECTED"
                        if modality.impact_level is ImpactLimit.LOW
                        else "CARDIO_MODALITY_SELECTED"
                    ),
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


def _safe_cardio(
    request: NormalizedProgramRequest,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> tuple[ExerciseCandidate, ...]:
    impact_rank = {ImpactLimit.LOW: 0, ImpactLimit.MODERATE: 1, ImpactLimit.HIGH: 2}
    older_novice = (
        request.source.age >= ruleset.older_adult_modifier_age
        and request.training_status is TrainingStatus.NOVICE
    )
    maximum_impact = ImpactLimit.MODERATE if older_novice else request.constraints.impact_limit
    return tuple(
        item
        for item in exercises
        if ExerciseLabel.CARDIO in item.labels
        and item.equipment.issubset(request.constraints.available_equipment)
        and impact_rank[item.impact_level] <= impact_rank[maximum_impact]
        and item.name.lower()
        not in {
            "cardio exercise",
            "cardio machine exercise",
            "cardio machine workouts",
        }
    )


def _cardio_rank(
    request: NormalizedProgramRequest,
    exercise: ExerciseCandidate,
    ruleset: ProgramRuleset,
) -> tuple[int, int, int, int, int]:
    demand = {"low": 0, "moderate": 1, "high": 2}
    older_novice = (
        request.source.age >= ruleset.older_adult_modifier_age
        and request.training_status is TrainingStatus.NOVICE
    )
    impact_weight = 8 if older_novice else 4
    conventional = any(
        token in exercise.name.lower()
        for token in ("walk", "march", "cycle", "bike", "elliptical", "treadmill", "rowing")
    )
    return (
        demand[exercise.impact_level.value] * impact_weight,
        0 if conventional else 1,
        exercise.fatigue_cost,
        demand[exercise.skill_demand.value] + demand[exercise.stability_demand.value],
        exercise.setup_cost,
    )
