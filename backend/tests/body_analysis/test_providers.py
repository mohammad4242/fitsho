from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Any, cast

import httpx
import pytest

from app.body_analysis.providers import (
    AIProviderError,
    ImageInput,
    ModelCapabilityFilter,
    ModelRoute,
    OpenRouterProvider,
    ProviderErrorCode,
    StructuredGenerationRequest,
)


def _run[ResultT](awaitable: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(awaitable)


def _provider(handler: httpx.MockTransport) -> OpenRouterProvider:
    return OpenRouterProvider(
        httpx.AsyncClient(transport=handler),
        api_key="test-openrouter-secret",
        timeout_seconds=5,
    )


def _request(*, fallback_models: tuple[str, ...] = ()) -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        system_prompt="Return a non-medical visible-body analysis.",
        input_payload={"session_id": "session-1"},
        response_schema={
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["ok"]}},
            "required": ["status"],
            "additionalProperties": False,
        },
        schema_name="fitsho_body_analysis",
        route=ModelRoute(primary_model="vision-primary", fallback_models=fallback_models),
        temperature=0.1,
        max_output_tokens=1200,
    )


def _completion(content: str, *, model: str = "vision-primary") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "generation-1",
            "model": model,
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "cost": 0.0012},
        },
    )


def test_openrouter_catalog_normalizes_and_filters_model_capabilities() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "acme/vision-json",
                        "name": "Vision JSON",
                        "context_length": 131072,
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                        "supported_parameters": ["response_format", "max_tokens"],
                        "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                    },
                    {
                        "id": "acme/text-only",
                        "name": "Text only",
                        "context_length": 8192,
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["text"],
                        },
                        "supported_parameters": ["temperature"],
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                ]
            },
        )

    provider = _provider(httpx.MockTransport(handler))
    models = _run(
        provider.list_models(
            ModelCapabilityFilter(image_input=True, structured_output=True)
        )
    )

    assert seen == {
        "url": "https://openrouter.ai/api/v1/models",
        "authorization": "Bearer test-openrouter-secret",
    }
    assert [model.model_id for model in models] == ["acme/vision-json"]
    assert models[0].provider_family == "acme"
    assert models[0].supports_text_input is True
    assert models[0].supports_image_input is True
    assert models[0].supports_structured_output is True
    assert models[0].context_length == 131072
    assert str(models[0].input_price_per_token) == "0.000001"
    assert str(models[0].output_price_per_token) == "0.000002"


def test_openrouter_get_model_capabilities_rejects_unknown_model() -> None:
    provider = _provider(
        httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []}))
    )

    with pytest.raises(AIProviderError) as error:
        _run(provider.get_model_capabilities("missing/model"))

    assert error.value.code is ProviderErrorCode.MODEL_NOT_FOUND
    assert "not available" in error.value.safe_message


def test_openrouter_connection_test_validates_key_before_loading_catalog() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.headers["authorization"] == "Bearer test-openrouter-secret"
        if request.url.path.endswith("/auth/key"):
            return httpx.Response(200, json={"data": {"label": "fitsho"}})
        return httpx.Response(200, json={"data": []})

    result = _run(_provider(httpx.MockTransport(handler)).test_connection())

    assert result.ok is True
    assert result.model_count == 0
    assert paths == ["/api/v1/auth/key", "/api/v1/models"]


