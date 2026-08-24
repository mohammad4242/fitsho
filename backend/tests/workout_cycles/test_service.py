import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier, Lock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.exercises.enums import MuscleGroup
from app.profile.enums import FitnessGoal, HomeTrainingSetup, Sex, TrainingLocation
from app.profile.models import BodyMeasurement, UserProfile
from app.workout_cycles.enums import (
    WorkoutCycleFeedbackProgress,
    WorkoutCycleFeedbackSatisfaction,
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
)
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleFeedback
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workout_cycles.service import (
    WorkoutCycleAlreadyCompletedError,
    WorkoutCycleNotFoundError,
    WorkoutCyclePlanInactiveError,
    calculate_current_week,
    complete_cycle,
    get_cycle_for_user,
    start_cycle,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan
from app.workouts.program_engine.enums import Goal


def make_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def make_profile(db: Session, user_id: UUID) -> UserProfile:
    profile = UserProfile(
        user_id=user_id,
        display_name="Cycle Athlete",
        birth_date=date(1995, 1, 1),
        sex=Sex.MALE,
        height_cm=180,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        experience_level="beginner",
        training_days_per_week=3,
        preferred_weekdays=[0, 2, 4],
        priority_muscles=[MuscleGroup.BACK.value],
        training_location=TrainingLocation.GYM,
        home_training_setup=None,
        session_duration_minutes=60,
        plan_duration_weeks=4,
    )
    db.add(profile)
    db.add(BodyMeasurement(user_id=user_id, weight_kg=Decimal("80")))
    db.flush()
    return profile


def make_plan(db: Session, user_id: UUID, *, duration_weeks: int = 4) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": duration_weeks},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="deterministic",
    )
    db.add(plan)
    db.flush()
    return plan


@pytest.mark.parametrize("duration_weeks", [4, 6, 8])
def test_start_cycle_accepts_supported_plan_durations(db: Session, duration_weeks: int) -> None:
    user = make_user(db, f"duration-{duration_weeks}@example.com")
    plan = make_plan(db, user.id, duration_weeks=duration_weeks)

    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    assert cycle.status is WorkoutCycleStatus.ACTIVE
    assert cycle.duration_weeks == duration_weeks
    assert cycle.user_id == user.id
    assert cycle.workout_plan_id == plan.id


@pytest.mark.parametrize(
    ("elapsed", "duration_weeks", "expected_week"),
    [
        (timedelta(days=0), 4, 1),
        (timedelta(days=6, hours=23), 4, 1),
        (timedelta(days=7), 4, 2),
        (timedelta(days=14), 4, 3),
        (timedelta(days=27), 4, 4),
        (timedelta(days=28), 4, 4),
        (timedelta(days=90), 4, 4),
        (timedelta(days=-1), 4, 1),
    ],
)
def test_calculate_current_week_is_bounded_and_uses_seven_day_weeks(
    elapsed: timedelta,
    duration_weeks: int,
    expected_week: int,
) -> None:
    started_at = datetime(2026, 1, 1, 12, tzinfo=UTC)

    assert (
        calculate_current_week(
            started_at,
            duration_weeks,
            now=started_at + elapsed,
        )
        == expected_week
    )


def test_calculate_current_week_normalizes_timezone_aware_datetimes() -> None:
    started_at = datetime(2026, 1, 1, 15, tzinfo=timezone(timedelta(hours=3)))
    now = datetime(2026, 1, 8, 12, tzinfo=UTC)

    assert calculate_current_week(started_at, 4, now=now) == 2


def test_start_cycle_is_idempotent_for_one_plan(db: Session) -> None:
    user = make_user(db, "idempotent-cycle@example.com")
    plan = make_plan(db, user.id)

    first = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    second = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    assert second.id == first.id
    assert db.query(WorkoutCycle).filter_by(workout_plan_id=plan.id).count() == 1


