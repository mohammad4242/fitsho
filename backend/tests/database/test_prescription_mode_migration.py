from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy import inspect


def _load_migration():
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260821_103_add_prescription_modes.py"
    )
    spec = spec_from_file_location("prescription_mode_migration", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prescription_migration_has_canonical_ids_and_mode_aware_constraints(db) -> None:
    migration = _load_migration()
    assert migration.CANONICAL_DURATION_EXERCISES == {
        ("free-exercise-db", "0464"): (20, 40),
        ("free-exercise-db", "0705"): (20, 40),
        ("fitsho_training_template", "side-plank"): (20, 40),
    }

    inspector = inspect(db.get_bind())
    exercise_columns = {item["name"] for item in inspector.get_columns("exercises")}
    plan_columns = {item["name"] for item in inspector.get_columns("workout_plan_exercises")}
    assert {
        "prescription_mode",
        "duration_min_seconds",
        "duration_max_seconds",
    }.issubset(exercise_columns)
    assert {
        "prescription_mode",
        "duration_min_seconds",
        "duration_max_seconds",
    }.issubset(plan_columns)

    exercise_checks = {
        item["name"]: item["sqltext"] or ""
        for item in inspector.get_check_constraints("exercises")
    }
    plan_checks = {
        item["name"]: item["sqltext"] or ""
        for item in inspector.get_check_constraints("workout_plan_exercises")
    }
    assert "ck_exercises_prescription_contract" in exercise_checks
    assert "ck_workout_plan_exercises_prescription_contract" in plan_checks
    assert "duration_min_seconds" in exercise_checks["ck_exercises_prescription_contract"]
    assert "duration_max_seconds" in exercise_checks["ck_exercises_prescription_contract"]
    plan_contract = plan_checks["ck_workout_plan_exercises_prescription_contract"]
    assert "reps_min" in plan_contract and "reps_max" in plan_contract
    assert "rir" in plan_contract and "IS NULL" in plan_contract
