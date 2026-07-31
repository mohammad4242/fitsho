from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from app.ai.models import ZenApiKind
from app.ai.schemas import (
    ProviderErrorCode,
    WorkoutGenerationModelRequest,
    WorkoutGenerationModelResponse,
    WorkoutPlanModelOutput,
    WorkoutProviderError,
)


class OpenCodeZenWorkoutPlanProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: SecretStr | str | None,
        base_url: str,
        model: str,
        timeout_seconds: float,
        api_kind: ZenApiKind = ZenApiKind.RESPONSES,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_kind = api_kind
        self._timeout = httpx.Timeout(timeout_seconds)

    async def generate_plan(
        self, request: WorkoutGenerationModelRequest
    ) -> WorkoutGenerationModelResponse:
        api_key = self._api_key_value()
        if api_key is None:
            raise WorkoutProviderError(
                ProviderErrorCode.NOT_CONFIGURED,
                "Workout generation is not configured.",
            )
        try:
            response = await self._client.post(
                self._endpoint(),
                headers=self._headers(api_key),
                json=self._request_body(request),
                timeout=self._timeout,
            )
        except httpx.TimeoutException as error:
            raise WorkoutProviderError(
                ProviderErrorCode.TIMEOUT,
                "Workout generation timed out. Please try again.",
            ) from error
        except httpx.RequestError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.CONNECTION_FAILURE,
                "Workout generation is temporarily unavailable. Please try again.",
            ) from error

        self._raise_for_status(response)
        payload = self._parse_response_envelope(response)
        plan = self._parse_plan(payload)
        usage = payload.get("usageMetadata" if self._api_kind is ZenApiKind.GEMINI else "usage")
        usage_data = usage if isinstance(usage, dict) else {}
        provider_request_id = payload.get(
            "responseId" if self._api_kind is ZenApiKind.GEMINI else "id"
        )
        input_key, output_key = self._usage_keys()
        return WorkoutGenerationModelResponse(
            plan=plan,
            provider_request_id=provider_request_id
            if isinstance(provider_request_id, str)
            else None,
            input_tokens=self._optional_int(usage_data.get(input_key)),
            output_tokens=self._optional_int(usage_data.get(output_key)),
        )

    async def check_availability(self) -> None:
        api_key = self._api_key_value()
        if api_key is None:
            raise WorkoutProviderError(
                ProviderErrorCode.NOT_CONFIGURED,
                "Workout generation is not configured.",
            )
        try:
            response = await self._client.post(
                self._endpoint(),
                headers=self._headers(api_key),
                json=self._availability_request_body(),
                timeout=self._timeout,
            )
        except httpx.TimeoutException as error:
            raise WorkoutProviderError(
                ProviderErrorCode.TIMEOUT,
                "Workout generation timed out. Please try again.",
            ) from error
        except httpx.RequestError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.CONNECTION_FAILURE,
                "Workout generation is temporarily unavailable. Please try again.",
            ) from error
        self._raise_for_status(response)
        self._parse_response_envelope(response)

    def _endpoint(self) -> str:
        if self._api_kind is ZenApiKind.RESPONSES:
            return f"{self._base_url}/responses"
        if self._api_kind is ZenApiKind.CHAT_COMPLETIONS:
            return f"{self._base_url}/chat/completions"
        if self._api_kind is ZenApiKind.MESSAGES:
            return f"{self._base_url}/messages"
        return f"{self._base_url}/models/{self._model}:generateContent"

    def _headers(self, api_key: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self._api_kind is ZenApiKind.MESSAGES:
            headers["anthropic-version"] = "2023-06-01"
        if self._api_kind is ZenApiKind.GEMINI:
            headers["x-goog-api-key"] = api_key
        return headers

    def _api_key_value(self) -> str | None:
        if isinstance(self._api_key, SecretStr):
            return self._api_key.get_secret_value()
        if isinstance(self._api_key, str) and self._api_key:
            return self._api_key
        return None

    def _request_body(self, request: WorkoutGenerationModelRequest) -> dict[str, object]:
        if self._api_kind is ZenApiKind.CHAT_COMPLETIONS:
            return {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": self._input_text(request)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "fitsho_workout_plan",
                        "strict": True,
                        "schema": request.response_schema,
                    },
                },
            }
        if self._api_kind is ZenApiKind.MESSAGES:
            return {
                "model": self._model,
                "max_tokens": 8192,
                "system": request.system_prompt,
                "messages": [{"role": "user", "content": self._input_text(request)}],
                "tools": [
                    {
                        "name": "fitsho_workout_plan",
                        "description": "Return the generated Fitsho workout plan.",
                        "input_schema": request.response_schema,
                    }
                ],
                "tool_choice": {"type": "tool", "name": "fitsho_workout_plan"},
            }
        if self._api_kind is ZenApiKind.GEMINI:
            return {
                "systemInstruction": {"parts": [{"text": request.system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": self._input_text(request)}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": request.response_schema,
                },
            }
        return {
            "model": self._model,
            "instructions": request.system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                request.input_payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    ],
                }
            ],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "fitsho_workout_plan",
                    "strict": True,
                    "schema": request.response_schema,
                }
            },
        }

    def _availability_request_body(self) -> dict[str, object]:
        if self._api_kind is ZenApiKind.CHAT_COMPLETIONS:
            return {
                "model": self._model,
                "messages": [{"role": "user", "content": "Reply only: OK"}],
                "max_tokens": 1,
            }
        if self._api_kind is ZenApiKind.MESSAGES:
            return {
                "model": self._model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "Reply only: OK"}],
            }
        if self._api_kind is ZenApiKind.GEMINI:
            return {
                "contents": [
                    {"role": "user", "parts": [{"text": "Reply only: OK"}]}
                ],
                "generationConfig": {"maxOutputTokens": 1},
            }
        return {
            "model": self._model,
            "input": "Reply only: OK",
            "max_output_tokens": 1,
            "store": False,
        }

    @staticmethod
    def _input_text(request: WorkoutGenerationModelRequest) -> str:
        return json.dumps(request.input_payload, ensure_ascii=False, separators=(",", ":"))

    def _usage_keys(self) -> tuple[str, str]:
        if self._api_kind is ZenApiKind.CHAT_COMPLETIONS:
            return "prompt_tokens", "completion_tokens"
        if self._api_kind is ZenApiKind.GEMINI:
            return "promptTokenCount", "candidatesTokenCount"
        return "input_tokens", "output_tokens"

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in {401, 403}:
            raise WorkoutProviderError(
                ProviderErrorCode.UNAUTHORIZED,
                "Workout generation credentials were rejected.",
            )
        if response.status_code == 429:
            raise WorkoutProviderError(
                ProviderErrorCode.RATE_LIMITED,
                "Workout generation is busy. Please try again later.",
            )
        if response.status_code >= 500:
            raise WorkoutProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "Workout generation is temporarily unavailable. Please try again.",
            )
        if response.status_code >= 400:
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation request could not be completed.",
            )

    @staticmethod
    def _parse_response_envelope(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            ) from error
        if not isinstance(payload, dict):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            error_type = str(
                error_payload.get("type") or error_payload.get("code") or ""
            ).casefold()
            if "auth" in error_type or "unauthorized" in error_type:
                code = ProviderErrorCode.UNAUTHORIZED
                message = "Workout generation credentials were rejected."
            elif "invalid_request" in error_type or "bad_request" in error_type:
                code = ProviderErrorCode.MALFORMED_RESPONSE
                message = "Workout generation request could not be completed."
            else:
                code = ProviderErrorCode.PROVIDER_UNAVAILABLE
                message = "Workout generation is temporarily unavailable. Please try again."
            raise WorkoutProviderError(code, message)
        return payload

    def _parse_plan(self, payload: dict[str, Any]) -> WorkoutPlanModelOutput:
        if self._api_kind is ZenApiKind.MESSAGES:
            plan_payload = self._extract_messages_tool_input(payload)
        elif self._api_kind is ZenApiKind.CHAT_COMPLETIONS:
            plan_payload = self._load_plan_json(self._extract_chat_completions_output_text(payload))
        elif self._api_kind is ZenApiKind.GEMINI:
            plan_payload = self._load_plan_json(self._extract_gemini_output_text(payload))
        else:
            plan_payload = self._load_plan_json(self._extract_output_text(payload))
        try:
            return WorkoutPlanModelOutput.model_validate(plan_payload)
        except ValidationError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "Workout generation returned invalid plan data.",
            ) from error

    @staticmethod
    def _load_plan_json(output_text: str) -> object:
        try:
            return json.loads(output_text)
        except json.JSONDecodeError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "Workout generation returned invalid plan data.",
            ) from error

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        direct_output = payload.get("output_text")
        if isinstance(direct_output, str):
            return direct_output
        output = payload.get("output")
        if not isinstance(output, list):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    raise WorkoutProviderError(
                        ProviderErrorCode.REFUSAL,
                        "Workout generation could not produce a plan.",
                    )
                text = part.get("text")
                if part.get("type") == "output_text" and isinstance(text, str):
                    return text
        raise WorkoutProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Workout generation returned an invalid response.",
        )

    @staticmethod
    def _extract_chat_completions_output_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        if message.get("refusal") is not None:
            raise WorkoutProviderError(
                ProviderErrorCode.REFUSAL,
                "Workout generation could not produce a plan.",
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        return content

    @staticmethod
    def _extract_messages_tool_input(payload: dict[str, Any]) -> object:
        if payload.get("stop_reason") == "refusal":
            raise WorkoutProviderError(
                ProviderErrorCode.REFUSAL,
                "Workout generation could not produce a plan.",
            )
        content = payload.get("content")
        if not isinstance(content, list):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_use" and part.get("name") == "fitsho_workout_plan":
                return part.get("input")
        raise WorkoutProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Workout generation returned an invalid response.",
        )

    @staticmethod
    def _extract_gemini_output_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if (
            not isinstance(candidates, list)
            or not candidates
            or not isinstance(candidates[0], dict)
        ):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        content = candidates[0].get("content")
        if not isinstance(content, dict):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        parts = content.get("parts")
        if not isinstance(parts, list):
            raise WorkoutProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Workout generation returned an invalid response.",
            )
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                return text
        raise WorkoutProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Workout generation returned an invalid response.",
        )

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) else None
