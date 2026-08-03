from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import SecretStr

from app.body_analysis.providers.models import (
    AIProviderError,
    ImageInput,
    ModelCapabilities,
    ModelCapabilityFilter,
    ProviderConnectionResult,
    ProviderErrorCode,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
    _ProviderCompletion,
)


class OpenRouterProvider:
    """OpenRouter adapter with bounded fallback and structured-output repair."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: SecretStr | str | None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 30.0,
        app_url: str | None = None,
        app_name: str = "Fitsho",
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)
        self._app_url = app_url
        self._app_name = app_name

    async def test_connection(self) -> ProviderConnectionResult:
        await self._request_json("GET", "/auth/key")
        models = await self.list_models()
        return ProviderConnectionResult(
            checked_at=datetime.now(UTC),
            model_count=len(models),
        )

    async def list_models(
        self, filters: ModelCapabilityFilter | None = None
    ) -> tuple[ModelCapabilities, ...]:
        payload = await self._request_json("GET", "/models")
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "The AI provider returned an invalid model catalog.",
            )

        models = tuple(
            model
            for raw_model in raw_models
            if isinstance(raw_model, Mapping)
            if (model := self._normalize_model(raw_model)) is not None
            if filters is None or model.matches(filters)
        )
        return tuple(sorted(models, key=lambda model: (model.display_name.lower(), model.model_id)))

    async def get_model_capabilities(self, model_id: str) -> ModelCapabilities:
        models = await self.list_models()
        match = next((model for model in models if model.model_id == model_id), None)
        if match is None:
            raise AIProviderError(
                ProviderErrorCode.MODEL_NOT_FOUND,
                "The selected AI model is not available.",
            )
        return match

    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse:
        return await self._generate(request, images=())

    async def analyze_images(
        self,
        request: StructuredGenerationRequest,
        *,
        images: tuple[ImageInput, ...],
    ) -> StructuredGenerationResponse:
        if not images:
            raise AIProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "At least one processed image is required for image analysis.",
            )
        return await self._generate(request, images=images)

    def normalize_error(self, error: Exception) -> AIProviderError:
        if isinstance(error, AIProviderError):
            return error
        if isinstance(error, httpx.TimeoutException):
            return AIProviderError(
                ProviderErrorCode.TIMEOUT,
                "The AI provider request timed out.",
            )
        if isinstance(error, httpx.RequestError):
            return AIProviderError(
                ProviderErrorCode.CONNECTION_FAILURE,
                "The AI provider is temporarily unreachable.",
            )
        return AIProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "The AI provider is temporarily unavailable.",
        )

    async def _generate(
        self,
        request: StructuredGenerationRequest,
        *,
        images: tuple[ImageInput, ...],
    ) -> StructuredGenerationResponse:
        self._validate_schema(request.response_schema)
        attempted_models: list[str] = []
        repair_available = True
        last_error: AIProviderError | None = None
        model_ids = dict.fromkeys(
            (request.route.primary_model, *request.route.fallback_models)
        )

        for model_id in model_ids:
            attempted_models.append(model_id)
            try:
                completion = await self._request_completion(
                    request,
                    model_id=model_id,
                    images=images,
                    repair=False,
                )
                self._validate_output(completion.payload, request.response_schema)
            except AIProviderError as error:
                last_error = error
                if error.code is ProviderErrorCode.UNAUTHORIZED:
                    raise error
                if error.code is not ProviderErrorCode.INVALID_OUTPUT or not repair_available:
                    continue
                repair_available = False
                try:
                    completion = await self._request_completion(
                        request,
                        model_id=model_id,
                        images=images,
                        repair=True,
                    )
                    self._validate_output(completion.payload, request.response_schema)
                except AIProviderError as repair_error:
                    last_error = repair_error
                    continue

            return StructuredGenerationResponse(
                payload=completion.payload,
                model_id=model_id,
                attempted_models=tuple(attempted_models),
                provider_request_id=completion.provider_request_id,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                cost=completion.cost,
            )

        if last_error is not None:
            raise last_error
        raise AIProviderError(
            ProviderErrorCode.MODEL_NOT_FOUND,
            "No AI model was configured for this request.",
        )

    async def _request_completion(
        self,
        request: StructuredGenerationRequest,
        *,
        model_id: str,
        images: tuple[ImageInput, ...],
        repair: bool,
    ) -> _ProviderCompletion:
        payload = await self._request_json(
            "POST",
            "/chat/completions",
            json_body=self._completion_body(
                request,
                model_id=model_id,
                images=images,
                repair=repair,
            ),
        )
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise self._invalid_output_error()
        message = choices[0].get("message")
        if not isinstance(message, Mapping):
            raise self._invalid_output_error()
        if message.get("refusal"):
            raise AIProviderError(
                ProviderErrorCode.REFUSAL,
                "The AI provider refused this analysis request.",
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise self._invalid_output_error()
        try:
            structured = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise self._invalid_output_error() from error
        if not isinstance(structured, dict):
            raise self._invalid_output_error()

        usage = payload.get("usage")
        usage_data = usage if isinstance(usage, Mapping) else {}
        provider_request_id = payload.get("id")
        return _ProviderCompletion(
            payload=structured,
            provider_request_id=(
                provider_request_id if isinstance(provider_request_id, str) else None
            ),
            input_tokens=self._optional_int(usage_data.get("prompt_tokens")),
            output_tokens=self._optional_int(usage_data.get("completion_tokens")),
            cost=self._optional_decimal(usage_data.get("cost")),
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        api_key = self._api_key_value()
        if api_key is None:
            raise AIProviderError(
                ProviderErrorCode.NOT_CONFIGURED,
                "The AI provider is not configured.",
            )
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(api_key),
                json=json_body,
                timeout=self._timeout,
            )
        except Exception as error:
            raise self.normalize_error(error) from error

        if response.status_code >= 400:
            raise self._http_error(response)
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "The AI provider returned a malformed response.",
                provider_status_code=response.status_code,
                provider_request_id=self._request_id(response),
            ) from error
        if not isinstance(payload, dict):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "The AI provider returned a malformed response.",
                provider_status_code=response.status_code,
                provider_request_id=self._request_id(response),
            )
        return payload

    def _completion_body(
        self,
        request: StructuredGenerationRequest,
        *,
        model_id: str,
        images: tuple[ImageInput, ...],
        repair: bool,
    ) -> dict[str, object]:
        if repair:
            repair_text = (
                "The previous response failed schema validation. Return a corrected JSON object "
                "that strictly matches the supplied response schema.\n"
                + json.dumps(request.input_payload, ensure_ascii=False, separators=(",", ":"))
            )
            user_content: str | list[dict[str, object]] = (
                self._image_content(repair_text, images) if images else repair_text
            )
        elif images:
            input_text = json.dumps(
                request.input_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            user_content = self._image_content(input_text, images)
        else:
            user_content = json.dumps(
                request.input_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )

        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.response_schema,
                },
            },
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }

    @staticmethod
    def _image_content(
        initial_text: str,
        images: tuple[ImageInput, ...],
    ) -> list[dict[str, object]]:
        content: list[dict[str, object]] = [{"type": "text", "text": initial_text}]
        for image in images:
            content.extend(
                [
                    {
                        "type": "text",
                        "text": f"Processed anonymized {image.label} view:",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image.mime_type};base64,{image.base64_data}"
                        },
                    },
                ]
            )
        return content

    def _headers(self, api_key: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self._app_url:
            headers["HTTP-Referer"] = self._app_url
        if self._app_name:
            headers["X-Title"] = self._app_name
        return headers

    def _api_key_value(self) -> str | None:
        if isinstance(self._api_key, SecretStr):
            return self._api_key.get_secret_value() or None
        return self._api_key or None

    @classmethod
    def _normalize_model(cls, raw: Mapping[str, Any]) -> ModelCapabilities | None:
        model_id = raw.get("id")
        if not isinstance(model_id, str) or not model_id:
            return None
        display_name = raw.get("name")
        architecture = raw.get("architecture")
        architecture_data = architecture if isinstance(architecture, Mapping) else {}
        input_modalities = cls._string_set(architecture_data.get("input_modalities"))
        supported_parameters = cls._string_set(raw.get("supported_parameters"))
        pricing = raw.get("pricing")
        pricing_data = pricing if isinstance(pricing, Mapping) else {}
        status = raw.get("status")
        return ModelCapabilities(
            provider="openrouter",
            model_id=model_id,
            display_name=display_name if isinstance(display_name, str) else model_id,
            provider_family=model_id.split("/", 1)[0],
            supports_text_input="text" in input_modalities,
            supports_image_input="image" in input_modalities,
            supports_structured_output=bool(
                {"response_format", "structured_outputs"} & supported_parameters
            ),
            context_length=cls._optional_int(raw.get("context_length")),
            input_price_per_token=cls._optional_decimal(pricing_data.get("prompt")),
            output_price_per_token=cls._optional_decimal(pricing_data.get("completion")),
            available=not (isinstance(status, str) and status.lower() == "unavailable"),
        )

    @staticmethod
    def _string_set(value: object) -> set[str]:
        if not isinstance(value, list):
            return set()
        return {item for item in value if isinstance(item, str)}

    @staticmethod
    def _validate_schema(schema: dict[str, Any]) -> None:
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise AIProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "The requested structured-output schema is invalid.",
            ) from error

    @classmethod
    def _validate_output(cls, payload: dict[str, Any], schema: dict[str, Any]) -> None:
        try:
            Draft202012Validator(schema).validate(payload)
        except ValidationError as error:
            raise cls._invalid_output_error() from error

    @staticmethod
    def _invalid_output_error() -> AIProviderError:
        return AIProviderError(
            ProviderErrorCode.INVALID_OUTPUT,
            "The AI provider returned invalid structured output.",
        )

    @staticmethod
    def _http_error(response: httpx.Response) -> AIProviderError:
        status_code = response.status_code
        if status_code in {401, 403}:
            code = ProviderErrorCode.UNAUTHORIZED
            message = "The AI provider credential was rejected."
        elif status_code == 404:
            code = ProviderErrorCode.MODEL_NOT_FOUND
            message = "The selected AI model is not available."
        elif status_code in {408, 504}:
            code = ProviderErrorCode.TIMEOUT
            message = "The AI provider request timed out."
        elif status_code == 429:
            code = ProviderErrorCode.RATE_LIMITED
            message = "The AI provider rate limit was reached."
        elif status_code >= 500:
            code = ProviderErrorCode.PROVIDER_UNAVAILABLE
            message = "The AI provider is temporarily unavailable."
        else:
            code = ProviderErrorCode.INVALID_REQUEST
            message = "The AI provider rejected the request."
        return AIProviderError(
            code,
            message,
            provider_status_code=status_code,
            provider_request_id=OpenRouterProvider._request_id(response),
        )

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        request_id: str | None = response.headers.get("x-request-id")
        if request_id is not None:
            return request_id
        fallback_request_id: str | None = response.headers.get("openrouter-request-id")
        return fallback_request_id

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_decimal(value: object) -> Decimal | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
