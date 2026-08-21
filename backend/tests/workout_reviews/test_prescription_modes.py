from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.schemas import WorkoutPlanExerciseOutput
from app.exercises.enums import PrescriptionMode
from app.workout_reviews.schemas import (
    WorkoutReviewDayDraft,
    WorkoutReviewDraftUpdate,
    WorkoutReviewExerciseDraft,
)
from app.workout_reviews.validation import WorkoutReviewDraftValidator
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise


def test_coach_review_preserves_duration_contract() -> None:
    draft = WorkoutReviewExerciseDraft(
        order_index=1,
        exercise_id=uuid4(),
        sets=2,
        prescription_mode=PrescriptionMode.DURATION,
        reps_min=None,
        reps_max=None,
        duration_min_seconds=20,
        duration_max_seconds=40,
        rir=None,
        rest_seconds=60,
    )

    output = WorkoutPlanExerciseOutput(
        exercise_id=draft.exercise_id,
        sets=draft.sets,
        prescription_mode=draft.prescription_mode,
        reps_min=draft.reps_min,
        reps_max=draft.reps_max,
        duration_min_seconds=draft.duration_min_seconds,
        duration_max_seconds=draft.duration_max_seconds,
        rest_seconds=draft.rest_seconds,
        rir=draft.rir,
        estimated_minutes=4,
        notes_en=None,
        notes_fa=None,
    )

    assert output.prescription_mode is PrescriptionMode.DURATION
    assert output.rir is None


def test_coach_review_rejects_duration_rir() -> None:
    with pytest.raises(ValidationError, match="null RIR"):
        WorkoutReviewExerciseDraft(
            order_index=1,
            exercise_id=uuid4(),
            sets=2,
            prescription_mode=PrescriptionMode.DURATION,
            reps_min=None,
            reps_max=None,
            duration_min_seconds=20,
            duration_max_seconds=40,
            rir=2,
            rest_seconds=60,
        )


def test_coach_review_does_not_restore_source_rir_for_duration() -> None:
    exercise_id = uuid4()
    source_day = WorkoutDay(
        day_number=1,
        title_en="Day 1",
        title_fa="روز ۱",
        estimated_duration_minutes=20,
    )
    source_item = WorkoutPlanExercise(
        exercise_id=exercise_id,
        order_index=1,
        sets=2,
        reps_min=8,
        reps_max=12,
        rest_seconds=60,
        rir=2,
        estimated_minutes=4,
    )
    payload = WorkoutReviewDraftUpdate(
        expected_revision=1,
        days=[
            WorkoutReviewDayDraft(
                day_number=1,
                exercises=[
                    WorkoutReviewExerciseDraft(
                        order_index=1,
                        exercise_id=exercise_id,
                        sets=2,
                        prescription_mode=PrescriptionMode.DURATION,
                        duration_min_seconds=20,
                        duration_max_seconds=40,
                        rir=None,
                        rest_seconds=60,
                    )
                ],
            )
        ],
    )

    model = WorkoutReviewDraftValidator._to_model(
        WorkoutPlan(days=[source_day]),
        payload,
        {(1, 1): (source_day, source_item)},
    )

    assert model.days[0].exercises[0].rir is None
