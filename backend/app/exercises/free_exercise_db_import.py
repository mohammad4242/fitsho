from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.admin.media import MediaValidationError, _signature_extension
from app.config import Settings, get_settings
from app.database.session import get_engine
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MediaPresentation,
    MediaRole,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.focus_classifier import classify_muscle_focus, refine_primary_muscle
from app.exercises.free_exercise_db_translations import CURATED_TRANSLATIONS
from app.exercises.models import (
    Exercise,
    ExerciseCautionTagItem,
    ExerciseEquipment,
    ExerciseLabelItem,
    ExerciseMediaAsset,
    ExerciseSecondaryMuscle,
)

BODY_REGION_MAP: dict[str, BodyRegion] = {
    "back": BodyRegion.UPPER_BODY,
    "chest": BodyRegion.UPPER_BODY,
    "hips": BodyRegion.LOWER_BODY,
    "lower arms": BodyRegion.UPPER_BODY,
    "lower legs": BodyRegion.LOWER_BODY,
    "shoulders": BodyRegion.UPPER_BODY,
    "upper arms": BodyRegion.UPPER_BODY,
    "upper legs": BodyRegion.LOWER_BODY,
    "waist": BodyRegion.CORE,
}

MUSCLE_GROUP_MAP: dict[str, MuscleGroup] = {
    "abdominals": MuscleGroup.ABS,
    "abs": MuscleGroup.ABS,
    "adductors": MuscleGroup.ADDUCTORS,
    "anterior deltoid": MuscleGroup.SHOULDERS,
    "biceps": MuscleGroup.BICEPS,
    "calves": MuscleGroup.CALVES,
    "deltoids": MuscleGroup.SHOULDERS,
    "delts": MuscleGroup.SHOULDERS,
    "erector spinae": MuscleGroup.LOWER_BACK,
    "erectors": MuscleGroup.LOWER_BACK,
    "forearm extensors": MuscleGroup.FOREARMS,
    "forearms": MuscleGroup.FOREARMS,
    "glutes": MuscleGroup.GLUTES,
    "gluteus medius": MuscleGroup.GLUTES,
    "hamstrings": MuscleGroup.HAMSTRINGS,
    "lats": MuscleGroup.BACK,
    "lower back": MuscleGroup.LOWER_BACK,
    "middle back": MuscleGroup.BACK,
    "neck flexors": MuscleGroup.NECK,
    "obliques": MuscleGroup.OBLIQUES,
    "pectorals": MuscleGroup.CHEST,
    "posterior deltoid": MuscleGroup.SHOULDERS,
    "quadriceps": MuscleGroup.QUADRICEPS,
    "quads": MuscleGroup.QUADRICEPS,
    "rear deltoids": MuscleGroup.SHOULDERS,
    "rectus abdominis": MuscleGroup.ABS,
    "rhomboids": MuscleGroup.BACK,
    "spinal erectors": MuscleGroup.LOWER_BACK,
    "spine": MuscleGroup.LOWER_BACK,
    "sternocleidomastoid": MuscleGroup.NECK,
    "thoracic spine": MuscleGroup.LOWER_BACK,
    "traps": MuscleGroup.TRAPS,
    "triceps": MuscleGroup.TRICEPS,
    "upper back": MuscleGroup.BACK,
    "upper pectorals": MuscleGroup.CHEST,
}

EQUIPMENT_MAP: dict[str, Equipment] = {
    "band": Equipment.RESISTANCE_BAND,
    "barbell": Equipment.BARBELL,
    "body weight": Equipment.BODYWEIGHT,
    "cable": Equipment.CABLE,
    "dumbbell": Equipment.DUMBBELL,
    "ez barbell": Equipment.BARBELL,
    "kettlebell": Equipment.OTHER,
    "leverage machine": Equipment.MACHINE,
    "rope": Equipment.OTHER,
    "sled machine": Equipment.MACHINE,
    "smith machine": Equipment.MACHINE,
    "stability ball": Equipment.OTHER,
    "weighted": Equipment.OTHER,
}

DIFFICULTY_MAP: dict[str, Difficulty] = {
    "beginner": Difficulty.BEGINNER,
    "intermediate": Difficulty.INTERMEDIATE,
    "advanced": Difficulty.ADVANCED,
}


def map_body_region(value: str) -> BodyRegion | None:
    return BODY_REGION_MAP.get(value.strip().lower())


def map_muscle_group(value: str) -> MuscleGroup | None:
    return MUSCLE_GROUP_MAP.get(value.strip().lower())


def map_equipment(value: str) -> Equipment | None:
    return EQUIPMENT_MAP.get(value.strip().lower())


def map_difficulty(value: str) -> Difficulty | None:
    return DIFFICULTY_MAP.get(value.strip().lower())


SOURCE_NAME = "free-exercise-db"


@dataclass(frozen=True)
class ExerciseTranslation:
    name_fa: str
    instructions_fa: list[str]


