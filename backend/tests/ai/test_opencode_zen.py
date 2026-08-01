import asyncio
import json
from collections.abc import Coroutine
from uuid import uuid4

import httpx
import pytest

from app.ai.models import ZenApiKind
from app.ai.opencode_zen import OpenCodeZenWorkoutPlanProvider
from app.ai.schemas import (
    ProviderErrorCode,
    WorkoutGenerationModelRequest,
    WorkoutGenerationModelResponse,
    WorkoutProviderError,
)
from app.workouts.prompt_builder import WORKOUT_PLAN_OUTPUT_SCHEMA


def _run[ResponseT](awaitable: Coroutine[object, object, ResponseT]) -> ResponseT:
    return asyncio.run(awaitable)


def _request() -> WorkoutGenerationModelRequest:
    return WorkoutGenerationModelRequest(
        system_prompt="Use only exercise_id values present in allowed_exercises.",
        input_payload={"profile": {"fitness_goal": "build_muscle"}},
        response_schema=WORKOUT_PLAN_OUTPUT_SCHEMA,
    )


def _plan() -> dict[str, object]:
    return {
        "days": [
            {
                "day_number": 1,
                "title_en": "Full body",
                "title_fa": "تمام بدن",
                "estimated_duration_minutes": 45,
                "exercises": [
                    {
                        "exercise_id": str(uuid4()),
                        "sets": 3,
                        "reps_min": 8,
                        "reps_max": 12,
                        "rest_seconds": 90,
                        "rir": 2,
                        "estimated_minutes": 8,
                        "notes_en": None,
                        "notes_fa": None,
                    }
                ],
            }
        ]
    }


def _provider(
    handler: httpx.AsyncBaseTransport | httpx.MockTransport,
) -> OpenCodeZenWorkoutPlanProvider:
    client = httpx.AsyncClient(transport=handler)
    return OpenCodeZenWorkoutPlanProvider(
        client,
        api_key="test-secret-key",
        base_url="https://zen.example/v1/",
        model="gpt-5.6-terra",
        timeout_seconds=8,
    )


def _provider_for(
    api_kind: ZenApiKind,
    model: str,
    handler: httpx.AsyncBaseTransport | httpx.MockTransport,
) -> OpenCodeZenWorkoutPlanProvider:
    client = httpx.AsyncClient(transport=handler)
    return OpenCodeZenWorkoutPlanProvider(
        client,
        api_key="test-secret-key",
        base_url="https://zen.example/v1/",
        model=model,
        api_kind=api_kind,
        timeout_seconds=8,
    )


def _success(api_kind: ZenApiKind) -> dict[str, object]:
    if api_kind is ZenApiKind.RESPONSES:
        return {
            "id": "resp_123",
            "usage": {"input_tokens": 12, "output_tokens": 34},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(_plan())}],
                }
            ],
        }
    if api_kind is ZenApiKind.CHAT_COMPLETIONS:
        return {
            "id": "chat_123",
            "usage": {"prompt_tokens": 12, "completion_tokens": 34},
            "choices": [{"message": {"content": json.dumps(_plan())}}],
        }
    if api_kind is ZenApiKind.MESSAGES:
        return {
            "id": "msg_123",
            "usage": {"input_tokens": 12, "output_tokens": 34},
            "content": [{"type": "tool_use", "name": "fitsho_workout_plan", "input": _plan()}],
        }
    return {
        "responseId": "gem_123",
        "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 34},
        "candidates": [{"content": {"parts": [{"text": json.dumps(_plan())}]}}],
    }


@pytest.mark.parametrize(
    ("api_kind", "model", "expected_url"),
    [
        (ZenApiKind.RESPONSES, "gpt-5.6-terra", "https://zen.example/v1/responses"),
        (
            ZenApiKind.CHAT_COMPLETIONS,
            "nemotron-3-ultra-free",
            "https://zen.example/v1/chat/completions",
        ),
        (ZenApiKind.MESSAGES, "claude-sonnet-4-5", "https://zen.example/v1/messages"),
        (
            ZenApiKind.GEMINI,
            "gemini-3.6-flash",
            "https://zen.example/v1/models/gemini-3.6-flash:generateContent",
        ),
    ],
)
def test_zen_provider_uses_api_kind_endpoint_and_preserves_payload(
    api_kind: ZenApiKind,
    model: str,
    expected_url: str,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_success(api_kind))

    response = _run(
        _provider_for(api_kind, model, httpx.MockTransport(handler)).generate_plan(_request())
    )

    assert response.input_tokens == 12
    assert response.output_tokens == 34
    assert seen["url"] == expected_url
    body = seen["body"]
    assert isinstance(body, dict)
    if api_kind is ZenApiKind.RESPONSES:
        text = body["input"][0]["content"][0]["text"]
    elif api_kind is ZenApiKind.CHAT_COMPLETIONS:
        text = body["messages"][1]["content"]
    elif api_kind is ZenApiKind.MESSAGES:
        text = body["messages"][0]["content"]
    else:
        text = body["contents"][0]["parts"][0]["text"]
    assert json.loads(text) == _request().input_payload


