from uuid import UUID, uuid4

import pytest

from app.ai.schemas import (
    WorkoutPlanDayOutput,
    WorkoutPlanExerciseOutput,
    WorkoutPlanModelOutput,
)
from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate
from app.workouts.time_budget import WorkoutGenerationPolicy
from app.workouts.validator import WorkoutPlanValidationError, WorkoutPlanValidator

FIRST_ID = uuid4()
SECOND_ID = uuid4()
THIRD_ID = uuid4()


def _candidate(
    exercise_id: UUID,
    *,
    pattern: MovementPattern,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    muscle: MuscleGroup = MuscleGroup.CHEST,
    labels: tuple[ExerciseLabel, ...] = (),
) -> WorkoutExerciseCandidate:
    return WorkoutExerciseCandidate(
        id=exercise_id,
        primary_muscle=muscle,
        secondary_muscles=(),
        movement_pattern=pattern,
        exercise_type=exercise_type,
        equipment=(Equipment.BODYWEIGHT,),
        difficulty=Difficulty.BEGINNER,
        caution_tags=(),
        labels=labels,
    )


def _candidates() -> CandidateSet:
    return CandidateSet(
        exercises=(
            _candidate(FIRST_ID, pattern=MovementPattern.HORIZONTAL_PUSH),
            _candidate(SECOND_ID, pattern=MovementPattern.HORIZONTAL_PULL, muscle=MuscleGroup.BACK),
            _candidate(THIRD_ID, pattern=MovementPattern.SQUAT, muscle=MuscleGroup.QUADRICEPS),
        ),
        candidate_set_hash="a" * 64,
        soft_cautions=(),
        minimum_candidate_count=1,
    )


def _exercise(
    exercise_id: UUID,
    *,
    sets: int = 3,
    rest_seconds: int = 90,
    estimated_minutes: int = 7,
    notes_en: str | None = None,
) -> WorkoutPlanExerciseOutput:
    return WorkoutPlanExerciseOutput(
        exercise_id=exercise_id,
        sets=sets,
        reps_min=8,
        reps_max=12,
        rest_seconds=rest_seconds,
        rir=2,
        estimated_minutes=estimated_minutes,
        notes_en=notes_en,
        notes_fa=None,
    )


def _plan(days: list[WorkoutPlanDayOutput] | None = None) -> WorkoutPlanModelOutput:
    return WorkoutPlanModelOutput(
        days=days
        or [
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Full body",
                title_fa="تمام بدن",
                estimated_duration_minutes=26,
                exercises=[_exercise(FIRST_ID), _exercise(SECOND_ID), _exercise(THIRD_ID)],
            )
        ]
    )


def _validator() -> WorkoutPlanValidator:
    return WorkoutPlanValidator(
        candidates=_candidates(),
        policy=WorkoutGenerationPolicy.for_session_duration(45),
        required_day_count=1,
    )


def test_validator_accepts_a_valid_plan() -> None:
    _validator().validate(_plan())


def test_validator_accepts_a_model_day_estimate_within_ten_minutes() -> None:
    plan = _plan(
        [
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Full body",
                title_fa="تمام بدن",
                estimated_duration_minutes=36,
                exercises=[
                    _exercise(FIRST_ID, estimated_minutes=17),
                    _exercise(SECOND_ID, estimated_minutes=17),
                    _exercise(THIRD_ID, estimated_minutes=17),
                ],
            )
        ]
    )

    _validator().validate(plan)


def test_validator_rejects_a_model_day_estimate_more_than_ten_minutes_away() -> None:
    plan = _plan(
        [
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Full body",
                title_fa="تمام بدن",
                estimated_duration_minutes=37,
                exercises=[_exercise(FIRST_ID), _exercise(SECOND_ID), _exercise(THIRD_ID)],
            )
        ]
    )

    with pytest.raises(WorkoutPlanValidationError) as exc_info:
        _validator().validate(plan)

    assert "duration_mismatch" in {problem.code for problem in exc_info.value.problems}


