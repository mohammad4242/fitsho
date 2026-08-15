from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database.session import get_engine
from app.exercises.enums import MediaRole, MediaType
from app.exercises.models import (
    Exercise,
    ExerciseCautionTagItem,
    ExerciseEquipment,
    ExerciseLabelItem,
    ExerciseMediaAsset,
    ExerciseSecondaryMuscle,
)
from app.exercises.owner_video_analysis import (
    CatalogueExercise,
    CodexCliExerciseAnalyzer,
    OwnerVideoAnalysis,
    build_catalogue_snapshot,
    resolve_existing_match,
    resolve_presentation,
)
from app.exercises.owner_video_media import (
    PreparedOwnerVideo,
    PublishedOwnerVideo,
    prepare_owner_video,
    publish_owner_video,
    sha256_file,
)

OWNER_VIDEO_SOURCE = "owner-video"
ImportStatus = Literal[
    "matched_existing",
    "created_new",
    "duplicate_video",
    "needs_review",
    "failed",
]
PrepareVideo = Callable[..., PreparedOwnerVideo]
PublishVideo = Callable[..., PublishedOwnerVideo]


class ExerciseAnalyzer(Protocol):
    def analyze(
        self,
        prepared: PreparedOwnerVideo,
        catalogue: Sequence[CatalogueExercise],
    ) -> OwnerVideoAnalysis: ...


@dataclass(frozen=True)
class OwnerVideoImportItem:
    filename: str
    source_id: str | None
    status: ImportStatus
    exercise_id: str | None = None
    media_path: str | None = None
    reason: str | None = None
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class OwnerVideoImportReport:
    total: int = 0
    processed: int = 0
    matched_existing: int = 0
    created_new: int = 0
    duplicate_videos: int = 0
    needs_review: int = 0
    failed: int = 0
    items: list[OwnerVideoImportItem] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "processed": self.processed,
            "matched_existing": self.matched_existing,
            "created_new": self.created_new,
            "duplicate_videos": self.duplicate_videos,
            "needs_review": self.needs_review,
            "failed": self.failed,
            "items": [asdict(item) for item in self.items],
        }


