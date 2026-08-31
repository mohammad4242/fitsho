from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.runners.base import RunnerError, RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities

TOKEN = "a" * 32


class ImageRunner:
    name = AgentName.ANTIGRAVITY

    def __init__(self, supports_image: bool) -> None:
        self.supports_image = supports_image
        self.requests: list[RunnerRequest] = []
        self.seen_files: list[Path] = []

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
        self.seen_files = [path for path in request.image_paths if path.is_file()]
        return RunnerResult(
            payload={"answer": "image ok"},
            model_id=request.model_id,
            input_tokens=None,
            output_tokens=None,
            duration_seconds=0.1,
        )


def metadata() -> dict[str, object]:
    return {
        "agent": "antigravity",
        "model_id": "fake-model",
        "system_prompt": "Describe the image.",
        "input_payload": {},
        "response_schema": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
        "schema_name": "image_answer",
        "temperature": 0,
        "max_output_tokens": 100,
        "timeout_seconds": 5,
    }


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


def client(tmp_path: Path, runner: ImageRunner) -> TestClient:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    return TestClient(create_app(settings, registry=RunnerRegistry([runner])))


def test_image_route_rejects_unverified_image_capability(tmp_path: Path) -> None:
    runner = ImageRunner(False)
    response = client(tmp_path, runner).post(
        "/v1/analyze-images",
        data={"metadata": __import__("json").dumps(metadata())},
        files={"images": ("original.png", b"image", "image/png")},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert runner.requests == []
    assert list(tmp_path.iterdir()) == []


def test_image_route_uses_generated_workspace_names_and_cleans_up(tmp_path: Path) -> None:
    runner = ImageRunner(True)
    response = client(tmp_path, runner).post(
        "/v1/analyze-images",
        data={"metadata": __import__("json").dumps(metadata())},
        files=[
            ("images", ("first.png", png_bytes(), "image/png")),
            ("images", ("second.png", png_bytes(), "image/png")),
        ],
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json()["payload"] == {"answer": "image ok"}
    assert [path.name for path in runner.requests[0].image_paths] == [
        "image-01.png",
        "image-02.png",
    ]
    assert len(runner.seen_files) == 2
    assert list(tmp_path.iterdir()) == []


def test_image_route_rejects_path_fields_and_bad_metadata(tmp_path: Path) -> None:
    runner = ImageRunner(True)
    bad = metadata()
    bad["image_paths"] = ["/etc/passwd"]
    response = client(tmp_path, runner).post(
        "/v1/analyze-images",
        data={"metadata": __import__("json").dumps(bad)},
        files={"images": ("photo.png", b"image", "image/png")},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "passwd" not in response.text


def test_image_route_rejects_bytes_that_do_not_match_declared_mime(tmp_path: Path) -> None:
    runner = ImageRunner(True)
    response = client(tmp_path, runner).post(
        "/v1/analyze-images",
        data={"metadata": __import__("json").dumps(metadata())},
        files={"images": ("photo.png", b"not an image", "image/png")},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert runner.requests == []


def test_image_route_cleans_workspace_after_runner_failure(tmp_path: Path) -> None:
    class FailingImageRunner(ImageRunner):
        async def run(self, request: RunnerRequest) -> RunnerResult:
            self.requests.append(request)
            raise RunnerError("provider_unavailable", "private runner failure")

    runner = FailingImageRunner(True)
    response = client(tmp_path, runner).post(
        "/v1/analyze-images",
        data={"metadata": __import__("json").dumps(metadata())},
        files={"images": ("photo.png", png_bytes(), "image/png")},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "private runner failure" not in response.text
    assert list(tmp_path.iterdir()) == []
