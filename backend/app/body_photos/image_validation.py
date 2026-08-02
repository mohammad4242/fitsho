from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings

FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}
SIGNATURES: dict[str, Callable[[bytes], bool]] = {
    "JPEG": lambda data: data.startswith(b"\xff\xd8\xff"),
    "PNG": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "WEBP": lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}


class BodyPhotoValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedBodyPhoto:
    content: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    crop_confidence: float
    crop_geometry_verified: bool


def _read_limited(upload: UploadFile, settings: Settings) -> bytes:
    chunks: list[bytes] = []
    total = 0
    upload.file.seek(0)
    while chunk := upload.file.read(settings.body_photo_read_chunk_bytes):
        total += len(chunk)
        if total > settings.body_photo_max_bytes:
            raise BodyPhotoValidationError
        chunks.append(chunk)
    if total == 0:
        raise BodyPhotoValidationError
    return b"".join(chunks)


def _validate_attestation(head_cropped: str | None, crop_confidence: str | None) -> float:
    if head_cropped != "true" or crop_confidence is None:
        raise BodyPhotoValidationError
    try:
        confidence = float(crop_confidence)
    except ValueError as error:
        raise BodyPhotoValidationError from error
    if not 0.8 <= confidence <= 1.0:
        raise BodyPhotoValidationError
    return confidence


def _validate_geometry(width: int, height: int) -> None:
    if width <= 0 or height <= 0 or height < width or height > width * 3:
        raise BodyPhotoValidationError


def _normalized_mode(image: Image.Image, image_format: str) -> Image.Image:
    if image_format == "JPEG":
        return image.convert("RGB")
    if image.mode in {"RGB", "RGBA"}:
        return image.copy()
    return image.convert("RGBA" if "transparency" in image.info else "RGB")


def validate_and_normalize(
    upload: UploadFile,
    settings: Settings,
    *,
    head_cropped: str | None,
    crop_confidence: str | None,
) -> NormalizedBodyPhoto:
    confidence = _validate_attestation(head_cropped, crop_confidence)
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise BodyPhotoValidationError
    content = _read_limited(upload, settings)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as probe:
                image_format = probe.format
                if image_format not in FORMAT_DETAILS:
                    raise BodyPhotoValidationError
                mime_type, extension = FORMAT_DETAILS[image_format]
                if upload.content_type != mime_type or not SIGNATURES[image_format](content):
                    raise BodyPhotoValidationError
                width, height = probe.size
                if width * height > settings.body_photo_max_pixels:
                    raise BodyPhotoValidationError
                _validate_geometry(width, height)
                probe.verify()

            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded)
                _validate_geometry(*oriented.size)
                normalized = _normalized_mode(oriented, image_format)
                output = BytesIO()
                if image_format == "JPEG":
                    normalized.save(output, format="JPEG", quality=90, optimize=True)
                elif image_format == "PNG":
                    normalized.save(output, format="PNG", optimize=True)
                else:
                    normalized.save(output, format="WEBP", quality=90, method=6)
    except (
        BodyPhotoValidationError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise BodyPhotoValidationError from error
    except (OSError, UnidentifiedImageError, ValueError) as error:
        raise BodyPhotoValidationError from error

    normalized_content = output.getvalue()
    if not normalized_content or len(normalized_content) > settings.body_photo_max_bytes:
        raise BodyPhotoValidationError
    return NormalizedBodyPhoto(
        content=normalized_content,
        mime_type=mime_type,
        extension=extension,
        width=normalized.width,
        height=normalized.height,
        crop_confidence=confidence,
        crop_geometry_verified=True,
    )
