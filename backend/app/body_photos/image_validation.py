from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from app.body_photos.schemas import BodyPhotoCropEvidenceInput
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
    crop_original_height: int
    crop_top: int
    crop_bottom: int
    processed_sha256: str
    crop_evidence_sha256: str


@dataclass(frozen=True)
class CropEvidence:
    confidence: float
    original_height: int
    crop_top: int
    crop_bottom: int
    processed_sha256: str
    evidence_sha256: str


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


def _parse_crop_evidence(
    *,
    head_cropped: str | None,
    crop_confidence: str | None,
    original_height: str | None,
    crop_top: str | None,
    crop_bottom: str | None,
    processed_sha256: str | None,
    crop_evidence_sha256: str | None,
) -> CropEvidence:
    if (
        head_cropped != "true"
        or crop_confidence is None
        or original_height is None
        or crop_top is None
        or crop_bottom is None
        or processed_sha256 is None
        or crop_evidence_sha256 is None
    ):
        raise BodyPhotoValidationError
    try:
        parsed = BodyPhotoCropEvidenceInput.model_validate(
            {
                "confidence": crop_confidence,
                "original_height": original_height,
                "crop_top": crop_top,
                "crop_bottom": crop_bottom,
                "processed_sha256": processed_sha256,
                "crop_evidence_sha256": crop_evidence_sha256,
            }
        )
    except ValidationError as error:
        raise BodyPhotoValidationError from error
    return CropEvidence(
        confidence=parsed.confidence,
        original_height=parsed.original_height,
        crop_top=parsed.crop_top,
        crop_bottom=parsed.crop_bottom,
        processed_sha256=parsed.processed_sha256.casefold(),
        evidence_sha256=parsed.crop_evidence_sha256.casefold(),
    )


def _validate_output_geometry(width: int, height: int, settings: Settings) -> None:
    if (
        width < settings.body_photo_min_width
        or height < settings.body_photo_min_height
        or height < width
        or height > width * 3
    ):
        raise BodyPhotoValidationError


def _verify_crop_evidence(
    content: bytes,
    output_height: int,
    evidence: CropEvidence,
    settings: Settings,
) -> None:
    actual_digest = sha256(content).hexdigest()
    if not compare_digest(actual_digest, evidence.processed_sha256):
        raise BodyPhotoValidationError
    if (
        evidence.original_height <= 0
        or evidence.crop_top < 0
        or evidence.crop_bottom > evidence.original_height
        or evidence.crop_bottom <= evidence.crop_top
        or evidence.crop_bottom - evidence.crop_top != output_height
        or evidence.crop_top / evidence.original_height < settings.body_photo_min_crop_top_ratio
    ):
        raise BodyPhotoValidationError
    canonical = (
        f"v1:{actual_digest}:{evidence.original_height}:{evidence.crop_top}:{evidence.crop_bottom}"
    )
    actual_evidence_digest = sha256(canonical.encode()).hexdigest()
    if not compare_digest(actual_evidence_digest, evidence.evidence_sha256):
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
    original_height: str | None,
    crop_top: str | None,
    crop_bottom: str | None,
    processed_sha256: str | None,
    crop_evidence_sha256: str | None,
) -> NormalizedBodyPhoto:
    evidence = _parse_crop_evidence(
        head_cropped=head_cropped,
        crop_confidence=crop_confidence,
        original_height=original_height,
        crop_top=crop_top,
        crop_bottom=crop_bottom,
        processed_sha256=processed_sha256,
        crop_evidence_sha256=crop_evidence_sha256,
    )
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
                probe.verify()

            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded)
                _validate_output_geometry(*oriented.size, settings)
                _verify_crop_evidence(content, oriented.height, evidence, settings)
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
        crop_confidence=evidence.confidence,
        crop_geometry_verified=True,
        crop_original_height=evidence.original_height,
        crop_top=evidence.crop_top,
        crop_bottom=evidence.crop_bottom,
        processed_sha256=evidence.processed_sha256,
        crop_evidence_sha256=evidence.evidence_sha256,
    )
