from collections import deque
from collections.abc import Iterable

from app.ai.schemas import WorkoutGenerationModelRequest, WorkoutGenerationModelResponse


class FakeWorkoutPlanModelProvider:
    def __init__(self, responses: Iterable[WorkoutGenerationModelResponse | Exception]) -> None:
        self._responses = deque(responses)
        self.calls: list[WorkoutGenerationModelRequest] = []

    async def generate_plan(
        self, request: WorkoutGenerationModelRequest
    ) -> WorkoutGenerationModelResponse:
        self.calls.append(request)
        response = self._responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response
