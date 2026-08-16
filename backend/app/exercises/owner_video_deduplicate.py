from __future__ import annotations

import argparse
import json
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.enums import ExerciseContentType
from app.exercises.models import Exercise


@dataclass
class DeduplicationReport:
    candidate_groups: int = 0
    candidate_exercises: int = 0
    media_assets_to_move: int = 0
    blocked_exercises: int = 0
    merged_exercises: int = 0
    moved_media_assets: int = 0
    groups: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        return payload


def _normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.casefold()).replace("\u200c", " ")
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized).split()
    )


def _group_key(exercise: Exercise) -> tuple[str, str]:
    return _normalized_name(exercise.name_en), _normalized_name(exercise.name_fa)


def _canonical_rank(exercise: Exercise) -> tuple[int, object, str]:
    source_priority = {
        "free-exercise-db": 0,
        "fitsho_training_template": 1,
        "owner-video": 2,
    }
    return source_priority.get(exercise.source or "", 3), exercise.created_at, str(exercise.id)


def _candidate_groups(db: Session) -> list[tuple[Exercise, list[Exercise]]]:
    exercises = db.scalars(
        select(Exercise)
        .where(Exercise.content_type == ExerciseContentType.EXERCISE)
        .options(selectinload(Exercise.media_assets))
        .order_by(Exercise.created_at, Exercise.id)
    ).all()
    grouped: defaultdict[tuple[str, str], list[Exercise]] = defaultdict(list)
    for exercise in exercises:
        grouped[_group_key(exercise)].append(exercise)

    candidates: list[tuple[Exercise, list[Exercise]]] = []
    for exercises_with_same_name in grouped.values():
        if len(exercises_with_same_name) < 2:
            continue
        canonical = min(exercises_with_same_name, key=_canonical_rank)
        duplicates = [item for item in exercises_with_same_name if item.id != canonical.id]
        candidates.append((canonical, duplicates))
    return sorted(candidates, key=lambda item: (_group_key(item[0]), str(item[0].id)))


def _has_conflicting_reference(db: Session, canonical_id: UUID, duplicate_id: UUID) -> bool:
    workout_conflict = db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM workout_plan_exercises duplicate_slot
                JOIN workout_plan_exercises canonical_slot
                  ON canonical_slot.workout_day_id = duplicate_slot.workout_day_id
                 AND canonical_slot.exercise_id = :canonical_id
                WHERE duplicate_slot.exercise_id = :duplicate_id
            )
            """
        ),
        {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
    ).scalar_one()
    alternative_reference = db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM exercise_alternatives
                WHERE exercise_id = :duplicate_id OR alternative_exercise_id = :duplicate_id
            )
            """
        ),
        {"duplicate_id": duplicate_id},
    ).scalar_one()
    return bool(workout_conflict or alternative_reference)


def _move_media_assets(db: Session, canonical: Exercise, duplicate: Exercise) -> int:
    assets = sorted(
        duplicate.media_assets,
        key=lambda asset: (asset.presentation, asset.role, asset.sort_order, str(asset.id)),
    )
    moved = 0
    for asset in assets:
        current_orders = [
            item.sort_order
            for item in canonical.media_assets
            if item.presentation == asset.presentation and item.role == asset.role
        ]
        asset.sort_order = max(current_orders, default=-1) + 1
        duplicate.media_assets.remove(asset)
        asset.exercise = canonical
        canonical.media_assets.append(asset)
        db.flush()
        moved += 1
    return moved


def _merge_one(db: Session, canonical: Exercise, duplicate: Exercise) -> int:
    if _has_conflicting_reference(db, canonical.id, duplicate.id):
        raise ValueError(f"Exercise {duplicate.id} has a conflicting reference")

    for table_name, column_name in (
        ("exercise_secondary_muscles", "muscle"),
        ("exercise_equipment", "equipment"),
        ("exercise_caution_tags", "caution_tag"),
        ("exercise_label_items", "label"),
    ):
        db.execute(
            text(
                f"INSERT INTO {table_name} (exercise_id, {column_name}) "
                f"SELECT :canonical_id, {column_name} FROM {table_name} "
                "WHERE exercise_id = :duplicate_id ON CONFLICT DO NOTHING"
            ),
            {"canonical_id": canonical.id, "duplicate_id": duplicate.id},
        )
    db.execute(
        text(
            "UPDATE workout_plan_exercises SET exercise_id = :canonical_id "
            "WHERE exercise_id = :duplicate_id"
        ),
        {"canonical_id": canonical.id, "duplicate_id": duplicate.id},
    )
    db.execute(
        text(
            "UPDATE training_program_template_slots SET exercise_id = :canonical_id "
            "WHERE exercise_id = :duplicate_id"
        ),
        {"canonical_id": canonical.id, "duplicate_id": duplicate.id},
    )
    moved = _move_media_assets(db, canonical, duplicate)
    db.delete(duplicate)
    db.flush()
    return moved


def merge_duplicate_exercises(db: Session, *, apply: bool) -> DeduplicationReport:
    report = DeduplicationReport()
    for canonical, duplicates in _candidate_groups(db):
        blocked = [
            duplicate
            for duplicate in duplicates
            if _has_conflicting_reference(db, canonical.id, duplicate.id)
        ]
        mergeable = [duplicate for duplicate in duplicates if duplicate not in blocked]
        media_count = sum(len(duplicate.media_assets) for duplicate in mergeable)
        report.candidate_groups += 1
        report.candidate_exercises += len(mergeable)
        report.media_assets_to_move += media_count
        report.blocked_exercises += len(blocked)
        report.groups.append(
            {
                "name_en": canonical.name_en,
                "name_fa": canonical.name_fa,
                "canonical_id": str(canonical.id),
                "duplicate_ids": [str(item.id) for item in mergeable],
                "blocked_ids": [str(item.id) for item in blocked],
                "media_assets_to_move": media_count,
            }
        )
        if not apply:
            continue
        for duplicate in mergeable:
            report.moved_media_assets += _merge_one(db, canonical, duplicate)
            report.merged_exercises += 1
    if apply:
        db.commit()
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge exact duplicate exercise cards safely")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        report = merge_duplicate_exercises(db, apply=args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 1 if report.blocked_exercises else 0


if __name__ == "__main__":
    raise SystemExit(main())
