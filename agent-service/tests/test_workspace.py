import asyncio
import shutil
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from app.workspace import WorkspaceLimits, create_request_workspace


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def test_workspace_is_removed_after_success(tmp_path: Path) -> None:
    async def scenario() -> Path:
        async with create_request_workspace("request/with-traversal", root=tmp_path) as workspace:
            image_path = workspace.save_image(b"jpeg", "image/jpeg", 1)
            assert image_path.name == "image-01.jpg"
            assert image_path.read_bytes() == b"jpeg"
            return image_path.parent

    workspace_path = run(scenario())
    assert not workspace_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_workspace_is_removed_after_failure(tmp_path: Path) -> None:
    workspace_path: Path | None = None

    async def scenario() -> None:
        nonlocal workspace_path
        with pytest.raises(RuntimeError, match="boom"):
            async with create_request_workspace(root=tmp_path) as workspace:
                workspace_path = workspace.save_image(b"png", "image/png", 2).parent
                raise RuntimeError("boom")

    run(scenario())
    assert workspace_path is not None
    assert not workspace_path.exists()


def test_workspace_is_removed_when_task_is_cancelled(tmp_path: Path) -> None:
    workspace_path: Path | None = None

    async def scenario() -> None:
        nonlocal workspace_path

        async def use_workspace() -> None:
            nonlocal workspace_path
            async with create_request_workspace(root=tmp_path) as workspace:
                workspace_path = workspace.save_image(b"webp", "image/webp", 1).parent
                await asyncio.sleep(60)

        task = asyncio.create_task(use_workspace())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert workspace_path is not None
    assert not workspace_path.exists()


def test_workspace_cleanup_does_not_suppress_removal_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    calls = 0

    def fail_once(path: Path, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise OSError("cleanup failed")

    monkeypatch.setattr(shutil, "rmtree", fail_once)

    async def scenario() -> None:
        async with create_request_workspace(root=tmp_path):
            pass

    with pytest.raises(OSError, match="cleanup failed"):
        run(scenario())
    assert calls == 1


def test_image_validation_enforces_mime_size_count_and_generated_names(tmp_path: Path) -> None:
    async def scenario() -> None:
        limits = WorkspaceLimits(max_images=2, max_file_bytes=4, max_total_bytes=5)
        async with create_request_workspace(root=tmp_path) as workspace:
            with pytest.raises(ValueError, match="mime"):
                workspace.save_image(b"<svg>secret</svg>", "image/svg+xml", 1)
            with pytest.raises(ValueError, match="empty"):
                workspace.save_image(b"", "image/png", 1)
            with pytest.raises(ValueError, match="size"):
                workspace.save_image(b"12345", "image/jpeg", 1, limits)

            first = workspace.save_image(b"1234", "image/jpeg", 1, limits)
            assert first.name == "image-01.jpg"
            with pytest.raises(ValueError, match="total"):
                workspace.save_image(b"12", "image/png", 2, limits)
            with pytest.raises(ValueError, match="index"):
                workspace.save_image(b"1", "image/webp", 3, limits)
            assert workspace.path is not None
            assert not (workspace.path / "secret").exists()

    run(scenario())
