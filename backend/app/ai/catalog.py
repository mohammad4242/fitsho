"""Compatibility data used only while replaying historical migrations."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from app.ai.models import ZenApiKind


class BillingClass(StrEnum):
    FREE = "free"


@dataclass(frozen=True)
class DocumentedZenModel:
    model_id: str
    display_name: str
    api_kind: ZenApiKind
    billing_class: BillingClass


DOCUMENTED_ZEN_MODELS = {
    "nemotron-3-ultra-free": DocumentedZenModel(
        model_id="nemotron-3-ultra-free",
        display_name="Nemotron 3 Ultra Free",
        api_kind=ZenApiKind.CHAT_COMPLETIONS,
        billing_class=BillingClass.FREE,
    )
}


def documented_model_uuid(model_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fitsho:zen:{model_id}")
