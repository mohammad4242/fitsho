from dataclasses import dataclass

import httpx
from pydantic import SecretStr

from app.ai.models import AiModel
from app.ai.opencode_zen import OpenCodeZenWorkoutPlanProvider
from app.ai.provider import WorkoutPlanModelProvider


@dataclass(frozen=True)
class ModelProviderCandidate:
    model_id: str
    provider: WorkoutPlanModelProvider


def build_model_candidates(
    models: tuple[AiModel, ...],
    client: httpx.AsyncClient,
    *,
    api_key: SecretStr | str | None,
    base_url: str,
    timeout_seconds: float,
) -> tuple[ModelProviderCandidate, ...]:
    candidates: list[ModelProviderCandidate] = []
    for model in models:
        if model.api_kind is None:
            raise ValueError("A routing model requires an API kind")
        provider = OpenCodeZenWorkoutPlanProvider(
            client,
            api_key=api_key,
            base_url=base_url,
            model=model.model_id,
            timeout_seconds=timeout_seconds,
            api_kind=model.api_kind,
        )
        candidates.append(ModelProviderCandidate(model_id=model.model_id, provider=provider))
    return tuple(candidates)
