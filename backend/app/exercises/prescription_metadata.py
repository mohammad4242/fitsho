from __future__ import annotations

from dataclasses import dataclass

from app.exercises.enums import PrescriptionMode


@dataclass(frozen=True)
class ExercisePrescriptionMetadata:
    mode: PrescriptionMode
    duration_min_seconds: int | None = None
    duration_max_seconds: int | None = None


# These source IDs are the stable Free Exercise DB identifiers recorded in the
# catalog focus manifest. Display names are intentionally not used here.
CANONICAL_PRESCRIPTION_METADATA: dict[tuple[str, str], ExercisePrescriptionMetadata] = {
    ("free-exercise-db", "0464"): ExercisePrescriptionMetadata(
        mode=PrescriptionMode.DURATION,
        duration_min_seconds=20,
        duration_max_seconds=40,
    ),
    ("free-exercise-db", "0705"): ExercisePrescriptionMetadata(
        mode=PrescriptionMode.DURATION,
        duration_min_seconds=20,
        duration_max_seconds=40,
    ),
    ("fitsho_training_template", "side-plank"): ExercisePrescriptionMetadata(
        mode=PrescriptionMode.DURATION,
        duration_min_seconds=20,
        duration_max_seconds=40,
    ),
}


def prescription_metadata_for_identifier(
    source: str | None,
    source_id: str | None,
) -> ExercisePrescriptionMetadata:
    return CANONICAL_PRESCRIPTION_METADATA.get(
        (source or "", source_id or ""), ExercisePrescriptionMetadata(PrescriptionMode.REPS)
    )
