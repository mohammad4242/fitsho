from sqlalchemy.orm import Session
from sqlalchemy import select
from app.config import get_settings
from app.database.session import get_engine
from app.training_templates.models import TrainingProgramTemplate

settings = get_settings()
engine = get_engine(settings.database_url)
with Session(engine) as db:
    t = db.scalars(select(TrainingProgramTemplate).where(TrainingProgramTemplate.slug == 't07-4-day-3-lower-1-upper')).first()
    for slot in t.days[0].slots:
        print(slot.slot_order, slot.exercise_slug_hint, slot.intensity_method)
