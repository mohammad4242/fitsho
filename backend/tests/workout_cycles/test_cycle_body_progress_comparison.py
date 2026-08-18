from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.body_analysis.enums import BodyAnalysisClassification, BodyArea
from app.body_photos.enums import BodyPhotoPurpose
from app.profile.models import BodyMeasurement
from app.workout_cycles.body_progress_models import WorkoutCycleBodyProgressComparison
from app.workout_cycles.body_progress_service import (
    WorkoutCycleBodyProgressComparisonNotFoundError,
    compare_cycle_body_progress,
)
from tests.body_analysis.test_progress_comparison import _session_with_result
from tests.body_photos.test_session_api import ORIGIN
from tests.workout_cycles.test_replacement_api import _plan_with_cycle, _register, _user


def _cycle_with_snapshots(
    db: Session,
    *,
    include_start: bool = True,
    include_end: bool = True,
):
    user = _user(db)
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user.id)
    assert cycle is not None
    start_at = datetime.now(UTC) - timedelta(days=30)
    cycle.started_at = start_at
    db.commit()

    if include_start:
        db.add(
            BodyMeasurement(
                user_id=user.id,
                weight_kg=Decimal("80.00"),
                waist_circumference_cm=Decimal("90.00"),
                measured_at=start_at,
            )
        )
        db.commit()
        _session_with_result(
            db,
            user,
            created_at=start_at,
            findings={
                BodyArea.SHOULDERS: (BodyAnalysisClassification.CLEAR_LAG, 0.9),
            },
        )

    if include_end:
        end_session, end_analysis, _ = _session_with_result(
            db,
            user,
            created_at=datetime.now(UTC),
            findings={
                BodyArea.SHOULDERS: (BodyAnalysisClassification.MILD_LAG, 0.9),
            },
            purpose=BodyPhotoPurpose.CYCLE_COMPLETION,
        )
        end_session.cycle_id = cycle.id
        end_analysis.cycle_id = cycle.id
        db.add(
            BodyMeasurement(
                user_id=user.id,
                cycle_id=cycle.id,
                weight_kg=Decimal("78.00"),
                waist_circumference_cm=Decimal("87.00"),
                measured_at=end_session.created_at,
            )
        )
        db.commit()

    return user, cycle


def test_cycle_comparison_contains_measurement_deltas_analysis_changes_and_provenance(
    db: Session,
) -> None:
    user, cycle = _cycle_with_snapshots(db)

    comparison = compare_cycle_body_progress(db, user_id=user.id, cycle_id=cycle.id)

    assert comparison.cycle_id == cycle.id
    assert comparison.start_measurement_id is not None
    assert comparison.end_measurement_id is not None
    assert comparison.start_session_id is not None
    assert comparison.end_session_id is not None
    assert comparison.comparison_result["measurement"]["metrics"]["weight_kg"]["delta"] == -2.0
    assert (
        comparison.comparison_result["measurement"]["metrics"]["waist_circumference_cm"]["delta"]
        == -3.0
    )
    analysis = comparison.comparison_result["body_analysis"]
    assert "shoulders" in analysis["improved_areas"]
    assert analysis["comparison"]["areas"]
    assert comparison.comparison_result["provenance"]["cycle_id"] == str(cycle.id)


def test_cycle_comparison_represents_missing_start_and_end_data_safely(db: Session) -> None:
    user, cycle = _cycle_with_snapshots(db, include_start=False, include_end=False)

    comparison = compare_cycle_body_progress(db, user_id=user.id, cycle_id=cycle.id)

    assert comparison.comparison_result["missing_data"] == [
        "start_measurement",
        "end_measurement",
        "start_analysis",
        "end_analysis",
    ]
    assert comparison.comparison_result["measurement"]["status"] == "missing_both"
    assert comparison.comparison_result["body_analysis"]["status"] == "missing_both"
    assert comparison.start_measurement_id is None
    assert comparison.end_result_version_id is None


@pytest.mark.parametrize(
    ("include_start", "include_end", "expected_status", "missing_key"),
    [
        (False, True, "missing_start", "start_measurement"),
        (True, False, "missing_end", "end_measurement"),
    ],
)
def test_cycle_comparison_represents_one_missing_side_safely(
    db: Session,
    include_start: bool,
    include_end: bool,
    expected_status: str,
    missing_key: str,
) -> None:
    user, cycle = _cycle_with_snapshots(
        db,
        include_start=include_start,
        include_end=include_end,
    )

    comparison = compare_cycle_body_progress(db, user_id=user.id, cycle_id=cycle.id)

    assert comparison.comparison_result["measurement"]["status"] == expected_status
    assert comparison.comparison_result["body_analysis"]["status"] == expected_status
    assert missing_key in comparison.comparison_result["missing_data"]


def test_cycle_comparison_requires_owned_cycle(db: Session) -> None:
    owner, cycle = _cycle_with_snapshots(db, include_start=False, include_end=False)
    other = _user(db)

    with pytest.raises(WorkoutCycleBodyProgressComparisonNotFoundError):
        compare_cycle_body_progress(db, user_id=other.id, cycle_id=cycle.id)

    assert db.query(WorkoutCycleBodyProgressComparison).filter_by(user_id=other.id).count() == 0
    assert owner.id != other.id


def test_cycle_comparison_updates_the_same_snapshot_when_end_data_is_added(db: Session) -> None:
    user, cycle = _cycle_with_snapshots(db, include_start=True, include_end=False)
    first = compare_cycle_body_progress(db, user_id=user.id, cycle_id=cycle.id)

    end_session, end_analysis, _ = _session_with_result(
        db,
        user,
        created_at=datetime.now(UTC),
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.MILD_LAG, 0.9)},
        purpose=BodyPhotoPurpose.CYCLE_COMPLETION,
    )
    end_session.cycle_id = cycle.id
    end_analysis.cycle_id = cycle.id
    db.add(
        BodyMeasurement(
            user_id=user.id,
            cycle_id=cycle.id,
            weight_kg=Decimal("79.00"),
            measured_at=end_session.created_at,
        )
    )
    db.commit()

    second = compare_cycle_body_progress(db, user_id=user.id, cycle_id=cycle.id)

    assert second.id == first.id
    assert second.end_session_id == end_session.id
    assert second.end_analysis_id == end_analysis.id


def test_cycle_body_progress_comparison_endpoint_is_registered_and_owned(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"cycle-body-endpoint-{datetime.now(UTC).timestamp()}@example.com")
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.get(
        f"/api/v1/workout-cycles/{cycle.id}/body-progress-comparison",
        headers=ORIGIN,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cycle_id"] == str(cycle.id)
    assert body["result"]["provenance"]["cycle_id"] == str(cycle.id)
    assert body["result"]["missing_data"] == [
        "start_measurement",
        "end_measurement",
        "start_analysis",
        "end_analysis",
    ]
