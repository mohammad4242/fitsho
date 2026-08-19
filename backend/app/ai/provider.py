from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.ai.schemas import WorkoutGenerationModelRequest, WorkoutGenerationModelResponse

if TYPE_CHECKING:
    from app.ai.reasoning import AIReasoningInput


class WorkoutPlanModelProvider(Protocol):
    async def generate_plan(
        self, request: WorkoutGenerationModelRequest
    ) -> WorkoutGenerationModelResponse: ...


class AIReasoningProvider(Protocol):
    async def reason(self, request: AIReasoningInput) -> object: ...
