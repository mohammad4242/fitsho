from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import posixpath
import shutil
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.exercises.enums import MediaType
from app.exercises.media_resolver import is_valid_media_asset, resolve_primary_media
from app.exercises.models import Exercise, ExerciseMediaAsset

VIDEO_EXTENSIONS = {".gif", ".mkv", ".mp4", ".webm"}
PLACEHOLDER_TOKEN = "placeholder"
MANIFEST_VERSION = 2
SUPPORTED_MANIFEST_VERSIONS = frozenset({1, MANIFEST_VERSION})

DISCOVERED = "DISCOVERED"
COPIED = "COPIED"
HASH_VERIFIED = "HASH_VERIFIED"
DB_UPDATED = "DB_UPDATED"
COMPLETED = "COMPLETED"
LIFECYCLE_STATES = frozenset({DISCOVERED, COPIED, HASH_VERIFIED, DB_UPDATED, COMPLETED})
_LIFECYCLE_RANK = {
    DISCOVERED: 0,
    COPIED: 1,
    HASH_VERIFIED: 2,
    DB_UPDATED: 3,
    COMPLETED: 4,
}
ROLLBACK_PLANNED = "planned"
ROLLBACK_ALREADY_RESTORED = "already-restored"
ROLLBACK_CONFLICT = "conflict"
ROLLBACK_MISSING = "missing"


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


