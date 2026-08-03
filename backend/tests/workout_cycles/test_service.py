import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleFeedback
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workout_cycles.service import (
    WorkoutCycleAlreadyCompletedError,
    WorkoutCycleNotFoundError,
    WorkoutCyclePlanInactiveError,
    complete_cycle,
    get_cycle_for_user,
    start_cycle,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan


def make_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
    return user


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
def test_start_cycle_accepts_supported_plan_durations(
    db: Session, duration_weeks: int
) -> None:
    user = make_user(db, f"duration-{duration_weeks}@example.com")
    plan = make_plan(db, user.id, duration_weeks=duration_weeks)

    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    assert cycle.status is WorkoutCycleStatus.ACTIVE
    assert cycle.duration_weeks == duration_weeks
    assert cycle.user_id == user.id
    assert cycle.workout_plan_id == plan.id


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
            assert check_db.scalar(
                select(func.count()).select_from(WorkoutCycle).where(
                    WorkoutCycle.workout_plan_id == plan_id
                )
            ) == 1
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
            assert check_db.scalar(
                select(func.count()).select_from(WorkoutCycleFeedback).where(
                    WorkoutCycleFeedback.cycle_id == cycle_id
                )
            ) == 1
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
