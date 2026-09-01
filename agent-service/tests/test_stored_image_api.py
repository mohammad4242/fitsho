import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from app.private_media import PrivateMediaError, PrivateMediaResolver
from app.runners.base import RunnerError, RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import (
    AgentName,
    AuthState,
    RunnerCapabilities,
    RunnerModelCapabilities,
    StoredImageGenerationInput,
    StoredImageReference,
)

BODY_KEY = "ab/abcdef0123456789abcdef0123456789.jpg"
FOOD_KEY = "cd/cd23456789abcdef0123456789abcdef.jpg"


def _stored_reference(
    *,
    label: str = "front",
    mime_type: str = "image/jpeg",
    scope: str = "body",
    key: str = BODY_KEY,
) -> dict[str, str]:
    return {
        "label": label,
        "mime_type": mime_type,
        "storage_scope": scope,
        "storage_key": key,
    }


def _generation() -> dict[str, object]:
    return {
        "agent": "antigravity",
        "model_id": "fake-model",
        "system_prompt": "Describe the image.",
        "input_payload": {},
        "response_schema": {"type": "object"},
        "schema_name": "image_answer",
        "temperature": 0,
        "max_output_tokens": 100,
        "timeout_seconds": 5,
    }


def _write(root: Path, scope: str, key: str, content: bytes = b"image") -> Path:
    path = root / scope / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _jpeg_bytes(color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    output = BytesIO()
    Image.new("RGB", (4, 4), color=color).save(output, format="JPEG")
    return output.getvalue()


class StoredImageRunner:
    name = AgentName.ANTIGRAVITY

    def __init__(self, supports_image: bool = True, fail: bool = False) -> None:
        self.supports_image = supports_image
        self.fail = fail
        self.requests: list[RunnerRequest] = []

    async def capabilities(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            agent=self.name,
            installed=True,
            auth_state=AuthState.UNKNOWN,
            models=[
                RunnerModelCapabilities(
                    model_id="fake-model",
                    supports_text_input=True,
                    supports_image_input=self.supports_image,
                    supports_structured_output=True,
                )
            ],
        )

    async def run(self, request: RunnerRequest) -> RunnerResult:
        self.requests.append(request)
        if self.fail:
            raise RunnerError("provider_unavailable", "private runner failure")
        return RunnerResult(
            payload={"answer": "image ok"},
            model_id=request.model_id,
            input_tokens=None,
            output_tokens=None,
            duration_seconds=0.1,
        )


def _stored_client(
    tmp_path: Path,
    runner: StoredImageRunner,
    **settings_overrides: int,
) -> tuple[TestClient, Path, Path]:
    shared_root = tmp_path / "shared"
    (shared_root / "body").mkdir(parents=True)
    (shared_root / "food").mkdir()
    workspace_root = tmp_path / "workspace"
    settings = Settings(
        agent_service_token=__import__("pydantic").SecretStr("a" * 32),
        agent_workspace_root=workspace_root,
        agent_shared_private_media_root=shared_root,
        agent_max_file_bytes=settings_overrides.get("max_file_bytes", 1024 * 1024),
        agent_max_total_bytes=settings_overrides.get("max_total_bytes", 2 * 1024 * 1024),
    )
    return (
        TestClient(create_app(settings, registry=RunnerRegistry([runner]))),
        shared_root,
        workspace_root,
    )


def _stored_request(
    *images: dict[str, str],
) -> dict[str, object]:
    return {"generation": _generation(), "images": list(images)}


def _post_stored(client: TestClient, payload: dict[str, object], token: str = "a" * 32):
    return client.post(
        "/v1/analyze-stored-images",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def _assert_workspace_empty(workspace_root: Path) -> None:
    if workspace_root.exists():
        assert list(workspace_root.iterdir()) == []


def _resolver(root: Path, **limits: int) -> PrivateMediaResolver:
    return PrivateMediaResolver(
        root,
        max_images=limits.get("max_images", 5),
        max_file_bytes=limits.get("max_file_bytes", 1024),
        max_total_bytes=limits.get("max_total_bytes", 2048),
    )


def test_stored_image_contract_is_composed_and_forbids_paths() -> None:
    reference = StoredImageReference.model_validate(_stored_reference())
    request = StoredImageGenerationInput.model_validate(
        {"generation": _generation(), "images": [reference.model_dump()]}
    )

    assert request.generation.image_labels is None
    assert request.images == (reference,)
    with pytest.raises(ValidationError):
        StoredImageReference.model_validate({**_stored_reference(), "path": "/etc/passwd"})

    with pytest.raises(ValidationError):
        StoredImageGenerationInput.model_validate(
            {
                "generation": {**_generation(), "image_labels": ["front"]},
                "images": [_stored_reference()],
            }
        )


def test_private_media_resolver_resolves_body_and_food_under_scoped_roots(tmp_path: Path) -> None:
    _write(tmp_path / "shared", "body", BODY_KEY)
    _write(tmp_path / "shared", "food", FOOD_KEY)
    resolver = _resolver(tmp_path / "shared")

    body_path = resolver.resolve("body", BODY_KEY, "image/jpeg")
    food_path = resolver.resolve("food", FOOD_KEY, "image/jpeg")

    assert body_path == (tmp_path / "shared/body" / BODY_KEY).resolve()
    assert food_path == (tmp_path / "shared/food" / FOOD_KEY).resolve()


@pytest.mark.parametrize(
    ("scope", "key", "mime_type"),
    [
        ("body", "/etc/passwd", "image/jpeg"),
        ("body", "../abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab/../abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab//abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab/c/abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab/abcdef0123456789abcdef0123456789.png", "image/jpeg"),
        ("body", "ab/abcdef0123456789abcdef0123456789.gif", "image/jpeg"),
        ("other", BODY_KEY, "image/jpeg"),
    ],
)
def test_private_media_resolver_rejects_unsafe_or_mismatched_references(
    tmp_path: Path, scope: str, key: str, mime_type: str
) -> None:
    _write(tmp_path / "shared", "body", BODY_KEY)
    resolver = _resolver(tmp_path / "shared")

    with pytest.raises(PrivateMediaError) as error:
        resolver.resolve(scope, key, mime_type)

    assert str(tmp_path) not in str(error.value)


def test_private_media_resolver_rejects_missing_directories_and_symlink_escape(
    tmp_path: Path,
) -> None:
    root = tmp_path / "shared"
    _write(root, "body", BODY_KEY)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    escape = root / "body/ab/abcdef0123456789abcdef0123456780.jpg"
    escape.symlink_to(outside)
    resolver = _resolver(root)

    for key in (
        "ab/abcdef0123456789abcdef0123456781.jpg",
        "ab/abcdef0123456789abcdef0123456782.jpg",
    ):
        with pytest.raises(PrivateMediaError):
            resolver.resolve("body", key, "image/jpeg")
    with pytest.raises(PrivateMediaError):
        resolver.resolve("body", "ab/abcdef0123456789abcdef0123456780.jpg", "image/jpeg")

    directory_key = "ab/abcdef0123456789abcdef0123456783.jpg"
    (root / "body" / directory_key).mkdir()
    with pytest.raises(PrivateMediaError):
        resolver.resolve("body", directory_key, "image/jpeg")

    escaped_root = tmp_path / "escaped-root"
    _write(escaped_root, "body", BODY_KEY)
    root_with_link = tmp_path / "root-with-link"
    root_with_link.mkdir()
    (root_with_link / "body").symlink_to(escaped_root / "body", target_is_directory=True)
    with pytest.raises(PrivateMediaError):
        _resolver(root_with_link).resolve("body", BODY_KEY, "image/jpeg")


def test_private_media_resolver_enforces_per_file_and_total_size_limits(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    _write(root, "body", BODY_KEY, b"12345")
    second_key = "ab/abcdef0123456789abcdef0123456788.jpg"
    _write(root, "body", second_key, b"12345")

    with pytest.raises(PrivateMediaError):
        _resolver(root, max_file_bytes=4).resolve("body", BODY_KEY, "image/jpeg")
    with pytest.raises(PrivateMediaError):
        _resolver(root, max_total_bytes=9).resolve_many(
            (
                StoredImageReference.model_validate(_stored_reference()),
                StoredImageReference.model_validate(
                    _stored_reference(key=second_key, label="side")
                ),
            )
        )


def test_private_media_resolver_enforces_image_count_limit(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    _write(root, "body", BODY_KEY)
    references = tuple(
        StoredImageReference.model_validate(
            _stored_reference(key=BODY_KEY, label=f"image-{index}")
        )
        for index in range(2)
    )

    with pytest.raises(PrivateMediaError):
        _resolver(root, max_images=1).resolve_many(references)


def test_stored_image_route_reads_body_file_in_place_and_emits_transport_metadata(
    tmp_path: Path,
) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    source = _write(shared_root, "body", BODY_KEY, _jpeg_bytes())
    original = source.read_bytes()

    response = _post_stored(
        client,
        _stored_request(_stored_reference(label="front")),
    )

    assert response.status_code == 200
    assert response.json()["payload"] == {"answer": "image ok"}
    assert runner.requests[0].image_paths == (source.resolve(),)
    assert source.read_bytes() == original
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_reads_food_file_and_preserves_label_and_mime(tmp_path: Path) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    source = _write(shared_root, "food", FOOD_KEY, _jpeg_bytes((240, 240, 240)))

    response = _post_stored(
        client,
        _stored_request(
            _stored_reference(
                label="food_photo", scope="food", key=FOOD_KEY, mime_type="image/jpeg"
            )
        ),
    )

    assert response.status_code == 200
    assert runner.requests[0].image_paths == (source.resolve(),)
    assert source.is_file()
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_cleans_workspace_after_runner_failure(tmp_path: Path) -> None:
    runner = StoredImageRunner(fail=True)
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    source = _write(shared_root, "body", BODY_KEY, _jpeg_bytes())
    original = source.read_bytes()

    response = _post_stored(client, _stored_request(_stored_reference()))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "private runner failure" not in response.text
    assert source.read_bytes() == original
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_sets_task_kind_and_image_count_telemetry(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = StoredImageRunner()
    client, shared_root, _ = _stored_client(tmp_path, runner)
    _write(shared_root, "body", BODY_KEY, _jpeg_bytes())
    with caplog.at_level("INFO", logger="fitsho.agent_service"):
        response = _post_stored(client, _stored_request(_stored_reference()))

    assert response.status_code == 200
    record = json.loads(caplog.records[-1].message)
    assert record["task_kind"] == "analyze_stored_images"
    assert record["image_count"] == 1


@pytest.mark.parametrize(
    "key",
    [
        "/etc/passwd",
        "../abcdef0123456789abcdef0123456789.jpg",
        "ab/../abcdef0123456789abcdef0123456789.jpg",
    ],
)
def test_stored_image_route_rejects_absolute_and_traversal_keys(tmp_path: Path, key: str) -> None:
    runner = StoredImageRunner()
    client, _, workspace_root = _stored_client(tmp_path, runner)

    response = _post_stored(client, _stored_request(_stored_reference(key=key)))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert key not in response.text
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_rejects_wrong_scope_missing_file_and_directory(
    tmp_path: Path,
) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    directory_key = "ab/abcdef0123456789abcdef0123456783.jpg"
    (shared_root / "body" / directory_key).mkdir(parents=True)

    for reference in (
        _stored_reference(scope="nutrition"),
        _stored_reference(key="ab/abcdef0123456789abcdef0123456781.jpg"),
        _stored_reference(key=directory_key),
    ):
        response = _post_stored(client, _stored_request(reference))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        _assert_workspace_empty(workspace_root)


def test_stored_image_route_rejects_symlink_escape(tmp_path: Path) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(_jpeg_bytes())
    link = shared_root / "body" / "ab/abcdef0123456789abcdef0123456780.jpg"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    response = _post_stored(
        client,
        _stored_request(_stored_reference(key="ab/abcdef0123456789abcdef0123456780.jpg")),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert str(outside) not in response.text
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_rejects_oversized_and_total_overflow_images(tmp_path: Path) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner, max_file_bytes=1024)
    first = _write(shared_root, "body", BODY_KEY, b"x" * 1025)
    oversized = _post_stored(client, _stored_request(_stored_reference()))
    assert oversized.status_code == 422
    assert first.is_file()

    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(
        tmp_path / "total", runner, max_total_bytes=1024
    )
    first_key = BODY_KEY
    second_key = "ab/abcdef0123456789abcdef0123456788.jpg"
    _write(shared_root, "body", first_key, b"x" * 600)
    _write(shared_root, "body", second_key, b"y" * 600)
    total = _post_stored(
        client,
        _stored_request(
            _stored_reference(key=first_key, label="front"),
            _stored_reference(key=second_key, label="side"),
        ),
    )
    assert total.status_code == 422
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_rejects_mime_extension_mismatch(tmp_path: Path) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    _write(shared_root, "body", BODY_KEY, _jpeg_bytes())

    response = _post_stored(
        client,
        _stored_request(_stored_reference(mime_type="image/png")),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_rejects_more_than_configured_image_limit(tmp_path: Path) -> None:
    runner = StoredImageRunner()
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    _write(shared_root, "body", BODY_KEY, _jpeg_bytes())
    references = [_stored_reference(label=f"image-{index}") for index in range(6)]

    response = _post_stored(client, _stored_request(*references))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    _assert_workspace_empty(workspace_root)


def test_stored_image_route_requires_authentication(tmp_path: Path) -> None:
    runner = StoredImageRunner()
    client, _, _ = _stored_client(tmp_path, runner)

    response = client.post("/v1/analyze-stored-images", json=_stored_request(_stored_reference()))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert runner.requests == []


def test_stored_image_route_rejects_runner_without_image_capability(tmp_path: Path) -> None:
    runner = StoredImageRunner(supports_image=False)
    client, shared_root, workspace_root = _stored_client(tmp_path, runner)
    _write(shared_root, "body", BODY_KEY, _jpeg_bytes())

    response = _post_stored(client, _stored_request(_stored_reference()))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert runner.requests == []
    _assert_workspace_empty(workspace_root)