def _validated_local_media_path(
    public_path: object,
    settings: Settings,
) -> tuple[Path | None, bool]:
    """Return a canonical media-relative path and whether the value is unsafe.

    Database media paths are public URL paths, never machine-local paths.  Keep
    this check in the migration audit so the resolver remains a database-only
    selection helper with no filesystem probing.
    """
    if not isinstance(public_path, str) or not public_path or public_path.strip() != public_path:
        return None, True
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in public_path):
        return None, True
    if "\\" in public_path:
        return None, True
    try:
        parsed = urlsplit(public_path)
    except ValueError:
        return None, True
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.path != public_path
    ):
        return None, True

    decoded = public_path
    for _ in range(8):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    if decoded != public_path or "%" in public_path or "\\" in decoded:
        return None, True
    if unicodedata.normalize("NFC", public_path) != public_path:
        return None, True

    prefix = settings.media_public_path.rstrip("/")
    if not prefix or not public_path.startswith(f"{prefix}/"):
        return None, True
    if posixpath.normpath(public_path) != public_path:
        return None, True

    relative_text = public_path.removeprefix(f"{prefix}/")
    relative = Path(relative_text)
    if (
        not relative.parts
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        return None, True

    media_root = settings.media_root.resolve()
    candidate = settings.media_root / relative
    try:
        resolved_candidate = candidate.resolve(strict=False)
        resolved_candidate.relative_to(media_root)
    except (OSError, RuntimeError, ValueError):
        return None, True
    return relative, False


def _is_explicit_placeholder_media_type(media_type: object) -> bool:
    return _json_value(media_type) == MediaType.PLACEHOLDER.value


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
    row = {
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
    _set_row_state(row, DISCOVERED)
    return row


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
        asset_rows: list[dict[str, object]] = []
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
                row = _media_row(
                    settings=settings,
                    exercise=exercise,
                    asset=asset,
                    current_path=asset.media_path,
                    source_path=source_path,
                    reference_kind="asset",
                    destination=None,
                )
                rows.append(row)
                asset_rows.append(row)
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
            row = _media_row(
                settings=settings,
                exercise=exercise,
                asset=asset,
                current_path=asset.media_path,
                source_path=source_path,
                reference_kind="asset",
                destination=destination,
            )
            rows.append(row)
            asset_rows.append(row)

        valid_assets = [asset for asset in exercise.media_assets if is_valid_media_asset(asset)]
        if valid_assets and _is_placeholder_path(exercise.media_path):
            rows.append(
                _media_row(
                    settings=settings,
                    exercise=exercise,
                    asset=None,
                    current_path=exercise.media_path,
                    source_path=None,
                    reference_kind="legacy",
                    destination=None,
                )
            )
            continue
        source_path = resolve_source_path(
            exercise.media_path,
            settings=settings,
            roots=source_roots,
            seed_root=seed_root,
        )
        if source_path is not None:
            reference_source_paths.add(source_path.resolve())

        if source_path is None and not _is_placeholder_path(exercise.media_path):
            matching_destinations = {
                str(row["destination_physical_path"])
                for row in asset_rows
                if row["current_db_path"] == exercise.media_path
                and row.get("destination_physical_path")
            }
            matching_sources = [
                Path(str(row["current_physical_path"]))
                for row in asset_rows
                if row["current_db_path"] == exercise.media_path
                and row.get("current_physical_path")
            ]
            if len(matching_destinations) == 1:
                destination = Path(next(iter(matching_destinations)))
                source_path = next(
                    (candidate for candidate in matching_sources if candidate.is_file()),
                    None,
                )
                if source_path is not None:
                    reference_source_paths.add(source_path.resolve())
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
                continue
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
    manifest = {
        "version": MANIFEST_VERSION,
        "summary": summary,
        "rows": rows,
    }
    _set_manifest_state(manifest, DISCOVERED)
    return manifest


def _set_row_state(row: dict[str, object], state: str) -> None:
    if state not in LIFECYCLE_STATES:
        raise MediaMigrationError(f"Unsupported media migration state: {state}")
    row["state"] = state
    row["lifecycle_state"] = state


def _advance_row_state(row: dict[str, object], state: str) -> None:
    current_state = _inferred_row_state(row)
    if _LIFECYCLE_RANK[current_state] > _LIFECYCLE_RANK[state]:
        state = current_state
    _set_row_state(row, state)


def _inferred_row_state(row: dict[str, object]) -> str:
    state = DISCOVERED
    for key in ("lifecycle_state", "state"):
        value = row.get(key)
        if isinstance(value, str) and value in LIFECYCLE_STATES:
            if _LIFECYCLE_RANK[value] > _LIFECYCLE_RANK[state]:
                state = value
    if row.get("db_updated") and _LIFECYCLE_RANK[state] < _LIFECYCLE_RANK[DB_UPDATED]:
        state = DB_UPDATED
    elif row.get("hash_verified") and _LIFECYCLE_RANK[state] < _LIFECYCLE_RANK[HASH_VERIFIED]:
        state = HASH_VERIFIED
    elif row.get("copied") and _LIFECYCLE_RANK[state] < _LIFECYCLE_RANK[COPIED]:
        state = COPIED
    return state


def _set_manifest_state(manifest: dict[str, object], state: str) -> None:
    if state not in LIFECYCLE_STATES:
        raise MediaMigrationError(f"Unsupported media migration state: {state}")
    manifest["state"] = state
    manifest["lifecycle_state"] = state


def _manifest_state_from_rows(manifest: dict[str, object]) -> str:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    if not rows:
        return DISCOVERED

    row_states = [_inferred_row_state(row) for row in rows if isinstance(row, dict)]
    if len(row_states) != len(rows):
        raise MediaMigrationError("Manifest row is invalid")

    actionable_rows = [
        row for row in rows if isinstance(row, dict) and row.get("destination_physical_path")
    ]
    if (
        actionable_rows
        and all(_inferred_row_state(row) == COMPLETED for row in actionable_rows)
        and all(_inferred_row_state(row) == COMPLETED or row.get("placeholder") for row in rows)
    ):
        return COMPLETED
    if actionable_rows and all(
        _LIFECYCLE_RANK[_inferred_row_state(row)] >= _LIFECYCLE_RANK[DB_UPDATED]
        for row in actionable_rows
    ):
        return DB_UPDATED
    if actionable_rows and all(
        _LIFECYCLE_RANK[_inferred_row_state(row)] >= _LIFECYCLE_RANK[HASH_VERIFIED]
        for row in actionable_rows
    ):
        return HASH_VERIFIED
    if any(_LIFECYCLE_RANK[_inferred_row_state(row)] >= _LIFECYCLE_RANK[COPIED] for row in rows):
        return COPIED
    return DISCOVERED


def _normalise_manifest(manifest: dict[str, object]) -> dict[str, object]:
    version = manifest.get("version")
    if type(version) is not int or version not in SUPPORTED_MANIFEST_VERSIONS:
        raise MediaMigrationError("Unsupported media migration manifest")
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise MediaMigrationError("Manifest rows are invalid")
    for row in rows:
        if not isinstance(row, dict):
            raise MediaMigrationError("Manifest row is invalid")
        _set_row_state(row, _inferred_row_state(row))
    manifest_state = manifest.get("lifecycle_state") or manifest.get("state")
    derived_state = _manifest_state_from_rows(manifest)
    if not isinstance(manifest_state, str) or manifest_state not in LIFECYCLE_STATES:
        manifest_state = derived_state
    elif _LIFECYCLE_RANK[derived_state] > _LIFECYCLE_RANK[manifest_state]:
        manifest_state = derived_state
    _set_manifest_state(manifest, manifest_state)
    return manifest


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{path.name}.", dir=path.parent) as temp_dir:
        temporary_path = Path(temp_dir) / "manifest.json"
        with temporary_path.open("x", encoding="utf-8", newline="") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)


def _write_immutable_snapshot(path: Path, content: str) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise MediaMigrationError(
                f"Immutable snapshot must be a regular immutable snapshot: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{path.name}.", dir=path.parent) as temp_dir:
        temporary_path = Path(temp_dir) / "snapshot"
        with temporary_path.open("x", encoding="utf-8", newline="") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                raise MediaMigrationError(
                    f"Immutable snapshot must be a regular immutable snapshot: {path}"
                ) from None


def _manifest_json(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)


def _manifest_csv(manifest: dict[str, object]) -> str:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    fieldnames = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue()


def write_manifest(manifest: dict[str, object], manifest_dir: Path) -> None:
    """Persist only the mutable manifest, replacing it atomically."""
    _normalise_manifest(manifest)
    _atomic_write_text(manifest_dir / "migration_manifest.json", _manifest_json(manifest))


def write_inventory(manifest: dict[str, object], manifest_dir: Path) -> None:
    """Create initial snapshots once, then persist the mutable manifest."""
    _normalise_manifest(manifest)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    _write_immutable_snapshot(
        manifest_dir / "before_inventory.json",
        _manifest_json(manifest),
    )
    _write_immutable_snapshot(
        manifest_dir / "before_inventory.csv",
        _manifest_csv(manifest),
    )
    write_manifest(manifest, manifest_dir)


def load_manifest(manifest_dir: Path) -> dict[str, object]:
    path = manifest_dir / "migration_manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MediaMigrationError(f"Manifest does not exist: {path}") from error
    if not isinstance(payload, dict):
        raise MediaMigrationError("Unsupported media migration manifest")
    return _normalise_manifest(payload)


def copy_and_verify_row(row: dict[str, object]) -> None:
    if row.get("placeholder"):
        row["hash_verified"] = False
        _advance_row_state(row, DISCOVERED)
        return
    source_value = row.get("current_physical_path")
    destination_value = row.get("destination_physical_path")
    expected_digest = row.get("sha256")
    if not isinstance(destination_value, str):
        raise MediaMigrationError("A media row has no destination")
    if not isinstance(expected_digest, str):
        raise MediaMigrationError("A media row has no source hash")
    destination = Path(destination_value)
    if destination.exists() or destination.is_symlink():
        if not destination.is_file():
            raise MediaMigrationError(f"Destination hash mismatch: {destination}")
        destination_digest = sha256_file(destination)
        if destination_digest != expected_digest:
            raise MediaMigrationError(f"Destination hash mismatch: {destination}")
        row["copied"] = False
        row["destination_sha256"] = destination_digest
        row["hash_verified"] = True
        _advance_row_state(row, HASH_VERIFIED)
        return
    if not isinstance(source_value, str):
        raise MediaMigrationError("A media row has no source")
    source = Path(source_value)
    if not source.is_file():
        raise MediaMigrationError(f"Source media is missing: {source}")
    if sha256_file(source) != expected_digest:
        raise MediaMigrationError(f"Source hash changed: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination_digest = sha256_file(destination)
    if destination_digest != expected_digest:
        raise MediaMigrationError(f"Copied hash mismatch: {destination}")
    row["copied"] = True
    row["destination_sha256"] = destination_digest
    row["hash_verified"] = True
    _advance_row_state(row, HASH_VERIFIED)


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


def _is_database_reference_row(row: dict[str, object]) -> bool:
    """Return whether a manifest row describes a real database media reference."""
    reference_kind = row.get("reference_kind")
    if reference_kind in {"orphan", "disk_orphan", "seed-static", "seed_static"}:
        return False
    if reference_kind == "asset" or (reference_kind is None and row.get("media_asset_id")):
        return bool(row.get("media_asset_id"))
    if reference_kind in {"legacy", "exercise"} or reference_kind is None:
        return bool(row.get("exercise_id"))
    return False


def _is_rollback_manifest_row(row: dict[str, object]) -> bool:
    """Return whether a row records a verified database migration mapping."""
    if not _is_database_reference_row(row):
        return False
    if any(
        not isinstance(row.get(key), str) or not str(row[key]).strip()
        for key in ("current_db_path", "destination_public_path", "sha256")
    ):
        return False
    return bool(row.get("hash_verified") and row.get("db_updated"))


def _rollback_manifest_rows(
    manifest: dict[str, object],
) -> list[tuple[int | None, dict[str, object]]]:
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise MediaMigrationError("Manifest rows are invalid")
    references: list[tuple[int | None, dict[str, object]]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise MediaMigrationError("Manifest row is invalid")
        if _is_rollback_manifest_row(row):
            references.append((index, row))
    return references


def _rollback_source_candidates(
    row: dict[str, object],
    *,
    settings: Settings,
    legacy_roots: tuple[Path, ...],
) -> tuple[Path, ...]:
    candidates: list[Path] = []

    def add(path: Path) -> None:
        if path not in candidates:
            candidates.append(path)

    physical_value = row.get("current_physical_path")
    if isinstance(physical_value, str) and physical_value:
        physical = Path(physical_value)
        add(physical)
        try:
            relative = physical.relative_to(settings.media_root)
        except ValueError:
            relative = None
        if relative is not None:
            for root in legacy_roots:
                add(root / relative)
        staging_prefix = Path("/var/lib/fitsho/media-migration-source")
        try:
            staging_relative = physical.relative_to(staging_prefix)
        except ValueError:
            staging_relative = None
        if staging_relative is not None:
            for root in legacy_roots:
                add(root / staging_prefix.name / staging_relative)
        for root in legacy_roots:
            add(root / physical.name)

    public_value = row.get("current_db_path")
    if isinstance(public_value, str) and public_value:
        relative = _safe_relative_public_path(public_value, settings)
        if relative is not None:
            for root in (*legacy_roots, settings.media_root):
                add(root / relative)
        for root in legacy_roots:
            add(root / Path(public_value).name)

    return tuple(candidates)


def _rollback_source_evidence(
    row: dict[str, object],
    *,
    settings: Settings,
    legacy_roots: tuple[Path, ...],
) -> tuple[Path | None, str | None]:
    expected_digest = row.get("sha256")
    if not isinstance(expected_digest, str) or not expected_digest:
        return None, "manifest source hash is missing"
    candidates = _rollback_source_candidates(
        row,
        settings=settings,
        legacy_roots=legacy_roots,
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None, "old media source is missing"
    for source in existing:
        if sha256_file(source) == expected_digest:
            return source, None
    return None, "old media source hash does not match manifest"


def _rollback_reference(
    db: Session,
    row: dict[str, object],
    *,
    for_update: bool = False,
) -> Exercise | ExerciseMediaAsset | None:
    reference_kind = row.get("reference_kind")
    if reference_kind == "asset" or (reference_kind is None and row.get("media_asset_id")):
        value = row.get("media_asset_id")
        if not isinstance(value, str):
            return None
        try:
            asset_id = UUID(value)
        except ValueError:
            return None
        asset_statement = select(ExerciseMediaAsset).where(ExerciseMediaAsset.id == asset_id)
        if for_update:
            asset_statement = asset_statement.with_for_update()
        asset = db.scalar(asset_statement)
        if asset is None:
            return None
        exercise_id = row.get("exercise_id")
        if exercise_id and str(asset.exercise_id) != str(exercise_id):
            return None
        return asset
    value = row.get("exercise_id")
    if not isinstance(value, str):
        return None
    try:
        exercise_id = UUID(value)
    except ValueError:
        return None
    exercise_statement = select(Exercise).where(Exercise.id == exercise_id)
    if for_update:
        exercise_statement = exercise_statement.with_for_update()
    return db.scalar(exercise_statement)


def _is_legacy_pointer_manifest_row(row: dict[str, object]) -> bool:
    return (
        row.get("reference_kind") in {"legacy", "exercise"}
        and bool(row.get("exercise_id"))
        and isinstance(row.get("current_db_path"), str)
        and isinstance(row.get("destination_public_path"), str)
        and isinstance(row.get("sha256"), str)
    )


def _v1_pointer_rollback_rows(
    db: Session,
    manifest: dict[str, object],
) -> list[dict[str, object]]:
    """Derive legacy Exercise.media_path rows from an asset-only v1 manifest.

    v1 did not record the legacy Exercise pointer separately.  A pointer is
    recoverable only when its current canonical destination identifies one
    destination for that exercise.  Duplicate asset rows are acceptable when
    they carry the same old path and digest; different destinations are not.
    """
    if manifest.get("version") != 1:
        return []
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise MediaMigrationError("Manifest rows are invalid")
    if any(_is_legacy_pointer_manifest_row(row) for row in rows if isinstance(row, dict)):
        existing_exercises = {
            str(row["exercise_id"])
            for row in rows
            if isinstance(row, dict) and _is_legacy_pointer_manifest_row(row)
        }
    else:
        existing_exercises = set()
    asset_rows_by_exercise: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if not isinstance(row, dict) or not _is_rollback_manifest_row(row):
            continue
        if row.get("reference_kind") not in {"asset", None} or not row.get("media_asset_id"):
            continue
        exercise_id = row.get("exercise_id")
        destination = row.get("destination_public_path")
        if not isinstance(exercise_id, str) or not isinstance(destination, str):
            continue
        asset_rows_by_exercise.setdefault(exercise_id, []).append(row)

    derived: list[dict[str, object]] = []
    for exercise in _load_exercises(db):
        exercise_id = str(exercise.id)
        if exercise_id in existing_exercises or _is_placeholder_path(exercise.media_path):
            continue
        candidates = [
            row
            for row in asset_rows_by_exercise.get(exercise_id, [])
            if row.get("destination_public_path") == exercise.media_path
        ]
        candidate_groups: dict[str, list[dict[str, object]]] = {}
        for row in candidates:
            destination = str(row["destination_public_path"])
            candidate_groups.setdefault(destination, []).append(row)
        candidate_group = next(iter(candidate_groups.values()), [])
        old_evidence = {(row.get("current_db_path"), row.get("sha256")) for row in candidate_group}
        if len(candidate_groups) == 1 and len(old_evidence) == 1:
            candidate = candidate_group[0]
            derived.append(
                {
                    "reference_kind": "legacy",
                    "exercise_id": exercise_id,
                    "current_db_path": candidate.get("current_db_path"),
                    "current_physical_path": candidate.get("current_physical_path"),
                    "destination_public_path": exercise.media_path,
                    "sha256": candidate.get("sha256"),
                    "hash_verified": True,
                    "db_updated": True,
                    "placeholder": False,
                    "derived_from_v1_asset": candidate.get("media_asset_id"),
                }
            )
            continue
        restored_candidates = [
            row
            for row in asset_rows_by_exercise.get(exercise_id, [])
            if row.get("current_db_path") == exercise.media_path
        ]
        restored_groups: dict[str, list[dict[str, object]]] = {}
        for row in restored_candidates:
            destination = row.get("destination_public_path")
            if isinstance(destination, str):
                restored_groups.setdefault(destination, []).append(row)
        restored_group = next(iter(restored_groups.values()), [])
        restored_evidence = {
            (row.get("current_db_path"), row.get("sha256")) for row in restored_group
        }
        if len(restored_groups) == 1 and len(restored_evidence) == 1:
            candidate = restored_group[0]
            derived.append(
                {
                    "reference_kind": "legacy",
                    "exercise_id": exercise_id,
                    "current_db_path": exercise.media_path,
                    "current_physical_path": candidate.get("current_physical_path"),
                    "destination_public_path": candidate.get("destination_public_path"),
                    "sha256": candidate.get("sha256"),
                    "hash_verified": True,
                    "db_updated": True,
                    "placeholder": False,
                    "derived_from_v1_asset": candidate.get("media_asset_id"),
                }
            )
            continue
        reason = (
            "v1 Exercise.media_path matches multiple verified asset destinations"
            if (
                len(candidate_groups) > 1
                or (len(candidate_groups) == 1 and len(old_evidence) > 1)
                or len(restored_groups) > 1
                or (len(restored_groups) == 1 and len(restored_evidence) > 1)
            )
            else "v1 Exercise.media_path has no uniquely verified asset destination"
        )
        derived.append(
            {
                "reference_kind": "legacy",
                "exercise_id": exercise_id,
                "current_db_path": exercise.media_path,
                "destination_public_path": exercise.media_path,
                "sha256": None,
                "hash_verified": False,
                "db_updated": False,
                "placeholder": False,
                "derivation_error": reason,
            }
        )
    return derived


def _rollback_plan_row(
    db: Session,
    *,
    row_index: int | None,
    row: dict[str, object],
    settings: Settings,
    legacy_roots: tuple[Path, ...],
) -> dict[str, object]:
    result: dict[str, object] = {
        "manifest_row": row_index,
        "reference_kind": row.get("reference_kind"),
        "exercise_id": row.get("exercise_id"),
        "media_asset_id": row.get("media_asset_id"),
        "current_db_path": row.get("current_db_path"),
        "destination_public_path": row.get("destination_public_path"),
        "sha256": row.get("sha256"),
        "status": ROLLBACK_MISSING,
        "source_path": None,
        "reason": None,
    }
    derivation_error = row.get("derivation_error")
    if isinstance(derivation_error, str) and derivation_error:
        result["reason"] = derivation_error
        return result
    current_path = row.get("current_db_path")
    destination_path = row.get("destination_public_path")
    reference = _rollback_reference(db, row)
    if reference is None:
        result["reason"] = "database reference row is missing"
        return result
    if not isinstance(current_path, str) or not current_path:
        result["reason"] = "manifest current database path is missing"
        return result
    if not isinstance(destination_path, str) or not destination_path:
        result["reason"] = "manifest destination public path is missing"
        return result
    actual_path = reference.media_path
    if actual_path == destination_path:
        result["status"] = ROLLBACK_PLANNED
    elif actual_path == current_path:
        result["status"] = ROLLBACK_ALREADY_RESTORED
    else:
        result["status"] = ROLLBACK_CONFLICT
        result["reason"] = "database reference path conflicts with manifest"
        return result
    source_path, reason = _rollback_source_evidence(
        row,
        settings=settings,
        legacy_roots=legacy_roots,
    )
    if source_path is None:
        result["status"] = ROLLBACK_MISSING
        result["reason"] = reason
        return result
    result["source_path"] = str(source_path)
    return result


def build_rollback_plan(
    db: Session,
    *,
    settings: Settings,
    manifest: dict[str, object],
    legacy_roots: tuple[Path, ...] = (),
) -> dict[str, object]:
    """Build a read-only rollback plan for actual exercise media references."""
    manifest_rows = _rollback_manifest_rows(manifest)
    manifest_rows.extend((None, row) for row in _v1_pointer_rollback_rows(db, manifest))
    with db.no_autoflush:
        planned_rows = [
            _rollback_plan_row(
                db,
                row_index=index,
                row=row,
                settings=settings,
                legacy_roots=legacy_roots,
            )
            for index, row in manifest_rows
        ]
    summary = {
        "total": len(planned_rows),
        "planned": sum(row["status"] == ROLLBACK_PLANNED for row in planned_rows),
        "already_restored": sum(row["status"] == ROLLBACK_ALREADY_RESTORED for row in planned_rows),
        "conflict": sum(row["status"] == ROLLBACK_CONFLICT for row in planned_rows),
        "missing": sum(row["status"] == ROLLBACK_MISSING for row in planned_rows),
    }
    return {"rows": planned_rows, "summary": summary}


def _rollback_failure_summary(summary: object) -> bool:
    return isinstance(summary, dict) and bool(summary.get("conflict") or summary.get("missing"))


def _mark_database_rolled_back(manifest: dict[str, object], plan: dict[str, object]) -> None:
    rows = manifest.get("rows")
    plan_rows = plan.get("rows")
    if not isinstance(rows, list) or not isinstance(plan_rows, list):
        raise MediaMigrationError("Rollback plan is invalid")
    for plan_row in plan_rows:
        if not isinstance(plan_row, dict):
            raise MediaMigrationError("Rollback plan row is invalid")
        if plan_row.get("status") not in {ROLLBACK_PLANNED, ROLLBACK_ALREADY_RESTORED}:
            continue
        row_index = plan_row.get("manifest_row")
        if row_index is None:
            continue
        if not isinstance(row_index, int) or not 0 <= row_index < len(rows):
            raise MediaMigrationError("Rollback plan row index is invalid")
        row = rows[row_index]
        if not isinstance(row, dict):
            raise MediaMigrationError("Manifest row is invalid")
        row["db_updated"] = False
        _set_row_state(row, HASH_VERIFIED if row.get("hash_verified") else DISCOVERED)
    _set_manifest_state(manifest, _manifest_state_from_rows(manifest))


def apply_database_rollback(
    db: Session,
    *,
    settings: Settings,
    manifest: dict[str, object],
    legacy_roots: tuple[Path, ...] = (),
) -> dict[str, object]:
    """Validate and apply a complete rollback plan atomically."""
    plan = build_rollback_plan(
        db,
        settings=settings,
        manifest=manifest,
        legacy_roots=legacy_roots,
    )
    summary = plan["summary"]
    if _rollback_failure_summary(summary):
        raise MediaMigrationError("Rollback plan has conflict or missing rows")
    plan_rows = plan["rows"]
    assert isinstance(plan_rows, list)
    try:
        with db.begin_nested():
            for plan_row in plan_rows:
                assert isinstance(plan_row, dict)
                if plan_row.get("status") != ROLLBACK_PLANNED:
                    continue
                row_index = plan_row.get("manifest_row")
                if isinstance(row_index, int):
                    rows = manifest["rows"]
                    assert isinstance(rows, list)
                    row = rows[row_index]
                    assert isinstance(row, dict)
                else:
                    row = plan_row
                reference = _rollback_reference(db, row, for_update=True)
                if reference is None:
                    raise MediaMigrationError("Rollback database reference disappeared")
                destination_path = row.get("destination_public_path")
                current_path = row.get("current_db_path")
                if not isinstance(destination_path, str) or not isinstance(current_path, str):
                    raise MediaMigrationError("Rollback manifest paths are invalid")
                if reference.media_path != destination_path:
                    raise MediaMigrationError("Rollback database reference conflict")
                reference.media_path = current_path
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise MediaMigrationError("Manifest rows are invalid")
    for plan_row in plan_rows:
        if plan_row.get("manifest_row") is not None:
            continue
        if plan_row.get("status") not in {ROLLBACK_PLANNED, ROLLBACK_ALREADY_RESTORED}:
            continue
        rows.append(
            {
                "reference_kind": "legacy",
                "exercise_id": plan_row.get("exercise_id"),
                "current_db_path": plan_row.get("current_db_path"),
                "current_physical_path": plan_row.get("source_path"),
                "destination_public_path": plan_row.get("destination_public_path"),
                "sha256": plan_row.get("sha256"),
                "hash_verified": True,
                "db_updated": False,
                "placeholder": False,
                "state": HASH_VERIFIED,
                "lifecycle_state": HASH_VERIFIED,
            }
        )
    _mark_database_rolled_back(manifest, plan)
    return plan


def update_database_from_manifest(
    db: Session,
    *,
    settings: Settings,
    manifest: dict[str, object],
) -> int:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    asset_destinations = _row_destination_map(manifest)
    legacy_rows = {
        str(row["exercise_id"]): row
        for row in rows
        if row.get("reference_kind") == "legacy" and row.get("exercise_id")
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
            pointer_row = legacy_rows.get(str(exercise.id))
            if pointer_row is not None and pointer_row.get("placeholder"):
                continue
            if (
                pointer_row is not None
                and pointer_row.get("destination_public_path")
                and pointer_row.get("hash_verified")
            ):
                exercise.media_path = str(pointer_row["destination_public_path"])
                pointer_media_type = pointer_row.get("media_type")
                if pointer_media_type is not None:
                    exercise.media_type = MediaType(str(pointer_media_type))
            elif any(is_valid_media_asset(asset) for asset in exercise.media_assets):
                primary = resolve_primary_media(exercise)
                exercise.media_path = primary.path
                exercise.media_type = primary.media_type
            else:
                if (
                    pointer_row is not None
                    and pointer_row.get("destination_public_path")
                    and pointer_row.get("hash_verified")
                ):
                    exercise.media_path = str(pointer_row["destination_public_path"])
                    pointer_media_type = pointer_row.get("media_type")
                    if pointer_media_type is not None:
                        exercise.media_type = MediaType(str(pointer_media_type))
        db.flush()
    db.commit()
    return assets_updated


def mark_database_updated(manifest: dict[str, object]) -> None:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    for row in rows:
        if not isinstance(row, dict) or not _is_database_reference_row(row):
            if isinstance(row, dict) and row.get("db_updated"):
                row["db_updated"] = False
                if row.get("state") == DB_UPDATED or row.get("lifecycle_state") == DB_UPDATED:
                    _set_row_state(row, HASH_VERIFIED if row.get("hash_verified") else DISCOVERED)
            continue
        if row.get("destination_public_path") and row.get("hash_verified"):
            row["db_updated"] = True
            _advance_row_state(row, DB_UPDATED)
    _set_manifest_state(manifest, _manifest_state_from_rows(manifest))


def mark_completed(manifest: dict[str, object]) -> None:
    rows = manifest["rows"]
    assert isinstance(rows, list)
    for row in rows:
        if row.get("destination_public_path") and row.get("hash_verified"):
            _advance_row_state(row, COMPLETED)
        elif row.get("placeholder") and not row.get("destination_public_path"):
            _advance_row_state(row, COMPLETED)
    _set_manifest_state(manifest, _manifest_state_from_rows(manifest))


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
    unsafe_db_paths: list[str] = []
    for exercise in _load_exercises(db):
        references = [
            (exercise.media_path, exercise.media_type),
            *((asset.media_path, asset.media_type) for asset in exercise.media_assets),
        ]
        for public_path, media_type in references:
            if _is_explicit_placeholder_media_type(media_type):
                continue
            relative, unsafe = _validated_local_media_path(public_path, settings)
            if unsafe:
                unsafe_db_paths.append(public_path)
            if relative is None or not (settings.media_root / relative).is_file():
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
        "UNSAFE_DB_PATHS": len(unsafe_db_paths),
        "ORPHAN_DESTINATION_FILES": len(orphan_destinations),
        "missing_source_paths": missing_sources,
        "hash_mismatch_paths": hash_mismatches,
        "broken_db_paths": broken_db_paths,
        "unsafe_db_paths": unsafe_db_paths,
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
            _set_manifest_state(manifest, _manifest_state_from_rows(manifest))
            write_manifest(manifest, args.manifest_dir)
            if not args.apply:
                print("COPY_VERIFY_ONLY")
                return 0
            update_database_from_manifest(db, settings=settings, manifest=manifest)
            mark_database_updated(manifest)
            mark_completed(manifest)
            write_manifest(manifest, args.manifest_dir)
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
                    for key in (
                        "MISSING_SOURCE_FILES",
                        "HASH_MISMATCHES",
                        "BROKEN_DB_PATHS",
                        "UNSAFE_DB_PATHS",
                    )
                )
                else 1
            )
        rows = manifest["rows"]
        if not isinstance(rows, list):
            raise MediaMigrationError("Manifest rows are invalid")
        rollback_roots = tuple(root.path for root in source_roots)
        if not args.apply:
            report = build_rollback_plan(
                db,
                settings=settings,
                manifest=manifest,
                legacy_roots=rollback_roots,
            )
            report["rollback_dry_run"] = True
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 1 if _rollback_failure_summary(report.get("summary")) else 0
        report = apply_database_rollback(
            db,
            settings=settings,
            manifest=manifest,
            legacy_roots=rollback_roots,
        )
        write_manifest(manifest, args.manifest_dir)
        report["rollback_dry_run"] = False
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
