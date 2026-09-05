from app.config import get_settings
from app.database.session import get_engine
from sqlalchemy.orm import Session
from app.training_templates.service import load_template_references
import os

engine = get_engine(os.environ["TEST_DATABASE_URL"])
with Session(engine) as db:
    reference = next(
        item
        for item in load_template_references(db)
        if item.slug == "t16-6-day-advanced-body-part"
    )
    for day in reference.days:
        for slot in day.slots:
            if slot.intensity_method == "superset":
                print(slot.exercise_slug_hint, slot.superset_group, slot.superset_exercise_slug_hint)