def test_start_cycle_rejects_unsupported_plan_duration(db: Session) -> None:
    user = make_user(db, "unsupported-duration@example.com")
    plan = make_plan(db, user.id, duration_weeks=5)

    with pytest.raises(ValueError, match="4, 6, or 8"):
        start_cycle(db, user_id=user.id, workout_plan_id=plan.id)


@pytest.mark.parametrize(
    "plan_status",
    [WorkoutPlanStatus.GENERATING, WorkoutPlanStatus.SUPERSEDED, WorkoutPlanStatus.FAILED],
)
def test_start_cycle_requires_an_active_workout_plan(
    db: Session, plan_status: WorkoutPlanStatus
) -> None:
    user = make_user(db, f"inactive-{plan_status.value}@example.com")
    plan = make_plan(db, user.id)
    plan.status = plan_status
    db.flush()

    with pytest.raises(WorkoutCyclePlanInactiveError):
        start_cycle(db, user_id=user.id, workout_plan_id=plan.id)


def test_cycle_cannot_be_created_twice_at_database_level(db: Session) -> None:
    user = make_user(db, "unique-cycle@example.com")
    plan = make_plan(db, user.id)
    db.add_all(
        [
            WorkoutCycle(user_id=user.id, workout_plan_id=plan.id, duration_weeks=4),
            WorkoutCycle(user_id=user.id, workout_plan_id=plan.id, duration_weeks=4),
        ]
    )

    with pytest.raises(IntegrityError, match="uq_workout_cycles_workout_plan_id"):
        db.flush()


def test_other_user_cannot_read_or_complete_cycle(db: Session) -> None:
    owner = make_user(db, "cycle-owner@example.com")
    other = make_user(db, "cycle-other@example.com")
    plan = make_plan(db, owner.id)
    cycle = start_cycle(db, user_id=owner.id, workout_plan_id=plan.id)

    assert get_cycle_for_user(db, cycle_id=cycle.id, user_id=other.id) is None
    with pytest.raises(WorkoutCycleNotFoundError):
        complete_cycle(db, cycle_id=cycle.id, user_id=other.id)


def test_complete_cycle_allows_feedback_to_be_omitted(db: Session) -> None:
    user = make_user(db, "optional-feedback@example.com")
    plan = make_plan(db, user.id, duration_weeks=6)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    completed = complete_cycle(db, cycle_id=cycle.id, user_id=user.id)

    assert completed.status is WorkoutCycleStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.completion_feedback is None


def test_complete_cycle_stores_structured_optional_feedback(db: Session) -> None:
    user = make_user(db, "cycle-feedback@example.com")
    plan = make_plan(db, user.id, duration_weeks=8)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    feedback = CompletionFeedbackInput(
        adherence_percent=82,
        performance_changes="Added reps on pressing movements.",
        pain_or_limitation_feedback="Mild discomfort during deep knee flexion.",
        measurements={"weight_kg": 81.2, "waist_cm": 84},
    )

    completed = complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=feedback,
    )

    assert completed.completion_feedback is not None
    assert completed.completion_feedback.adherence_percent == 82
    assert completed.completion_feedback.measurements == {
        "weight_kg": 81.2,
        "waist_cm": 84,
    }
    assert completed.completion_feedback.submitted_at is not None


