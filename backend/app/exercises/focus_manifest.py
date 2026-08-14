from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.exercises.enums import MuscleFocus, MuscleGroup
from app.exercises.focus_classifier import classify_muscle_focus, refine_primary_muscle
from app.exercises.models import Exercise

MANIFEST_PATH = Path(__file__).with_name("focus_manifest.json")


class UnresolvedMuscleFocusError(ValueError):
    pass


@dataclass(frozen=True)
class FocusManifestEntry:
    key: str
    slug: str
    name_en: str
    previous_primary_muscle: MuscleGroup | None
    primary_muscle: MuscleGroup | None
    muscle_focus: MuscleFocus | None
    basis: str

    def as_json(self) -> dict[str, str | None]:
        payload = asdict(self)
        return {
            key: value.value if isinstance(value, MuscleGroup | MuscleFocus) else value
            for key, value in payload.items()
        }


def stable_exercise_key(exercise: Exercise) -> str:
    if exercise.source and exercise.source_id:
        return f"{exercise.source}:{exercise.source_id}"
    return f"slug:{exercise.slug}"


def _metadata_text(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


def _metadata_text_list(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return ()
    return tuple(value)


def manifest_entry_for_exercise(exercise: Exercise) -> FocusManifestEntry:
    metadata = exercise.source_metadata_en or {}
    primary_muscle = refine_primary_muscle(
        exercise.primary_muscle,
        exercise.name_en,
        exercise.movement_pattern,
    )
    classification = classify_muscle_focus(
        primary_muscle=primary_muscle,
        source_target=_metadata_text(metadata, "target"),
        source_muscle_group=_metadata_text(metadata, "muscleGroup"),
        secondary_targets=_metadata_text_list(metadata, "secondaryMuscles"),
        name_en=exercise.name_en,
        movement_pattern=exercise.movement_pattern,
        exercise_type=exercise.exercise_type,
        instructions_en=exercise.instructions_en,
    )
    if primary_muscle is not None and classification is None:
        raise UnresolvedMuscleFocusError(
            f"{stable_exercise_key(exercise)}: unresolved focus for {exercise.name_en}"
        )
    return FocusManifestEntry(
        key=stable_exercise_key(exercise),
        slug=exercise.slug,
        name_en=exercise.name_en,
        previous_primary_muscle=exercise.primary_muscle,
        primary_muscle=primary_muscle,
        muscle_focus=classification.focus if classification is not None else None,
        basis=classification.basis if classification is not None else "primary_muscle:null",
    )


def _entry_from_json(payload: dict[str, Any]) -> FocusManifestEntry:
    return FocusManifestEntry(
        key=str(payload["key"]),
        slug=str(payload["slug"]),
        name_en=str(payload["name_en"]),
        previous_primary_muscle=(
            MuscleGroup(payload["previous_primary_muscle"])
            if payload.get("previous_primary_muscle") is not None
            else None
        ),
        primary_muscle=(
            MuscleGroup(payload["primary_muscle"])
            if payload.get("primary_muscle") is not None
            else None
        ),
        muscle_focus=(
            MuscleFocus(payload["muscle_focus"])
            if payload.get("muscle_focus") is not None
            else None
        ),
        basis=str(payload["basis"]),
    )


def load_focus_manifest(path: Path = MANIFEST_PATH) -> dict[str, FocusManifestEntry]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("Exercise focus manifest must be a list of objects")
    entries = [_entry_from_json(item) for item in payload]
    manifest = {entry.key: entry for entry in entries}
    if len(manifest) != len(entries):
        raise ValueError("Exercise focus manifest contains duplicate stable keys")
    return manifest


FOCUS_MANIFEST = load_focus_manifest()
