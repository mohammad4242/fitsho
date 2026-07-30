from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ai.catalog import (
    NoEnabledRouteModelsError,
    get_model_by_id,
    select_route_models,
    synchronize_zen_catalogue,
)
from app.ai.models import AiModel, AiRoutingSettings, BillingClass, RoutingMode, ZenApiKind


def _model(
    model_id: str,
    billing_class: BillingClass,
    *,
    priority: int,
    is_enabled: bool = True,
) -> AiModel:
    return AiModel(
        id=uuid4(),
        model_id=model_id,
        display_name=model_id,
        api_kind=ZenApiKind.CHAT_COMPLETIONS,
        billing_class=billing_class,
        priority=priority,
        is_enabled=is_enabled,
        is_custom=False,
        classification_required=False,
    )


def _reset_models(db: Session, mode: RoutingMode) -> AiRoutingSettings:
    settings = db.get(AiRoutingSettings, 1)
    assert settings is not None
    settings.manual_model_id = None
    settings.mode = mode
    db.flush()
    db.execute(delete(AiModel))
    db.flush()
    return settings


def test_automatic_route_returns_only_enabled_free_models_in_priority_order(db: Session) -> None:
    _reset_models(db, RoutingMode.AUTOMATIC)
    db.add_all(
        [
            _model("nemotron-3-ultra-free", BillingClass.FREE, priority=20),
            _model("big-pickle", BillingClass.FREE, priority=10),
            _model("gpt-5.6-terra", BillingClass.PAID, priority=1),
            _model("disabled-free", BillingClass.FREE, priority=0, is_enabled=False),
        ]
    )
    db.flush()

    assert [model.model_id for model in select_route_models(db)] == [
        "big-pickle",
        "nemotron-3-ultra-free",
    ]


def test_manual_route_rejects_a_disabled_model(db: Session) -> None:
    settings = _reset_models(db, RoutingMode.MANUAL)
    disabled = _model("nemotron-3-ultra-free", BillingClass.FREE, priority=1, is_enabled=False)
    db.add(disabled)
    db.flush()
    settings.manual_model_id = disabled.id
    db.flush()

    with pytest.raises(NoEnabledRouteModelsError):
        select_route_models(db)


def test_unknown_zen_id_is_disabled_until_admin_classifies_it(db: Session) -> None:
    result = synchronize_zen_catalogue(db, {"new-free-model"})

    assert result.needs_classification == ["new-free-model"]
    model = get_model_by_id(db, "new-free-model")
    assert model is not None
    assert model.is_enabled is False
    assert model.classification_required is True
    assert model.api_kind is None
    assert model.billing_class is None
