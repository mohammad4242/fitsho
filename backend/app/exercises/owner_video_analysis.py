from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MediaPresentation,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise
from app.exercises.owner_video_media import PreparedOwnerVideo
from app.exercises.taxonomy import is_compatible_muscle_focus

AnalysisDecision = Literal["match_existing", "create_new", "needs_review"]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
ANALYSIS_SCHEMA_VERSION = "owner-video-analysis-v1"
ANALYSIS_PROMPT_VERSION = "owner-video-prompt-v1"


class OwnerVideoAnalysisError(ValueError):
    pass


class CatalogueExercise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    name_en: str
    name_fa: str
    aliases_en: tuple[str, ...]
    body_region: BodyRegion | None
    primary_muscle: MuscleGroup | None
    movement_pattern: MovementPattern
    equipment: tuple[Equipment, ...]


class OwnerVideoAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    name_en: str = Field(min_length=2, max_length=160)
    name_fa: str = Field(min_length=2, max_length=160)
    visible_text: list[str] = Field(max_length=20)
    aliases_en: list[str] = Field(max_length=20)
    body_region: BodyRegion | None
    primary_muscle: MuscleGroup | None
    muscle_focus: MuscleFocus | None
    secondary_muscles: list[MuscleGroup] = Field(max_length=16)
    equipment: list[Equipment] = Field(min_length=1, max_length=9)
    difficulty: Difficulty
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    labels: list[ExerciseLabel] = Field(max_length=2)
    caution_tags: list[ExerciseCautionTag] = Field(max_length=10)
    instructions_en: list[str] = Field(min_length=3, max_length=6)
    instructions_fa: list[str] = Field(min_length=3, max_length=6)
    safety_notes_en: list[str] = Field(max_length=10)
    safety_notes_fa: list[str] = Field(max_length=10)
    short_description_en: str = Field(min_length=2, max_length=1000)
    short_description_fa: str = Field(min_length=2, max_length=1000)
    form_cues_en: list[str] = Field(max_length=10)
    form_cues_fa: list[str] = Field(max_length=10)
    common_mistakes_en: list[str] = Field(max_length=10)
    common_mistakes_fa: list[str] = Field(max_length=10)
    breathing_en: str = Field(min_length=2, max_length=1000)
    breathing_fa: str = Field(min_length=2, max_length=1000)
    presentation: MediaPresentation
    presentation_confidence: float = Field(ge=0, le=1)
    identification_confidence: float = Field(ge=0, le=1)
    decision: AnalysisDecision
    match_confidence: float = Field(ge=0, le=1)
    existing_exercise_id: UUID | None
    review_reasons: list[str] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.instructions_en) != len(self.instructions_fa):
            raise ValueError("English and Persian instruction counts must match")
        if bool(self.body_region) != bool(self.primary_muscle):
            raise ValueError("Body region and primary muscle must be provided together")
        if not is_compatible_muscle_focus(self.primary_muscle, self.muscle_focus):
            raise ValueError("Muscle focus is incompatible with the primary muscle")
        if self.decision == "match_existing" and self.existing_exercise_id is None:
            raise ValueError("Existing exercise ID is required for a match")
        if self.decision == "create_new" and self.existing_exercise_id is not None:
            raise ValueError("New exercise analysis cannot select an existing exercise")
        return self


def build_catalogue_snapshot(db: Session) -> tuple[CatalogueExercise, ...]:
    exercises = db.scalars(
        select(Exercise)
        .where(Exercise.is_active.is_(True))
        .options(selectinload(Exercise.equipment_items))
        .order_by(Exercise.name_en, Exercise.id)
    ).all()
    return tuple(
        CatalogueExercise(
            id=exercise.id,
            name_en=exercise.name_en,
            name_fa=exercise.name_fa,
            aliases_en=tuple(exercise.aliases_en or ()),
            body_region=exercise.body_region,
            primary_muscle=exercise.primary_muscle,
            movement_pattern=exercise.movement_pattern,
            equipment=tuple(item.equipment for item in exercise.equipment_items),
        )
        for exercise in exercises
    )


def _normalized_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def resolve_existing_match(
    analysis: OwnerVideoAnalysis,
    catalogue: Sequence[CatalogueExercise],
    settings: Settings,
) -> UUID | None:
    if analysis.decision != "match_existing" or analysis.existing_exercise_id is None:
        return None
    if analysis.identification_confidence < settings.owner_video_identification_confidence:
        return None
    if analysis.match_confidence < settings.owner_video_match_confidence:
        return None
    candidate = next(
        (item for item in catalogue if item.id == analysis.existing_exercise_id),
        None,
    )
    if candidate is None:
        return None
    analysis_names = {
        _normalized_name(value)
        for value in (analysis.name_en, *analysis.aliases_en, *analysis.visible_text)
        if _normalized_name(value)
    }
    candidate_names = {
        _normalized_name(value)
        for value in (candidate.name_en, *candidate.aliases_en)
        if _normalized_name(value)
    }
    if not analysis_names.intersection(candidate_names):
        return None
    if analysis.primary_muscle is not candidate.primary_muscle:
        return None
    if analysis.movement_pattern is not candidate.movement_pattern:
        return None
    if not set(analysis.equipment).intersection(candidate.equipment):
        return None
    return candidate.id


