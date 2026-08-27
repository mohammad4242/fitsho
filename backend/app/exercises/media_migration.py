from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.exercises.enums import MediaType
from app.exercises.media_resolver import is_valid_media_asset, resolve_primary_media
from app.exercises.models import Exercise, ExerciseMediaAsset

VIDEO_EXTENSIONS = {".gif", ".mkv", ".mp4", ".webm"}
PLACEHOLDER_TOKEN = "placeholder"
MANIFEST_VERSION = 1


class MediaMigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceRoot:
    label: str
    path: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def exercise_folder(slug: str, exercise_id: UUID | str) -> str:
    return f"{slug}--{str(exercise_id).replace('-', '')[:8]}"


def destination_relative_path(
    *,
    slug: str,
    exercise_id: UUID | str,
    digest: str,
    extension: str,
) -> Path:
    return Path("exercises") / exercise_folder(slug, exercise_id) / f"media-{digest}{extension}"


def _public_path(settings: Settings, relative_path: Path) -> str:
    return f"{settings.media_public_path.rstrip('/')}/{relative_path.as_posix()}"


def _json_value(value: object) -> object:
    return getattr(value, "value", value)


def _is_placeholder_path(path: str) -> bool:
    return PLACEHOLDER_TOKEN in path.casefold()


def _safe_relative_public_path(public_path: str, settings: Settings) -> Path | None:
    prefix = f"{settings.media_public_path.rstrip('/')}/"
    if not public_path.startswith(prefix):
        return None
    relative = Path(public_path.removeprefix(prefix))
    if not relative.parts or ".." in relative.parts or relative.is_absolute():
        return None
    return relative


def resolve_source_path(
    public_path: str,
    *,
    settings: Settings,
    roots: tuple[SourceRoot, ...],
    seed_root: Path | None = None,
) -> Path | None:
    relative = _safe_relative_public_path(public_path, settings)
    if relative is not None:
        for root in roots:
            candidate = root.path / relative
            if candidate.is_file():
                return candidate
    if seed_root is not None and public_path.startswith("/exercises/"):
        candidate = seed_root / Path(public_path).name
        if candidate.is_file():
            return candidate
    return None


def _media_row(
    *,
    settings: Settings,
    exercise: Exercise | None,
    asset: ExerciseMediaAsset | None,
    current_path: str,
    source_path: Path | None,
    reference_kind: str,
    destination: Path | None,
) -> dict[str, object]:
    digest = sha256_file(source_path) if source_path is not None else None
    extension = source_path.suffix.lower() if source_path is not None else ""
    if source_path is not None and destination is None and exercise is not None:
        destination = settings.media_root / destination_relative_path(
            slug=exercise.slug,
            exercise_id=exercise.id,
            digest=digest or "",
            extension=extension,
        )
    destination_relative = (
        destination.relative_to(settings.media_root).as_posix() if destination is not None else None
    )
    return {
        "reference_kind": reference_kind,
        "exercise_id": str(exercise.id) if exercise is not None else None,
        "exercise_slug": exercise.slug if exercise is not None else None,
        "exercise_name_fa": exercise.name_fa if exercise is not None else None,
        "exercise_name_en": exercise.name_en if exercise is not None else None,
        "source": (
            _json_value(asset.source)
            if asset is not None and asset.source is not None
            else exercise.source
            if exercise is not None
            else None
        ),
        "source_id": (
            asset.source_id
            if asset is not None and asset.source_id is not None
            else exercise.source_id
            if exercise is not None
            else None
        ),
        "current_db_path": current_path,
        "current_physical_path": str(source_path) if source_path is not None else None,
        "media_asset_id": str(asset.id) if asset is not None else None,
        "presentation": _json_value(asset.presentation) if asset is not None else None,
        "role": _json_value(asset.role) if asset is not None else None,
        "sort_order": asset.sort_order if asset is not None else None,
        "media_type": _json_value(asset.media_type)
        if asset is not None
        else (_json_value(exercise.media_type) if exercise is not None else None),
        "file_size": source_path.stat().st_size if source_path is not None else None,
        "sha256": digest,
        "destination_sha256": None,
        "destination_relative_path": destination_relative,
        "destination_physical_path": str(destination) if destination is not None else None,
        "destination_public_path": (
            _public_path(settings, Path(destination_relative))
            if destination_relative is not None
            else None
        ),
        "exists_before": bool(destination is not None and destination.is_file()),
        "copied": False,
        "hash_verified": False,
        "db_updated": False,
        "placeholder": _is_placeholder_path(current_path),
        "missing_before": source_path is None and not _is_placeholder_path(current_path),
    }


