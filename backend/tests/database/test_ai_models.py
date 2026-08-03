from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.body_analysis.admin_config.models import AIProviderCredential, AITaskConfig


def test_ai_task_configuration_tables_are_present(db: Session) -> None:
    inspector = inspect(db.connection())

    assert AIProviderCredential.__tablename__ in inspector.get_table_names()
    assert AITaskConfig.__tablename__ in inspector.get_table_names()

    assert AIProviderCredential.__table__.c.encrypted_api_key.nullable is False
    assert AITaskConfig.__table__.c.primary_model_id.nullable is True
