from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.ai.models import AiModel, AiRoutingSettings, BillingClass, RoutingMode, ZenApiKind


def test_ai_model_migration_seeds_documented_nemotron_default(db: Session) -> None:
    inspector = inspect(db.connection())

    assert "ai_models" in inspector.get_table_names()
    assert "ai_routing_settings" in inspector.get_table_names()

    model = db.scalar(select(AiModel).where(AiModel.model_id == "nemotron-3-ultra-free"))
    settings = db.get(AiRoutingSettings, 1)

    assert model is not None
    assert model.api_kind is ZenApiKind.CHAT_COMPLETIONS
    assert model.billing_class is BillingClass.FREE
    assert model.is_enabled is True
    assert settings is not None
    assert settings.mode is RoutingMode.MANUAL
    assert settings.manual_model_id == model.id
