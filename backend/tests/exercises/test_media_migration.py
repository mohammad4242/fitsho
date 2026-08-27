import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session


def _rollback_exercise(slug: str):
    from app.exercises.enums import BodyRegion, Difficulty, MediaType, MuscleGroup
    from app.exercises.models import Exercise

    return Exercise(
        slug=slug,
        name_en="Rollback Exercise",
        name_fa="حرکت بازگشت",
        body_region=BodyRegion.LOWER_BODY,
        primary_muscle=MuscleGroup.QUADRICEPS,
        difficulty=Difficulty.BEGINNER,
        instructions_en=["Set up.", "Move.", "Return."],
        instructions_fa=["آماده شو.", "حرکت کن.", "برگرد."],
        safety_notes_en=[],
        safety_notes_fa=[],
        media_path="/media/canonical-exercise.mp4",
        media_type=MediaType.VIDEO,
    )


def _rollback_manifest(exercise, asset, old_exercise_path: str, old_asset_path: str, digest: str):
    return {
        "version": 2,
        "summary": {},
        "rows": [
            {
                "reference_kind": "legacy",
                "exercise_id": str(exercise.id),
                "current_db_path": old_exercise_path,
                "current_physical_path": None,
                "destination_public_path": exercise.media_path,
                "sha256": digest,
                "hash_verified": True,
                "db_updated": True,
                "placeholder": False,
            },
            {
                "reference_kind": "asset",
                "exercise_id": str(exercise.id),
                "media_asset_id": str(asset.id),
                "current_db_path": old_asset_path,
                "current_physical_path": None,
                "destination_public_path": asset.media_path,
                "sha256": digest,
                "hash_verified": True,
                "db_updated": True,
                "placeholder": False,
            },
            {
                "reference_kind": "orphan",
                "current_db_path": "",
                "destination_public_path": "/media/exercises/_unreferenced/media.mp4",
                "sha256": digest,
                "hash_verified": True,
                "db_updated": True,
            },
            {
                "reference_kind": "seed-static",
                "current_db_path": "/exercises/seed.mp4",
                "destination_public_path": "/media/exercises/seed/media.mp4",
                "sha256": digest,
                "hash_verified": True,
                "db_updated": True,
            },
        ],
    }


def _rollback_rows(report: dict[str, object]) -> list[dict[str, object]]:
    rows = report["rows"]
    assert isinstance(rows, list)
    return [row for row in rows if isinstance(row, dict)]