@pytest.mark.parametrize(
    "plan,expected_code",
    [
        (
            _plan(
                [
                    WorkoutPlanDayOutput(
                        day_number=2,
                        title_en="Bad",
                        title_fa="بد",
                        estimated_duration_minutes=8,
                        exercises=[_exercise(FIRST_ID)],
                    )
                ]
            ),
            "day_numbers",
        ),
        (
            _plan(
                [
                    WorkoutPlanDayOutput(
                        day_number=1,
                        title_en="Bad",
                        title_fa="بد",
                        estimated_duration_minutes=8,
                        exercises=[_exercise(uuid4())],
                    )
                ]
            ),
            "exercise_not_allowed",
        ),
        (
            _plan(
                [
                    WorkoutPlanDayOutput(
                        day_number=1,
                        title_en="Bad",
                        title_fa="بد",
                        estimated_duration_minutes=16,
                        exercises=[_exercise(FIRST_ID), _exercise(FIRST_ID)],
                    )
                ]
            ),
            "duplicate_exercise",
        ),
        (
            _plan(
                [
                    WorkoutPlanDayOutput(
                        day_number=1,
                        title_en="Bad",
                        title_fa="بد",
                        estimated_duration_minutes=8,
                        exercises=[_exercise(FIRST_ID, sets=1)],
                    )
                ]
            ),
            "sets_out_of_policy",
        ),
        (
            _plan(
                [
                    WorkoutPlanDayOutput(
                        day_number=1,
                        title_en="Bad",
                        title_fa="بد",
                        estimated_duration_minutes=45,
                        exercises=[_exercise(FIRST_ID)],
                    )
                ]
            ),
            "duration_mismatch",
        ),
    ],
)
def test_validator_reports_structured_semantic_problems(
    plan: WorkoutPlanModelOutput, expected_code: str
) -> None:
    with pytest.raises(WorkoutPlanValidationError) as exc_info:
        _validator().validate(plan)

    assert expected_code in {problem.code for problem in exc_info.value.problems}


def test_validator_rejects_plan_that_overflows_time_budget() -> None:
    overlong_day = WorkoutPlanDayOutput(
        day_number=1,
        title_en="Long",
        title_fa="طولانی",
        estimated_duration_minutes=45,
        exercises=[_exercise(FIRST_ID, sets=5, rest_seconds=180)] * 4,
    )

    with pytest.raises(WorkoutPlanValidationError) as exc_info:
        _validator().validate(_plan([overlong_day]))

    codes = {problem.code for problem in exc_info.value.problems}
    assert "duplicate_exercise" in codes
    assert "duration_exceeded" in codes


def test_validator_rejects_isolation_before_a_suitable_compound() -> None:
    candidates = CandidateSet(
        exercises=(
            _candidate(FIRST_ID, pattern=MovementPattern.HORIZONTAL_PUSH),
            _candidate(
                SECOND_ID,
                pattern=MovementPattern.ELBOW_FLEXION,
                exercise_type=ExerciseType.ISOLATION,
                muscle=MuscleGroup.BICEPS,
            ),
            _candidate(THIRD_ID, pattern=MovementPattern.SQUAT, muscle=MuscleGroup.QUADRICEPS),
        ),
        candidate_set_hash="a" * 64,
        soft_cautions=(),
        minimum_candidate_count=1,
    )
    validator = WorkoutPlanValidator(
        candidates=candidates,
        policy=WorkoutGenerationPolicy.for_session_duration(45),
        required_day_count=1,
    )
    plan = _plan(
        [
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Bad order",
                title_fa="ترتیب بد",
                estimated_duration_minutes=26,
                exercises=[_exercise(SECOND_ID), _exercise(FIRST_ID), _exercise(THIRD_ID)],
            )
        ]
    )

    with pytest.raises(WorkoutPlanValidationError) as exc_info:
        validator.validate(plan)

    assert "compound_order" in {problem.code for problem in exc_info.value.problems}


def test_cardio_cannot_fill_required_strength_slot() -> None:
    candidates = CandidateSet(
        exercises=(
            _candidate(
                FIRST_ID,
                pattern=MovementPattern.OTHER,
                labels=(ExerciseLabel.CARDIO,),
            ),
            _candidate(SECOND_ID, pattern=MovementPattern.HORIZONTAL_PUSH),
        ),
        candidate_set_hash="a" * 64,
        soft_cautions=(),
        minimum_candidate_count=1,
    )
    validator = WorkoutPlanValidator(
        candidates=candidates,
        policy=WorkoutGenerationPolicy.for_session_duration(45),
        required_day_count=1,
    )
    plan = _plan(
        [
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Cardio only",
                title_fa="فقط هوازی",
                estimated_duration_minutes=8,
                exercises=[_exercise(FIRST_ID)],
            )
        ]
    )

    with pytest.raises(WorkoutPlanValidationError) as exc_info:
        validator.validate(plan)

    assert "insufficient_strength_movements" in {
        problem.code for problem in exc_info.value.problems
    }


@pytest.mark.parametrize("unsafe_note", ["<b>HTML</b>", "https://example.com", "```markdown"])
def test_validator_rejects_unsafe_model_notes(unsafe_note: str) -> None:
    plan = _plan(
        [
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Unsafe note",
                title_fa="یادداشت ناامن",
                estimated_duration_minutes=26,
                exercises=[
                    _exercise(FIRST_ID, notes_en=unsafe_note),
                    _exercise(SECOND_ID),
                    _exercise(THIRD_ID),
                ],
            )
        ]
    )

    with pytest.raises(WorkoutPlanValidationError) as exc_info:
        _validator().validate(plan)

    assert "unsafe_notes" in {problem.code for problem in exc_info.value.problems}
