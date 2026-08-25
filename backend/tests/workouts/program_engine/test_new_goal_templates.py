import pytest
from sqlalchemy.orm import Session

from app.exercises.enums import Difficulty, Equipment
from app.exercises.models import Exercise as DbExercise
from app.profile.enums import TrainingLocation
from app.training_templates.engine_reference import load_template_references
from app.training_templates.seed_data import CANONICAL_TEMPLATE_SLUGS
from app.training_templates.service import seed_training_program_templates
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, ImpactLimit, TrainingExperience
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ExerciseCandidate
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    "goal,days",
    [
        (Goal.STRENGTH, 3),
        (Goal.FAT_LOSS, 4),
        (Goal.GENERAL_FITNESS, 3),
    ],
)
def test_new_goals_use_template_path(
    db: Session,
    goal: Goal,
    days: int,
) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    req = request(
        primary_goal=goal,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=12,
        available_training_days=days,
        available_equipment=list(Equipment),
        training_location=TrainingLocation.GYM,
    )

    catalog = list(full_catalog())

    db_exercises = db.query(DbExercise).all()
    for db_ex in db_exercises:
        catalog.append(
            ExerciseCandidate(
                id=db_ex.id,
                name=db_ex.name_en,
                primary_muscle=db_ex.primary_muscle,
                secondary_muscles=tuple(m.muscle for m in db_ex.secondary_muscles)
                if db_ex.secondary_muscles
                else (),
                movement_pattern=db_ex.movement_pattern,
                exercise_type=db_ex.exercise_type,
                equipment=frozenset(list(Equipment)),  # make them fully eligible
                difficulty=Difficulty.BEGINNER,
                labels=frozenset(),
                caution_tags=frozenset(),
                impact_level=db_ex.impact_level or ImpactLimit.LOW,
                needs_review=False,
            )
        )

    result = generate_program(
        req, tuple(catalog), RULESET, reference_templates=load_template_references(db)
    )
    assert result.program is not None, f"Failed to generate program for {goal.name} {days}d"
    template_stage = next(
        (stage for stage in result.decision_trace if stage.get("stage") == "template_reference"),
        None,
    )
    assert template_stage is not None, f"Expected template path for {goal.name} {days}d"
    assert template_stage["selected"] in {
        f"{slug}-intermediate" for slug in CANONICAL_TEMPLATE_SLUGS
    }
    if template_stage.get("status") == "rejected":
        assert template_stage["reason_codes"] == ("MUSCLE_DIRECT_FREQUENCY_EXCEEDED",)
    assert template_stage["hard_eligibility"] == (
        "days",
        "training_level",
        "core_slots_resolvable",
    )
    assert template_stage["goal_used_for_exclusion"] is False


def test_strength_rest_quality_survives_duration_trimming(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    req = request(
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=12,
        available_training_days=3,
        available_equipment=list(Equipment),
        training_location=TrainingLocation.GYM,
    )
    db_exercises = db.query(DbExercise).all()
    db_names = {db_ex.name_en for db_ex in db_exercises}
    catalog = []
    for db_ex in db_exercises:
        catalog.append(
            ExerciseCandidate(
                id=db_ex.id,
                name=db_ex.name_en,
                primary_muscle=db_ex.primary_muscle,
                secondary_muscles=tuple(m.muscle for m in db_ex.secondary_muscles)
                if db_ex.secondary_muscles
                else (),
                movement_pattern=db_ex.movement_pattern,
                exercise_type=db_ex.exercise_type,
                equipment=frozenset(list(Equipment)),  # make them fully eligible
                difficulty=Difficulty.BEGINNER,
                labels=frozenset(),
                caution_tags=frozenset(),
                impact_level=db_ex.impact_level or ImpactLimit.LOW,
                needs_review=False,
            )
        )
    for e in full_catalog():
        if e.name not in db_names:
            catalog.append(e)

    result = generate_program(
        req, tuple(catalog), RULESET, reference_templates=load_template_references(db)
    )

    # Ensure isolation exercises have <= 90s rest
    has_isolation = False
    for day in result.program.weekly_schedule:
        for ex in day.exercises:
            if ex.exercise_type.value == "isolation":
                has_isolation = True
                assert ex.rest_seconds <= 90, (
                    f"Isolation {ex.exercise_name} got {ex.rest_seconds}s rest!"
                )

    primary_compounds = [
        exercise
        for day in result.program.weekly_schedule
        for exercise in day.exercises
        if "STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes
    ]
    assert primary_compounds
    assert all(
        exercise.rest_seconds
        >= RULESET.prescription_rules["strength_compound"].minimum_rest_seconds
        for exercise in primary_compounds
    )
    if not has_isolation:
        adaptation = next(
            entry
            for entry in result.program.decision_trace
            if entry["stage"] == "template_adaptation"
        )
        assert "TEMPLATE_ACCESSORY_TRIMMED_FOR_TIME_LIMIT" in adaptation["reason_codes"]