def test_openrouter_image_request_sends_three_processed_images_with_json_schema() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["authorization"] = request.headers["authorization"]
        return _completion('{"status":"ok"}')

    provider = _provider(httpx.MockTransport(handler))
    response = _run(
        provider.analyze_images(
            _request(),
            images=(
                ImageInput(label="front", mime_type="image/jpeg", base64_data="ZnJvbnQ="),
                ImageInput(label="side", mime_type="image/png", base64_data="c2lkZQ=="),
                ImageInput(label="back", mime_type="image/webp", base64_data="YmFjaw=="),
            ),
        )
    )

    assert response.payload == {"status": "ok"}
    assert response.model_id == "vision-primary"
    assert response.provider_request_id == "generation-1"
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert str(response.cost) == "0.0012"
    assert seen["authorization"] == "Bearer test-openrouter-secret"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "vision-primary"
    assert body["temperature"] == 0.1
    assert body["max_tokens"] == 1200
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "fitsho_body_analysis",
            "strict": True,
            "schema": _request().response_schema,
        },
    }
    user_content = body["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert json.loads(user_content[0]["text"]) == {"session_id": "session-1"}
    assert [item["text"] for item in user_content[1::2]] == [
        "Processed anonymized front view:",
        "Processed anonymized side view:",
        "Processed anonymized back view:",
    ]
    assert [item["image_url"]["url"] for item in user_content[2::2]] == [
        "data:image/jpeg;base64,ZnJvbnQ=",
        "data:image/png;base64,c2lkZQ==",
        "data:image/webp;base64,YmFjaw==",
    ]
    assert "test-openrouter-secret" not in json.dumps(body)


def test_openrouter_uses_configured_fallback_after_retryable_primary_failure() -> None:
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        attempts.append(body["model"])
        if body["model"] == "vision-primary":
            return httpx.Response(503, json={"error": {"message": "temporarily unavailable"}})
        return _completion('{"status":"ok"}', model="vision-fallback")

    provider = _provider(httpx.MockTransport(handler))
    response = _run(
        provider.generate_structured_text(
            _request(fallback_models=("vision-fallback",))
        )
    )

    assert attempts == ["vision-primary", "vision-fallback"]
    assert response.model_id == "vision-fallback"
    assert response.attempted_models == ("vision-primary", "vision-fallback")


def test_openrouter_repairs_invalid_structured_output_only_once() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return _completion('{"wrong":true}')
        return _completion('{"status":"ok"}')

    provider = _provider(httpx.MockTransport(handler))
    response = _run(provider.generate_structured_text(_request()))

    assert response.payload == {"status": "ok"}
    assert len(bodies) == 2
    messages = cast(list[dict[str, object]], bodies[1]["messages"])
    repaired_content = messages[1]["content"]
    assert isinstance(repaired_content, str)
    assert "failed schema validation" in repaired_content


def test_openrouter_image_repair_retains_anonymized_images() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return _completion('{"wrong":true}')
        return _completion('{"status":"ok"}')

    provider = _provider(httpx.MockTransport(handler))
    _run(
        provider.analyze_images(
            _request(),
            images=(
                ImageInput(label="front", mime_type="image/jpeg", base64_data="ZnJvbnQ="),
            ),
        )
    )

    messages = cast(list[dict[str, object]], bodies[1]["messages"])
    repair_content = cast(list[dict[str, object]], messages[1]["content"])
    assert "failed schema validation" in cast(str, repair_content[0]["text"])
    assert repair_content[2]["image_url"] == {
        "url": "data:image/jpeg;base64,ZnJvbnQ="
    }


def test_openrouter_rejects_malformed_output_after_single_controlled_repair() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _completion("not-json")

    provider = _provider(httpx.MockTransport(handler))

    with pytest.raises(AIProviderError) as error:
        _run(provider.generate_structured_text(_request()))

    assert calls == 2
    assert error.value.code is ProviderErrorCode.INVALID_OUTPUT
    assert error.value.safe_message == "The AI provider returned invalid structured output."


@pytest.mark.parametrize(
    ("provider_failure", "expected_code"),
    [
        (httpx.ReadTimeout("secret upstream details"), ProviderErrorCode.TIMEOUT),
        (httpx.ConnectError("secret upstream details"), ProviderErrorCode.CONNECTION_FAILURE),
    ],
)
def test_openrouter_normalizes_transport_errors_without_leaking_details(
    provider_failure: Exception,
    expected_code: ProviderErrorCode,
) -> None:
    provider = _provider(httpx.MockTransport(lambda _: httpx.Response(200)))

    error = provider.normalize_error(provider_failure)

    assert error.code is expected_code
    assert "secret upstream details" not in error.safe_message


def test_openrouter_normalizes_http_error_and_preserves_safe_request_id() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"x-request-id": "or-request-123"},
            json={"error": {"message": "do not expose this provider payload"}},
        )

    provider = _provider(httpx.MockTransport(handler))

    with pytest.raises(AIProviderError) as error:
        _run(provider.test_connection())

    assert error.value.code is ProviderErrorCode.RATE_LIMITED
    assert error.value.provider_status_code == 429
    assert error.value.provider_request_id == "or-request-123"
    assert "provider payload" not in error.value.safe_message