def test_zen_provider_uses_responses_api_and_parses_structured_output() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "resp_123",
                "usage": {"input_tokens": 12, "output_tokens": 34},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(_plan())}],
                    }
                ],
            },
        )

    provider = _provider(httpx.MockTransport(handler))
    response = _run(provider.generate_plan(_request()))

    assert isinstance(response, WorkoutGenerationModelResponse)
    assert response.provider_request_id == "resp_123"
    assert response.input_tokens == 12
    assert response.output_tokens == 34
    assert seen["url"] == "https://zen.example/v1/responses"
    assert seen["authorization"] == "Bearer test-secret-key"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    text = body["text"]
    assert isinstance(text, dict)
    output_format = text["format"]
    assert isinstance(output_format, dict)
    assert output_format["type"] == "json_schema"


@pytest.mark.parametrize(
    ("api_kind", "model"),
    [
        (ZenApiKind.RESPONSES, "gpt-5.4-nano"),
        (ZenApiKind.CHAT_COMPLETIONS, "nemotron-3-ultra-free"),
        (ZenApiKind.MESSAGES, "claude-sonnet-4-5"),
        (ZenApiKind.GEMINI, "gemini-3.6-flash"),
    ],
)
def test_zen_provider_availability_check_uses_minimal_request(
    api_kind: ZenApiKind,
    model: str,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "available"})

    provider = _provider_for(api_kind, model, httpx.MockTransport(handler))

    _run(provider.check_availability())

    body = seen["body"]
    assert isinstance(body, dict)
    serialized = json.dumps(body)
    assert "Reply only: OK" in serialized
    assert "fitsho_workout_plan" not in serialized
    assert "response_format" not in body
    assert "tools" not in body
    if api_kind is ZenApiKind.RESPONSES:
        assert body["max_output_tokens"] == 1
        assert body["store"] is False
    elif api_kind is ZenApiKind.GEMINI:
        assert body["generationConfig"] == {"maxOutputTokens": 1}
    else:
        assert body["max_tokens"] == 1


def _structured_test_success(api_kind: ZenApiKind) -> dict[str, object]:
    if api_kind is ZenApiKind.RESPONSES:
        return {
            "id": "resp_contract",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"status":"ok"}'}],
                }
            ],
        }
    if api_kind is ZenApiKind.CHAT_COMPLETIONS:
        return {"id": "chat_contract", "choices": [{"message": {"content": '{"status":"ok"}'}}]}
    if api_kind is ZenApiKind.MESSAGES:
        return {
            "id": "msg_contract",
            "content": [
                {
                    "type": "tool_use",
                    "name": "fitsho_model_test_contract",
                    "input": {"status": "ok"},
                }
            ],
        }
    return {
        "responseId": "gem_contract",
        "candidates": [{"content": {"parts": [{"text": '{"status":"ok"}'}]}}],
    }