def _iter_video_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() in VIDEO_EXTENSIONS
        ),
        key=lambda path: path.as_posix(),
    )


def _physical_storage_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in _iter_video_files(root):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"exercises", "media-migration-source"}:
            continue
        files.append(path)
    return files


def _load_exercises(db: Session) -> list[Exercise]:
    return list(db.scalars(select(Exercise).options(selectinload(Exercise.media_assets))).unique())


def _destination_for_key(
    *,
    settings: Settings,
    exercise: Exercise | None,
    digest: str,
    extension: str,
    orphan_label: str | None = None,
) -> Path:
    if exercise is not None:
        relative = destination_relative_path(
            slug=exercise.slug,
            exercise_id=exercise.id,
            digest=digest,
            extension=extension,
        )
    else:
        safe_label = (
            "-".join(item for item in (orphan_label or "unknown").casefold().split("-") if item)
            or "unknown"
        )
        relative = Path("exercises") / "_unreferenced" / safe_label / f"media-{digest}{extension}"
    return settings.media_root / relative


def build_inventory(
    db: Session,
    *,
    settings: Settings,
    source_roots: tuple[SourceRoot, ...],
    seed_root: Path | None = None,
) -> dict[str, object]:
    exercises = _load_exercises(db)
    rows: list[dict[str, object]] = []
    reference_source_paths: set[Path] = set()
    destination_by_key: dict[tuple[str, str, str], Path] = {}
    destination_by_digest: dict[tuple[str, str], Path] = {}

    for exercise in exercises:
        for asset in exercise.media_assets:
            source_path = resolve_source_path(
                asset.media_path,
                settings=settings,
                roots=source_roots,
                seed_root=seed_root,
            )
            if source_path is not None:
                reference_source_paths.add(source_path.resolve())
            if source_path is None or _is_placeholder_path(asset.media_path):
                rows.append(
                    _media_row(
                        settings=settings,
                        exercise=exercise,
                        asset=asset,
                        current_path=asset.media_path,
                        source_path=source_path,
                        reference_kind="asset",
                        destination=None,
                    )
                )
                continue
            digest = sha256_file(source_path)
            extension = source_path.suffix.lower()
            key = (str(exercise.id), digest, extension)
            destination = destination_by_key.setdefault(
                key,
                _destination_for_key(
                    settings=settings,
                    exercise=exercise,
                    digest=digest,
                    extension=extension,
                ),
            )
            destination_by_digest.setdefault((digest, extension), destination)
            rows.append(
                _media_row(
                    settings=settings,
                    exercise=exercise,
                    asset=asset,
                    current_path=asset.media_path,
                    source_path=source_path,
                    reference_kind="asset",
                    destination=destination,
                )
            )

        valid_assets = [asset for asset in exercise.media_assets if is_valid_media_asset(asset)]
        if valid_assets:
            continue
        source_path = resolve_source_path(
            exercise.media_path,
            settings=settings,
            roots=source_roots,
            seed_root=seed_root,
        )
        if source_path is not None:
            reference_source_paths.add(source_path.resolve())
        if source_path is None or _is_placeholder_path(exercise.media_path):
            rows.append(
                _media_row(
                    settings=settings,
                    exercise=exercise,
                    asset=None,
                    current_path=exercise.media_path,
                    source_path=source_path,
                    reference_kind="legacy",
                    destination=None,
                )
            )
            continue
        digest = sha256_file(source_path)
        extension = source_path.suffix.lower()
        key = (str(exercise.id), digest, extension)
        destination = destination_by_key.setdefault(
            key,
            _destination_for_key(
                settings=settings,
                exercise=exercise,
                digest=digest,
                extension=extension,
            ),
        )
        destination_by_digest.setdefault((digest, extension), destination)
        rows.append(
            _media_row(
                settings=settings,
                exercise=exercise,
                asset=None,
                current_path=exercise.media_path,
                source_path=source_path,
                reference_kind="legacy",
                destination=destination,
            )
        )

    for root in source_roots:
        for source_path in _physical_storage_files(root.path):
            resolved = source_path.resolve()
            if resolved in reference_source_paths:
                continue
            digest = sha256_file(source_path)
            extension = source_path.suffix.lower()
            orphan_destination: Path | None = destination_by_digest.get((digest, extension))
            if orphan_destination is None:
                orphan_destination = _destination_for_key(
                    settings=settings,
                    exercise=None,
                    digest=digest,
                    extension=extension,
                    orphan_label=root.label,
                )
                destination_by_digest[(digest, extension)] = orphan_destination
            rows.append(
                _media_row(
                    settings=settings,
                    exercise=None,
                    asset=None,
                    current_path="",
                    source_path=source_path,
                    reference_kind="orphan",
                    destination=orphan_destination,
                )
            )

    if seed_root is not None:
        for source_path in _iter_video_files(seed_root):
            digest = sha256_file(source_path)
            extension = source_path.suffix.lower()
            slug = source_path.stem
            seed_exercise = next((item for item in exercises if item.slug == slug), None)
            if seed_exercise is not None:
                key = (str(seed_exercise.id), digest, extension)
                destination = destination_by_key.setdefault(
                    key,
                    _destination_for_key(
                        settings=settings,
                        exercise=seed_exercise,
                        digest=digest,
                        extension=extension,
                    ),
                )
            else:
                destination = settings.media_root / "exercises" / "seed" / source_path.name
            rows.append(
                _media_row(
                    settings=settings,
                    exercise=seed_exercise,
                    asset=None,
                    current_path=f"/exercises/{source_path.name}",
                    source_path=source_path,
                    reference_kind="seed-static",
                    destination=destination,
                )
            )

    physical_files = {
        path.resolve() for root in source_roots for path in _physical_storage_files(root.path)
    }
    if seed_root is not None:
        physical_files.update(path.resolve() for path in _iter_video_files(seed_root))
    duplicate_paths = Counter(
        str(row["current_db_path"])
        for row in rows
        if row["current_db_path"] and not row["reference_kind"] == "orphan"
    )
    placeholder_count = sum(1 for row in rows if row["placeholder"])
    missing_count = sum(1 for row in rows if row["missing_before"])
    summary = {
        "database_exercises": len(exercises),
        "database_media_assets": sum(len(exercise.media_assets) for exercise in exercises),
        "database_references": sum(1 + len(exercise.media_assets) for exercise in exercises),
        "manifest_rows": len(rows),
        "valid_file_rows": sum(1 for row in rows if row["sha256"] is not None),
        "placeholder_references": placeholder_count,
        "missing_references": missing_count,
        "physical_video_files": len(physical_files),
        "distinct_sha256": len({row["sha256"] for row in rows if row["sha256"]}),
        "duplicate_db_path_groups": sum(1 for count in duplicate_paths.values() if count > 1),
        "duplicate_db_path_references": sum(
            count - 1 for count in duplicate_paths.values() if count > 1
        ),
        "source_roots": [{"label": root.label, "path": str(root.path)} for root in source_roots],
        "seed_root": str(seed_root) if seed_root is not None else None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return {
        "version": MANIFEST_VERSION,
        "summary": summary,
        "rows": rows,
    }


def write_inventory(manifest: dict[str, object], manifest_dir: Path) -> None:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    rows = manifest["rows"]
    if not isinstance(rows, list):
        raise MediaMigrationError("Manifest rows are invalid")
    (manifest_dir / "before_inventory.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (manifest_dir / "migration_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if rows:
        fieldnames = list(rows[0].keys())
        with (manifest_dir / "before_inventory.csv").open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def load_manifest(manifest_dir: Path) -> dict[str, object]:
    path = manifest_dir / "migration_manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MediaMigrationError(f"Manifest does not exist: {path}") from error
    if not isinstance(payload, dict) or payload.get("version") != MANIFEST_VERSION:
        raise MediaMigrationError("Unsupported media migration manifest")
    if not isinstance(payload.get("rows"), list):
        raise MediaMigrationError("Manifest rows are invalid")
    return payload


def copy_and_verify_row(row: dict[str, object]) -> None:
    if row.get("placeholder"):
        row["hash_verified"] = False
        return
    source_value = row.get("current_physical_path")
    destination_value = row.get("destination_physical_path")
    expected_digest = row.get("sha256")
    if not isinstance(source_value, str) or not isinstance(destination_value, str):
        raise MediaMigrationError("A media row has no source or destination")
    if not isinstance(expected_digest, str):
        raise MediaMigrationError("A media row has no source hash")
    source = Path(source_value)
    destination = Path(destination_value)
    if not source.is_file():
        raise MediaMigrationError(f"Source media is missing: {source}")
    if sha256_file(source) != expected_digest:
        raise MediaMigrationError(f"Source hash changed: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_file():
            raise MediaMigrationError(f"Destination hash mismatch: {destination}")
        destination_digest = sha256_file(destination)
        if destination_digest != expected_digest:
            raise MediaMigrationError(f"Destination hash mismatch: {destination}")
        row["copied"] = False
        row["destination_sha256"] = destination_digest
        row["hash_verified"] = True
        return
    shutil.copy2(source, destination)
    destination_digest = sha256_file(destination)
    if destination_digest != expected_digest:
        raise MediaMigrationError(f"Copied hash mismatch: {destination}")
    row["copied"] = True
    row["destination_sha256"] = destination_digest
    row["hash_verified"] = True


def _row_destination_map(manifest: dict[str, object]) -> dict[str, str]:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    return {
        str(row["media_asset_id"]): str(row["destination_public_path"])
        for row in rows
        if row.get("reference_kind") == "asset"
        and row.get("media_asset_id")
        and row.get("destination_public_path")
    }


def update_database_from_manifest(
    db: Session,
    *,
    settings: Settings,
    manifest: dict[str, object],
) -> int:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    asset_destinations = _row_destination_map(manifest)
    legacy_destinations = {
        str(row["exercise_id"]): str(row["destination_public_path"])
        for row in rows
        if row.get("reference_kind") == "legacy"
        and row.get("exercise_id")
        and row.get("destination_public_path")
    }
    exercises = _load_exercises(db)
    assets_updated = 0
    with db.begin_nested():
        for exercise in exercises:
            for asset in exercise.media_assets:
                destination = asset_destinations.get(str(asset.id))
                if destination is not None:
                    old_path = asset.media_path
                    asset.media_path = destination
                    assets_updated += 1
                    if asset.source is None:
                        if (
                            asset.media_attribution == "Provided by Fitsho project owner"
                            and not asset.media_source_url
                            and not old_path.startswith("/media/free-exercise-db/")
                            and not old_path.startswith("/media/owner-video/")
                        ):
                            asset.source = "admin"
                            asset.source_id = None
                        elif exercise.source == "free-exercise-db":
                            asset.source = "free-exercise-db"
                            asset.source_id = (
                                f"{exercise.source_id}:{asset.presentation.value}:"
                                f"{asset.sort_order}"
                            )
            primary = resolve_primary_media(exercise)
            if any(is_valid_media_asset(asset) for asset in exercise.media_assets):
                exercise.media_path = primary.path
                exercise.media_type = primary.media_type
            else:
                destination = legacy_destinations.get(str(exercise.id))
                if destination is not None:
                    exercise.media_path = destination
                    exercise.media_type = MediaType(
                        next(
                            str(row["media_type"])
                            for row in rows
                            if row.get("reference_kind") == "legacy"
                            and row.get("exercise_id") == str(exercise.id)
                            and row.get("media_type")
                        )
                    )
        db.flush()
    db.commit()
    return assets_updated


def mark_database_updated(manifest: dict[str, object]) -> None:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    for row in rows:
        if row.get("destination_public_path") and row.get("hash_verified"):
            row["db_updated"] = True


def audit_manifest(
    db: Session,
    *,
    settings: Settings,
    manifest: dict[str, object],
    fallback_roots: tuple[Path, ...] = (),
) -> dict[str, object]:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    source_files = {
        str(row["current_physical_path"])
        for row in rows
        if row.get("current_physical_path") and row.get("sha256")
    }
    destination_files = {
        str(row["destination_physical_path"])
        for row in rows
        if row.get("destination_physical_path") and row.get("sha256")
    }

    def source_exists(path_value: str) -> bool:
        source = Path(path_value)
        if source.is_file():
            return True
        try:
            relative = source.relative_to(settings.media_root)
        except ValueError:
            relative = None
        if relative is not None and any((root / relative).is_file() for root in fallback_roots):
            return True
        staging_prefix = Path("/var/lib/fitsho/media-migration-source")
        try:
            staging_relative = source.relative_to(staging_prefix)
        except ValueError:
            return False
        return any(
            (root / staging_prefix.name / staging_relative).is_file() for root in fallback_roots
        )

    missing_sources = [path for path in sorted(source_files) if not source_exists(path)]
    hash_mismatches: list[str] = []
    for row in rows:
        if not row.get("sha256") or not row.get("destination_physical_path"):
            continue
        destination = Path(str(row["destination_physical_path"]))
        if not destination.is_file():
            hash_mismatches.append(str(destination))
            continue
        destination_digest = sha256_file(destination)
        row["destination_sha256"] = destination_digest
        if destination_digest != row["sha256"]:
            hash_mismatches.append(str(destination))
    expected_destinations = {
        Path(path).resolve() for path in destination_files if Path(path).is_file()
    }
    exercises_root = settings.media_root / "exercises"
    actual_destinations = {path.resolve() for path in _iter_video_files(exercises_root)}
    orphan_destinations = sorted(str(path) for path in actual_destinations - expected_destinations)
    broken_db_paths: list[str] = []
    for exercise in _load_exercises(db):
        paths = [exercise.media_path, *(asset.media_path for asset in exercise.media_assets)]
        for public_path in paths:
            relative = _safe_relative_public_path(public_path, settings)
            if relative is not None and not (settings.media_root / relative).is_file():
                broken_db_paths.append(public_path)
    return {
        "TOTAL_SOURCE_FILES": len(source_files),
        "TOTAL_DESTINATION_FILES": len(actual_destinations),
        "TOTAL_DISTINCT_SHA256": len({row["sha256"] for row in rows if row.get("sha256")}),
        "HASHES_BEFORE": sum(1 for row in rows if row.get("sha256")),
        "HASHES_AFTER": sum(1 for row in rows if row.get("destination_sha256")),
        "MISSING_SOURCE_FILES": len(missing_sources),
        "HASH_MISMATCHES": len(hash_mismatches),
        "BROKEN_DB_PATHS": len(broken_db_paths),
        "ORPHAN_DESTINATION_FILES": len(orphan_destinations),
        "missing_source_paths": missing_sources,
        "hash_mismatch_paths": hash_mismatches,
        "broken_db_paths": broken_db_paths,
        "orphan_destination_paths": orphan_destinations,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Fitsho exercise media migration")
    parser.add_argument("command", choices=("inventory", "migrate", "audit", "rollback"))
    parser.add_argument("--manifest-dir", type=Path, default=Path("var/media-migration"))
    parser.add_argument("--source-root", action="append", type=Path, default=[])
    parser.add_argument("--legacy-root", action="append", type=Path, default=[])
    parser.add_argument("--seed-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    source_roots = tuple(
        [SourceRoot("active-media", path) for path in args.source_root]
        + [SourceRoot(f"legacy-media-{index}", path) for index, path in enumerate(args.legacy_root)]
    )
    if not source_roots:
        source_roots = (SourceRoot("active-media", settings.media_root),)
    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        if args.command == "inventory":
            manifest = build_inventory(
                db,
                settings=settings,
                source_roots=source_roots,
                seed_root=args.seed_root,
            )
            write_inventory(manifest, args.manifest_dir)
            print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        manifest = load_manifest(args.manifest_dir)
        if args.command == "migrate":
            rows = manifest["rows"]
            if not isinstance(rows, list):
                raise MediaMigrationError("Manifest rows are invalid")
            for row in rows:
                if not isinstance(row, dict):
                    raise MediaMigrationError("Manifest row is invalid")
                copy_and_verify_row(row)
            if not args.apply:
                write_inventory(manifest, args.manifest_dir)
                print("COPY_VERIFY_ONLY")
                return 0
            update_database_from_manifest(db, settings=settings, manifest=manifest)
            mark_database_updated(manifest)
            write_inventory(manifest, args.manifest_dir)
            print("COPY_VERIFY_DATABASE_UPDATE")
            return 0
        if args.command == "audit":
            report = audit_manifest(
                db,
                settings=settings,
                manifest=manifest,
                fallback_roots=tuple(args.legacy_root),
            )
            (args.manifest_dir / "audit_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return (
                0
                if all(
                    report[key] == 0
                    for key in ("MISSING_SOURCE_FILES", "HASH_MISMATCHES", "BROKEN_DB_PATHS")
                )
                else 1
            )
        rows = manifest["rows"]
        if not isinstance(rows, list):
            raise MediaMigrationError("Manifest rows are invalid")
        rollback_rows = [
            row
            for row in rows
            if isinstance(row, dict) and row.get("current_db_path") and row.get("db_updated")
        ]
        print(json.dumps({"rollback_dry_run": True, "rows": len(rollback_rows)}, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
