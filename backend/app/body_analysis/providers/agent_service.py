from __future__ import annotations

import base64
import binascii
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
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

_SAFE_MESSAGES: dict[ProviderErrorCode, str] = {
    ProviderErrorCode.NOT_CONFIGURED: "The Agent Service is not configured.",
    ProviderErrorCode.TIMEOUT: "The Agent Service request timed out.",
    ProviderErrorCode.CONNECTION_FAILURE: "The Agent Service is temporarily unreachable.",
    ProviderErrorCode.UNAUTHORIZED: "The Agent Service credential was rejected.",
    ProviderErrorCode.RATE_LIMITED: "The Agent Service is busy. Please try again.",
    ProviderErrorCode.PROVIDER_UNAVAILABLE: "The Agent Service is temporarily unavailable.",
    ProviderErrorCode.LOCATION_UNSUPPORTED: (
        "The provider does not support the current network location."
    ),
    ProviderErrorCode.INVALID_REQUEST: "The Agent Service rejected the request.",
    ProviderErrorCode.MALFORMED_RESPONSE: "The Agent Service returned a malformed response.",
    ProviderErrorCode.INVALID_OUTPUT: "The Agent Service returned invalid structured output.",
    ProviderErrorCode.REFUSAL: "The Agent Service refused this request.",
    ProviderErrorCode.MODEL_NOT_FOUND: "The selected AI model is not available.",
}

_SERVICE_CODE_MAP: dict[str, ProviderErrorCode] = {
    "timeout": ProviderErrorCode.TIMEOUT,
    "unauthorized": ProviderErrorCode.UNAUTHORIZED,
    "rate_limited": ProviderErrorCode.RATE_LIMITED,
    "invalid_request": ProviderErrorCode.INVALID_REQUEST,
    "invalid_output": ProviderErrorCode.INVALID_OUTPUT,
    "model_not_found": ProviderErrorCode.MODEL_NOT_FOUND,
    "provider_unavailable": ProviderErrorCode.PROVIDER_UNAVAILABLE,
    "location_unsupported": ProviderErrorCode.LOCATION_UNSUPPORTED,
}

_IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class AgentServiceProvider:
    """HTTP adapter for the internal Agent Service.

    The adapter deliberately knows only the stable HTTP contract. CLI names,
    command arguments, and subprocess behavior remain inside Agent Service.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        token: SecretStr | str | None,
        agent_name: str,
        profile_id: str | None = None,
        timeout_seconds: float = 30.0,
        max_image_bytes: int = 8 * 1024 * 1024,
        max_images: int = 5,
        max_total_image_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_image_bytes <= 0 or max_images <= 0 or max_total_image_bytes <= 0:
            raise ValueError("image limits must be positive")
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._agent_name = self._enum_value(agent_name)
        self._profile_id = (
            profile_id.strip() if isinstance(profile_id, str) and profile_id.strip() else None
        )
        self._timeout = httpx.Timeout(timeout_seconds)
        self._timeout_seconds = float(timeout_seconds)
        self._max_image_bytes = max_image_bytes
        self._max_images = max_images
        self._max_total_image_bytes = max_total_image_bytes

    async def test_connection(self) -> ProviderConnectionResult:
        models = await self.list_models()
        model = next(
            (
                item
                for item in models
                if item.supports_text_input and item.supports_structured_output
            ),
            None,
        )
        if model is None:
            raise AIProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "The Agent Service has no usable model configured.",
            )
        payload = await self._request_json(
            "POST",
            "/v1/test",
            json_body={"agent": self._agent_name, "model_id": model.model_id},
        )
        self._validate_test_output(payload, expected_model_id=model.model_id)
        return ProviderConnectionResult(
            checked_at=datetime.now(UTC),
            model_count=len(models),
        )

    async def list_models(
        self, filters: ModelCapabilityFilter | None = None
    ) -> tuple[ModelCapabilities, ...]:
        payload = await self._request_json("GET", "/v1/capabilities")
        runners = payload.get("runners")
        if not isinstance(runners, list):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            )
        runner = next(
            (
                item
                for item in runners
                if isinstance(item, Mapping) and item.get("agent") == self._agent_name
            ),
            None,
        )
        if runner is None:
            return ()
        installed = runner.get("installed") is True
        raw_models = runner.get("models")
        if not isinstance(raw_models, list):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            )
        models: list[ModelCapabilities] = []
        for raw_model in raw_models:
            if not isinstance(raw_model, Mapping):
                continue
            model_id = raw_model.get("model_id")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            model = ModelCapabilities(
                provider=f"agent_service:{self._agent_name}",
                model_id=model_id,
                display_name=model_id,
                provider_family=self._agent_name,
                supports_text_input=raw_model.get("supports_text_input") is True,
                supports_image_input=raw_model.get("supports_image_input") is True,
                supports_structured_output=raw_model.get("supports_structured_output") is True,
                context_length=None,
                input_price_per_token=None,
                output_price_per_token=None,
                available=installed,
            )
            if filters is None or model.matches(filters):
                models.append(model)
        return tuple(sorted(models, key=lambda item: item.model_id))

    async def get_model_capabilities(self, model_id: str) -> ModelCapabilities:
        models = await self.list_models()
        match = next((model for model in models if model.model_id == model_id), None)
        if match is None:
            raise AIProviderError(
                ProviderErrorCode.MODEL_NOT_FOUND,
                _SAFE_MESSAGES[ProviderErrorCode.MODEL_NOT_FOUND],
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
                _SAFE_MESSAGES[ProviderErrorCode.TIMEOUT],
            )
        if isinstance(error, httpx.RequestError):
            return AIProviderError(
                ProviderErrorCode.CONNECTION_FAILURE,
                _SAFE_MESSAGES[ProviderErrorCode.CONNECTION_FAILURE],
            )
        return AIProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            _SAFE_MESSAGES[ProviderErrorCode.PROVIDER_UNAVAILABLE],
        )

    async def _generate(
        self,
        request: StructuredGenerationRequest,
        *,
        images: tuple[ImageInput, ...],
    ) -> StructuredGenerationResponse:
        if len(images) > self._max_images:
            raise AIProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "Too many images were supplied for analysis.",
            )
        self._validate_schema(request.response_schema)
        model_id = request.route.primary_model
        body = self._generation_body(request, model_id=model_id)
        if images:
            source = self._image_source(images)
            payload = (
                await self._request_stored_images(body, images)
                if source == "stored"
                else await self._request_multipart(body, images)
            )
        else:
            payload = await self._request_json("POST", "/v1/generate", json_body=body)
        completion = self._parse_completion(payload, expected_model_id=model_id)
        self._validate_output(completion.payload, request.response_schema)
        return StructuredGenerationResponse(
            payload=completion.payload,
            model_id=model_id,
            attempted_models=(model_id,),
            provider_request_id=completion.provider_request_id,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            cost=None,
        )

    def _generation_body(
        self, request: StructuredGenerationRequest, *, model_id: str
    ) -> dict[str, object]:
        body: dict[str, object] = {
            "agent": self._agent_name,
            "model_id": model_id,
            "system_prompt": request.system_prompt,
            "input_payload": request.input_payload,
            "response_schema": request.response_schema,
            "schema_name": request.schema_name,
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens,
            "timeout_seconds": self._timeout_seconds,
        }
        if self._profile_id is not None:
            body["profile_id"] = self._profile_id
        try:
            json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as error:
            raise AIProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "The structured request could not be encoded.",
            ) from error
        return body

    @staticmethod
    def _image_source(images: tuple[ImageInput, ...]) -> Literal["inline", "stored"]:
        inline = all(image.base64_data is not None for image in images)
        stored = all(
            image.storage_scope is not None and image.storage_key is not None for image in images
        )
        if stored and not inline:
            return "stored"
        if inline and not stored:
            return "inline"
        raise AIProviderError(
            ProviderErrorCode.INVALID_REQUEST,
            "Inline and stored images cannot be mixed.",
        )

    async def _request_stored_images(
        self,
        metadata: dict[str, object],
        images: tuple[ImageInput, ...],
    ) -> dict[str, Any]:
        references: list[dict[str, str]] = []
        for image in images:
            if image.storage_scope is None or image.storage_key is None:
                raise AIProviderError(
                    ProviderErrorCode.INVALID_REQUEST,
                    "Stored image references are incomplete.",
                )
            references.append(
                {
                    "label": image.label,
                    "mime_type": image.mime_type,
                    "storage_scope": image.storage_scope,
                    "storage_key": image.storage_key,
                }
            )
        return await self._request_json(
            "POST",
            "/v1/analyze-stored-images",
            json_body={"generation": metadata, "images": references},
        )

    async def _request_multipart(
        self,
        metadata: dict[str, object],
        images: tuple[ImageInput, ...],
    ) -> dict[str, Any]:
        if self._token_value() is None:
            raise AIProviderError(
                ProviderErrorCode.NOT_CONFIGURED,
                _SAFE_MESSAGES[ProviderErrorCode.NOT_CONFIGURED],
            )
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        total_bytes = 0
        for index, image in enumerate(images, start=1):
            base64_data = image.base64_data
            if base64_data is None:
                raise AIProviderError(
                    ProviderErrorCode.INVALID_REQUEST,
                    "Inline image data is required for multipart analysis.",
                )
            max_encoded_bytes = ((self._max_image_bytes + 2) // 3) * 4
            if len(base64_data) > max_encoded_bytes:
                raise AIProviderError(
                    ProviderErrorCode.INVALID_REQUEST,
                    "The supplied image exceeds the configured limit.",
                )
            try:
                decoded = base64.b64decode(base64_data, validate=True)
            except (binascii.Error, ValueError) as error:
                raise AIProviderError(
                    ProviderErrorCode.INVALID_REQUEST,
                    "The supplied image could not be decoded.",
                ) from error
            if not decoded or len(decoded) > self._max_image_bytes:
                raise AIProviderError(
                    ProviderErrorCode.INVALID_REQUEST,
                    "The supplied image exceeds the configured limit.",
                )
            total_bytes += len(decoded)
            if total_bytes > self._max_total_image_bytes:
                raise AIProviderError(
                    ProviderErrorCode.INVALID_REQUEST,
                    "The supplied images exceed the configured limit.",
                )
            filename = self._safe_filename(image.label, index, image.mime_type)
            files.append(("images", (filename, decoded, image.mime_type)))
        multipart_metadata = {
            **metadata,
            "image_labels": [image.label for image in images],
        }
        try:
            response = await self._client.post(
                f"{self._base_url}/v1/analyze-images",
                headers=self._headers(),
                data={
                    "metadata": json.dumps(
                        multipart_metadata, ensure_ascii=False, separators=(",", ":")
                    )
                },
                files=files,
                timeout=self._timeout,
            )
        except Exception as error:
            raise self.normalize_error(error) from error
        return self._parse_http_response(response)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        if self._token_value() is None:
            raise AIProviderError(
                ProviderErrorCode.NOT_CONFIGURED,
                _SAFE_MESSAGES[ProviderErrorCode.NOT_CONFIGURED],
            )
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(),
                json=json_body,
                timeout=self._timeout,
            )
        except Exception as error:
            raise self.normalize_error(error) from error
        return self._parse_http_response(response)

    def _parse_http_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise self._http_error(response)
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
                provider_status_code=response.status_code,
                provider_request_id=self._response_request_id(response),
            ) from error
        if not isinstance(payload, dict):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
                provider_status_code=response.status_code,
                provider_request_id=self._response_request_id(response),
            )
        return payload

    def _parse_completion(
        self, payload: Mapping[str, Any], *, expected_model_id: str
    ) -> _ProviderCompletion:
        raw_payload = payload.get("payload")
        agent = payload.get("agent")
        model_id = payload.get("model_id")
        request_id = payload.get("request_id")
        duration_seconds = payload.get("duration_seconds")
        if (
            not isinstance(raw_payload, dict)
            or agent != self._agent_name
            or model_id != expected_model_id
            or not isinstance(request_id, str)
            or not request_id.strip()
            or not self._is_nonnegative_number(duration_seconds)
        ):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            )
        input_tokens = self._optional_nonnegative_int(payload.get("input_tokens"))
        output_tokens = self._optional_nonnegative_int(payload.get("output_tokens"))
        if payload.get("input_tokens") is not None and input_tokens is None:
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            )
        if payload.get("output_tokens") is not None and output_tokens is None:
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            )
        return _ProviderCompletion(
            payload=raw_payload,
            provider_request_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=None,
        )

    def _validate_test_output(self, payload: Mapping[str, Any], *, expected_model_id: str) -> None:
        duration_seconds = payload.get("duration_seconds")
        if (
            payload.get("ok") is not True
            or payload.get("agent") != self._agent_name
            or payload.get("model_id") != expected_model_id
            or not isinstance(payload.get("request_id"), str)
            or not str(payload.get("request_id")).strip()
            or not self._is_nonnegative_number(duration_seconds)
        ):
            raise AIProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                _SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            )

    @staticmethod
    def _validate_schema(schema: dict[str, Any]) -> None:
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise AIProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "The requested structured-output schema is invalid.",
            ) from error

    @staticmethod
    def _validate_output(payload: dict[str, Any], schema: dict[str, Any]) -> None:
        try:
            Draft202012Validator(schema).validate(payload)
        except Exception as error:
            raise AIProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                _SAFE_MESSAGES[ProviderErrorCode.INVALID_OUTPUT],
            ) from error

    def _headers(self) -> dict[str, str]:
        token = self._token_value()
        return {"Authorization": f"Bearer {token}"} if token is not None else {}

    def _token_value(self) -> str | None:
        if isinstance(self._token, SecretStr):
            return self._token.get_secret_value() or None
        if isinstance(self._token, str):
            return self._token.strip() or None
        return None

    @staticmethod
    def _enum_value(value: object) -> str:
        raw = getattr(value, "value", value)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("agent_name must be a non-empty string")
        return raw.strip()

    @classmethod
    def _safe_filename(cls, label: str, index: int, mime_type: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-_")[:32]
        return f"{stem or f'image-{index:02d}'}{_IMAGE_SUFFIXES[mime_type]}"

    @staticmethod
    def _optional_nonnegative_int(value: object) -> int | None:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    @staticmethod
    def _is_nonnegative_number(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and value >= 0
        )

    def _http_error(self, response: httpx.Response) -> AIProviderError:
        request_id = self._response_request_id(response)
        code_name: str | None = None
        try:
            body = response.json()
        except (TypeError, ValueError):
            body = None
        if isinstance(body, Mapping):
            error = body.get("error")
            if isinstance(error, Mapping):
                raw_code = error.get("code")
                if isinstance(raw_code, str):
                    code_name = raw_code
                body_request_id = error.get("request_id")
                if request_id is None and isinstance(body_request_id, str):
                    request_id = body_request_id
        code = _SERVICE_CODE_MAP.get(code_name or "")
        if code is None:
            code = self._status_code(response.status_code)
        return AIProviderError(
            code,
            _SAFE_MESSAGES[code],
            provider_status_code=response.status_code,
            provider_request_id=request_id,
        )

    @staticmethod
    def _status_code(status_code: int) -> ProviderErrorCode:
        if status_code == 401:
            return ProviderErrorCode.UNAUTHORIZED
        if status_code == 403:
            return ProviderErrorCode.LOCATION_UNSUPPORTED
        if status_code in {408, 504}:
            return ProviderErrorCode.TIMEOUT
        if status_code == 429:
            return ProviderErrorCode.RATE_LIMITED
        if status_code == 404:
            return ProviderErrorCode.MODEL_NOT_FOUND
        if 400 <= status_code < 500:
            return ProviderErrorCode.INVALID_REQUEST
        return ProviderErrorCode.PROVIDER_UNAVAILABLE

    @staticmethod
    def _response_request_id(response: httpx.Response) -> str | None:
        request_id = response.headers.get("x-request-id")
        return request_id if isinstance(request_id, str) else None
