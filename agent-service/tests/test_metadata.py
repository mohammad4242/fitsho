import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from app.runners.probes import CliMetadataProbe
from app.schemas import AuthState


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def write_fake_cli(tmp_path: Path) -> Path:
    script = tmp_path / "fake-cli.py"
    counter = tmp_path / "version-count"
    script.write_text(
        "#!/usr/bin/python3\n"
        "import pathlib, sys\n"
        f"counter = pathlib.Path({str(counter)!r})\n"
        "args = sys.argv[1:]\n"
        "if args == ['--version']:\n"
        "    counter.write_text(str(int(counter.read_text() if counter.exists() else '0') + 1))\n"
        "    print('fake-cli 1.2.3')\n"
        "elif args == ['login', 'status']:\n"
        "    print('Not logged in')\n"
        "    raise SystemExit(1)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_version_is_sanitized_and_cached_without_auth_status_call(tmp_path: Path) -> None:
    script = write_fake_cli(tmp_path)
    probe = CliMetadataProbe(
        executable=str(script),
        workspace=tmp_path,
        environment={"PATH": "/usr/bin"},
        auth_status_args=("login", "status"),
        auth_status_parser=lambda result: AuthState.UNAUTHENTICATED
        if "Not logged in" in result.stdout
        else AuthState.UNKNOWN,
    )

    assert run(probe.version()) == "fake-cli 1.2.3"
    assert run(probe.version()) == "fake-cli 1.2.3"
    assert (tmp_path / "version-count").read_text() == "1"


def test_auth_status_probe_is_separate_from_version_and_has_no_model_input(
    tmp_path: Path,
) -> None:
    script = write_fake_cli(tmp_path)
    probe = CliMetadataProbe(
        executable=str(script),
        workspace=tmp_path,
        environment={"PATH": "/usr/bin"},
        auth_status_args=("login", "status"),
        auth_status_parser=lambda result: AuthState.UNAUTHENTICATED
        if "Not logged in" in result.stdout
        else AuthState.UNKNOWN,
    )

    assert run(probe.auth_state()) is AuthState.UNAUTHENTICATED
    assert run(probe.version()) == "fake-cli 1.2.3"
