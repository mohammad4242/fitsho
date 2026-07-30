from uuid import uuid4

import httpx

from app.ai.models import AiModel, BillingClass, ZenApiKind
from app.ai.routing import build_model_candidates


def _model(model_id: str, api_kind: ZenApiKind) -> AiModel:
    return AiModel(
        id=uuid4(),
        model_id=model_id,
        display_name=model_id,
        api_kind=api_kind,
        billing_class=BillingClass.FREE,
        is_enabled=True,
        priority=10,
        is_custom=False,
        classification_required=False,
    )


def test_build_model_candidates_preserves_database_model_api_kind() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    candidates = build_model_candidates(
        (_model("nemotron-3-ultra-free", ZenApiKind.CHAT_COMPLETIONS),),
        client,
        api_key="test-key",
        base_url="https://zen.example/v1",
        timeout_seconds=8,
    )

    assert candidates[0].model_id == "nemotron-3-ultra-free"
    assert candidates[0].provider._endpoint() == "https://zen.example/v1/chat/completions"
