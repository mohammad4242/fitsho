from typing import Protocol

from app.ai.schemas import WorkoutGenerationModelRequest, WorkoutGenerationModelResponse


class WorkoutPlanModelProvider(Protocol):
    async def generate_plan(
        self, request: WorkoutGenerationModelRequest
    ) -> WorkoutGenerationModelResponse: ...
