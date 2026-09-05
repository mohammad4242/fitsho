import sys
import httpx

# Just start the FastAPI app locally or use TestClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.database.session import get_engine
from app.training_templates.service import seed_training_program_templates
from app.config import get_settings
from app.admin.dependencies import _get_current_user
from app.auth.models import User
from uuid import uuid4

settings = get_settings()
engine = get_engine(settings.database_url)
app = create_app()

def override_get_current_user():
    user = User(email="admin@fitsho.test", id=uuid4(), hashed_password="x")
    user.is_admin = True
    return user

app.dependency_overrides[_get_current_user] = override_get_current_user

with Session(engine) as db:
    seed_training_program_templates(db)

with TestClient(app) as client:
    res = client.get("/api/v1/admin/training-program-templates?days_per_week=4")
    template = res.json()["items"][0]
    print("TEMPLATE:", template["slug"])
    for day in template["days"]:
        print(f"DAY {day['day_number']} has {len(day['slots'])} slots")