@dataclass(frozen=True)
class ProgrammingMetadata:
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    caution_tags: tuple[ExerciseCautionTag, ...]


def classify_programming_metadata(
    *,
    name_en: str,
    primary_muscle: MuscleGroup | None,
    instructions_en: Sequence[str],
    steps_en: Sequence[str],
    form_cues_en: Sequence[str],
    common_mistakes_en: Sequence[str],
) -> ProgrammingMetadata:
    name = name_en.lower().replace("-", " ")
    is_mobility = _contains_any(name, ("stretch", "mobility"))
    source_text = (
        " ".join([name_en, *instructions_en, *steps_en, *form_cues_en, *common_mistakes_en])
        .lower()
        .replace("-", " ")
    )

    if _contains_any(name, ("pull up", "pullup", "chin up", "chinup", "pulldown")):
        movement_pattern = MovementPattern.VERTICAL_PULL
    elif _contains_any(name, ("row", "rear delt fly", "reverse fly")):
        movement_pattern = MovementPattern.HORIZONTAL_PULL
    elif _contains_any(name, ("overhead press", "shoulder press", "military press")):
        movement_pattern = MovementPattern.VERTICAL_PUSH
    elif _contains_any(name, ("bench press", "push up", "pushup", "chest press", "dip")):
        movement_pattern = MovementPattern.HORIZONTAL_PUSH
    elif "squat" in name:
        movement_pattern = MovementPattern.SQUAT
    elif _contains_any(name, ("deadlift", "good morning", "hyperextension")):
        movement_pattern = MovementPattern.HIP_HINGE
    elif _contains_any(name, ("lunge", "split squat", "step up")):
        movement_pattern = MovementPattern.LUNGE
    elif "leg extension" in name:
        movement_pattern = MovementPattern.KNEE_EXTENSION
    elif _contains_any(name, ("leg curl", "hamstring curl")):
        movement_pattern = MovementPattern.KNEE_FLEXION
    elif _contains_any(name, ("hip thrust", "glute bridge", "hip extension", "kickback")):
        movement_pattern = MovementPattern.HIP_EXTENSION
    elif _contains_any(name, ("hip abduction", "abductor")):
        movement_pattern = MovementPattern.HIP_ABDUCTION
    elif _contains_any(name, ("hip adduction", "adductor")):
        movement_pattern = MovementPattern.HIP_ADDUCTION
    elif _contains_any(name, ("calf raise", "calves raise")):
        movement_pattern = MovementPattern.CALF_RAISE
    elif "curl" in name:
        movement_pattern = MovementPattern.ELBOW_FLEXION
    elif _contains_any(name, ("triceps extension", "elbow extension")):
        movement_pattern = MovementPattern.ELBOW_EXTENSION
    elif _contains_any(name, ("lateral raise", "front raise")):
        movement_pattern = MovementPattern.SHOULDER_ABDUCTION
    elif "external rotation" in name:
        movement_pattern = MovementPattern.SHOULDER_EXTERNAL_ROTATION
    elif "shrug" in name:
        movement_pattern = MovementPattern.SHRUG
    elif _contains_any(name, ("crunch", "sit up", "bicycle", "twist")):
        movement_pattern = MovementPattern.SPINAL_FLEXION
    elif "side plank" in name:
        movement_pattern = MovementPattern.CORE_ANTI_LATERAL_FLEXION
    elif "plank" in name:
        movement_pattern = MovementPattern.CORE_ANTI_EXTENSION
    elif not is_mobility:
        pattern_by_muscle = {
            MuscleGroup.BICEPS: MovementPattern.ELBOW_FLEXION,
            MuscleGroup.TRICEPS: MovementPattern.ELBOW_EXTENSION,
            MuscleGroup.CALVES: MovementPattern.CALF_RAISE,
            MuscleGroup.QUADRICEPS: MovementPattern.KNEE_EXTENSION,
            MuscleGroup.HAMSTRINGS: MovementPattern.KNEE_FLEXION,
            MuscleGroup.GLUTES: MovementPattern.HIP_EXTENSION,
            MuscleGroup.ADDUCTORS: MovementPattern.HIP_ADDUCTION,
            MuscleGroup.TRAPS: MovementPattern.SHRUG,
        }
        movement_pattern = (
            pattern_by_muscle.get(primary_muscle, MovementPattern.OTHER)
            if primary_muscle is not None
            else MovementPattern.OTHER
        )
    else:
        movement_pattern = MovementPattern.OTHER

    if is_mobility:
        exercise_type = ExerciseType.MOBILITY
    elif movement_pattern in {
        MovementPattern.SPINAL_FLEXION,
        MovementPattern.CORE_ANTI_EXTENSION,
        MovementPattern.CORE_ANTI_ROTATION,
        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
    }:
        exercise_type = ExerciseType.CORE
    elif (
        movement_pattern
        in {
            MovementPattern.ELBOW_FLEXION,
            MovementPattern.ELBOW_EXTENSION,
            MovementPattern.SHOULDER_ABDUCTION,
            MovementPattern.SHOULDER_EXTERNAL_ROTATION,
            MovementPattern.SHRUG,
            MovementPattern.KNEE_EXTENSION,
            MovementPattern.KNEE_FLEXION,
            MovementPattern.HIP_ABDUCTION,
            MovementPattern.HIP_ADDUCTION,
            MovementPattern.CALF_RAISE,
        }
        or "fly" in name
    ):
        exercise_type = ExerciseType.ISOLATION
    elif movement_pattern is not MovementPattern.OTHER:
        exercise_type = ExerciseType.COMPOUND
    else:
        exercise_type = ExerciseType.OTHER

    cautions: list[ExerciseCautionTag] = []
    if movement_pattern is MovementPattern.HIP_HINGE:
        cautions.append(ExerciseCautionTag.LOWER_BACK_LOADING)
    if movement_pattern is MovementPattern.SPINAL_FLEXION:
        cautions.append(ExerciseCautionTag.SPINAL_FLEXION)
    if movement_pattern in {MovementPattern.SQUAT, MovementPattern.LUNGE}:
        cautions.append(ExerciseCautionTag.DEEP_KNEE_FLEXION)
    if movement_pattern in {MovementPattern.VERTICAL_PUSH, MovementPattern.VERTICAL_PULL}:
        cautions.append(ExerciseCautionTag.OVERHEAD_POSITION)
    if movement_pattern is MovementPattern.SHOULDER_EXTERNAL_ROTATION:
        cautions.append(ExerciseCautionTag.SHOULDER_EXTERNAL_ROTATION)
    if "internal rotation" in source_text:
        cautions.append(ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION)
    if "neck" in source_text:
        cautions.append(ExerciseCautionTag.NECK_LOADING)
    if "wrist" in source_text:
        cautions.append(ExerciseCautionTag.WRIST_LOADING)
    if _contains_any(source_text, ("balance", "single leg", "one leg")):
        cautions.append(ExerciseCautionTag.BALANCE_DEMAND)

    return ProgrammingMetadata(
        movement_pattern=movement_pattern,
        exercise_type=exercise_type,
        caution_tags=tuple(dict.fromkeys(cautions)),
    )


