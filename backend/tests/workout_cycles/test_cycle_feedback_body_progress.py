from __future__ import annotations

from fastapi.testclient import TestClient

from app.workout_cycles.body_progress_service import (
    compare_cycle_body_progress,
)
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workout_cycles.service import complete_cycle, get_cycle_feedback_body_progress_context
from tests.body_photos.test_session_api import ORIGIN
from tests.workout_cycles.test_cycle_body_progress_comparison import _cycle_with_snapshots
from tests.workout_cycles.test_replacement_api import _plan_with_cycle, _register, _user


def test_completion_feedback_links_the_owned_end_body_evidence(db) -> None:
    user, cycle = _cycle_with_snapshots(db)
    feedback = CompletionFeedbackInput(note_optional="Cycle completed.")

    completed = complete_cycle(db, cycle_id=cycle.id, user_id=user.id, feedback=feedback)

    stored = completed.completion_feedback
    assert stored is not None
    assert stored.body_progress_comparison is not None
    comparison = stored.body_progress_comparison
    assert stored.body_progress_comparison_id == comparison.id
    assert comparison.user_id == user.id
    assert comparison.cycle_id == cycle.id
    assert comparison.end_analysis_id is not None
    assert comparison.end_measurement_id is not None
    assert comparison.start_analysis_id is not None
    assert comparison.start_measurement_id is not None
    assert comparison.comparison_result["provenance"]["cycle_id"] == str(cycle.id)


def test_feedback_context_exposes_the_cycle_comparison_and_provenance(db) -> None:
    user, cycle = _cycle_with_snapshots(db)
    complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=CompletionFeedbackInput(note_optional="Use body evidence later."),
    )

    context = get_cycle_feedback_body_progress_context(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
    )

    assert context is not None
    assert context.cycle_id == cycle.id
    assert context.body_progress_comparison is not None
    assert context.body_progress_comparison.cycle_id == cycle.id
    assert context.body_progress_comparison.result.provenance.cycle_id == cycle.id


def test_feedback_cannot_use_another_users_body_evidence(db) -> None:
    owner, owner_cycle = _cycle_with_snapshots(db)
    other, other_cycle = _cycle_with_snapshots(db)
    other_comparison = compare_cycle_body_progress(
        db,
        user_id=other.id,
        cycle_id=other_cycle.id,
    )

    complete_cycle(
        db,
        cycle_id=owner_cycle.id,
        user_id=owner.id,
        feedback=CompletionFeedbackInput(note_optional="Owner feedback."),
    )

    stored = owner_cycle.completion_feedback
    assert stored is not None
    assert stored.body_progress_comparison_id != other_comparison.id
    assert stored.body_progress_comparison is not None
    assert stored.body_progress_comparison.user_id == owner.id
    assert stored.body_progress_comparison.cycle_id == owner_cycle.id
    assert other_cycle.user_id == other.id


def test_feedback_without_body_analysis_remains_valid_with_explicit_missing_context(db) -> None:
    user = _user(db)
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user.id)
    assert cycle is not None

    completed = complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=CompletionFeedbackInput(note_optional="No photos this cycle."),
    )

    stored = completed.completion_feedback
    assert stored is not None
    assert stored.body_progress_comparison is not None
    result = stored.body_progress_comparison.comparison_result
    assert result["missing_data"] == [
        "start_measurement",
        "end_measurement",
        "start_analysis",
        "end_analysis",
    ]
    assert result["body_analysis"]["status"] == "missing_both"


def test_feedback_body_progress_context_endpoint_is_registered(
    client: TestClient,
    db,
) -> None:
    user_id = _register(client, "cycle-feedback-context-endpoint@example.com")
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None
    complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user_id,
        feedback=CompletionFeedbackInput(note_optional="Endpoint context."),
    )

    response = client.get(
        f"/api/v1/workout-cycles/{cycle.id}/feedback/body-progress",
        headers=ORIGIN,
    )

    assert response.status_code == 200
    assert response.json()["cycle_id"] == str(cycle.id)
    assert response.json()["body_progress_comparison"] is not None
