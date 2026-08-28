from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.schemas import WorkoutPlanDayOutput, WorkoutPlanExerciseOutput, WorkoutPlanModelOutput
from app.exercises.enums import PrescriptionMode
from app.exercises.models import Exercise
from app.workout_reviews.enums import WorkoutReviewErrorCode
from app.workout_reviews.repository import get_exercises
from app.workout_reviews.schemas import WorkoutReviewDraftUpdate
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate
from app.workouts.time_budget import (
    ExerciseTiming,
    WorkoutGenerationPolicy,
    calculate_day_minutes,
    calculate_exercise_minutes,
)
from app.workouts.validator import WorkoutPlanValidationError, WorkoutPlanValidator


class DraftValidationError(Exception):
    def __init__(self, problems: list[dict[str, object]]) -> None:
        super().__init__("Workout review draft is invalid")
        self.code = WorkoutReviewErrorCode.INVALID_DRAFT
        self.problems = problems


@dataclass(frozen=True)
class ValidatedDraft:
    payload: WorkoutReviewDraftUpdate
    plan: WorkoutPlanModelOutput
    exercises: dict[UUID, Exercise]


class WorkoutReviewDraftValidator:
    def __init__(self, db: Session) -> None:
        self._db = db

    def validate(
        self,
        source: WorkoutPlan,
        payload: WorkoutReviewDraftUpdate,
    ) -> ValidatedDraft:
        source_slots = {
            (day.day_number, item.order_index): (day, item)
            for day in source.days
            for item in day.exercises
        }
        draft_slots = {
            (day.day_number, item.order_index): item
            for day in payload.days
            for item in day.exercises
        }
        problems: list[dict[str, object]] = []
        if set(source_slots) != set(draft_slots):
            problems.append(
                {
                    "code": "PLAN_STRUCTURE_CHANGED",
                    "message": "Workout days and exercise slots cannot be added or removed.",
                }
            )

        catalog = source.exercise_catalog_snapshot.get("exercises")
        allowed_ids = (
            {UUID(value) for value in catalog if _is_uuid(value)}
            if isinstance(catalog, dict)
            else set()
        )
        selected_ids = {item.exercise_id for item in draft_slots.values()}
        disallowed = selected_ids - allowed_ids
        for exercise_id in sorted(disallowed, key=str):
            problems.append(
                {
                    "code": WorkoutReviewErrorCode.EXERCISE_NOT_ALLOWED.value,
                    "message": "Exercise is outside the source plan candidate catalogue.",
                    "exercise_id": str(exercise_id),
                }
            )

        live = {exercise.id: exercise for exercise in get_exercises(self._db, allowed_ids)}
        for exercise_id in sorted(selected_ids, key=str):
            exercise = live.get(exercise_id)
            if (
                exercise is None
                or not exercise.is_active
                or not exercise.is_programmable
                or exercise.needs_review
            ):
                problems.append(
                    {
                        "code": WorkoutReviewErrorCode.EXERCISE_NOT_ALLOWED.value,
                        "message": "Exercise is not active and programmable.",
                        "exercise_id": str(exercise_id),
                    }
                )
        for item in draft_slots.values():
            exercise = live.get(item.exercise_id)
            if exercise is not None and item.prescription_mode is not exercise.prescription_mode:
                problems.append(
                    {
                        "code": "PRESCRIPTION_MODE_MISMATCH",
                        "message": "Prescription mode must match the selected exercise metadata.",
                        "exercise_id": str(item.exercise_id),
                    }
                )
        if problems:
            raise DraftValidationError(problems)

        model = self._to_model(source, payload, source_slots)
        candidates = tuple(self._candidate(exercise) for exercise in live.values())
        raw_session_duration = source.profile_snapshot.get("session_duration_minutes", 45)
        session_duration = raw_session_duration if isinstance(raw_session_duration, int) else 45
        policy = WorkoutGenerationPolicy.for_session_duration(session_duration)
        duration_policy = get_session_duration_policy(session_duration)
        source_sets = [item.sets for day in source.days for item in day.exercises]
        source_max_exercises = max((len(day.exercises) for day in source.days), default=1)
        policy = replace(
            policy,
            session_duration_minutes=duration_policy.maximum_minutes + policy.warmup_minutes,
            maximum_exercises_per_day=max(
                policy.maximum_exercises_per_day,
                source_max_exercises,
            ),
            maximum_sets=max(policy.maximum_sets, max(source_sets, default=0)),
        )
        source_max_duration = max(
            (
                5
                + calculate_day_minutes(
                    ExerciseTiming(item.sets, item.rest_seconds) for item in day.exercises
                )
                for day in source.days
            ),
            default=policy.session_duration_minutes,
        )
        policy = replace(
            policy,
            session_duration_minutes=max(policy.session_duration_minutes, source_max_duration),
        )
        try:
            WorkoutPlanValidator(
                candidates=CandidateSet(
                    exercises=candidates,
                    candidate_set_hash=source.candidate_set_hash,
                    soft_cautions=(),
                    minimum_candidate_count=1,
                ),
                policy=policy,
                required_day_count=len(source.days),
            ).validate(model)
        except WorkoutPlanValidationError as error:
            raise DraftValidationError(
                [problem.to_repair_payload() for problem in error.problems]
            ) from error
        return ValidatedDraft(payload=payload, plan=model, exercises=live)

    @staticmethod
    def _to_model(
        source: WorkoutPlan,
        payload: WorkoutReviewDraftUpdate,
        source_slots: dict[tuple[int, int], tuple[WorkoutDay, WorkoutPlanExercise]],
    ) -> WorkoutPlanModelOutput:
        source_days = {day.day_number: day for day in source.days}
        output_days: list[WorkoutPlanDayOutput] = []
        for draft_day in sorted(payload.days, key=lambda item: item.day_number):
            source_day = source_days[draft_day.day_number]
            output_exercises: list[WorkoutPlanExerciseOutput] = []
            for item in sorted(draft_day.exercises, key=lambda value: value.order_index):
                source_item = source_slots[(draft_day.day_number, item.order_index)][1]
                timing = ExerciseTiming(item.sets, item.rest_seconds)
                output_exercises.append(
                    WorkoutPlanExerciseOutput(
                        exercise_id=item.exercise_id,
                        sets=item.sets,
                        prescription_mode=item.prescription_mode,
                        reps_min=item.reps_min,
                        reps_max=item.reps_max,
                        duration_min_seconds=item.duration_min_seconds,
                        duration_max_seconds=item.duration_max_seconds,
                        rest_seconds=item.rest_seconds,
                        rir=(
                            None
                            if item.prescription_mode is PrescriptionMode.DURATION
                            else item.rir
                            if item.rir is not None
                            else source_item.rir
                        ),
                        estimated_minutes=calculate_exercise_minutes(timing),
                        notes_en=item.notes_en,
                        notes_fa=item.notes_fa,
                    )
                )
            timings = [ExerciseTiming(item.sets, item.rest_seconds) for item in draft_day.exercises]
            output_days.append(
                WorkoutPlanDayOutput(
                    day_number=draft_day.day_number,
                    title_en=source_day.title_en,
                    title_fa=source_day.title_fa,
                    estimated_duration_minutes=5 + calculate_day_minutes(timings),
                    exercises=output_exercises,
                )
            )
        return WorkoutPlanModelOutput(days=output_days)

    @staticmethod
    def _candidate(exercise: Exercise) -> WorkoutExerciseCandidate:
        return WorkoutExerciseCandidate(
            id=exercise.id,
            primary_muscle=exercise.primary_muscle,
            secondary_muscles=tuple(item.muscle for item in exercise.secondary_muscles),
            movement_pattern=exercise.movement_pattern,
            exercise_type=exercise.exercise_type,
            equipment=tuple(item.equipment for item in exercise.equipment_items),
            difficulty=exercise.difficulty,
            caution_tags=tuple(item.caution_tag for item in exercise.caution_tag_items),
            labels=tuple(item.label for item in exercise.labels),
            prescription_mode=exercise.prescription_mode,
            duration_min_seconds=exercise.duration_min_seconds,
            duration_max_seconds=exercise.duration_max_seconds,
        )


def _is_uuid(value: object) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True
