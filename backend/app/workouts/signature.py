from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable, Mapping
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.workouts.program_engine.schemas import ProgramGenerationRequest
from app.workouts.schemas import (
    GenerationSignatureContext,
    WorkoutExerciseCandidate,
)


def _value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    return value


def _string_value(value: object) -> str:
    return str(_value(value))


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _canonical_value(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()


def _canonical_value(value: object) -> object:
    if isinstance(value, (Enum, UUID, Decimal)):
        return str(_value(value))
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        return {
            str(_canonical_value(key)): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (set, frozenset)):
        items = [_canonical_value(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def normalize_physical_limitations(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in normalized
    )
    normalized = " ".join(normalized.split()).casefold()
    return normalized or None


def weight_bucket(weight_kg: Decimal | float | int | None) -> int | None:
    if weight_kg is None:
        return None
    weight = Decimal(str(weight_kg))
    return int(weight // Decimal("5")) * 5


def hash_candidate_set(candidates: Iterable[WorkoutExerciseCandidate]) -> str:
    payload = [
        {
            "id": str(candidate.id),
            "primary_muscle": _value(candidate.primary_muscle),
            "secondary_muscles": sorted(
                _string_value(value) for value in candidate.secondary_muscles
            ),
            "movement_pattern": _value(candidate.movement_pattern),
            "exercise_type": _value(candidate.exercise_type),
            "equipment": sorted(_string_value(value) for value in candidate.equipment),
            "difficulty": _value(candidate.difficulty),
            "caution_tags": sorted(_string_value(value) for value in candidate.caution_tags),
            "labels": sorted(_string_value(value) for value in candidate.labels),
        }
        for candidate in sorted(candidates, key=lambda item: str(item.id))
    ]
    return _canonical_hash(payload)


def build_generation_signature(context: GenerationSignatureContext) -> str:
    payload: dict[str, Any] = {
        "fitness_goal": _value(context.fitness_goal),
        "sex": _value(context.sex),
        "experience_level": _value(context.experience_level),
        "training_days_per_week": context.training_days_per_week,
        "training_location": _value(context.training_location),
        "home_training_setup": _value(context.home_training_setup),
        "available_equipment": sorted(
            _string_value(value)
            for value in (context.available_equipment or frozenset())
        ),
        "session_duration_minutes": context.session_duration_minutes,
        "plan_duration_weeks": context.plan_duration_weeks,
        "training_cautions": sorted(_string_value(value) for value in context.training_cautions),
        "physical_limitations": normalize_physical_limitations(context.physical_limitations),
        "weight_bucket_kg": weight_bucket(context.current_weight_kg),
        "candidate_set_hash": context.candidate_set_hash,
        "catalog_programming_version": context.catalog_programming_version,
        "model_id": context.model_id,
        "prompt_version": context.prompt_version,
        "generation_policy_version": context.generation_policy_version,
    }
    return _canonical_hash(payload)


def build_generation_request_signature(
    request: ProgramGenerationRequest,
    *,
    catalog_hash: str,
    reference_hash: str,
    engine_version: str,
    ruleset_version: str,
) -> str:
    """Hash effective generation inputs with stable collection serialization."""
    payload = {
        "request": request.model_dump(mode="python"),
        "catalog_hash": catalog_hash,
        "reference_hash": reference_hash,
        "engine_version": engine_version,
        "ruleset_version": ruleset_version,
    }
    return _canonical_hash(payload)