def _contains_any(value: str, terms: Sequence[str]) -> bool:
    return any(term in value for term in terms)


def classify_exercise_labels(
    *,
    body_part: str,
    target: str,
    exercise_type: ExerciseType,
) -> tuple[ExerciseLabel, ...]:
    labels: list[ExerciseLabel] = []
    if target.strip().lower() == "full body":
        labels.append(ExerciseLabel.FULL_BODY)
    if exercise_type is not ExerciseType.MOBILITY and (
        body_part.strip().lower() == "cardio" or target.strip().lower() == "cardiovascular system"
    ):
        labels.append(ExerciseLabel.CARDIO)
    return tuple(labels)


class ExerciseTranslator(Protocol):
    def translate(self, records: list[ImportCandidate]) -> dict[str, ExerciseTranslation]: ...


class CuratedExerciseTranslator:
    def __init__(self, translations: Mapping[str, Mapping[str, object]]) -> None:
        self._translations = translations

    def translate(self, records: list[ImportCandidate]) -> dict[str, ExerciseTranslation]:
        result: dict[str, ExerciseTranslation] = {}
        for record in records:
            item = self._translations.get(record.source_id)
            if item is None:
                continue
            name_fa = item.get("name_fa")
            instructions_fa = item.get("instructions_fa")
            if (
                not isinstance(name_fa, str)
                or not isinstance(instructions_fa, list)
                or not all(isinstance(step, str) for step in instructions_fa)
            ):
                raise ValueError(f"Invalid local translation for {record.source_id}")
            result[record.source_id] = ExerciseTranslation(
                name_fa=name_fa,
                instructions_fa=list(instructions_fa),
            )
        return result


