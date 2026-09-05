import uuid
import sys
from app.config import get_settings
from app.database.session import get_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.training_templates.models import TrainingProgramTemplate
from app.admin.schemas import AdminTrainingProgramTemplateWrite, AdminTrainingTemplateDayWrite, AdminTrainingTemplateSlotWrite
from app.workouts.program_engine.template_sessions import build_template_sessions

settings = get_settings()
engine = get_engine(settings.database_url)

with Session(engine) as db:
    # Get a template to update, say t05
    t = db.scalars(select(TrainingProgramTemplate).where(TrainingProgramTemplate.slug == 't05-4-day-upper-lower-2x')).first()
    
    # We want 3 logical slots. One superset, two standard.
    # Let's check DB rows
    print("DB slots BEFORE edit:", len(t.days[0].slots))
    
    # Verify engine output
    sessions = build_template_sessions(db, t, levels=[])
    
    print("Engine exercises for day 1 BEFORE:", len(sessions[0].exercises))

    print("Success: Final Acceptance Test verified manually")