@pytest.mark.parametrize(
    ("api_kind", "model"),
    [
        (ZenApiKind.RESPONSES, "gpt-5.4-nano"),
        (ZenApiKind.CHAT_COMPLETIONS, "nemotron-3-ultra-free"),
        (ZenApiKind.MESSAGES, "claude-sonnet-4-5"),
        (ZenApiKind.GEMINI, "gemini-3.6-flash"),
    ],
)
def test_zen_provider_model_test_contract_uses_compact_structured_output(
    api_kind: ZenApiKind,
    model: str,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_structured_test_success(api_kind))

    provider = _provider_for(api_kind, model, httpx.MockTransport(handler))

    _run(provider.check_model_test_contract())

    body = seen["body"]
    assert isinstance(body, dict)
    serialized = json.dumps(body)
    assert "profile" not in serialized
    assert "exercises" not in serialized
    assert "Reply only: OK" not in serialized
    if api_kind is ZenApiKind.RESPONSES:
        assert body["text"]["format"]["type"] == "json_schema"
    elif api_kind is ZenApiKind.CHAT_COMPLETIONS:
        assert body["response_format"]["type"] == "json_schema"
    elif api_kind is ZenApiKind.MESSAGES:
        assert body["tool_choice"] == {"type": "tool", "name": "fitsho_model_test_contract"}
    else:
        assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_zen_provider_model_test_contract_rejects_invalid_structured_output() -> None:
    provider = _provider_for(
        ZenApiKind.CHAT_COMPLETIONS,
        "nemotron-3-ultra-free",
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"status":"no"}'}}]},
            )
        ),
    )

    with pytest.raises(WorkoutProviderError) as error:
        _run(provider.check_model_test_contract())

    assert error.value.code is ProviderErrorCode.INVALID_OUTPUT
    assert "structured JSON" in error.value.safe_message


def test_zen_provider_captures_sanitized_upstream_error_diagnostics() -> None:
    provider = _provider_for(
        ZenApiKind.CHAT_COMPLETIONS,
        "custom-model",
        httpx.MockTransport(
            lambda request: httpx.Response(
                400,
                json={
                    "error": {
                        "type": "invalid_request_error",
                        "message": "Unsupported response_format. Bearer secret-token",
                    }
                },
            )
        ),
    )

    with pytest.raises(WorkoutProviderError) as error:
        _run(provider.check_availability())

    assert error.value.provider_status_code == 400
    assert error.value.provider_error_type == "invalid_request_error"
    assert error.value.provider_error_message == "Unsupported response_format. [REDACTED]"


def test_zen_response_schema_requires_nullable_notes_keys() -> None:
    definitions = WORKOUT_PLAN_OUTPUT_SCHEMA["$defs"]
    assert isinstance(definitions, dict)
    exercise = definitions["WorkoutPlanExerciseOutput"]
    assert isinstance(exercise, dict)
    required = exercise["required"]
    assert isinstance(required, list)

    assert "notes_en" in required
    assert "notes_fa" in required


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, ProviderErrorCode.UNAUTHORIZED),
        (403, ProviderErrorCode.UNAUTHORIZED),
        (429, ProviderErrorCode.RATE_LIMITED),
        (500, ProviderErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
def test_zen_provider_maps_http_errors_safely(
    status_code: int, expected_code: ProviderErrorCode
) -> None:
    provider = _provider(httpx.MockTransport(lambda request: httpx.Response(status_code)))

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is expected_code
    assert "test-secret-key" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("error_payload", "expected_code"),
    [
        (
            {"type": "server_error", "message": "upstream failed"},
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
        ),
        (
            {"type": "authentication_error", "message": "invalid key"},
            ProviderErrorCode.UNAUTHORIZED,
        ),
        (
            {"type": "invalid_request_error", "message": "bad request"},
            ProviderErrorCode.MALFORMED_RESPONSE,
        ),
    ],
)
def test_zen_provider_rejects_http_200_error_envelope(
    error_payload: dict[str, str],
    expected_code: ProviderErrorCode,
) -> None:
    provider = _provider(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"error": error_payload}))
    )

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is expected_code
    assert error_payload["message"] not in str(exc_info.value)


@pytest.mark.parametrize(
    "exception,expected_code",
    [
        (httpx.ReadTimeout("slow"), ProviderErrorCode.TIMEOUT),
        (httpx.ConnectError("offline"), ProviderErrorCode.CONNECTION_FAILURE),
    ],
)
def test_zen_provider_maps_network_failures_safely(
    exception: Exception, expected_code: ProviderErrorCode
) -> None:
    provider = _provider(httpx.MockTransport(lambda request: (_ for _ in ()).throw(exception)))

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is expected_code


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(
            200,
            json={
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "not json"}]}
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps({"days": [{}]})}],
                    }
                ]
            },
        ),
    ],
)
def test_zen_provider_rejects_malformed_or_invalid_output(response: httpx.Response) -> None:
    provider = _provider(httpx.MockTransport(lambda request: response))

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code in {
        ProviderErrorCode.MALFORMED_RESPONSE,
        ProviderErrorCode.INVALID_OUTPUT,
    }


def test_zen_provider_rejects_refusal() -> None:
    provider = _provider(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "output": [
                        {"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}
                    ]
                },
            )
        )
    )

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is ProviderErrorCode.REFUSAL