class OpenCodeZenExerciseTranslator:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        api_key = settings.opencode_zen_api_key
        self._api_key = api_key.get_secret_value() if api_key is not None else None
        self._endpoint = f"{settings.opencode_zen_base_url.rstrip('/')}/responses"
        self._model = settings.opencode_zen_model
        self._timeout = settings.opencode_zen_timeout_seconds
        self._client = client or httpx.Client()

    def translate(self, records: list[ImportCandidate]) -> dict[str, ExerciseTranslation]:
        if not records:
            return {}
        if not self._api_key:
            raise RuntimeError("OpenCode Zen translation is not configured")
        response = self._client.post(
            self._endpoint,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "instructions": (
                    "Translate each exercise name and instruction steps into natural Persian. "
                    "Do not add medical, injury, or safety claims. Preserve the source IDs."
                ),
                "input": json.dumps(
                    {
                        "exercises": [
                            {
                                "source_id": record.source_id,
                                "name_en": record.name_en,
                                "instructions_en": record.instructions_en,
                            }
                            for record in records
                        ]
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "store": False,
                "text": {"format": self._response_format()},
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        output_text = payload.get("output_text") if isinstance(payload, dict) else None
        if not isinstance(output_text, str):
            raise RuntimeError("OpenCode Zen translation returned no output text")
        try:
            translated_payload = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenCode Zen translation returned invalid JSON") from error
        translations = (
            translated_payload.get("translations") if isinstance(translated_payload, dict) else None
        )
        if not isinstance(translations, list):
            raise RuntimeError("OpenCode Zen translation returned invalid translations")
        result: dict[str, ExerciseTranslation] = {}
        for item in translations:
            if not isinstance(item, dict):
                raise RuntimeError("OpenCode Zen translation returned invalid translation item")
            source_id = item.get("source_id")
            name_fa = item.get("name_fa")
            instructions_fa = item.get("instructions_fa")
            if (
                not isinstance(source_id, str)
                or not isinstance(name_fa, str)
                or not isinstance(instructions_fa, list)
                or not all(isinstance(step, str) for step in instructions_fa)
            ):
                raise RuntimeError("OpenCode Zen translation returned invalid translation item")
            result[source_id] = ExerciseTranslation(
                name_fa=name_fa,
                instructions_fa=list(instructions_fa),
            )
        return result

    @staticmethod
    def _response_format() -> dict[str, object]:
        return {
            "type": "json_schema",
            "name": "fitsho_exercise_translations",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["translations"],
                "properties": {
                    "translations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["source_id", "name_fa", "instructions_fa"],
                            "properties": {
                                "source_id": {"type": "string"},
                                "name_fa": {"type": "string", "minLength": 2, "maxLength": 160},
                                "instructions_fa": {
                                    "type": "array",
                                    "items": {"type": "string", "minLength": 1},
                                    "minItems": 3,
                                    "maxItems": 6,
                                },
                            },
                        },
                    }
                },
            },
        }


@dataclass(frozen=True)
class ImportMediaAsset:
    presentation: MediaPresentation
    role: MediaRole
    source_url: str
    source_path: Path
    media_type: MediaType


@dataclass(frozen=True)
class ImportCandidate:
    source_id: str
    source_metadata: dict[str, object]
    slug: str
    name_en: str
    body_region: BodyRegion | None
    primary_muscle: MuscleGroup | None
    muscle_focus: MuscleFocus | None
    labels: tuple[ExerciseLabel, ...]
    secondary_muscles: list[MuscleGroup]
    equipment: list[Equipment]
    difficulty: Difficulty
    programming_metadata: ProgrammingMetadata
    aliases_en: list[str]
    short_description_en: str | None
    instructions_en: list[str]
    steps_en: list[str]
    form_cues_en: list[str]
    common_mistakes_en: list[str]
    breathing_en: str | None
    media_assets: list[ImportMediaAsset]


@dataclass
class ImportReport:
    imported_records: list[str] = field(default_factory=list)
    updated_records: list[str] = field(default_factory=list)
    skipped_records: list[str] = field(default_factory=list)
    missing_media: list[str] = field(default_factory=list)
    unmapped_enum_values: list[str] = field(default_factory=list)
    validation_failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "imported_records": self.imported_records,
            "updated_records": self.updated_records,
            "skipped_records": self.skipped_records,
            "missing_media": self.missing_media,
            "unmapped_enum_values": self.unmapped_enum_values,
            "validation_failures": self.validation_failures,
        }


