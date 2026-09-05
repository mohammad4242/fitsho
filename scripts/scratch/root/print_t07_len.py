from app.database.session import get_db
from app.training_templates.models import TrainingProgramTemplate
from sqlalchemy import select

db = next(get_db())
t07 = db.scalar(select(TrainingProgramTemplate).where(TrainingProgramTemplate.slug == "t07-4-day-hypertrophy"))
if t07:
    for day in t07.days:
        print("Day:", len(day.slots))
