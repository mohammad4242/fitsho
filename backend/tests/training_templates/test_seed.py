from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.service import seed_exercises
from app.training_templates.models import TrainingProgramTemplate, TrainingProgramTemplateSlot
from app.training_templates.service import seed_training_program_templates


def test_seed_adds_five_templates_for_every_supported_training_frequency(db: Session) -> None:
    seed_exercises(db)

    result = seed_training_program_templates(db)

    assert result.templates == 25
    templates = list(db.scalars(select(TrainingProgramTemplate)))
    assert {template.days_per_week for template in templates} == {2, 3, 4, 5, 6}
    for days_per_week in range(2, 7):
        assert sum(template.days_per_week == days_per_week for template in templates) >= 5


def test_seed_keeps_unavailable_exercise_as_explicit_placeholder(db: Session) -> None:
    seed_exercises(db)

    seed_training_program_templates(db)

    placeholder = db.scalar(
        select(TrainingProgramTemplateSlot).where(
            TrainingProgramTemplateSlot.exercise_slug_hint == "cable-pullover"
        )
    )
    assert placeholder is not None
    assert placeholder.exercise_id is None
    assert placeholder.placeholder_name_en == "Cable Pullover"