class FreeExerciseDbImporter:
    def __init__(
        self,
        db: Session,
        *,
        settings: Settings,
        source_root: Path,
        translator: ExerciseTranslator | None,
        dry_run: bool = False,
    ) -> None:
        self._db = db
        self._settings = settings
        self._source_root = source_root
        self._translator = translator
        self._dry_run = dry_run
        self._created_media: list[Path] = []

    def run(self, *, limit: int | None = None) -> ImportReport:
        report = ImportReport()
        pending: list[tuple[ImportCandidate, Exercise | None]] = []
        for raw_record in self._load_records(limit):
            candidate = self._parse_candidate(raw_record, report)
            if candidate is None:
                source_id = self._source_id_for_report(raw_record)
                report.skipped_records.append(source_id)
                continue
            existing = self._existing_exercise(candidate.source_id)
            if existing is not None and self._is_current(existing, candidate):
                report.skipped_records.append(candidate.source_id)
                continue
            pending.append((candidate, existing))

        if self._dry_run:
            for candidate, existing in pending:
                if existing is None:
                    report.imported_records.append(candidate.source_id)
                else:
                    report.updated_records.append(candidate.source_id)
            return report

        translations = self._translate(pending, report)
        try:
            for candidate, existing in pending:
                translation = translations.get(candidate.source_id)
                if translation is None:
                    report.skipped_records.append(candidate.source_id)
                    continue
                self._save_candidate(candidate, existing, translation, report)
            self._db.commit()
        except Exception:
            self._db.rollback()
            self._discard_created_media()
            raise
        return report

    def _load_records(self, limit: int | None) -> list[dict[str, object]]:
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        source_file = self._source_root / "data" / "exercises.json"
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"Source dataset does not exist: {source_file}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Source dataset is invalid JSON: {source_file}") from error
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError("Source dataset must be a list of exercise objects")
        records = [dict(item) for item in payload]
        return records if limit is None else records[:limit]

    def _parse_candidate(
        self,
        raw_record: dict[str, object],
        report: ImportReport,
    ) -> ImportCandidate | None:
        source_id = self._required_text(raw_record, "id")
        name_en = self._required_text(raw_record, "name")
        if source_id is None or name_en is None:
            report.validation_failures.append(
                f"{self._source_id_for_report(raw_record)}: id and name must be text values"
            )
            return None
        aliases = self._text_list(raw_record, "aliases", source_id, report)
        steps = self._text_list(raw_record, "steps", source_id, report)
        secondary_names = self._text_list(raw_record, "secondaryMuscles", source_id, report)
        form_cues = self._text_list(raw_record, "formCues", source_id, report)
        common_mistakes = self._text_list(raw_record, "commonMistakes", source_id, report)
        body_part = self._required_text(raw_record, "bodyPart")
        target = self._required_text(raw_record, "target")
        equipment_name = self._required_text(raw_record, "equipment")
        difficulty_name = self._required_text(raw_record, "difficulty")
        if (
            aliases is None
            or steps is None
            or secondary_names is None
            or form_cues is None
            or common_mistakes is None
            or body_part is None
            or target is None
            or equipment_name is None
            or difficulty_name is None
        ):
            return None
        body_region = map_body_region(body_part)
        primary_muscle = map_muscle_group(target)
        equipment = map_equipment(equipment_name)
        difficulty = map_difficulty(difficulty_name)
        if body_region is None:
            self._add_unmapped(report, f"bodyPart:{body_part}")
        if primary_muscle is None:
            self._add_unmapped(report, f"target:{target}")
        if equipment is None:
            self._add_unmapped(report, f"equipment:{equipment_name}")
        if difficulty is None:
            self._add_unmapped(report, f"difficulty:{difficulty_name}")
        if equipment is None or difficulty is None:
            return None
        secondary_muscles: list[MuscleGroup] = []
        for secondary_name in secondary_names:
            secondary = map_muscle_group(secondary_name)
            if secondary is None:
                self._add_unmapped(report, f"secondaryMuscles:{secondary_name}")
            elif secondary not in secondary_muscles:
                secondary_muscles.append(secondary)
        instructions = self._required_text(raw_record, "instructions")
        if instructions is None:
            report.validation_failures.append(f"{source_id}: instructions must be text")
            return None
        if len(steps) < 3:
            report.validation_failures.append(
                f"{source_id}: steps must contain at least three items"
            )
            return None
        normalized_instructions = self._normalize_instruction_steps(steps)
        programming_metadata = classify_programming_metadata(
            name_en=name_en,
            primary_muscle=primary_muscle,
            instructions_en=[instructions],
            steps_en=steps,
            form_cues_en=form_cues,
            common_mistakes_en=common_mistakes,
        )
        primary_muscle = refine_primary_muscle(
            primary_muscle,
            name_en,
            programming_metadata.movement_pattern,
        )
        classification = classify_muscle_focus(
            primary_muscle=primary_muscle,
            source_target=target,
            source_muscle_group=self._optional_text(raw_record, "muscleGroup"),
            secondary_targets=secondary_names,
            name_en=name_en,
            movement_pattern=programming_metadata.movement_pattern,
            exercise_type=programming_metadata.exercise_type,
            instructions_en=[instructions, *steps],
        )
        if primary_muscle is not None and classification is None:
            report.validation_failures.append(f"{source_id}: muscle focus is unresolved")
            return None
        muscle_focus = classification.focus if classification is not None else None
        secondary_muscles = [
            muscle for muscle in secondary_muscles if muscle is not primary_muscle
        ]
        labels = classify_exercise_labels(
            body_part=body_part,
            target=target,
            exercise_type=programming_metadata.exercise_type,
        )
        media_assets = self._media_assets(raw_record, source_id, report)
        if not any(asset.role is MediaRole.VIDEO for asset in media_assets):
            report.validation_failures.append(
                f"{source_id}: at least one local video asset is required"
            )
            return None
        return ImportCandidate(
            source_id=source_id,
            source_metadata=raw_record,
            slug=self._slug_for(source_id, name_en),
            name_en=name_en,
            body_region=body_region,
            primary_muscle=primary_muscle,
            muscle_focus=muscle_focus,
            labels=labels,
            secondary_muscles=secondary_muscles,
            equipment=[equipment],
            difficulty=difficulty,
            programming_metadata=programming_metadata,
            aliases_en=aliases,
            short_description_en=self._optional_text(raw_record, "shortDescription"),
            instructions_en=normalized_instructions,
            steps_en=steps,
            form_cues_en=form_cues,
            common_mistakes_en=common_mistakes,
            breathing_en=self._optional_text(raw_record, "breathing"),
            media_assets=media_assets,
        )

    def _text_list(
        self,
        record: Mapping[str, object],
        field_name: str,
        source_id: str,
        report: ImportReport,
    ) -> list[str] | None:
        value = record.get(field_name)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            report.validation_failures.append(
                f"{source_id}: {field_name} must be a list of text values"
            )
            return None
        return [item.strip() for item in value]

    def _media_assets(
        self,
        record: Mapping[str, object],
        source_id: str,
        report: ImportReport,
    ) -> list[ImportMediaAsset]:
        assets: list[ImportMediaAsset] = []
        configurations = (
            ("videos", MediaRole.VIDEO, MediaType.VIDEO, "videos"),
            ("thumbnails", MediaRole.THUMBNAIL, MediaType.IMAGE, "thumbnails"),
        )
        for source_field, role, media_type, directory in configurations:
            urls = record.get(source_field)
            url_map = urls if isinstance(urls, Mapping) else {}
            for label, presentation in (
                ("male", MediaPresentation.MALE),
                ("female", MediaPresentation.FEMALE),
            ):
                value = url_map.get(label)
                if not isinstance(value, str) or not value:
                    report.missing_media.append(f"{source_id}:{label}:{role.value}")
                    continue
                filename = Path(urlsplit(value).path).name
                if not filename or filename != Path(filename).name:
                    report.validation_failures.append(
                        f"{source_id}: invalid {label} {role.value} URL"
                    )
                    continue
                source_path = self._source_root / directory / label / filename
                if not source_path.is_file():
                    report.missing_media.append(f"{source_id}:{label}:{role.value}")
                    continue
                assets.append(
                    ImportMediaAsset(
                        presentation=presentation,
                        role=role,
                        source_url=value,
                        source_path=source_path,
                        media_type=media_type,
                    )
                )
        return assets

    def _existing_exercise(self, source_id: str) -> Exercise | None:
        return self._db.scalar(
            select(Exercise)
            .where(Exercise.source == SOURCE_NAME, Exercise.source_id == source_id)
            .options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.media_assets),
                selectinload(Exercise.caution_tag_items),
                selectinload(Exercise.labels),
            )
        )

    def _is_current(self, exercise: Exercise, candidate: ImportCandidate) -> bool:
        expected_assets = {
            (asset.presentation, asset.role, asset.source_url) for asset in candidate.media_assets
        }
        actual_assets = {
            (asset.presentation, asset.role, asset.media_source_url)
            for asset in exercise.media_assets
        }
        return (
            exercise.source_metadata_en == candidate.source_metadata
            and actual_assets == expected_assets
            and all(self._stored_media_exists(asset.media_path) for asset in exercise.media_assets)
            and exercise.movement_pattern is candidate.programming_metadata.movement_pattern
            and exercise.primary_muscle is candidate.primary_muscle
            and exercise.muscle_focus is candidate.muscle_focus
            and exercise.exercise_type is candidate.programming_metadata.exercise_type
            and exercise.is_programmable is True
            and {item.label for item in exercise.labels} == set(candidate.labels)
            and {item.caution_tag for item in exercise.caution_tag_items}
            == set(candidate.programming_metadata.caution_tags)
        )

    def _stored_media_exists(self, public_path: str) -> bool:
        public_root = self._settings.media_public_path.rstrip("/")
        prefix = f"{public_root}/"
        if not public_path.startswith(prefix):
            return False
        relative_path = Path(public_path.removeprefix(prefix))
        if ".." in relative_path.parts:
            return False
        return (self._settings.media_root / relative_path).is_file()

    def _translate(
        self,
        pending: list[tuple[ImportCandidate, Exercise | None]],
        report: ImportReport,
    ) -> dict[str, ExerciseTranslation]:
        if not pending:
            return {}
        if self._translator is None:
            raise RuntimeError("OpenCode Zen translation is not configured")
        translations = self._translator.translate([candidate for candidate, _ in pending])
        for candidate, _ in pending:
            translation = translations.get(candidate.source_id)
            if translation is None:
                report.validation_failures.append(f"{candidate.source_id}: translation is missing")
                continue
            if not translation.name_fa.strip() or len(translation.instructions_fa) != len(
                candidate.instructions_en
            ):
                report.validation_failures.append(f"{candidate.source_id}: translation is invalid")
        return translations

    def _save_candidate(
        self,
        candidate: ImportCandidate,
        existing: Exercise | None,
        translation: ExerciseTranslation,
        report: ImportReport,
    ) -> None:
        if not translation.name_fa.strip() or len(translation.instructions_fa) != len(
            candidate.instructions_en
        ):
            report.skipped_records.append(candidate.source_id)
            return
        copied_paths: list[Path] = []
        try:
            stored_assets = []
            for asset in candidate.media_assets:
                public_path, absolute_path = self._copy_media(asset)
                if absolute_path is not None:
                    copied_paths.append(absolute_path)
                stored_assets.append((asset, public_path))
            with self._db.begin_nested():
                exercise = existing or Exercise(slug=candidate.slug)
                if existing is None:
                    self._db.add(exercise)
                self._apply_candidate(exercise, candidate, translation, stored_assets)
                self._db.flush()
        except (MediaValidationError, OSError, ValueError) as error:
            for path in copied_paths:
                path.unlink(missing_ok=True)
                if path in self._created_media:
                    self._created_media.remove(path)
            report.validation_failures.append(f"{candidate.source_id}: {error}")
            report.skipped_records.append(candidate.source_id)
            return
        if existing is None:
            report.imported_records.append(candidate.source_id)
        else:
            report.updated_records.append(candidate.source_id)

    def _apply_candidate(
        self,
        exercise: Exercise,
        candidate: ImportCandidate,
        translation: ExerciseTranslation,
        stored_assets: list[tuple[ImportMediaAsset, str]],
    ) -> None:
        default_asset, default_path = next(
            (item for item in stored_assets if item[0].role is MediaRole.VIDEO), stored_assets[0]
        )
        exercise.name_en = candidate.name_en
        exercise.name_fa = translation.name_fa.strip()
        exercise.body_region = candidate.body_region
        exercise.primary_muscle = candidate.primary_muscle
        exercise.muscle_focus = candidate.muscle_focus
        exercise.difficulty = candidate.difficulty
        exercise.movement_pattern = candidate.programming_metadata.movement_pattern
        exercise.exercise_type = candidate.programming_metadata.exercise_type
        exercise.instructions_en = candidate.instructions_en
        exercise.instructions_fa = [item.strip() for item in translation.instructions_fa]
        exercise.safety_notes_en = []
        exercise.safety_notes_fa = []
        exercise.media_path = default_path
        exercise.media_type = default_asset.media_type
        exercise.media_source_url = default_asset.source_url
        exercise.media_license = None
        exercise.media_attribution = None
        exercise.source = SOURCE_NAME
        exercise.source_id = candidate.source_id
        exercise.aliases_en = candidate.aliases_en
        exercise.short_description_en = candidate.short_description_en
        exercise.steps_en = candidate.steps_en
        exercise.form_cues_en = candidate.form_cues_en
        exercise.common_mistakes_en = candidate.common_mistakes_en
        exercise.breathing_en = candidate.breathing_en
        exercise.source_metadata_en = candidate.source_metadata
        exercise.needs_review = True
        exercise.is_active = True
        exercise.is_programmable = True
        self._sync_secondary_muscles(exercise, candidate.secondary_muscles)
        self._sync_equipment(exercise, candidate.equipment)
        self._sync_caution_tags(exercise, candidate.programming_metadata.caution_tags)
        self._sync_labels(exercise, candidate.labels)
        self._sync_media_assets(exercise, stored_assets)

    @staticmethod
    def _sync_secondary_muscles(exercise: Exercise, desired: list[MuscleGroup]) -> None:
        desired_set = set(desired)
        for item in list(exercise.secondary_muscles):
            if item.muscle not in desired_set:
                exercise.secondary_muscles.remove(item)
        existing = {item.muscle for item in exercise.secondary_muscles}
        exercise.secondary_muscles.extend(
            ExerciseSecondaryMuscle(muscle=muscle) for muscle in desired if muscle not in existing
        )

    @staticmethod
    def _sync_equipment(exercise: Exercise, desired: list[Equipment]) -> None:
        desired_set = set(desired)
        for item in list(exercise.equipment_items):
            if item.equipment not in desired_set:
                exercise.equipment_items.remove(item)
        existing = {item.equipment for item in exercise.equipment_items}
        exercise.equipment_items.extend(
            ExerciseEquipment(equipment=equipment)
            for equipment in desired
            if equipment not in existing
        )

    @staticmethod
    def _sync_caution_tags(
        exercise: Exercise,
        desired: tuple[ExerciseCautionTag, ...],
    ) -> None:
        desired_set = set(desired)
        for item in list(exercise.caution_tag_items):
            if item.caution_tag not in desired_set:
                exercise.caution_tag_items.remove(item)
        existing = {item.caution_tag for item in exercise.caution_tag_items}
        exercise.caution_tag_items.extend(
            ExerciseCautionTagItem(caution_tag=caution_tag)
            for caution_tag in desired
            if caution_tag not in existing
        )

    @staticmethod
    def _sync_labels(exercise: Exercise, desired: tuple[ExerciseLabel, ...]) -> None:
        desired_set = set(desired)
        for item in list(exercise.labels):
            if item.label not in desired_set:
                exercise.labels.remove(item)
        existing = {item.label for item in exercise.labels}
        exercise.labels.extend(
            ExerciseLabelItem(label=label) for label in desired if label not in existing
        )

    @staticmethod
    def _sync_media_assets(
        exercise: Exercise,
        desired: list[tuple[ImportMediaAsset, str]],
    ) -> None:
        desired_keys = {(asset.presentation, asset.role) for asset, _ in desired}
        for item in list(exercise.media_assets):
            if (item.presentation, item.role) not in desired_keys:
                exercise.media_assets.remove(item)
        existing = {(item.presentation, item.role): item for item in exercise.media_assets}
        for asset, public_path in desired:
            media_item: ExerciseMediaAsset | None = existing.get((asset.presentation, asset.role))
            if media_item is None:
                media_item = ExerciseMediaAsset(
                    presentation=asset.presentation,
                    role=asset.role,
                )
                exercise.media_assets.append(media_item)
            media_item.media_path = public_path
            media_item.media_type = asset.media_type
            media_item.media_source_url = asset.source_url
            media_item.media_license = None
            media_item.media_attribution = None

    def _copy_media(self, asset: ImportMediaAsset) -> tuple[str, Path | None]:
        source_size = asset.source_path.stat().st_size
        if source_size == 0:
            raise MediaValidationError("Media file cannot be empty")
        if source_size > self._settings.import_media_max_bytes:
            raise MediaValidationError(
                f"Media file exceeds the {self._settings.import_media_max_bytes} bytes limit"
            )
        with asset.source_path.open("rb") as file_handle:
            signature = _signature_extension(file_handle.read(64))
        expected_extension = ".mp4" if asset.media_type is MediaType.VIDEO else ".jpg"
        if signature != expected_extension:
            raise MediaValidationError("Media signature does not match its expected type")
        digest = self._sha256(asset.source_path)
        relative_path = Path(SOURCE_NAME) / digest[:2] / f"{digest}{expected_extension}"
        destination = self._settings.media_root / relative_path
        public_path = f"{self._settings.media_public_path.rstrip('/')}/{relative_path.as_posix()}"
        if destination.exists():
            return public_path, None
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=".import-", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                with asset.source_path.open("rb") as source_file:
                    shutil.copyfileobj(source_file, temporary)
            os.replace(temporary_path, destination)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
        self._created_media.append(destination)
        return public_path, destination

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_handle:
            while chunk := file_handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _discard_created_media(self) -> None:
        for path in self._created_media:
            path.unlink(missing_ok=True)
        self._created_media.clear()

    @staticmethod
    def _required_text(record: Mapping[str, object], field_name: str) -> str | None:
        value = record.get(field_name)
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()

    @staticmethod
    def _optional_text(record: Mapping[str, object], field_name: str) -> str | None:
        value = record.get(field_name)
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _source_id_for_report(record: Mapping[str, object]) -> str:
        value = record.get("id")
        return value if isinstance(value, str) and value else "<unknown>"

    @staticmethod
    def _add_unmapped(report: ImportReport, value: str) -> None:
        if value not in report.unmapped_enum_values:
            report.unmapped_enum_values.append(value)

    @staticmethod
    def _normalize_instruction_steps(steps: list[str]) -> list[str]:
        normalized = list(steps)
        while len(normalized) > 6:
            normalized[-2:] = [f"{normalized[-2]} {normalized[-1]}"]
        return normalized

    @staticmethod
    def _slug_for(source_id: str, name_en: str) -> str:
        def normalize(value: str) -> str:
            characters = [character.lower() if character.isalnum() else "-" for character in value]
            return "-".join(part for part in "".join(characters).split("-") if part)

        prefix = f"fedb-{normalize(source_id)}"
        available = 120 - len(prefix) - 1
        suffix = normalize(name_en)[:available].strip("-") or "exercise"
        return f"{prefix}-{suffix}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import the local Free Exercise DB dataset")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    translator = None if args.dry_run else CuratedExerciseTranslator(CURATED_TRANSLATIONS)
    with Session(get_engine(settings.database_url)) as db:
        report = FreeExerciseDbImporter(
            db,
            settings=settings,
            source_root=args.source_root.resolve(),
            translator=translator,
            dry_run=args.dry_run,
        ).run(limit=args.limit)
    rendered_report = json.dumps(report.as_dict(), ensure_ascii=False, indent=2)
    if args.report is not None:
        args.report.write_text(rendered_report + "\n", encoding="utf-8")
    print(rendered_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
