import hashlib
import json
from pathlib import Path

import pytest


def test_destination_path_is_deterministic_and_collision_safe() -> None:
    from app.exercises.media_migration import destination_relative_path

    path = destination_relative_path(
        slug="romanian-deadlift",
        exercise_id="12345678-1234-1234-1234-123456789abc",
        digest="a" * 64,
        extension=".mp4",
    )

    assert path.as_posix() == ("exercises/romanian-deadlift--12345678/" + f"media-{'a' * 64}.mp4")


def test_copy_and_verify_is_idempotent_and_refuses_hash_mismatch(tmp_path: Path) -> None:
    from app.exercises.media_migration import MediaMigrationError, copy_and_verify_row

    source = tmp_path / "source.mp4"
    destination = tmp_path / "destination.mp4"
    source.write_bytes(b"source video")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    row = {
        "current_physical_path": str(source),
        "destination_physical_path": str(destination),
        "sha256": digest,
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    copy_and_verify_row(row)
    copy_and_verify_row(row)

    assert destination.read_bytes() == source.read_bytes()
    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest

    destination.write_bytes(b"different video")
    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)


def test_copy_and_verify_first_second_third_runs_allow_missing_source(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import copy_and_verify_row

    source = tmp_path / "source.mp4"
    destination = tmp_path / "canonical" / "media.mp4"
    source.write_bytes(b"source video")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    row = {
        "current_physical_path": str(source),
        "destination_physical_path": str(destination),
        "sha256": digest,
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    copy_and_verify_row(row)
    assert row["copied"] is True
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert len(list(tmp_path.rglob("*.mp4"))) == 2

    copy_and_verify_row(row)
    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert len(list(tmp_path.rglob("*.mp4"))) == 2

    row["current_physical_path"] = str(tmp_path / "source-no-longer-mounted.mp4")
    copy_and_verify_row(row)
    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert destination.read_bytes() == b"source video"
    assert len(list(destination.parent.glob("*.mp4"))) == 1


def test_copy_and_verify_existing_destination_does_not_require_source(tmp_path: Path) -> None:
    from app.exercises.media_migration import copy_and_verify_row

    destination = tmp_path / "canonical.mp4"
    destination.write_bytes(b"canonical video")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    row = {
        "current_physical_path": None,
        "destination_physical_path": str(destination),
        "sha256": digest,
        "placeholder": False,
        "copied": True,
        "hash_verified": False,
    }

    copy_and_verify_row(row)

    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert destination.read_bytes() == b"canonical video"


def test_copy_and_verify_destination_mismatch_wins_when_source_is_missing(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import MediaMigrationError, copy_and_verify_row

    destination = tmp_path / "canonical.mp4"
    destination.write_bytes(b"wrong video")
    row = {
        "current_physical_path": str(tmp_path / "source-no-longer-mounted.mp4"),
        "destination_physical_path": str(destination),
        "sha256": hashlib.sha256(b"expected video").hexdigest(),
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)

    assert destination.read_bytes() == b"wrong video"


def test_copy_and_verify_non_file_destination_fails_before_missing_source(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import MediaMigrationError, copy_and_verify_row

    destination = tmp_path / "canonical.mp4"
    destination.mkdir()
    row = {
        "current_physical_path": str(tmp_path / "source-no-longer-mounted.mp4"),
        "destination_physical_path": str(destination),
        "sha256": "a" * 64,
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)

    assert destination.is_dir()


def test_write_inventory_keeps_initial_snapshots_immutable_and_updates_manifest(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import load_manifest, write_inventory

    manifest = {
        "version": 1,
        "summary": {"manifest_rows": 1},
        "rows": [
            {
                "media_asset_id": "asset-1",
                "current_db_path": "/media/source.mp4",
                "copied": False,
                "hash_verified": False,
                "db_updated": False,
            }
        ],
    }

    write_inventory(manifest, tmp_path)
    assert (tmp_path / "before_inventory.csv").is_file()
    before_json = (tmp_path / "before_inventory.json").read_bytes()
    before_csv = (tmp_path / "before_inventory.csv").read_bytes()

    manifest["rows"][0]["copied"] = True
    manifest["rows"][0]["hash_verified"] = True
    write_inventory(manifest, tmp_path)

    assert (tmp_path / "before_inventory.json").read_bytes() == before_json
    assert (tmp_path / "before_inventory.csv").read_bytes() == before_csv
    assert load_manifest(tmp_path)["rows"][0]["copied"] is True


def test_write_inventory_manifest_replacement_is_atomic_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.exercises.media_migration as media_migration

    manifest = {
        "version": 1,
        "summary": {},
        "rows": [{"media_asset_id": "asset-1", "copied": False}],
    }
    media_migration.write_inventory(manifest, tmp_path)
    old_manifest = (tmp_path / "migration_manifest.json").read_bytes()
    manifest["rows"][0]["copied"] = True

    def fail_replace(source: str, destination: str) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr(media_migration.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        media_migration.write_inventory(manifest, tmp_path)

    assert (tmp_path / "migration_manifest.json").read_bytes() == old_manifest
    assert not list(tmp_path.glob(".migration_manifest.json.*.tmp"))


def test_write_inventory_rejects_existing_snapshot_symlink_without_touching_target(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import MediaMigrationError, write_inventory

    target = tmp_path / "original.json"
    target.write_bytes(b"original snapshot")
    (tmp_path / "before_inventory.json").symlink_to(target)
    manifest = {"version": 1, "summary": {}, "rows": []}

    with pytest.raises(MediaMigrationError, match="regular immutable snapshot"):
        write_inventory(manifest, tmp_path)

    assert target.read_bytes() == b"original snapshot"


def test_write_inventory_rejects_existing_snapshot_directory_without_touching_it(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import MediaMigrationError, write_inventory

    snapshot = tmp_path / "before_inventory.json"
    snapshot.mkdir()
    marker = snapshot / "marker"
    marker.write_bytes(b"original snapshot")
    manifest = {"version": 1, "summary": {}, "rows": []}

    with pytest.raises(MediaMigrationError, match="regular immutable snapshot"):
        write_inventory(manifest, tmp_path)

    assert snapshot.is_dir()
    assert marker.read_bytes() == b"original snapshot"


def test_load_manifest_backfills_lifecycle_and_progresses_v1_rows(tmp_path: Path) -> None:
    from app.exercises.media_migration import (
        copy_and_verify_row,
        load_manifest,
        mark_completed,
        mark_database_updated,
    )

    source = tmp_path / "source.mp4"
    destination = tmp_path / "destination.mp4"
    source.write_bytes(b"source video")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (tmp_path / "migration_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "summary": {},
                "rows": [
                    {
                        "media_asset_id": "asset-1",
                        "current_physical_path": str(source),
                        "destination_physical_path": str(destination),
                        "destination_public_path": "/media/destination.mp4",
                        "sha256": digest,
                        "placeholder": False,
                        "copied": False,
                        "hash_verified": False,
                        "db_updated": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(tmp_path)
    assert manifest["state"] == "DISCOVERED"
    assert manifest["rows"][0]["state"] == "DISCOVERED"

    copy_and_verify_row(manifest["rows"][0])
    assert manifest["rows"][0]["state"] == "HASH_VERIFIED"

    mark_database_updated(manifest)
    assert manifest["rows"][0]["state"] == "DB_UPDATED"

    mark_completed(manifest)
    assert manifest["state"] == "COMPLETED"
    assert manifest["rows"][0]["state"] == "COMPLETED"
