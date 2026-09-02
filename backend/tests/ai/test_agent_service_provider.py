from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
import pytest

from app.body_analysis.providers.agent_service import AgentServiceProvider
from app.body_analysis.providers.models import (
    AIProviderError,
    ImageInput,
    ModelCapabilityFilter,
    ModelRoute,
    ProviderErrorCode,
    StructuredGenerationRequest,
)

T = TypeVar("T")


def _run[T](awaitable: Awaitable[T]) -> T:
    return asyncio.run(awaitable)


def _request() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        system_prompt="Return only the requested body-analysis object.",
        input_payload={"profile": {"goal": "build_muscle"}},
        response_schema={
            "type": "object",
            "properties": {"score": {"type": "number"}},
            "required": ["score"],
            "additionalProperties": False,
        },
        schema_name="body_analysis",
        route=ModelRoute(primary_model="gemini-2.5-pro"),
        temperature=0.0,
        max_output_tokens=512,
    )


def _output(*, model_id: str = "gemini-2.5-pro", request_id: str = "req-agent-1") -> dict[str, Any]:
    return {
        "payload": {"score": 0.82},
        "agent": "antigravity",
        "model_id": model_id,
        "request_id": request_id,
        "input_tokens": 17,
        "output_tokens": 9,
        "duration_seconds": 0.4,
    }


def _stored_image() -> ImageInput:
    return ImageInput(
        label="front",
        mime_type="image/jpeg",
        storage_scope="body",
        storage_key="ab/abcdef0123456789abcdef0123456789.jpg",
    )


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> AgentServiceProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AgentServiceProvider(
        client,
        base_url="http://agent-service:9001/",
        token="agent-service-test-token",
        agent_name="antigravity",
        timeout_seconds=7.0,
    )


def test_generate_structured_text_maps_contract_and_auth_header() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_output())

    response = _run(_provider(handler).generate_structured_text(_request()))

    assert response.payload == {"score": 0.82}
    assert response.model_id == "gemini-2.5-pro"
    assert response.attempted_models == ("gemini-2.5-pro",)
    assert response.provider_request_id == "req-agent-1"
    assert response.input_tokens == 17
    assert response.output_tokens == 9
    assert seen["method"] == "POST"
    assert seen["url"] == "http://agent-service:9001/v1/generate"
    assert seen["authorization"] == "Bearer agent-service-test-token"
    assert seen["body"] == {
        "agent": "antigravity",
        "model_id": "gemini-2.5-pro",
        "system_prompt": _request().system_prompt,
        "input_payload": _request().input_payload,
        "response_schema": _request().response_schema,
        "schema_name": "body_analysis",
        "temperature": 0.0,
        "max_output_tokens": 512,
        "timeout_seconds": 7.0,
    }