def test_complete_cycle_stores_structured_coaching_feedback(db: Session) -> None:
    user = make_user(db, "structured-cycle-feedback@example.com")
    plan = make_plan(db, user.id, duration_weeks=8)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    feedback = CompletionFeedbackInput(
        overall_difficulty=WorkoutCycleWeeklyCheckInDifficulty.HARD,
        overall_recovery=WorkoutCycleWeeklyCheckInRecovery.GOOD,
        overall_satisfaction=WorkoutCycleFeedbackSatisfaction.SATISFIED,
        strength_progress=WorkoutCycleFeedbackProgress.IMPROVED,
        muscle_progress=WorkoutCycleFeedbackProgress.IMPROVED,
        endurance_progress=WorkoutCycleFeedbackProgress.UNCHANGED,
        energy_progress=WorkoutCycleFeedbackProgress.DECLINED,
        progressed_muscles=[MuscleGroup.CHEST, MuscleGroup.SHOULDERS],
        lagging_muscles=[MuscleGroup.BACK],
        goal_changed=True,
        next_goal=Goal.STRENGTH,
        schedule_changed=True,
        next_training_days=4,
        next_session_duration_minutes=60,
        equipment_changed=False,
        new_limitation="Avoid deep knee flexion.",
        note_optional="Felt stronger overall.",
        measurements={"weight_kg": 81.2},
    )

    completed = complete_cycle(db, cycle_id=cycle.id, user_id=user.id, feedback=feedback)

    stored = completed.completion_feedback
    assert stored is not None
    assert stored.overall_difficulty is WorkoutCycleWeeklyCheckInDifficulty.HARD
    assert stored.overall_recovery is WorkoutCycleWeeklyCheckInRecovery.GOOD
    assert stored.overall_satisfaction is WorkoutCycleFeedbackSatisfaction.SATISFIED
    assert stored.strength_progress is WorkoutCycleFeedbackProgress.IMPROVED
    assert stored.energy_progress is WorkoutCycleFeedbackProgress.DECLINED
    assert stored.progressed_muscles == [MuscleGroup.CHEST.value, MuscleGroup.SHOULDERS.value]
    assert stored.lagging_muscles == [MuscleGroup.BACK.value]
    assert stored.goal_changed is True
    assert stored.next_goal is Goal.STRENGTH
    assert stored.schedule_changed is True
    assert stored.next_training_days == 4
    assert stored.next_session_duration_minutes == 60
    assert stored.equipment_changed is False
    assert stored.new_limitation == "Avoid deep knee flexion."
    assert stored.note_optional == "Felt stronger overall."


def test_confirmed_end_cycle_changes_update_only_confirmed_profile_fields(db: Session) -> None:
    user = make_user(db, "confirmed-profile-changes@example.com")
    profile = make_profile(db, user.id)
    plan = make_plan(db, user.id)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=CompletionFeedbackInput(
            goal_changed=True,
            next_goal=Goal.FAT_LOSS,
            schedule_changed=True,
            next_training_days=4,
            next_session_duration_minutes=75,
            next_preferred_weekdays=[1, 3, 5, 6],
            equipment_changed=True,
            next_training_location=TrainingLocation.HOME,
            next_home_training_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            new_limitation="Avoid deep knee flexion.",
        ),
    )

    assert profile.display_name == "Cycle Athlete"
    assert profile.height_cm == 180
    assert profile.fitness_goal is FitnessGoal.FAT_LOSS
    assert profile.training_days_per_week == 4
    assert profile.session_duration_minutes == 75
    assert profile.preferred_weekdays == [1, 3, 5, 6]
    assert profile.training_location is TrainingLocation.HOME
    assert profile.home_training_setup is HomeTrainingSetup.DUMBBELLS_AVAILABLE
    assert profile.physical_limitations == "Avoid deep knee flexion."
    stored = cycle.completion_feedback
    assert stored is not None
    assert stored.next_preferred_weekdays == [1, 3, 5, 6]
    assert stored.next_training_location is TrainingLocation.HOME
    assert stored.next_home_training_setup is HomeTrainingSetup.DUMBBELLS_AVAILABLE


def test_unconfirmed_end_cycle_values_do_not_change_profile(db: Session) -> None:
    user = make_user(db, "unconfirmed-profile-changes@example.com")
    profile = make_profile(db, user.id)
    plan = make_plan(db, user.id)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=CompletionFeedbackInput(
            goal_changed=False,
            next_goal=Goal.FAT_LOSS,
            schedule_changed=False,
            next_training_days=4,
            next_session_duration_minutes=75,
            next_preferred_weekdays=[1, 3, 5, 6],
            equipment_changed=False,
            next_training_location=TrainingLocation.HOME,
            next_home_training_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        ),
    )

    assert profile.fitness_goal is FitnessGoal.BUILD_MUSCLE
    assert profile.training_days_per_week == 3
    assert profile.session_duration_minutes == 60
    assert profile.preferred_weekdays == [0, 2, 4]
    assert profile.training_location is TrainingLocation.GYM
    assert profile.home_training_setup is None
    assert profile.physical_limitations is None