def test_rollback_plan_uses_actual_references_and_legacy_root_evidence(
    db: Session, test_settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import app.exercises.media_migration as media_migration
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.media_migration import build_rollback_plan
    from app.exercises.models import ExerciseMediaAsset

    legacy = tmp_path / "legacy"
    old_video = legacy / "old.mp4"
    old_video.parent.mkdir(parents=True)
    old_video.write_bytes(b"old video")
    exercise = _rollback_exercise("rollback-plan")
    exercise.media_path = "/media/canonical-exercise.mp4"
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            media_path="/media/canonical-asset.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    db.add(exercise)
    db.flush()
    asset = exercise.media_assets[0]
    placeholder_exercise = _rollback_exercise("rollback-exercise-placeholder")
    placeholder_exercise.media_path = "/media/exercise-placeholder.svg"
    db.add(placeholder_exercise)
    db.flush()
    placeholder_asset = ExerciseMediaAsset(
        presentation=MediaPresentation.UNSPECIFIED,
        role=MediaRole.VIDEO,
        media_path="/media/exercise-placeholder.svg",
        media_type=MediaType.VIDEO,
    )
    placeholder_exercise.media_assets.append(placeholder_asset)
    db.flush()
    manifest = _rollback_manifest(
        exercise,
        asset,
        "/media/old.mp4",
        "/media/old.mp4",
        hashlib.sha256(b"old video").hexdigest(),
    )
    manifest["rows"].append(
        {
            "reference_kind": "asset",
            "exercise_id": str(exercise.id),
            "media_asset_id": str(placeholder_asset.id),
            "current_db_path": placeholder_asset.media_path,
            "destination_public_path": None,
            "sha256": None,
            "hash_verified": False,
            "db_updated": False,
            "placeholder": True,
        }
    )
    manifest["rows"].append(
        {
            "reference_kind": "legacy",
            "exercise_id": str(placeholder_exercise.id),
            "current_db_path": placeholder_exercise.media_path,
            "destination_public_path": None,
            "sha256": None,
            "hash_verified": False,
            "db_updated": False,
            "placeholder": True,
        }
    )
    manifest["rows"][0]["destination_public_path"] = "/media/canonical-exercise.mp4"
    manifest["rows"][1]["destination_public_path"] = "/media/canonical-asset.mp4"
    manifest_before = json.dumps(manifest, sort_keys=True)

    report = build_rollback_plan(
        db,
        settings=test_settings,
        manifest=manifest,
        legacy_roots=(legacy,),
    )

    assert report["summary"] == {
        "total": 2,
        "planned": 2,
        "already_restored": 0,
        "conflict": 0,
        "missing": 0,
    }
    assert {row["reference_kind"] for row in _rollback_rows(report)} == {"legacy", "asset"}
    assert all(row["status"] == "planned" for row in _rollback_rows(report))
    assert all(row["source_path"] == str(old_video) for row in _rollback_rows(report))
    assert exercise.media_path == "/media/canonical-exercise.mp4"
    assert json.dumps(manifest, sort_keys=True) == manifest_before

    manifest_dir = tmp_path / "manifest"
    media_migration.write_manifest(manifest, manifest_dir)
    monkeypatch.setattr(media_migration, "get_settings", lambda: test_settings)
    monkeypatch.setattr(media_migration, "create_engine", lambda _: db.get_bind())
    assert (
        media_migration.main(
            [
                "rollback",
                "--manifest-dir",
                str(manifest_dir),
                "--legacy-root",
                str(legacy),
            ]
        )
        == 0
    )
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["rollback_dry_run"] is True
    assert dry_run["summary"] == report["summary"]


def test_apply_rollback_restores_exercise_and_asset_without_deleting_files(
    db: Session, test_settings, tmp_path: Path
) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.media_migration import apply_database_rollback
    from app.exercises.models import ExerciseMediaAsset

    legacy = tmp_path / "legacy"
    old_video = legacy / "old.mp4"
    old_video.parent.mkdir(parents=True)
    old_video.write_bytes(b"old video")
    exercise = _rollback_exercise("rollback-apply")
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            media_path="/media/canonical-asset.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    db.add(exercise)
    db.flush()
    asset = exercise.media_assets[0]
    manifest = _rollback_manifest(
        exercise,
        asset,
        "/media/old.mp4",
        "/media/old.mp4",
        hashlib.sha256(b"old video").hexdigest(),
    )
    manifest["rows"][0]["destination_public_path"] = "/media/canonical-exercise.mp4"
    manifest["rows"][1]["destination_public_path"] = "/media/canonical-asset.mp4"

    report = apply_database_rollback(
        db,
        settings=test_settings,
        manifest=manifest,
        legacy_roots=(legacy,),
    )
    db.expire_all()
    stored = db.scalar(select(type(exercise)).where(type(exercise).id == exercise.id))

    assert report["summary"]["planned"] == 2
    assert stored is not None
    assert stored.media_path == "/media/old.mp4"
    assert stored.media_assets[0].media_path == "/media/old.mp4"
    assert old_video.read_bytes() == b"old video"
    assert all(row["db_updated"] is False for row in manifest["rows"][:2])
    assert all(row["state"] == "HASH_VERIFIED" for row in manifest["rows"][:2])


def test_rollback_conflict_aborts_all_database_changes(
    db: Session, test_settings, tmp_path: Path
) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.media_migration import MediaMigrationError, apply_database_rollback
    from app.exercises.models import ExerciseMediaAsset

    legacy = tmp_path / "legacy"
    old_video = legacy / "old.mp4"
    old_video.parent.mkdir(parents=True)
    old_video.write_bytes(b"old video")
    exercise = _rollback_exercise("rollback-conflict")
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            media_path="/media/canonical-asset.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    db.add(exercise)
    db.flush()
    asset = exercise.media_assets[0]
    manifest = _rollback_manifest(
        exercise,
        asset,
        "/media/old.mp4",
        "/media/old.mp4",
        hashlib.sha256(b"old video").hexdigest(),
    )
    exercise.media_path = "/media/another-current-path.mp4"

    with pytest.raises(MediaMigrationError, match="conflict"):
        apply_database_rollback(
            db,
            settings=test_settings,
            manifest=manifest,
            legacy_roots=(legacy,),
        )

    assert exercise.media_path == "/media/another-current-path.mp4"
    assert asset.media_path == "/media/canonical-asset.mp4"
    assert all(row["db_updated"] is True for row in manifest["rows"][:2])


def test_rollback_is_idempotent_when_references_are_already_restored(
    db: Session, test_settings: object, tmp_path: Path
) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.media_migration import apply_database_rollback
    from app.exercises.models import ExerciseMediaAsset

    legacy = tmp_path / "legacy"
    old_video = legacy / "old.mp4"
    old_video.parent.mkdir(parents=True)
    old_video.write_bytes(b"old video")
    exercise = _rollback_exercise("rollback-idempotent")
    exercise.media_path = "/media/old.mp4"
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            media_path="/media/old.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    db.add(exercise)
    db.flush()
    asset = exercise.media_assets[0]
    manifest = _rollback_manifest(
        exercise,
        asset,
        "/media/old.mp4",
        "/media/old.mp4",
        hashlib.sha256(b"old video").hexdigest(),
    )
    manifest["rows"][0]["destination_public_path"] = "/media/canonical-exercise.mp4"
    manifest["rows"][1]["destination_public_path"] = "/media/canonical-asset.mp4"

    report = apply_database_rollback(
        db,
        settings=test_settings,
        manifest=manifest,
        legacy_roots=(legacy,),
    )

    assert report["summary"]["already_restored"] == 2
    assert report["summary"]["planned"] == 0
    assert exercise.media_path == "/media/old.mp4"
    assert asset.media_path == "/media/old.mp4"


def test_rollback_missing_old_evidence_fails_without_database_changes(
    db: Session, test_settings, tmp_path: Path
) -> None:
    from app.exercises.media_migration import MediaMigrationError, apply_database_rollback

    exercise = _rollback_exercise("rollback-missing")
    db.add(exercise)
    db.flush()
    manifest = {
        "version": 2,
        "summary": {},
        "rows": [
            {
                "reference_kind": "legacy",
                "exercise_id": str(exercise.id),
                "current_db_path": "/media/missing.mp4",
                "destination_public_path": exercise.media_path,
                "sha256": "f" * 64,
                "hash_verified": True,
                "db_updated": True,
            }
        ],
    }

    with pytest.raises(MediaMigrationError, match="missing"):
        apply_database_rollback(
            db,
            settings=test_settings,
            manifest=manifest,
            legacy_roots=(tmp_path / "legacy",),
        )

    assert exercise.media_path == "/media/canonical-exercise.mp4"


@pytest.mark.parametrize("evidence", ["missing", "hash-mismatch"])
def test_already_restored_requires_matching_old_source_evidence(
    db: Session, test_settings, tmp_path: Path, evidence: str
) -> None:
    from app.exercises.media_migration import (
        MediaMigrationError,
        apply_database_rollback,
        build_rollback_plan,
    )

    legacy = tmp_path / "legacy"
    old_video = legacy / "old.mp4"
    if evidence == "hash-mismatch":
        old_video.parent.mkdir(parents=True)
        old_video.write_bytes(b"changed old video")
    exercise = _rollback_exercise(f"rollback-already-restored-{evidence}")
    exercise.media_path = "/media/old.mp4"
    db.add(exercise)
    db.flush()
    manifest = {
        "version": 2,
        "summary": {},
        "rows": [
            {
                "reference_kind": "legacy",
                "exercise_id": str(exercise.id),
                "current_db_path": "/media/old.mp4",
                "destination_public_path": "/media/canonical-exercise.mp4",
                "sha256": hashlib.sha256(b"old video").hexdigest(),
                "hash_verified": True,
                "db_updated": True,
                "placeholder": False,
            }
        ],
    }
    manifest_before = json.dumps(manifest, sort_keys=True)

    report = build_rollback_plan(
        db,
        settings=test_settings,
        manifest=manifest,
        legacy_roots=(legacy,),
    )

    assert report["summary"] == {
        "total": 1,
        "planned": 0,
        "already_restored": 0,
        "conflict": 0,
        "missing": 1,
    }
    assert report["rows"][0]["status"] == "missing"
    with pytest.raises(MediaMigrationError, match="missing"):
        apply_database_rollback(
            db,
            settings=test_settings,
            manifest=manifest,
            legacy_roots=(legacy,),
        )

    assert exercise.media_path == "/media/old.mp4"
    assert json.dumps(manifest, sort_keys=True) == manifest_before
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


def test_mark_database_updated_only_marks_real_reference_rows() -> None:
    from app.exercises.media_migration import mark_database_updated

    manifest = {
        "version": 2,
        "summary": {},
        "rows": [
            {
                "reference_kind": "asset",
                "exercise_id": "exercise-1",
                "media_asset_id": "asset-1",
                "destination_public_path": "/media/asset.mp4",
                "hash_verified": True,
                "db_updated": False,
            },
            {
                "reference_kind": "orphan",
                "destination_public_path": "/media/orphan.mp4",
                "hash_verified": True,
                "db_updated": True,
                "state": "DB_UPDATED",
            },
            {
                "reference_kind": "seed-static",
                "destination_public_path": "/media/seed.mp4",
                "hash_verified": True,
                "db_updated": True,
                "state": "DB_UPDATED",
            },
        ],
    }

    mark_database_updated(manifest)

    assert manifest["rows"][0]["db_updated"] is True
    assert manifest["rows"][1]["db_updated"] is False
    assert manifest["rows"][1]["state"] == "HASH_VERIFIED"
    assert manifest["rows"][2]["db_updated"] is False
    assert manifest["rows"][2]["state"] == "HASH_VERIFIED"
