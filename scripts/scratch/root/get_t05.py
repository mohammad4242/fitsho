from fastapi.testclient import TestClient
from app.main import create_app
from app.auth.dependencies import get_current_user
from app.auth.models import User
from uuid import uuid4

app = create_app()

def override_get_current_user():
    user = User(email='admin@fitsho.test', id=uuid4())
    user.is_admin = True
    return user

app.dependency_overrides[get_current_user] = override_get_current_user

with TestClient(app) as client:
    res = client.get('/api/v1/admin/training-program-templates?days_per_week=4')
    t = res.json()['items'][0]
    print('TEMPLATE:', t['slug'])
    for day in t['days']:
        print('DAY', day['day_number'], 'has', len(day['slots']), 'slots')
