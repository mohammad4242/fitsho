from app.workouts.program_engine.enums import TrainingExperience
from app.workouts.program_engine.enums import ImpactLimit
from app.exercises.enums import Difficulty
from app.training_templates.engine_reference import load_template_references
import pytest
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.exercises.enums import Equipment
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog, request

from sqlalchemy.orm import Session

from app.training_templates.service import seed_training_program_templates

@pytest.mark.parametrize(
    "goal,days,expected_slug_prefix",
    [
        (Goal.STRENGTH, 3, "three-day-full-body-strength"),
        (Goal.FAT_LOSS, 4, "four-day-upper-lower-fat-loss"),
        (Goal.GENERAL_FITNESS, 3, "three-day-full-body-general-fitness"),
    ],
)
def test_new_goals_use_template_path(
    db: Session,
    goal: Goal,
    days: int,
    expected_slug_prefix: str,
) -> None:
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
    
    # Add placeholders to catalog so explicit slots resolve
    from app.exercises.models import Exercise as DbExercise
    from app.workouts.program_engine.schemas import ExerciseCandidate
    from app.exercises.models import Exercise as DbExercise
    from app.workouts.program_engine.schemas import ExerciseCandidate
    db_exercises = db.query(DbExercise).all()
    for db_ex in db_exercises:

        catalog.append(
            ExerciseCandidate(
                id=db_ex.id,
                name=db_ex.name_en,
                primary_muscle=db_ex.primary_muscle,
                secondary_muscles=tuple(m.muscle for m in db_ex.secondary_muscles) if db_ex.secondary_muscles else (),
                movement_pattern=db_ex.movement_pattern,
                exercise_type=db_ex.exercise_type,
                equipment=frozenset(list(Equipment)), # make them fully eligible
                    difficulty=Difficulty.BEGINNER,
                labels=frozenset(),
                caution_tags=frozenset(),
                impact_level=db_ex.impact_level or ImpactLimit.LOW,
                needs_review=False,
            )
        )
                    
        for c in catalog:
            if "Barbell Bent" in c.name:
                print("IN CATALOG BEFORE GEN:", c.name, c.primary_muscle)
    result = generate_program(req, tuple(catalog), RULESET, reference_templates=load_template_references(db))
    assert result.program is not None, f"Failed to generate program for {goal.name} {days}d"
    template_stage = next(
        (stage for stage in result.decision_trace if stage.get("stage") == "template_reference"),
        None,
    )
    assert template_stage is not None, f"Expected template path for {goal.name} {days}d"
    assert template_stage.get("status") != "rejected", f"Template rejected for {goal.name} {days}d"
    assert template_stage["selected"].startswith(expected_slug_prefix)

def test_strength_isolation_rest_is_short(db: Session) -> None:
    print("REQUEST EQ:", request(available_equipment=list(Equipment)).available_equipment)
    seed_training_program_templates(db)
    req = request(
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=12,
        available_training_days=3,
        available_equipment=list(Equipment),
        training_location=TrainingLocation.GYM,
    )
    from app.exercises.models import Exercise as DbExercise
    from app.workouts.program_engine.schemas import ExerciseCandidate
    db_exercises = db.query(DbExercise).all()
    db_names = {db_ex.name_en for db_ex in db_exercises}
    catalog = []
    for db_ex in db_exercises:
        catalog.append(
            ExerciseCandidate(
                id=db_ex.id,
                name=db_ex.name_en,
                primary_muscle=db_ex.primary_muscle,
                secondary_muscles=tuple(m.muscle for m in db_ex.secondary_muscles) if db_ex.secondary_muscles else (),
                movement_pattern=db_ex.movement_pattern,
                exercise_type=db_ex.exercise_type,
                equipment=frozenset(list(Equipment)), # make them fully eligible
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
    
    result = generate_program(req, tuple(catalog), RULESET, reference_templates=load_template_references(db))
    
    # Ensure isolation exercises have <= 90s rest
    has_isolation = False
    for day in result.program.weekly_schedule:
        for ex in day.exercises:
            if ex.exercise_type.value == "isolation":
                has_isolation = True
                assert ex.rest_seconds <= 90, f"Isolation {ex.exercise_name} got {ex.rest_seconds}s rest!"
    
    assert has_isolation, "Expected at least one isolation exercise to verify rest times"
