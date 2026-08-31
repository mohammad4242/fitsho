import asyncio
import os
import sys
from collections.abc import Awaitable, Callable, Coroutine
from pathlib import Path
from typing import Any

from app.auth.base import AuthCommand
from app.auth.process import AuthProcess


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake-pty-auth.py"
    script.write_text(body, encoding="utf-8")
    return script


def make_callback(chunks: list[str]) -> Callable[[str], Awaitable[None]]:
    async def on_output(text: str) -> None:
        chunks.append(text)

    return on_output


def test_pty_process_streams_output_and_accepts_input(tmp_path: Path) -> None:
    script = write_script(
        tmp_path,
        "import sys\n"
        "print('READY', flush=True)\n"
        "if sys.stdin.readline().strip() == 'continue':\n"
        "    print('AUTHENTICATED', flush=True)\n",
    )
    chunks: list[str] = []

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(sys.executable, (str(script),), use_pty=True),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
            max_output_bytes=4096,
            output_callback=make_callback(chunks),
        )
        await process.start()
        await asyncio.sleep(0.05)
        assert process.is_running
        await process.send_input("continue")
        result = await process.wait()
        assert result.returncode == 0
        assert "READY" in result.final_text
        assert "AUTHENTICATED" in result.final_text
        assert "READY" in "".join(chunks)

    run(scenario())


def test_pty_process_termination_reaps_child(tmp_path: Path) -> None:
    script = write_script(tmp_path, "import time\ntime.sleep(60)\n")
    chunks: list[str] = []

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(sys.executable, (str(script),), use_pty=True),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
            max_output_bytes=4096,
            output_callback=make_callback(chunks),
        )
        await process.start()
        assert process.is_running
        await process.terminate()
        assert not process.is_running
        result = await process.wait()
        assert result.returncode != 0

    run(scenario())
