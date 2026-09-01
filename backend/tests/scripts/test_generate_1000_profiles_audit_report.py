from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

import scripts.generate_1000_profiles_audit_report as audit_module
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.program_engine.enums import PhysicalJobDemand, RecoveryRating
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.service import WorkoutGenerationService
from scripts.generate_1000_profiles_audit_report import (
    ProfileSpec,
    evaluate_single_profile,
)
from tests.workouts.test_service import _seed_bodyweight_template_catalog


def _create_test_profile(
    *,
    experience_level: ExperienceLevel,
    training_location: TrainingLocation,
    home_setup: HomeTrainingSetup | None = None,
    training_days: int = 3,
    cautions: list[TrainingCaution] | None = None,
) -> ProfileSpec:
    return ProfileSpec(
        index=1,
        name="تست روتینگ",
        sex=Sex.MALE,
        birth_date=date(1998, 1, 1),
        age=28,
        height_cm=178,
        weight_kg=75.0,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        experience_level=experience_level,
        training_age_months=0 if experience_level is ExperienceLevel.FIRST_MONTH else 6,
        training_days_per_week=training_days,
        session_duration_minutes=45,
        training_location=training_location,
        home_training_setup=home_setup,
        priority_muscle=None,
        training_cautions=cautions or [],
        plan_duration_weeks=6,
        sleep_quality=RecoveryRating.GOOD,
        stress_level=RecoveryRating.AVERAGE,
        physical_job_demand=PhysicalJobDemand.LOW,
    )


@pytest.mark.parametrize(
    ("experience_level", "training_days", "expected_slug"),
    [
        (ExperienceLevel.FIRST_MONTH, 2, "bw-first-month-2d-v1"),
        (ExperienceLevel.FIRST_MONTH, 3, "bw-first-month-3d-v1"),
        (ExperienceLevel.FIRST_MONTH, 4, "bw-first-month-4d-v1"),
        (ExperienceLevel.BEGINNER, 2, "bw-beginner-2d-v1"),
        (ExperienceLevel.BEGINNER, 3, "bw-beginner-3d-v1"),
        (ExperienceLevel.BEGINNER, 4, "bw-beginner-4d-v1"),
    ],
)
def test_first_month_and_beginner_home_bodyweight_routes_to_fixed_template_without_engine(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    experience_level: ExperienceLevel,
    training_days: int,
    expected_slug: str,
) -> None:
    _seed_bodyweight_template_catalog(db)
    service = WorkoutGenerationService(db, settings=None)
    catalog = service._load_catalog()

    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("generate_program must not be called for supported fixed bodyweight")

    monkeypatch.setattr(audit_module, "generate_program", fail_engine)

    spec = _create_test_profile(
        experience_level=experience_level,
        training_location=TrainingLocation.HOME,
        home_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
        training_days=training_days,
    )

    res = evaluate_single_profile(
        spec,
        catalog=catalog,
        references=(),
        exercise_map={},
        ruleset=RULESET,
        db=db,
    )

    assert res["generation_path"] == "bodyweight_fixed_template"
    assert res["status"] == "SUCCESS"
    assert res["template_slug"] == expected_slug
    assert res["days_count"] == training_days


def test_beginner_home_dumbbells_routes_to_program_engine(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WorkoutGenerationService(db, settings=None)
    catalog = service._load_catalog()

    engine_called = False

    def spy_engine(*args: object, **kwargs: object) -> MagicMock:
        nonlocal engine_called
        engine_called = True
        mock = MagicMock()
        mock.is_success = False
        mock.program = None
        mock.error_code = MagicMock(value="MOCK_TEST_ERROR")
        mock.errors = []
        mock.decision_trace = ()
        return mock

    monkeypatch.setattr(audit_module, "generate_program", spy_engine)

    spec = _create_test_profile(
        experience_level=ExperienceLevel.BEGINNER,
        training_location=TrainingLocation.HOME,
        home_setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        training_days=3,
    )

    res = evaluate_single_profile(
        spec,
        catalog=catalog,
        references=(),
        exercise_map={},
        ruleset=RULESET,
        db=db,
    )

    assert engine_called is True
    assert res["generation_path"] == "program_engine"


def test_beginner_gym_routes_to_program_engine(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WorkoutGenerationService(db, settings=None)
    catalog = service._load_catalog()

    engine_called = False

    def spy_engine(*args: object, **kwargs: object) -> MagicMock:
        nonlocal engine_called
        engine_called = True
        mock = MagicMock()
        mock.is_success = False
        mock.program = None
        mock.error_code = MagicMock(value="MOCK_TEST_ERROR")
        mock.errors = []
        mock.decision_trace = ()
        return mock

    monkeypatch.setattr(audit_module, "generate_program", spy_engine)

    spec = _create_test_profile(
        experience_level=ExperienceLevel.BEGINNER,
        training_location=TrainingLocation.GYM,
        home_setup=None,
        training_days=3,
    )

    res = evaluate_single_profile(
        spec,
        catalog=catalog,
        references=(),
        exercise_map={},
        ruleset=RULESET,
        db=db,
    )

    assert engine_called is True
    assert res["generation_path"] == "program_engine"


@pytest.mark.parametrize("exp_level", [ExperienceLevel.INTERMEDIATE, ExperienceLevel.ADVANCED])
def test_intermediate_and_advanced_pure_bodyweight_rejects_without_calling_engine(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    exp_level: ExperienceLevel,
) -> None:
    service = WorkoutGenerationService(db, settings=None)
    catalog = service._load_catalog()

    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("generate_program must not be called for unsupported bodyweight level")

    monkeypatch.setattr(audit_module, "generate_program", fail_engine)

    spec = _create_test_profile(
        experience_level=exp_level,
        training_location=TrainingLocation.HOME,
        home_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
        training_days=3,
    )

    res = evaluate_single_profile(
        spec,
        catalog=catalog,
        references=(),
        exercise_map={},
        ruleset=RULESET,
        db=db,
    )

    assert res["generation_path"] == "bodyweight_fixed_template"
    assert res["status"] == "FAILED"
    assert res["failure_info"]["root_cause"] == "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED"


def test_fixed_template_safety_or_caution_rejection_does_not_fall_through_to_engine(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_bodyweight_template_catalog(db)
    service = WorkoutGenerationService(db, settings=None)
    catalog = service._load_catalog()

    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("generate_program must NEVER be called when fixed template rejects")

    monkeypatch.setattr(audit_module, "generate_program", fail_engine)

    # Wrist injury causes pushup/plank exercises in the fixed template to be unavailable
    spec = _create_test_profile(
        experience_level=ExperienceLevel.BEGINNER,
        training_location=TrainingLocation.HOME,
        home_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
        training_days=3,
        cautions=[TrainingCaution.WRIST],
    )

    res = evaluate_single_profile(
        spec,
        catalog=catalog,
        references=(),
        exercise_map={},
        ruleset=RULESET,
        db=db,
    )

    assert res["generation_path"] == "bodyweight_fixed_template"
    assert res["status"] == "FAILED"
    assert res["failure_info"]["root_cause"] == "BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE"
