from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AiModel, AiRoutingSettings, BillingClass, RoutingMode, ZenApiKind


class NoEnabledRouteModelsError(Exception):
    pass


@dataclass(frozen=True)
class DocumentedZenModel:
    model_id: str
    display_name: str
    api_kind: ZenApiKind
    billing_class: BillingClass


@dataclass(frozen=True)
class CatalogSyncResult:
    synchronized_model_ids: list[str]
    needs_classification: list[str]


_RESPONSES_MODEL_IDS = (
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.5-pro",
    "gpt-5.4", "gpt-5.4-pro", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.3-codex",
    "gpt-5.3-codex-spark", "gpt-5.2", "gpt-5.2-codex", "gpt-5.1",
    "gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5",
    "gpt-5-codex", "gpt-5-nano",
)
_MESSAGES_MODEL_IDS = (
    "claude-fable-5", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
    "claude-opus-4-6", "claude-opus-4-5", "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-sonnet-4-5", "claude-haiku-4-5", "qwen3.7-max", "qwen3.7-plus",
    "qwen3.6-plus", "qwen3.5-plus",
)
_GEMINI_MODEL_IDS = (
    "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
    "gemini-3.1-pro", "gemini-3-flash",
)
_CHAT_COMPLETIONS_MODEL_IDS = (
    "grok-4.5", "grok-build-0.1", "deepseek-v4-pro", "deepseek-v4-flash", "minimax-m3",
    "minimax-m2.7", "minimax-m2.5", "glm-5.2", "glm-5.1", "glm-5", "kimi-k2.5",
    "kimi-k2.6", "kimi-k2.7-code", "kimi-k3", "big-pickle", "mimo-v2.5-free",
    "laguna-s-2.1-free", "ling-3.0-flash-free", "north-mini-code-free",
    "nemotron-3-ultra-free", "deepseek-v4-flash-free",
)
_FREE_MODEL_IDS = frozenset(
    {
        "big-pickle", "deepseek-v4-flash-free", "mimo-v2.5-free", "laguna-s-2.1-free",
        "ling-3.0-flash-free", "north-mini-code-free", "nemotron-3-ultra-free",
    }
)


def _display_name(model_id: str) -> str:
    return model_id.replace("-", " ").title().replace("Gpt", "GPT").replace("Glm", "GLM")


def _entry(model_id: str, api_kind: ZenApiKind) -> DocumentedZenModel:
    return DocumentedZenModel(
        model_id=model_id,
        display_name=_display_name(model_id),
        api_kind=api_kind,
        billing_class=BillingClass.FREE if model_id in _FREE_MODEL_IDS else BillingClass.PAID,
    )


DOCUMENTED_ZEN_MODELS = {
    entry.model_id: entry
    for api_kind, model_ids in (
        (ZenApiKind.RESPONSES, _RESPONSES_MODEL_IDS),
        (ZenApiKind.MESSAGES, _MESSAGES_MODEL_IDS),
        (ZenApiKind.GEMINI, _GEMINI_MODEL_IDS),
        (ZenApiKind.CHAT_COMPLETIONS, _CHAT_COMPLETIONS_MODEL_IDS),
    )
    for entry in (_entry(model_id, api_kind) for model_id in model_ids)
}


def documented_model_uuid(model_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fitsho:zen:{model_id}")


def get_model_by_id(db: Session, model_id: str) -> AiModel | None:
    return db.scalar(select(AiModel).where(AiModel.model_id == model_id))


def select_route_models(db: Session) -> tuple[AiModel, ...]:
    settings = db.get(AiRoutingSettings, 1)
    if settings is None:
        raise NoEnabledRouteModelsError
    if settings.mode is RoutingMode.MANUAL:
        if settings.manual_model_id is None:
            raise NoEnabledRouteModelsError
        model = db.scalar(
            select(AiModel).where(
                AiModel.id == settings.manual_model_id,
                AiModel.is_enabled.is_(True),
                AiModel.classification_required.is_(False),
            )
        )
        if model is None:
            raise NoEnabledRouteModelsError
        return (model,)
    models = tuple(
        db.scalars(
            select(AiModel)
            .where(
                AiModel.is_enabled.is_(True),
                AiModel.classification_required.is_(False),
                AiModel.billing_class == BillingClass.FREE,
            )
            .order_by(AiModel.priority, AiModel.model_id)
        )
    )
    if not models:
        raise NoEnabledRouteModelsError
    return models


def synchronize_zen_catalogue(db: Session, model_ids: set[str]) -> CatalogSyncResult:
    now = datetime.now(UTC)
    existing = {model.model_id: model for model in db.scalars(select(AiModel))}
    synchronized: list[str] = []
    needs_classification: list[str] = []
    for model_id in sorted(model_ids):
        entry = DOCUMENTED_ZEN_MODELS.get(model_id)
        model = existing.get(model_id)
        if model is not None and model.is_custom:
            continue
        if entry is None:
            if model is None:
                model = AiModel(
                    model_id=model_id,
                    display_name=_display_name(model_id),
                    api_kind=None,
                    billing_class=None,
                    is_enabled=False,
                    priority=1000,
                    is_custom=False,
                    classification_required=True,
                )
                db.add(model)
            model.last_synced_at = now
            needs_classification.append(model_id)
            continue
        if model is None:
            model = AiModel(
                id=documented_model_uuid(model_id),
                model_id=entry.model_id,
                display_name=entry.display_name,
                api_kind=entry.api_kind,
                billing_class=entry.billing_class,
                is_enabled=True,
                priority=10 if model_id == "nemotron-3-ultra-free" else 1000,
                is_custom=False,
                classification_required=False,
            )
            db.add(model)
        else:
            model.display_name = entry.display_name
            model.api_kind = entry.api_kind
            model.billing_class = entry.billing_class
            model.is_enabled = True
            model.classification_required = False
        model.last_synced_at = now
        synchronized.append(model_id)

    for model in existing.values():
        if not model.is_custom and model.model_id not in model_ids:
            model.is_enabled = False
            model.last_synced_at = now
    db.flush()
    return CatalogSyncResult(
        synchronized_model_ids=synchronized,
        needs_classification=needs_classification,
    )
