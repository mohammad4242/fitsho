from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

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
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/responses"
        self._model = model
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
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
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
        usage = payload.get("usage")
        usage_data = usage if isinstance(usage, dict) else {}
        provider_request_id = payload.get("id")
        return WorkoutGenerationModelResponse(
            plan=plan,
            provider_request_id=provider_request_id
            if isinstance(provider_request_id, str)
            else None,
            input_tokens=self._optional_int(usage_data.get("input_tokens")),
            output_tokens=self._optional_int(usage_data.get("output_tokens")),
        )

    def _api_key_value(self) -> str | None:
        if isinstance(self._api_key, SecretStr):
            return self._api_key.get_secret_value()
        if isinstance(self._api_key, str) and self._api_key:
            return self._api_key
        return None

    def _request_body(self, request: WorkoutGenerationModelRequest) -> dict[str, object]:
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
        return payload

    @staticmethod
    def _parse_plan(payload: dict[str, Any]) -> WorkoutPlanModelOutput:
        output_text = OpenCodeZenWorkoutPlanProvider._extract_output_text(payload)
        try:
            plan_payload = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "Workout generation returned invalid plan data.",
            ) from error
        try:
            return WorkoutPlanModelOutput.model_validate(plan_payload)
        except ValidationError as error:
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
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) else None
