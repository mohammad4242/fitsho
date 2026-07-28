from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.ai.schemas import WorkoutPlanDayOutput, WorkoutPlanModelOutput
from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate
from app.workouts.time_budget import (
    ExerciseTiming,
    WorkoutGenerationPolicy,
    calculate_day_minutes,
    calculate_exercise_minutes,
    fits_session_duration,
)


@dataclass(frozen=True)
class ValidationProblem:
    code: str
    message: str
    day_number: int | None = None
    exercise_id: UUID | None = None

    def to_repair_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.day_number is not None:
            payload["day_number"] = self.day_number
        if self.exercise_id is not None:
            payload["exercise_id"] = str(self.exercise_id)
        return payload


class WorkoutPlanValidationError(Exception):
    def __init__(self, problems: list[ValidationProblem]) -> None:
        super().__init__("Workout plan failed semantic validation")
        self.problems = problems


class WorkoutPlanValidator:
    def __init__(
        self,
        *,
        candidates: CandidateSet,
        policy: WorkoutGenerationPolicy,
        required_day_count: int,
    ) -> None:
        self._candidates = candidates
        self._policy = policy
        self._required_day_count = required_day_count
        self._candidate_by_id = {candidate.id: candidate for candidate in candidates.exercises}

    def validate(self, plan: WorkoutPlanModelOutput) -> None:
        problems: list[ValidationProblem] = []
        self._validate_day_structure(plan, problems)
        for day in plan.days:
            self._validate_day(day, problems)
        self._validate_no_identical_days(plan, problems)
        self._validate_weekly_balance(plan, problems)
        if problems:
            raise WorkoutPlanValidationError(problems)

    def _validate_day_structure(
        self, plan: WorkoutPlanModelOutput, problems: list[ValidationProblem]
    ) -> None:
        if len(plan.days) != self._required_day_count:
            problems.append(
                ValidationProblem(
                    code="day_count",
                    message="Plan must include exactly the requested number of training days.",
                )
            )
        actual_numbers = [day.day_number for day in plan.days]
        expected_numbers = list(range(1, self._required_day_count + 1))
        if actual_numbers != expected_numbers:
            problems.append(
                ValidationProblem(
                    code="day_numbers",
                    message="Training day numbers must be unique and sequential starting at one.",
                )
            )

    def _validate_day(self, day: WorkoutPlanDayOutput, problems: list[ValidationProblem]) -> None:
        exercises = day.exercises
        if not exercises:
            problems.append(
                ValidationProblem(
                    code="empty_day",
                    message="Each training day must include at least one exercise.",
                    day_number=day.day_number,
                )
            )
            return
        if len(exercises) > self._policy.maximum_exercises_per_day:
            problems.append(
                ValidationProblem(
                    code="exercise_count_exceeded",
                    message="Training day exceeds the allowed exercise count.",
                    day_number=day.day_number,
                )
            )

        selected: list[WorkoutExerciseCandidate] = []
        seen_ids: set[UUID] = set()
        timings: list[ExerciseTiming] = []
        for exercise in exercises:
            candidate = self._candidate_by_id.get(exercise.exercise_id)
            if candidate is None:
                problems.append(
                    ValidationProblem(
                        code="exercise_not_allowed",
                        message="Selected exercise is not in the allowed candidate set.",
                        day_number=day.day_number,
                        exercise_id=exercise.exercise_id,
                    )
                )
                continue
            selected.append(candidate)
            if exercise.exercise_id in seen_ids:
                problems.append(
                    ValidationProblem(
                        code="duplicate_exercise",
                        message="An exercise may not appear more than once in the same day.",
                        day_number=day.day_number,
                        exercise_id=exercise.exercise_id,
                    )
                )
            seen_ids.add(exercise.exercise_id)
            self._validate_prescription(day.day_number, exercise, problems)
            timings.append(ExerciseTiming(sets=exercise.sets, rest_seconds=exercise.rest_seconds))
            expected_minutes = calculate_exercise_minutes(
                timings[-1],
                set_execution_seconds=self._policy.set_execution_seconds,
                transition_seconds=self._policy.transition_seconds_per_exercise,
            )
            if abs(exercise.estimated_minutes - expected_minutes) > 2:
                problems.append(
                    ValidationProblem(
                        code="exercise_duration_mismatch",
                        message="Exercise duration does not match the deterministic time budget.",
                        day_number=day.day_number,
                        exercise_id=exercise.exercise_id,
                    )
                )

        calculated_minutes = self._policy.warmup_minutes + calculate_day_minutes(
            timings,
            set_execution_seconds=self._policy.set_execution_seconds,
            transition_seconds=self._policy.transition_seconds_per_exercise,
        )
        if abs(day.estimated_duration_minutes - calculated_minutes) > 5:
            problems.append(
                ValidationProblem(
                    code="duration_mismatch",
                    message="Day duration does not match the deterministic time budget.",
                    day_number=day.day_number,
                )
            )
        if not fits_session_duration(timings, self._policy):
            problems.append(
                ValidationProblem(
                    code="duration_exceeded",
                    message="Day exceeds the requested session duration.",
                    day_number=day.day_number,
                )
            )
        if (
            selected
            and self._has_suitable_compound_candidate()
            and all(candidate.exercise_type is ExerciseType.ISOLATION for candidate in selected)
        ):
            problems.append(
                ValidationProblem(
                    code="isolation_only_day",
                    message=(
                        "A day cannot contain only isolation exercises "
                        "when suitable compounds exist."
                    ),
                    day_number=day.day_number,
                )
            )

    def _validate_prescription(
        self,
        day_number: int,
        exercise: object,
        problems: list[ValidationProblem],
    ) -> None:
        from app.ai.schemas import WorkoutPlanExerciseOutput

        if not isinstance(exercise, WorkoutPlanExerciseOutput):
            return
        if not self._policy.minimum_sets <= exercise.sets <= self._policy.maximum_sets:
            problems.append(
                ValidationProblem(
                    code="sets_out_of_policy",
                    message="Sets are outside the allowed range.",
                    day_number=day_number,
                    exercise_id=exercise.exercise_id,
                )
            )
        if not (
            self._policy.minimum_repetitions
            <= exercise.reps_min
            <= exercise.reps_max
            <= self._policy.maximum_repetitions
        ):
            problems.append(
                ValidationProblem(
                    code="repetitions_out_of_policy",
                    message="Repetitions are outside the allowed range.",
                    day_number=day_number,
                    exercise_id=exercise.exercise_id,
                )
            )
        if exercise.rest_seconds not in self._policy.allowed_rest_seconds:
            problems.append(
                ValidationProblem(
                    code="rest_out_of_policy",
                    message="Rest duration is not allowed by the generation policy.",
                    day_number=day_number,
                    exercise_id=exercise.exercise_id,
                )
            )
        if exercise.rir not in self._policy.allowed_rir:
            problems.append(
                ValidationProblem(
                    code="rir_out_of_policy",
                    message="RIR is not allowed by the generation policy.",
                    day_number=day_number,
                    exercise_id=exercise.exercise_id,
                )
            )

    def _validate_no_identical_days(
        self, plan: WorkoutPlanModelOutput, problems: list[ValidationProblem]
    ) -> None:
        day_signatures: set[tuple[UUID, ...]] = set()
        for day in plan.days:
            signature = tuple(exercise.exercise_id for exercise in day.exercises)
            if signature in day_signatures:
                problems.append(
                    ValidationProblem(
                        code="identical_day",
                        message="Training days must not repeat the identical exercise sequence.",
                        day_number=day.day_number,
                    )
                )
            day_signatures.add(signature)

    def _validate_weekly_balance(
        self, plan: WorkoutPlanModelOutput, problems: list[ValidationProblem]
    ) -> None:
        selected = [
            self._candidate_by_id[exercise.exercise_id]
            for day in plan.days
            for exercise in day.exercises
            if exercise.exercise_id in self._candidate_by_id
        ]
        if not selected:
            return
        self._require_variety(
            {candidate.movement_pattern for candidate in selected},
            {candidate.movement_pattern for candidate in self._candidates.exercises},
            min(3, len(selected)),
            "movement_pattern_balance",
            "Plan needs broader movement-pattern coverage.",
            problems,
        )
        self._require_variety(
            {candidate.primary_muscle for candidate in selected},
            {candidate.primary_muscle for candidate in self._candidates.exercises},
            min(2, len(selected)),
            "muscle_group_balance",
            "Plan needs broader muscle-group coverage.",
            problems,
        )

    @staticmethod
    def _require_variety(
        selected: set[MovementPattern] | set[MuscleGroup],
        available: set[MovementPattern] | set[MuscleGroup],
        selected_count: int,
        code: str,
        message: str,
        problems: list[ValidationProblem],
    ) -> None:
        required = min(selected_count, len(available))
        if len(selected) < required:
            problems.append(ValidationProblem(code=code, message=message))

    def _has_suitable_compound_candidate(self) -> bool:
        return any(
            candidate.exercise_type is ExerciseType.COMPOUND
            for candidate in self._candidates.exercises
        )
