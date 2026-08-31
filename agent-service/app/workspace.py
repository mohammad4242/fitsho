import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True)
class WorkspaceLimits:
    max_images: int = 5
    max_file_bytes: int = 8 * 1024 * 1024
    max_total_bytes: int = 20 * 1024 * 1024


class RequestWorkspace:
    def __init__(self, request_id: str | None = None, root: Path | None = None) -> None:
        self.request_id = request_id
        self.root = root or Path("/tmp/fitsho-agent")
        self.path: Path | None = None
        self._saved_indices: set[int] = set()
        self._total_bytes = 0

    async def __aenter__(self) -> "RequestWorkspace":
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = Path(tempfile.mkdtemp(prefix="request-", dir=self.root))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        path = self.path
        self.path = None
        if path is not None:
            shutil.rmtree(path)

    def save_image(
        self,
        data: bytes,
        mime_type: str,
        index: int,
        limits: WorkspaceLimits = WorkspaceLimits(),  # noqa: B008
    ) -> Path:
        if self.path is None:
            raise RuntimeError("workspace is not active")
        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError("unsupported image mime type")
        if not data:
            raise ValueError("image is empty")
        if limits.max_images <= 0 or limits.max_file_bytes <= 0 or limits.max_total_bytes <= 0:
            raise ValueError("image limits must be positive")
        if index < 1 or index > limits.max_images or index in self._saved_indices:
            raise ValueError("image index is invalid")
        data_size = len(data)
        if data_size > limits.max_file_bytes:
            raise ValueError("image exceeds file size limit")
        if self._total_bytes + data_size > limits.max_total_bytes:
            raise ValueError("images exceed total size limit")

        suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime_type]
        image_path = self.path / f"image-{index:02d}{suffix}"
        try:
            with image_path.open("xb") as image_file:
                image_file.write(data)
        except FileExistsError as exc:
            raise ValueError("image index is invalid") from exc
        self._saved_indices.add(index)
        self._total_bytes += data_size
        return image_path


def create_request_workspace(
    request_id: str | None = None,
    root: Path | None = None,
) -> RequestWorkspace:
    return RequestWorkspace(request_id=request_id, root=root)
