import asyncio
import json
from collections.abc import Coroutine
from uuid import uuid4

import httpx
import pytest

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
    *,
    model: str = "gpt-5.6-terra",
) -> OpenCodeZenWorkoutPlanProvider:
    client = httpx.AsyncClient(transport=handler)
    return OpenCodeZenWorkoutPlanProvider(
        client,
        api_key="test-secret-key",
        base_url="https://zen.example/v1/",
        model=model,
        timeout_seconds=8,
    )


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


def test_unknown_model_uses_responses_api() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(_plan())}],
                    }
                ]
            },
        )

    provider = _provider(httpx.MockTransport(handler), model="future-model-2026")
    _run(provider.generate_plan(_request()))

    assert seen["url"] == "https://zen.example/v1/responses"


def test_nemotron_provider_uses_chat_completions_and_parses_choices_output() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_123",
                "usage": {"prompt_tokens": 12, "completion_tokens": 34},
                "choices": [{"message": {"content": json.dumps(_plan())}}],
            },
        )

    provider = _provider(httpx.MockTransport(handler), model="nemotron-3-ultra-free")
    response = _run(provider.generate_plan(_request()))

    assert response.provider_request_id == "chatcmpl_123"
    assert response.input_tokens == 12
    assert response.output_tokens == 34
    assert seen["url"] == "https://zen.example/v1/chat/completions"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body == {
        "model": "nemotron-3-ultra-free",
        "messages": [
            {"role": "system", "content": _request().system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    _request().input_payload, ensure_ascii=False, separators=(",", ":")
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "fitsho_workout_plan",
                "strict": True,
                "schema": WORKOUT_PLAN_OUTPUT_SCHEMA,
            },
        },
    }


@pytest.mark.parametrize(
    "choices",
    [[], [{}], [{"message": {}}], [{"message": {"content": None}}]],
)
def test_nemotron_provider_rejects_malformed_choices(choices: list[object]) -> None:
    provider = _provider(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": choices})),
        model="nemotron-3-ultra-free",
    )

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is ProviderErrorCode.MALFORMED_RESPONSE


def test_nemotron_provider_classifies_chat_completions_refusal() -> None:
    provider = _provider(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": None, "refusal": "no"}}]},
            )
        ),
        model="nemotron-3-ultra-free",
    )

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is ProviderErrorCode.REFUSAL


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
