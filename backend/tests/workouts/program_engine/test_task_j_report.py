"""Focused contract tests for the truthful Batch2 report projection."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import scripts.generate_e2e_report as report
import scripts.generate_e2e_report_batch2 as batch2
from app.auth.models import User
from app.config import get_settings
from app.exercises.enums import ExerciseType, MuscleGroup
from app.workouts.schemas import WorkoutDayResponse

TEST_PROFILES_BATCH2 = batch2.TEST_PROFILES_BATCH2
TEST_PROFILES_BATCH2 = [
    dict(profile, priority_muscles=profile["priority_muscles"][:1])
    for profile in TEST_PROFILES_BATCH2
]


def _profile(number: int, *, limitations_text: str | None = None) -> dict:
    profile = dict(TEST_PROFILES_BATCH2[0])
    profile.update(num=number, name=f"پروفایل {number}", limitations_text=limitations_text)
    return profile


def _success_result(
    *,
    gate_status: str = "accepted",
    coverage_status: str = "satisfied",
    number: int = 1,
) -> dict:
    return {
        "success": True,
        "plan": SimpleNamespace(
            safety_status="clear",
            days=[],
            plan_duration_weeks=4,
            engine_version="program_engine_v1",
        ),
        "error_code": None,
        "errors": (),
        "safety_status": "clear",
        "latency_sec": 0.1,
        "final_gate": {
            "status": gate_status,
            "reason_codes": (),
            "constraint_reason_codes": (
                ("FULL_BODY_PATTERN_UNAVAILABLE:pull",) if gate_status != "accepted" else ()
            ),
        },
        "weekly_coverage": {
            "status": coverage_status,
            "reason_codes": (
                ("FULL_BODY_PATTERN_UNAVAILABLE:pull",) if coverage_status == "constrained" else ()
            ),
            "missing_patterns": ("pull",) if coverage_status == "constrained" else (),
            "missing_major_muscles": ("back",) if coverage_status == "constrained" else (),
        },
        "weekly_distribution": {
            "status": "not_needed",
            "reason_codes": ("WEEKLY_REDISTRIBUTION_ALREADY_BALANCED",),
        },
        "requested_day_count": 2,
        "actual_day_count": 2,
        "per_day": (
            {
                "day_number": 1,
                "exercise_count": 4,
                "main_exercise_count": 4,
                "supplemental_exercise_count": 0,
                "total_exercise_count": 4,
                "duration_minutes": 45,
            },
            {
                "day_number": 2,
                "exercise_count": 3,
                "main_exercise_count": 3,
                "supplemental_exercise_count": 0,
                "total_exercise_count": 3,
                "duration_minutes": 43,
            },
        ),
        "profile_number": number,
    }


def test_batch2_evidence_uses_canonical_main_and_supplemental_counts() -> None:
    main_item = SimpleNamespace(
        exercise_type=ExerciseType.COMPOUND,
        primary_muscle=MuscleGroup.CHEST,
    )
    core_item = SimpleNamespace(
        # CORE remains supplemental even when its stored muscle is unexpected.
        exercise_type=ExerciseType.CORE,
        primary_muscle=MuscleGroup.CHEST,
    )
    program = SimpleNamespace(
        aggregate_metrics={
            "final_quality_gate": {"status": "accepted"},
            "weekly_coverage": {"status": "satisfied"},
            "weekly_distribution": {"status": "not_needed"},
        },
        weekly_schedule=(
            SimpleNamespace(
                day_index=1,
                exercises=(main_item, main_item, main_item, main_item, core_item),
                estimated_duration_minutes=60,
            ),
        ),
    )

    evidence = batch2._successful_result_evidence(program, requested_day_count=1)

    assert evidence["per_day"] == (
        {
            "day_number": 1,
            "exercise_count": 4,
            "main_exercise_count": 4,
            "supplemental_exercise_count": 1,
            "total_exercise_count": 5,
            "duration_minutes": 60,
        },
    )


def test_projection_reconciles_mixed_outcomes_from_the_same_raw_records() -> None:
    raw_results = [
        (_profile(1), _success_result(number=1)),
        (
            _profile(6),
            _success_result(
                gate_status="accepted_with_constraints", coverage_status="constrained", number=6
            ),
        ),
        (
            _profile(10, limitations_text="audit-only limitation"),
            {
                "success": False,
                "plan": None,
                "error_code": "ENGINE_FAILURE_X",
                "errors": ("REASON_A", "REASON_B"),
                "safety_status": "rejected",
                "latency_sec": 0.2,
            },
        ),
    ]
    before = deepcopy(raw_results)

    projection = batch2.project_batch2_results(raw_results)

    assert projection["summary"] == {
        "total": 3,
        "success": 2,
        "failure": 1,
        "constrained": 1,
    }
    assert [item["status"] for item in projection["details"]] == [
        "success",
        "constrained",
        "failure",
    ]
    assert projection["details"][1]["weekly_coverage"]["status"] == "constrained"
    assert projection["details"][2]["error_code"] == "ENGINE_FAILURE_X"
    assert projection["details"][2]["errors"] == ["REASON_A", "REASON_B"]
    assert raw_results == before


def test_html_uses_projection_evidence_and_escapes_engine_diagnostics() -> None:
    results = [
        (
            _profile(6),
            _success_result(
                gate_status="accepted_with_constraints", coverage_status="constrained", number=6
            ),
        ),
        (
            _profile(10, limitations_text="سابقه متنی برای ممیزی"),
            {
                "success": False,
                "plan": None,
                "error_code": "ENGINE_<FAILURE>",
                "errors": ("REASON_<unsafe>",),
                "safety_status": "rejected",
                "latency_sec": 0.2,
            },
        ),
    ]

    html = batch2.generate_html_report(results)

    assert "تعداد برنامه‌های محدودشده" in html
    assert "accepted_with_constraints" in html
    assert "constrained" in html
    assert "FULL_BODY_PATTERN_UNAVAILABLE:pull" in html
    assert "ENGINE_&lt;FAILURE&gt;" in html
    assert "REASON_&lt;unsafe&gt;" in html
    assert "REASON_<unsafe>" not in html
    assert "سابقه متنی برای ممیزی" in html
    assert "تولید موفق برنامه‌های خانگی با وزن بدن (کاربر ۶)" not in html
    assert "سد ایمنی آسیب‌های متنی ثبت‌نشده (کاربر ۱۰)" not in html
    assert "برنامه‌های تولیدشده و پذیرفته‌شده" in html
    assert "بهینه‌سازی‌شده" not in html


def test_persian_day_reports_name_all_three_exercise_count_concepts() -> None:
    day = WorkoutDayResponse.model_construct(
        title_fa="روز اول",
        exercises=[],
        estimated_duration_minutes=60,
        main_exercise_count=4,
        supplemental_exercise_count=1,
        total_exercise_count=5,
    )

    for rendered in (report.render_day_block(day), batch2.render_day_block(day)):
        assert "حرکات اصلی: ۴" in rendered
        assert "Core / تکمیلی: ۱" in rendered
        assert "مجموع حرکات: ۵" in rendered


def test_real_batch2_run_is_rollback_isolated_and_evidence_reconciles(monkeypatch) -> None:
    captured_user_ids = []
    original_generate = batch2.generate_program

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        captured_user_ids.append(args[0].user_id)
        return result

    monkeypatch.setattr(batch2, "generate_program", capture_generate)
    monkeypatch.setattr(batch2, "TEST_PROFILES_BATCH2", TEST_PROFILES_BATCH2)

    results = batch2.run_batch2_profiles()
    projection = batch2.project_batch2_results(results)
    summary = projection["summary"]

    assert len(results) == 10
    assert len({profile["num"] for profile, _ in results}) == 10
    assert len(captured_user_ids) == 10
    assert len(set(captured_user_ids)) == 10
    assert summary["total"] == 10
    assert summary["success"] + summary["failure"] == 10
    assert summary["constrained"] <= summary["success"]

    for (profile, raw), detail in zip(results, projection["details"], strict=True):
        assert detail["status"] == (
            "failure"
            if not raw["success"]
            else "constrained"
            if raw["final_gate"]["status"] == "accepted_with_constraints"
            else "success"
        )
        if raw["success"]:
            assert detail["requested_day_count"] == profile["training_days_per_week"]
            assert raw["final_gate"]["status"] in {
                "accepted",
                "accepted_with_constraints",
            }
            assert raw["final_gate"]["reason_codes"] is not None
            assert raw["weekly_coverage"] is not None
            assert raw["weekly_distribution"] is not None
            assert raw["actual_day_count"] == len(raw["per_day"])
            assert raw["actual_day_count"] == len(raw["plan"].days)
            assert all(
                day["exercise_count"] == day["main_exercise_count"]
                and day["total_exercise_count"] == len(plan_day.exercises)
                and day["supplemental_exercise_count"]
                == day["total_exercise_count"] - day["main_exercise_count"]
                and plan_day.main_exercise_count == day["main_exercise_count"]
                and plan_day.supplemental_exercise_count
                == day["supplemental_exercise_count"]
                and plan_day.total_exercise_count == day["total_exercise_count"]
                and day["duration_minutes"] == plan_day.estimated_duration_minutes
                for day, plan_day in zip(raw["per_day"], raw["plan"].days, strict=True)
            )
        else:
            assert detail["requested_day_count"] is None
            assert detail["error_code"] == raw["error_code"]
            assert detail["errors"] == list(raw["errors"])

    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as db:
            assert (
                db.scalar(
                    select(func.count()).select_from(User).where(User.id.in_(captured_user_ids))
                )
                == 0
            )
    finally:
        engine.dispose()


def test_repeated_real_batch2_runs_are_deterministic_and_profile_isolated(monkeypatch) -> None:
    captured_user_ids = []
    original_generate = batch2.generate_program

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        captured_user_ids.append(args[0].user_id)
        return result

    monkeypatch.setattr(batch2, "generate_program", capture_generate)
    monkeypatch.setattr(batch2, "TEST_PROFILES_BATCH2", TEST_PROFILES_BATCH2)

    first_results = batch2.run_batch2_profiles()
    second_results = batch2.run_batch2_profiles()

    assert batch2.project_batch2_results(first_results) == batch2.project_batch2_results(
        second_results
    )

    first_ids = captured_user_ids[: len(TEST_PROFILES_BATCH2)]
    second_ids = captured_user_ids[len(TEST_PROFILES_BATCH2) :]
    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids)) == len(TEST_PROFILES_BATCH2)


def test_batch2_projection_is_stable_across_python_hash_seeds() -> None:
    child_code = """
import contextlib
import io
import json
import scripts.generate_e2e_report_batch2 as batch2

batch2.TEST_PROFILES_BATCH2 = [
    dict(profile, priority_muscles=profile["priority_muscles"][:1])
    for profile in batch2.TEST_PROFILES_BATCH2
]

with contextlib.redirect_stdout(io.StringIO()):
    projected = batch2.project_batch2_results(batch2.run_batch2_profiles())
print(json.dumps(projected, ensure_ascii=False, sort_keys=True))
"""
    backend_root = Path(__file__).parents[3]
    projections = []
    for seed in range(1, 6):
        environment = os.environ | {"PYTHONHASHSEED": str(seed)}
        completed = subprocess.run(
            [sys.executable, "-c", child_code],
            cwd=backend_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        projections.append(json.loads(completed.stdout))

    assert all(projection == projections[0] for projection in projections[1:])