def test_absent_end_cycle_changes_preserve_profile(db: Session) -> None:
    user = make_user(db, "absent-profile-changes@example.com")
    profile = make_profile(db, user.id)
    plan = make_plan(db, user.id)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=CompletionFeedbackInput(
            pain_or_limitation_feedback="Temporary discomfort was reported this cycle."
        ),
    )

    assert profile.training_days_per_week == 3
    assert profile.session_duration_minutes == 60
    assert profile.preferred_weekdays == [0, 2, 4]
    assert profile.priority_muscles == [MuscleGroup.BACK.value]
    assert profile.physical_limitations is None


def test_other_user_cannot_apply_confirmed_end_cycle_changes(db: Session) -> None:
    owner = make_user(db, "owner-confirmed-profile@example.com")
    owner_profile = make_profile(db, owner.id)
    other = make_user(db, "other-confirmed-profile@example.com")
    other_profile = make_profile(db, other.id)
    plan = make_plan(db, owner.id)
    cycle = start_cycle(db, user_id=owner.id, workout_plan_id=plan.id)

    with pytest.raises(WorkoutCycleNotFoundError):
        complete_cycle(
            db,
            cycle_id=cycle.id,
            user_id=other.id,
            feedback=CompletionFeedbackInput(
                schedule_changed=True,
                next_training_days=4,
                next_session_duration_minutes=75,
            ),
        )

    assert owner_profile.training_days_per_week == 3
    assert other_profile.training_days_per_week == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("next_training_days", 1),
        ("next_training_days", 7),
        ("next_session_duration_minutes", 20),
        ("next_session_duration_minutes", 91),
    ],
)
def test_completion_feedback_rejects_invalid_next_cycle_schedule(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        CompletionFeedbackInput(**{field: value})


@pytest.mark.parametrize("difficulty", list(WorkoutCycleWeeklyCheckInDifficulty))
@pytest.mark.parametrize("recovery", list(WorkoutCycleWeeklyCheckInRecovery))
@pytest.mark.parametrize("satisfaction", list(WorkoutCycleFeedbackSatisfaction))
def test_completion_feedback_accepts_canonical_classifications(
    difficulty: WorkoutCycleWeeklyCheckInDifficulty,
    recovery: WorkoutCycleWeeklyCheckInRecovery,
    satisfaction: WorkoutCycleFeedbackSatisfaction,
) -> None:
    feedback = CompletionFeedbackInput(
        overall_difficulty=difficulty,
        overall_recovery=recovery,
        overall_satisfaction=satisfaction,
    )

    assert feedback.overall_difficulty is difficulty
    assert feedback.overall_recovery is recovery
    assert feedback.overall_satisfaction is satisfaction


def test_completion_feedback_rejects_unknown_structured_values() -> None:
    with pytest.raises(ValidationError):
        CompletionFeedbackInput(overall_satisfaction="unknown")


def test_completion_feedback_allows_legacy_fields_without_new_structured_values() -> None:
    feedback = CompletionFeedbackInput(
        adherence_percent=82,
        performance_changes="Added reps.",
        pain_or_limitation_feedback="No pain.",
        measurements={"waist_cm": 84},
    )

    assert feedback.overall_difficulty is None
    assert feedback.overall_satisfaction is None
    assert feedback.performance_changes == "Added reps."
    assert feedback.measurements == {"waist_cm": 84}


def test_completed_cycle_cannot_be_completed_again(db: Session) -> None:
    user = make_user(db, "complete-once@example.com")
    plan = make_plan(db, user.id)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    complete_cycle(db, cycle_id=cycle.id, user_id=user.id)

    with pytest.raises(WorkoutCycleAlreadyCompletedError):
        complete_cycle(db, cycle_id=cycle.id, user_id=user.id)


def test_start_cycle_is_concurrency_idempotent_with_two_database_sessions() -> None:
    engine = create_engine(_test_database_url())
    email = f"concurrent-cycle-{uuid4()}@example.com"
    insert_barrier = Barrier(2)

    def synchronize_cycle_inserts(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if "INSERT INTO workout_cycles" in statement:
            insert_barrier.wait(timeout=5)

    event.listen(engine, "before_cursor_execute", synchronize_cycle_inserts)
    try:
        with Session(engine) as setup_db:
            user = make_user(setup_db, email)
            plan = make_plan(setup_db, user.id)
            user_id = user.id
            plan_id = plan.id
            setup_db.commit()

        def start_in_session() -> UUID:
            with Session(engine) as worker_db:
                cycle = start_cycle(worker_db, user_id=user_id, workout_plan_id=plan_id)
                worker_db.commit()
                return cycle.id

        with ThreadPoolExecutor(max_workers=2) as executor:
            cycle_ids = list(executor.map(lambda _index: start_in_session(), range(2)))

        assert cycle_ids[0] == cycle_ids[1]
        with Session(engine) as check_db:
            assert (
                check_db.scalar(
                    select(func.count())
                    .select_from(WorkoutCycle)
                    .where(WorkoutCycle.workout_plan_id == plan_id)
                )
                == 1
            )
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_cycle_inserts)
        with Session(engine) as cleanup_db:
            cleanup_db.execute(delete(User).where(User.email == email))
            cleanup_db.commit()
        engine.dispose()


def test_cycle_completion_is_concurrency_safe_with_optional_feedback() -> None:
    engine = create_engine(_test_database_url())
    email = f"concurrent-completion-{uuid4()}@example.com"
    lock_barrier = Barrier(2)
    participant_lock = Lock()
    participants = 0

    def synchronize_locked_cycle_read(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        nonlocal participants
        if "FROM workout_cycles" not in statement or "FOR UPDATE" not in statement:
            return
        with participant_lock:
            participants += 1
        lock_barrier.wait(timeout=5)

    event.listen(engine, "before_cursor_execute", synchronize_locked_cycle_read)
    try:
        with Session(engine) as setup_db:
            user = make_user(setup_db, email)
            plan = make_plan(setup_db, user.id)
            cycle = start_cycle(setup_db, user_id=user.id, workout_plan_id=plan.id)
            user_id = user.id
            cycle_id = cycle.id
            setup_db.commit()

        def complete_in_session(adherence_percent: int) -> str:
            with Session(engine) as worker_db:
                try:
                    complete_cycle(
                        worker_db,
                        cycle_id=cycle_id,
                        user_id=user_id,
                        feedback=CompletionFeedbackInput(adherence_percent=adherence_percent),
                    )
                    worker_db.commit()
                    return "completed"
                except WorkoutCycleAlreadyCompletedError:
                    worker_db.rollback()
                    return "already_completed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(complete_in_session, [70, 90]))

        assert participants == 2
        assert sorted(outcomes) == ["already_completed", "completed"]
        with Session(engine) as check_db:
            cycle = check_db.get(WorkoutCycle, cycle_id)
            assert cycle is not None
            assert cycle.status is WorkoutCycleStatus.COMPLETED
            assert (
                check_db.scalar(
                    select(func.count())
                    .select_from(WorkoutCycleFeedback)
                    .where(WorkoutCycleFeedback.cycle_id == cycle_id)
                )
                == 1
            )
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_locked_cycle_read)
        with Session(engine) as cleanup_db:
            cleanup_db.execute(delete(User).where(User.email == email))
            cleanup_db.commit()
        engine.dispose()


def _test_database_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test",
    )