def test_analyze_images_decodes_base64_and_sends_only_multipart_bytes() -> None:
    seen: dict[str, Any] = {}
    image_bytes = b"trusted-image-bytes"
    image = ImageInput(
        label="front view",
        mime_type="image/jpeg",
        base64_data=base64.b64encode(image_bytes).decode("ascii"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content
        return httpx.Response(200, json=_output())

    response = _run(
        _provider(handler).analyze_images(_request(), images=(image,))
    )

    assert response.payload == {"score": 0.82}
    body = seen["body"]
    assert image_bytes in body
    assert image.base64_data.encode() not in body
    assert b'filename="front-view.jpg"' in body
    assert b'name="metadata"' in body
    metadata_start = body.index(b'name="metadata"')
    metadata_start = body.index(b"\r\n\r\n", metadata_start) + 4
    metadata_end = body.index(b"\r\n", metadata_start)
    forwarded = json.loads(body[metadata_start:metadata_end])
    assert forwarded["system_prompt"] == _request().system_prompt
    assert forwarded["input_payload"] == _request().input_payload
    assert forwarded["response_schema"] == _request().response_schema
    assert forwarded["schema_name"] == _request().schema_name
    assert forwarded["temperature"] == _request().temperature
    assert forwarded["max_output_tokens"] == _request().max_output_tokens
    assert forwarded["image_labels"] == ["front view"]
    assert seen["headers"]["authorization"] == "Bearer agent-service-test-token"


def test_analyze_stored_images_sends_only_json_storage_references() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content
        return httpx.Response(200, json=_output())

    response = _run(
        _provider(handler).analyze_images(_request(), images=(_stored_image(),))
    )

    assert response.payload == {"score": 0.82}
    assert seen["method"] == "POST"
    assert seen["url"] == "http://agent-service:9001/v1/analyze-stored-images"
    assert seen["headers"]["content-type"] == "application/json"
    body = json.loads(seen["body"])
    assert body == {
        "generation": {
            "agent": "antigravity",
            "model_id": "gemini-2.5-pro",
            "system_prompt": _request().system_prompt,
            "input_payload": _request().input_payload,
            "response_schema": _request().response_schema,
            "schema_name": _request().schema_name,
            "temperature": _request().temperature,
            "max_output_tokens": _request().max_output_tokens,
            "timeout_seconds": 7.0,
        },
        "images": [
            {
                "label": "front",
                "mime_type": "image/jpeg",
                "storage_scope": "body",
                "storage_key": "ab/abcdef0123456789abcdef0123456789.jpg",
            }
        ],
    }
    assert b"base64_data" not in seen["body"]
    assert b"trusted-image-bytes" not in seen["body"]
    assert b"multipart/form-data" not in seen["body"]


def test_analyze_images_rejects_mixed_inline_and_stored_sources() -> None:
    inline = ImageInput(label="side", mime_type="image/jpeg", base64_data="c2lkZQ==")

    with pytest.raises(AIProviderError) as error:
        _run(_provider(lambda _: httpx.Response(500)).analyze_images(
            _request(), images=(inline, _stored_image())
        ))

    assert error.value.code is ProviderErrorCode.INVALID_REQUEST


def test_list_models_maps_capabilities_and_applies_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/capabilities"
        return httpx.Response(
            200,
            json={
                "runners": [
                    {
                        "agent": "antigravity",
                        "installed": True,
                        "version": "1.1.22",
                        "auth_state": "authenticated",
                        "models": [
                            {
                                "model_id": "gemini-2.5-pro",
                                "supports_text_input": True,
                                "supports_image_input": True,
                                "supports_structured_output": True,
                            },
                            {
                                "model_id": "text-only",
                                "supports_text_input": True,
                                "supports_image_input": False,
                                "supports_structured_output": True,
                            },
                        ],
                    }
                ]
            },
        )

    models = _run(
        _provider(handler).list_models(
            ModelCapabilityFilter(image_input=True, structured_output=True)
        )
    )

    assert tuple(model.model_id for model in models) == ("gemini-2.5-pro",)
    assert models[0].supports_image_input is True
    assert models[0].supports_structured_output is True


def test_connection_uses_service_test_contract() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/capabilities":
            return httpx.Response(
                200,
                json={
                    "runners": [
                        {
                            "agent": "antigravity",
                            "installed": True,
                            "version": "1.1.22",
                            "auth_state": "authenticated",
                            "models": [
                                {
                                    "model_id": "gemini-2.5-pro",
                                    "supports_text_input": True,
                                    "supports_image_input": False,
                                    "supports_structured_output": True,
                                }
                            ],
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "agent": "antigravity",
                "model_id": "gemini-2.5-pro",
                "request_id": "test-request",
                "duration_seconds": 0.1,
            },
        )

    result = _run(_provider(handler).test_connection())

    assert result.model_count == 1
    assert paths == ["/v1/capabilities", "/v1/test"]


def test_get_model_capabilities_rejects_unknown_model_with_safe_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"runners": []})

    with pytest.raises(AIProviderError) as caught:
        _run(_provider(handler).get_model_capabilities("missing"))

    assert caught.value.code is ProviderErrorCode.MODEL_NOT_FOUND
    assert "missing" not in caught.value.safe_message


@pytest.mark.parametrize(
    ("status_code", "service_code", "expected"),
    [
        (401, "unauthorized", ProviderErrorCode.UNAUTHORIZED),
        (403, "location_unsupported", ProviderErrorCode.LOCATION_UNSUPPORTED),
        (408, "timeout", ProviderErrorCode.TIMEOUT),
        (429, "rate_limited", ProviderErrorCode.RATE_LIMITED),
        (502, "provider_unavailable", ProviderErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
def test_service_error_codes_map_to_safe_backend_errors(
    status_code: int,
    service_code: str,
    expected: ProviderErrorCode,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "error": {
                    "code": service_code,
                    "message": "internal command output must not reach the member",
                    "request_id": "secret-provider-trace",
                }
            },
        )

    with pytest.raises(AIProviderError) as caught:
        _run(_provider(handler).generate_structured_text(_request()))

    assert caught.value.code is expected
    assert "internal command" not in caught.value.safe_message
    assert "secret-provider-trace" not in caught.value.safe_message


def test_timeout_and_connection_errors_normalize_without_raw_exception_text() -> None:
    provider = _provider(lambda request: httpx.Response(200))

    timeout = provider.normalize_error(httpx.ReadTimeout("socket timed out"))
    connection = provider.normalize_error(httpx.ConnectError("private host details"))

    assert timeout.code is ProviderErrorCode.TIMEOUT
    assert connection.code is ProviderErrorCode.CONNECTION_FAILURE
    assert "socket timed out" not in timeout.safe_message
    assert "private host details" not in connection.safe_message
