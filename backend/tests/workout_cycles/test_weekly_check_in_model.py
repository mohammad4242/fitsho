from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.workout_cycles.enums import (
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
)
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleWeeklyCheckIn
from app.workout_cycles.schemas import WorkoutCycleWeeklyCheckInClassificationInput
from app.workout_cycles.service import (
    WorkoutCycleWeeklyCheckInCycleNotFoundError,
    WorkoutCycleWeeklyCheckInSessionsOutOfRangeError,
    WorkoutCycleWeeklyCheckInWeekOutOfRangeError,
    create_weekly_check_in,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan


def _user(db: Session, email_prefix: str = "weekly-check-in") -> User:
    user = User(email=f"{email_prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def _cycle(
    db: Session,
    *,
    duration_weeks: int = 4,
    training_days: int = 3,
    user: User | None = None,
) -> tuple[User, WorkoutCycle]:
    owner = user or _user(db)
    plan = WorkoutPlan(
        user_id=owner.id,
        status=WorkoutPlanStatus.SUPERSEDED,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": duration_weeks},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="coach_review",
    )
    for day_number in range(1, training_days + 1):
        plan.days.append(
            WorkoutDay(
                day_number=day_number,
                title_en=f"Day {day_number}",
                title_fa=f"روز {day_number}",
                estimated_duration_minutes=20,
            )
        )
    db.add(plan)
    db.flush()

    cycle = WorkoutCycle(
        user_id=owner.id,
        workout_plan_id=plan.id,
        duration_weeks=duration_weeks,
    )
    db.add(cycle)
    db.flush()
    return owner, cycle


def _check_in(
    user: User,
    cycle: WorkoutCycle,
    *,
    week_number: int = 1,
    sessions_completed: int = 2,
) -> WorkoutCycleWeeklyCheckIn:
    return WorkoutCycleWeeklyCheckIn(
        user_id=user.id,
        cycle_id=cycle.id,
        week_number=week_number,
        sessions_completed=sessions_completed,
        perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
        recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD,
        has_pain_or_limitation=False,
        note_optional="Felt good.",
    )


def test_valid_weekly_check_in_persists_with_explicit_ownership(db: Session) -> None:
    user, cycle = _cycle(db)

    check_in = create_weekly_check_in(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        week_number=1,
        sessions_completed=2,
        perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
        recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD,
        has_pain_or_limitation=False,
        note_optional="Felt good.",
    )

    assert check_in.id is not None
    assert check_in.user_id == user.id
    assert check_in.cycle_id == cycle.id
    assert check_in.week_number == 1
    assert check_in.sessions_completed == 2
    assert check_in.submitted_at is not None
    assert check_in.created_at is not None
    assert check_in.updated_at is not None
    assert check_in.cycle.user_id == check_in.user_id


def test_duplicate_cycle_week_is_rejected(db: Session) -> None:
    user, cycle = _cycle(db)
    db.add(_check_in(user, cycle))
    db.flush()

    db.add(_check_in(user, cycle))
    with pytest.raises(IntegrityError, match="uq_workout_cycle_weekly_checkins_cycle_week"):
        db.flush()


def test_invalid_week_number_is_rejected(db: Session) -> None:
    user, cycle = _cycle(db)
    db.add(_check_in(user, cycle, week_number=0))

    with pytest.raises(IntegrityError, match="week_positive"):
        db.flush()


def test_week_beyond_cycle_duration_is_rejected(db: Session) -> None:
    user, cycle = _cycle(db, duration_weeks=4)

    with pytest.raises(WorkoutCycleWeeklyCheckInWeekOutOfRangeError):
        create_weekly_check_in(
            db,
            user_id=user.id,
            cycle_id=cycle.id,
            week_number=5,
            sessions_completed=2,
            perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.EASY,
            recovery_rating=WorkoutCycleWeeklyCheckInRecovery.AVERAGE,
            has_pain_or_limitation=False,
        )


def test_negative_sessions_completed_is_rejected(db: Session) -> None:
    user, cycle = _cycle(db)
    db.add(_check_in(user, cycle, sessions_completed=-1))

    with pytest.raises(IntegrityError, match="sessions_completed_nonnegative"):
        db.flush()


def test_sessions_completed_cannot_exceed_prescribed_training_days(db: Session) -> None:
    user, cycle = _cycle(db, training_days=3)

    with pytest.raises(WorkoutCycleWeeklyCheckInSessionsOutOfRangeError):
        create_weekly_check_in(
            db,
            user_id=user.id,
            cycle_id=cycle.id,
            week_number=1,
            sessions_completed=4,
            perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.HARD,
            recovery_rating=WorkoutCycleWeeklyCheckInRecovery.POOR,
            has_pain_or_limitation=True,
        )


@pytest.mark.parametrize("difficulty", list(WorkoutCycleWeeklyCheckInDifficulty))
@pytest.mark.parametrize("recovery", list(WorkoutCycleWeeklyCheckInRecovery))
def test_supported_difficulty_and_recovery_values_persist(
    db: Session,
    difficulty: WorkoutCycleWeeklyCheckInDifficulty,
    recovery: WorkoutCycleWeeklyCheckInRecovery,
) -> None:
    user, cycle = _cycle(db)
    check_in = _check_in(user, cycle)
    check_in.perceived_difficulty = difficulty
    check_in.recovery_rating = recovery
    db.add(check_in)
    db.flush()

    assert check_in.perceived_difficulty is difficulty
    assert check_in.recovery_rating is recovery


def test_wrong_owner_cannot_create_check_in_for_cycle(db: Session) -> None:
    owner, cycle = _cycle(db)
    other_user = _user(db, "other-weekly-check-in")

    with pytest.raises(WorkoutCycleWeeklyCheckInCycleNotFoundError):
        create_weekly_check_in(
            db,
            user_id=other_user.id,
            cycle_id=cycle.id,
            week_number=1,
            sessions_completed=1,
            perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.EASY,
            recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD,
            has_pain_or_limitation=False,
        )

    assert owner.id != other_user.id


@pytest.mark.parametrize("difficulty", list(WorkoutCycleWeeklyCheckInDifficulty))
def test_classification_schema_accepts_every_canonical_difficulty(
    difficulty: WorkoutCycleWeeklyCheckInDifficulty,
) -> None:
    classification = WorkoutCycleWeeklyCheckInClassificationInput(
        perceived_difficulty=difficulty.value,
        recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD.value,
    )

    assert classification.perceived_difficulty is difficulty


@pytest.mark.parametrize("recovery", list(WorkoutCycleWeeklyCheckInRecovery))
def test_classification_schema_accepts_every_canonical_recovery(
    recovery: WorkoutCycleWeeklyCheckInRecovery,
) -> None:
    classification = WorkoutCycleWeeklyCheckInClassificationInput(
        perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE.value,
        recovery_rating=recovery.value,
    )

    assert classification.recovery_rating is recovery


@pytest.mark.parametrize("field", ["perceived_difficulty", "recovery_rating"])
def test_classification_schema_rejects_unknown_values(field: str) -> None:
    payload = {
        "perceived_difficulty": WorkoutCycleWeeklyCheckInDifficulty.EASY.value,
        "recovery_rating": WorkoutCycleWeeklyCheckInRecovery.GOOD.value,
    }
    payload[field] = "unknown_value"

    with pytest.raises(ValidationError):
        WorkoutCycleWeeklyCheckInClassificationInput(**payload)


@pytest.mark.parametrize("field", ["perceived_difficulty", "recovery_rating"])
def test_database_rejects_unknown_classification_values(db: Session, field: str) -> None:
    user, cycle = _cycle(db)
    check_in = _check_in(user, cycle)
    setattr(check_in, field, "unknown_value")
    db.add(check_in)

    with pytest.raises(StatementError):
        db.flush()


@pytest.mark.parametrize("difficulty", list(WorkoutCycleWeeklyCheckInDifficulty))
@pytest.mark.parametrize("recovery", list(WorkoutCycleWeeklyCheckInRecovery))
def test_persisted_classifications_round_trip(
    db: Session,
    difficulty: WorkoutCycleWeeklyCheckInDifficulty,
    recovery: WorkoutCycleWeeklyCheckInRecovery,
) -> None:
    user, cycle = _cycle(db)
    check_in = _check_in(user, cycle)
    check_in.perceived_difficulty = difficulty
    check_in.recovery_rating = recovery
    db.add(check_in)
    db.flush()
    db.expire(check_in)

    saved = db.get(WorkoutCycleWeeklyCheckIn, check_in.id)

    assert saved is not None
    assert saved.perceived_difficulty is difficulty
    assert saved.recovery_rating is recovery