class OwnerVideoImporter:
    def __init__(
        self,
        db: Session,
        *,
        settings: Settings,
        source_root: Path,
        analyzer: ExerciseAnalyzer,
        prepare_video: PrepareVideo = prepare_owner_video,
        publish_video: PublishVideo = publish_owner_video,
    ) -> None:
        self._db = db
        self._settings = settings
        self._source_root = source_root
        self._analyzer = analyzer
        self._prepare_video = prepare_video
        self._publish_video = publish_video

    def run(
        self,
        *,
        limit: int | None = None,
        apply: bool,
    ) -> OwnerVideoImportReport:
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        source_files = self._source_files()
        selected_files = source_files if limit is None else source_files[:limit]
        report = OwnerVideoImportReport(total=len(source_files))
        for source_path in selected_files:
            report.processed += 1
            self._process_file(source_path, apply=apply, report=report)
        return report

    def _source_files(self) -> list[Path]:
        if not self._source_root.is_dir():
            raise ValueError(f"Owner video source directory does not exist: {self._source_root}")
        return sorted(
            (
                path
                for path in self._source_root.iterdir()
                if path.is_file() and path.suffix.casefold() == ".mp4"
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )

    def _process_file(
        self,
        source_path: Path,
        *,
        apply: bool,
        report: OwnerVideoImportReport,
    ) -> None:
        source_id: str | None = None
        published: PublishedOwnerVideo | None = None
        try:
            source_id = sha256_file(source_path)
            duplicate = self._db.scalar(
                select(ExerciseMediaAsset).where(
                    ExerciseMediaAsset.source == OWNER_VIDEO_SOURCE,
                    ExerciseMediaAsset.source_id == source_id,
                )
            )
            if duplicate is not None:
                report.duplicate_videos += 1
                report.items.append(
                    OwnerVideoImportItem(
                        filename=source_path.name,
                        source_id=source_id,
                        status="duplicate_video",
                        exercise_id=str(duplicate.exercise_id),
                        media_path=duplicate.media_path,
                    )
                )
                return

            prepared = self._prepare_video(source_path, settings=self._settings)
            if prepared.source_id != source_id:
                raise ValueError("Prepared video digest does not match the original")
            catalogue = build_catalogue_snapshot(self._db)
            try:
                analysis = self._analyzer.analyze(prepared, catalogue)
            except Exception as error:
                analysis = self._fallback_analysis(source_path, source_id, error)
            match_id = resolve_existing_match(analysis, catalogue, self._settings)
            review_reasons = self._review_reasons(analysis, match_id)
            needs_review = bool(review_reasons)

            if not apply:
                self._record_dry_run(
                    source_path,
                    source_id,
                    match_id,
                    review_reasons,
                    report,
                )
                return

            published = self._publish_video(prepared, settings=self._settings)
            if match_id is not None:
                exercise = self._attach_to_existing(
                    match_id,
                    analysis,
                    source_id,
                    published,
                )
                status: ImportStatus = "matched_existing"
            else:
                exercise = self._create_exercise(
                    source_path,
                    analysis,
                    source_id,
                    published,
                    needs_review=needs_review,
                    review_reasons=review_reasons,
                )
                status = "needs_review" if needs_review else "created_new"
            self._db.commit()
        except Exception as error:
            self._db.rollback()
            if published is not None and published.created:
                published.absolute_path.unlink(missing_ok=True)
            report.failed += 1
            report.items.append(
                OwnerVideoImportItem(
                    filename=source_path.name,
                    source_id=source_id,
                    status="failed",
                    reason=self._failure_reason(error),
                )
            )
            return

        if match_id is not None:
            report.matched_existing += 1
        else:
            report.created_new += 1
            if needs_review:
                report.needs_review += 1
        report.items.append(
            OwnerVideoImportItem(
                filename=source_path.name,
                source_id=source_id,
                status=status,
                exercise_id=str(exercise.id),
                media_path=published.public_path,
                review_reasons=review_reasons,
            )
        )

    def _record_dry_run(
        self,
        source_path: Path,
        source_id: str,
        match_id: UUID | None,
        review_reasons: list[str],
        report: OwnerVideoImportReport,
    ) -> None:
        if match_id is not None:
            report.matched_existing += 1
            status: ImportStatus = "matched_existing"
            exercise_id = str(match_id)
        else:
            report.created_new += 1
            status = "needs_review" if review_reasons else "created_new"
            exercise_id = None
            if review_reasons:
                report.needs_review += 1
        report.items.append(
            OwnerVideoImportItem(
                filename=source_path.name,
                source_id=source_id,
                status=status,
                exercise_id=exercise_id,
                review_reasons=review_reasons,
            )
        )

    def _review_reasons(
        self,
        analysis: OwnerVideoAnalysis,
        match_id: UUID | None,
    ) -> list[str]:
        reasons = list(
            dict.fromkeys(reason.strip() for reason in analysis.review_reasons if reason)
        )
        if (
            analysis.identification_confidence
            < self._settings.owner_video_identification_confidence
        ):
            reasons.append("identification_confidence_below_threshold")
        if analysis.decision == "needs_review":
            reasons.append("codex_requested_review")
        if analysis.decision == "match_existing" and match_id is None:
            reasons.append("existing_match_not_corroborated")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _fallback_analysis(
        source_path: Path,
        source_id: str,
        error: Exception,
    ) -> OwnerVideoAnalysis:
        stem = source_path.stem[:100]
        failure_reason = OwnerVideoImporter._failure_reason(error)
        return OwnerVideoAnalysis.model_validate(
            {
                "source_id": source_id,
                "name_en": f"Owner Video Review {stem}",
                "name_fa": f"بازبینی ویدیوی مالک {stem}",
                "visible_text": [],
                "aliases_en": [],
                "body_region": "upper_body",
                "primary_muscle": "forearms",
                "muscle_focus": "general_forearms",
                "secondary_muscles": [],
                "equipment": ["other"],
                "difficulty": "beginner",
                "movement_pattern": "other",
                "exercise_type": "other",
                "labels": [],
                "caution_tags": ["other"],
                "instructions_en": [
                    "Review the attached owner video before programming this exercise.",
                    "Confirm the exercise identity and equipment.",
                    "Replace this placeholder metadata after review.",
                ],
                "instructions_fa": [
                    "پیش از برنامه‌ریزی، ویدیوی مالک پیوست‌شده را بازبینی کنید.",
                    "هویت حرکت و تجهیزات آن را تأیید کنید.",
                    "پس از بازبینی، این اطلاعات موقت را اصلاح کنید.",
                ],
                "safety_notes_en": ["Do not program until an administrator reviews this video."],
                "safety_notes_fa": ["تا زمان بازبینی ادمین، این حرکت را برنامه‌ریزی نکنید."],
                "short_description_en": "Owner video awaiting administrator review.",
                "short_description_fa": "ویدیوی مالک در انتظار بازبینی ادمین است.",
                "form_cues_en": [],
                "form_cues_fa": [],
                "common_mistakes_en": [],
                "common_mistakes_fa": [],
                "breathing_en": "Use controlled breathing after the exercise is identified.",
                "breathing_fa": "پس از شناسایی حرکت، تنفس کنترل‌شده داشته باشید.",
                "presentation": "unspecified",
                "presentation_confidence": 0.0,
                "identification_confidence": 0.0,
                "decision": "needs_review",
                "match_confidence": 0.0,
                "existing_exercise_id": None,
                "review_reasons": ["codex_analysis_failed", failure_reason],
            }
        )

    def _attach_to_existing(
        self,
        exercise_id: UUID,
        analysis: OwnerVideoAnalysis,
        source_id: str,
        published: PublishedOwnerVideo,
    ) -> Exercise:
        exercise = self._db.scalar(
            select(Exercise)
            .where(Exercise.id == exercise_id)
            .with_for_update()
            .options(selectinload(Exercise.media_assets))
        )
        if exercise is None:
            raise ValueError("Matched exercise no longer exists")
        presentation = resolve_presentation(analysis, self._settings)
        scoped_orders = [
            item.sort_order
            for item in exercise.media_assets
            if item.presentation is presentation and item.role is MediaRole.VIDEO
        ]
        exercise.media_assets.append(
            ExerciseMediaAsset(
                presentation=presentation,
                role=MediaRole.VIDEO,
                sort_order=max(scoped_orders, default=-1) + 1,
                media_path=published.public_path,
                media_type=MediaType.VIDEO,
                media_attribution="Fitsho owner-provided",
                source=OWNER_VIDEO_SOURCE,
                source_id=source_id,
            )
        )
        self._db.flush()
        return exercise

    def _create_exercise(
        self,
        source_path: Path,
        analysis: OwnerVideoAnalysis,
        source_id: str,
        published: PublishedOwnerVideo,
        *,
        needs_review: bool,
        review_reasons: list[str],
    ) -> Exercise:
        presentation = resolve_presentation(analysis, self._settings)
        source_metadata = analysis.model_dump(mode="json")
        source_metadata["review_reasons"] = review_reasons
        exercise = Exercise(
            slug=self._slug_for(source_id, analysis.name_en),
            name_en=analysis.name_en.strip(),
            name_fa=analysis.name_fa.strip(),
            body_region=analysis.body_region,
            primary_muscle=analysis.primary_muscle,
            muscle_focus=analysis.muscle_focus,
            difficulty=analysis.difficulty,
            movement_pattern=analysis.movement_pattern,
            exercise_type=analysis.exercise_type,
            instructions_en=[item.strip() for item in analysis.instructions_en],
            instructions_fa=[item.strip() for item in analysis.instructions_fa],
            safety_notes_en=[item.strip() for item in analysis.safety_notes_en],
            safety_notes_fa=[item.strip() for item in analysis.safety_notes_fa],
            media_path=published.public_path,
            media_type=MediaType.VIDEO,
            media_attribution="Fitsho owner-provided",
            source=OWNER_VIDEO_SOURCE,
            source_id=source_id,
            aliases_en=[item.strip() for item in analysis.aliases_en],
            short_description_en=analysis.short_description_en.strip(),
            steps_en=[item.strip() for item in analysis.instructions_en],
            form_cues_en=[item.strip() for item in analysis.form_cues_en],
            common_mistakes_en=[item.strip() for item in analysis.common_mistakes_en],
            breathing_en=analysis.breathing_en.strip(),
            source_metadata_en={
                "owner_video_filename": source_path.name,
                "owner_video_analysis": source_metadata,
            },
            needs_review=needs_review,
            is_active=True,
            is_programmable=not needs_review,
        )
        exercise.secondary_muscles.extend(
            ExerciseSecondaryMuscle(muscle=muscle)
            for muscle in dict.fromkeys(analysis.secondary_muscles)
            if muscle is not analysis.primary_muscle
        )
        exercise.equipment_items.extend(
            ExerciseEquipment(equipment=equipment)
            for equipment in dict.fromkeys(analysis.equipment)
        )
        exercise.caution_tag_items.extend(
            ExerciseCautionTagItem(caution_tag=caution)
            for caution in dict.fromkeys(analysis.caution_tags)
        )
        exercise.labels.extend(
            ExerciseLabelItem(label=label) for label in dict.fromkeys(analysis.labels)
        )
        exercise.media_assets.append(
            ExerciseMediaAsset(
                presentation=presentation,
                role=MediaRole.VIDEO,
                sort_order=0,
                media_path=published.public_path,
                media_type=MediaType.VIDEO,
                media_attribution="Fitsho owner-provided",
                source=OWNER_VIDEO_SOURCE,
                source_id=source_id,
            )
        )
        self._db.add(exercise)
        self._db.flush()
        return exercise

    @staticmethod
    def _slug_for(source_id: str, name_en: str) -> str:
        normalized = "-".join(re.findall(r"[a-z0-9]+", name_en.casefold()))
        prefix = f"owner-{source_id[:12]}"
        available = 120 - len(prefix) - 1
        suffix = normalized[:available].strip("-") or "exercise"
        return f"{prefix}-{suffix}"

    @staticmethod
    def _failure_reason(error: Exception) -> str:
        message = str(error).splitlines()[0].strip()
        return f"{type(error).__name__}: {message}" if message else type(error).__name__


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("limit must be at least 1")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import owner-provided exercise MP4 files with Codex analysis"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("../exercise-import/raw"),
    )
    parser.add_argument("--limit", type=positive_int)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def write_report(path: Path, report: OwnerVideoImportReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.parent / f".{path.name}-{uuid4().hex}.tmp"
    try:
        with staged.open("w", encoding="utf-8") as file_handle:
            json.dump(report.as_dict(), file_handle, ensure_ascii=False, indent=2)
            file_handle.write("\n")
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    analyzer = CodexCliExerciseAnalyzer(settings)
    with Session(get_engine(settings.database_url)) as db:
        report = OwnerVideoImporter(
            db,
            settings=settings,
            source_root=args.source_root.resolve(),
            analyzer=analyzer,
        ).run(limit=args.limit, apply=args.apply)
    write_report(args.report.resolve(), report)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