def resolve_presentation(
    analysis: OwnerVideoAnalysis,
    settings: Settings,
) -> MediaPresentation:
    if analysis.presentation_confidence < settings.owner_video_presentation_confidence:
        return MediaPresentation.UNSPECIFIED
    return analysis.presentation


def _validate_context(
    analysis: OwnerVideoAnalysis,
    prepared: PreparedOwnerVideo,
    catalogue: Sequence[CatalogueExercise],
) -> None:
    if analysis.source_id != prepared.source_id:
        raise OwnerVideoAnalysisError("Codex analysis digest does not match the source video")
    catalogue_ids = {exercise.id for exercise in catalogue}
    if (
        analysis.existing_exercise_id is not None
        and analysis.existing_exercise_id not in catalogue_ids
    ):
        raise OwnerVideoAnalysisError("Codex analysis selected an exercise outside the catalogue")


def _atomic_json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.parent / f".{path.name}-{uuid4().hex}.tmp"
    try:
        staged.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _prompt(
    prepared: PreparedOwnerVideo,
    catalogue: Sequence[CatalogueExercise],
) -> str:
    taxonomy = {
        "body_region": [item.value for item in BodyRegion],
        "primary_muscle": [item.value for item in MuscleGroup],
        "muscle_focus": [item.value for item in MuscleFocus],
        "equipment": [item.value for item in Equipment],
        "difficulty": [item.value for item in Difficulty],
        "movement_pattern": [item.value for item in MovementPattern],
        "exercise_type": [item.value for item in ExerciseType],
        "labels": [item.value for item in ExerciseLabel],
        "caution_tags": [item.value for item in ExerciseCautionTag],
        "presentation": [item.value for item in MediaPresentation],
    }
    catalogue_payload = [item.model_dump(mode="json") for item in catalogue]
    return (
        "Analyze only the attached representative frames from one exercise video. "
        "Identify the exercise, transcribe visible exercise text, map metadata only to the "
        "provided Fitsho taxonomy, and conservatively compare against the supplied catalogue. "
        "Never guess an existing match. Use needs_review when identification or matching is "
        "uncertain. Return only the JSON required by the output schema. Do not inspect or change "
        "files.\n"
        f"Source SHA-256: {prepared.source_id}\n"
        f"Allowed taxonomy: {json.dumps(taxonomy, separators=(',', ':'))}\n"
        "Active Fitsho exercises: "
        f"{json.dumps(catalogue_payload, ensure_ascii=False, separators=(',', ':'))}"
    )


class CodexCliExerciseAnalyzer:
    def __init__(
        self,
        settings: Settings,
        *,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        self._settings = settings
        self._runner = runner

    def analyze(
        self,
        prepared: PreparedOwnerVideo,
        catalogue: Sequence[CatalogueExercise],
    ) -> OwnerVideoAnalysis:
        work_directory = prepared.muted_path.parent.resolve()
        cache_path = work_directory / "analysis-cache.json"
        cached = self._load_cache(cache_path, prepared, catalogue)
        if cached is not None:
            return cached

        schema_path = work_directory / "analysis-schema.json"
        output_path = work_directory / "analysis-output.json"
        _atomic_json_write(schema_path, OwnerVideoAnalysis.model_json_schema())
        output_path.unlink(missing_ok=True)
        command = [
            self._settings.owner_video_codex_path,
            "exec",
            "-C",
            str(work_directory),
            "--skip-git-repo-check",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        if self._settings.owner_video_codex_model:
            command.extend(["--model", self._settings.owner_video_codex_model])
        for frame_path in prepared.frame_paths:
            command.extend(["--image", str(frame_path.resolve())])
        command.extend(["--", "-"])
        try:
            result = self._runner(
                command,
                input=_prompt(prepared, catalogue),
                capture_output=True,
                text=True,
                timeout=self._settings.owner_video_codex_timeout_seconds,
                check=False,
                cwd=work_directory,
            )
        except FileNotFoundError as error:
            raise OwnerVideoAnalysisError("Codex CLI is unavailable") from error
        except subprocess.TimeoutExpired as error:
            raise OwnerVideoAnalysisError("Codex analysis timed out") from error
        if result.returncode != 0:
            raise OwnerVideoAnalysisError("Codex analysis failed")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            analysis = OwnerVideoAnalysis.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise OwnerVideoAnalysisError("Codex returned invalid structured JSON") from error
        _validate_context(analysis, prepared, catalogue)
        _atomic_json_write(
            cache_path,
            {
                "schema_version": ANALYSIS_SCHEMA_VERSION,
                "prompt_version": ANALYSIS_PROMPT_VERSION,
                "analysis": analysis.model_dump(mode="json"),
            },
        )
        return analysis

    @staticmethod
    def _load_cache(
        cache_path: Path,
        prepared: PreparedOwnerVideo,
        catalogue: Sequence[CatalogueExercise],
    ) -> OwnerVideoAnalysis | None:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != ANALYSIS_SCHEMA_VERSION
                or payload.get("prompt_version") != ANALYSIS_PROMPT_VERSION
            ):
                return None
            analysis = OwnerVideoAnalysis.model_validate(payload.get("analysis"))
            _validate_context(analysis, prepared, catalogue)
        except (OSError, json.JSONDecodeError, ValidationError, OwnerVideoAnalysisError):
            return None
        return analysis
