from __future__ import annotations

from typing import Protocol

from app.body_analysis.providers.models import (
    AIProviderError,
    ImageInput,
    ModelCapabilities,
    ModelCapabilityFilter,
    ProviderConnectionResult,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)


class AIProvider(Protocol):
    """Stable provider contract consumed by analysis and admin services."""

    async def test_connection(self) -> ProviderConnectionResult: ...

    async def list_models(
        self, filters: ModelCapabilityFilter | None = None
    ) -> tuple[ModelCapabilities, ...]: ...

    async def get_model_capabilities(self, model_id: str) -> ModelCapabilities: ...

    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse: ...

    async def analyze_images(
        self,
        request: StructuredGenerationRequest,
        *,
        images: tuple[ImageInput, ...],
    ) -> StructuredGenerationResponse: ...

    def normalize_error(self, error: Exception) -> AIProviderError: ...
