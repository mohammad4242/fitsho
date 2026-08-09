from __future__ import annotations

import hashlib
import io
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.config import Settings
from app.nutrition.enums import (
    NutritionLabRequestStatus,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
)
from app.nutrition.models import (
    NutritionLabDocument,
    NutritionLabRequest,
    NutritionPlanPhysicianReview,
    NutritionReviewAuditEvent,
    NutritionWeeklyPlan,
)


class ClinicalError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def is_physician(db: Session, user_id: UUID) -> bool:
    return (
        db.scalar(
            select(UserSpecialistRole).where(
                UserSpecialistRole.user_id == user_id,
                UserSpecialistRole.role.in_([SpecialistRole.PHYSICIAN, SpecialistRole.DOCTOR]),
            )
        )
        is not None
    )


def require_physician(db: Session, user_id: UUID) -> None:
    if not is_physician(db, user_id):
        raise ClinicalError("PHYSICIAN_ROLE_REQUIRED")


def _path(root: Path, key: str) -> Path:
    resolved = root.resolve()
    relative = PurePosixPath(key)
    if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
        raise ClinicalError("INVALID_LAB_STORAGE_KEY")
    path = resolved.joinpath(*relative.parts)
    if not path.is_relative_to(resolved):
        raise ClinicalError("INVALID_LAB_STORAGE_KEY")
    return path


def _normalize(content: bytes, content_type: str | None) -> tuple[bytes, str, str]:
    if content_type == "application/pdf" and content.startswith(b"%PDF-"):
        return content, "application/pdf", ".pdf"
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            output = io.BytesIO()
            image.convert("RGB").save(output, "JPEG", quality=90, optimize=True)
        return output.getvalue(), "image/jpeg", ".jpg"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ClinicalError("INVALID_LAB_DOCUMENT") from error


def _store(root: Path, content: bytes, extension: str) -> str:
    identifier = uuid4().hex
    key = f"{identifier[:2]}/{identifier}{extension}"
    destination = _path(root, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as error:
        if temporary:
            temporary.unlink(missing_ok=True)
        raise ClinicalError("LAB_STORAGE_UNAVAILABLE") from error
    return key


def lab_response(row: NutritionLabDocument) -> dict[str, object]:
    return {
        "id": row.id,
        "original_filename": row.original_filename,
        "content_type": row.content_type,
        "byte_size": row.byte_size,
        "test_date": row.test_date,
        "laboratory_name": row.laboratory_name,
        "user_note": row.user_note,
        "category": row.category,
        "review_status": row.review_status,
        "request_id": row.request_id,
        "uploaded_at": row.uploaded_at,
        "retained_until": row.retained_until,
    }


async def upload_lab(
    db: Session,
    user_id: UUID,
    file: UploadFile,
    settings: Settings,
    *,
    test_date: date | None,
    laboratory_name: str | None,
    user_note: str | None,
    category: str | None,
    request_id: UUID | None,
) -> dict[str, object]:
    content = await file.read(settings.nutrition_lab_max_bytes + 1)
    if len(content) > settings.nutrition_lab_max_bytes:
        raise ClinicalError("LAB_DOCUMENT_TOO_LARGE")
    normalized, content_type, extension = _normalize(content, file.content_type)
    request = None
    if request_id:
        request = db.scalar(
            select(NutritionLabRequest).where(
                NutritionLabRequest.id == request_id,
                NutritionLabRequest.user_id == user_id,
            )
        )
        if request is None:
            raise ClinicalError("LAB_REQUEST_NOT_FOUND")
    key = _store(settings.nutrition_lab_storage_root, normalized, extension)
    row = NutritionLabDocument(
        user_id=user_id,
        storage_key=key,
        original_filename=(file.filename or f"lab{extension}")[:255],
        content_type=content_type,
        byte_size=len(normalized),
        sha256=hashlib.sha256(normalized).hexdigest(),
        test_date=test_date,
        laboratory_name=laboratory_name,
        user_note=user_note,
        category=category,
        review_status="unreviewed",
        request_id=request_id,
        assigned_physician_user_id=request.physician_user_id if request else None,
        retained_until=date.today() + timedelta(days=settings.nutrition_lab_retention_days),
    )
    db.add(row)
    if request:
        request.status = NutritionLabRequestStatus.UPLOADED
    db.commit()
    db.refresh(row)
    return lab_response(row)


def list_labs(db: Session, user_id: UUID) -> list[dict[str, object]]:
    return [
        lab_response(row)
        for row in db.scalars(
            select(NutritionLabDocument)
            .where(NutritionLabDocument.user_id == user_id)
            .order_by(NutritionLabDocument.uploaded_at.desc())
        )
    ]


def open_lab(
    db: Session, actor_id: UUID, document_id: UUID, settings: Settings
) -> tuple[BinaryIO, str, str]:
    row = db.get(NutritionLabDocument, document_id)
    if row is None:
        raise ClinicalError("LAB_DOCUMENT_NOT_FOUND")
    if row.user_id != actor_id:
        authorized = (
            row.assigned_physician_user_id == actor_id
            or db.scalar(
                select(NutritionPlanPhysicianReview)
                .join(
                    NutritionWeeklyPlan,
                    NutritionWeeklyPlan.id == NutritionPlanPhysicianReview.plan_id,
                )
                .where(
                    NutritionWeeklyPlan.user_id == row.user_id,
                    NutritionPlanPhysicianReview.physician_user_id == actor_id,
                )
            )
            is not None
        )
        if not authorized or not is_physician(db, actor_id):
            raise ClinicalError("LAB_DOCUMENT_NOT_FOUND")
    try:
        handle = _path(settings.nutrition_lab_storage_root, row.storage_key).open("rb")
    except OSError as error:
        raise ClinicalError("LAB_STORAGE_UNAVAILABLE") from error
    return handle, row.content_type, row.original_filename


def delete_lab(db: Session, user_id: UUID, document_id: UUID, settings: Settings) -> None:
    row = db.scalar(
        select(NutritionLabDocument).where(
            NutritionLabDocument.id == document_id,
            NutritionLabDocument.user_id == user_id,
        )
    )
    if row is None:
        raise ClinicalError("LAB_DOCUMENT_NOT_FOUND")
    _path(settings.nutrition_lab_storage_root, row.storage_key).unlink(missing_ok=True)
    db.delete(row)
    db.commit()


def review_queue(db: Session, physician_id: UUID) -> list[dict[str, object]]:
    require_physician(db, physician_id)
    now = datetime.now(UTC)
    reviews = db.scalars(
        select(NutritionPlanPhysicianReview)
        .where(
            NutritionPlanPhysicianReview.status.in_(
                [
                    NutritionPlanReviewStatus.PENDING,
                    NutritionPlanReviewStatus.IN_REVIEW,
                    NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION,
                    NutritionPlanReviewStatus.CHANGES_REQUESTED,
                ]
            )
        )
        .order_by(
            NutritionPlanPhysicianReview.priority.desc(),
            NutritionPlanPhysicianReview.requested_at,
        )
    ).all()
    return [
        {
            "review_id": row.id,
            "plan_id": row.plan_id,
            "status": row.status.value,
            "priority": row.priority,
            "physician_user_id": row.physician_user_id,
            "requested_at": row.requested_at,
            "target_review_by": row.target_review_by,
            "overdue": bool(row.target_review_by and row.target_review_by < now),
        }
        for row in reviews
    ]


def claim_review(db: Session, physician_id: UUID, review_id: UUID) -> dict[str, object]:
    require_physician(db, physician_id)
    review = db.scalar(
        select(NutritionPlanPhysicianReview)
        .where(NutritionPlanPhysicianReview.id == review_id)
        .with_for_update()
    )
    if review is None:
        raise ClinicalError("REVIEW_NOT_FOUND")
    if review.physician_user_id and review.physician_user_id != physician_id:
        raise ClinicalError("REVIEW_ALREADY_ASSIGNED")
    now = datetime.now(UTC)
    review.physician_user_id = physician_id
    review.assigned_at = review.assigned_at or now
    review.review_started_at = now
    review.status = NutritionPlanReviewStatus.IN_REVIEW
    plan = db.get(NutritionWeeklyPlan, review.plan_id)
    if plan is None:
        raise ClinicalError("NUTRITION_PLAN_NOT_FOUND")
    plan.lifecycle_status = NutritionPlanLifecycleStatus.PHYSICIAN_REVIEW_IN_PROGRESS
    db.add(
        NutritionReviewAuditEvent(
            review_id=review.id,
            actor_user_id=physician_id,
            action="review_claimed",
            metadata_snapshot={"plan_id": str(plan.id), "revision": plan.revision},
        )
    )
    db.commit()
    return {"review_id": review.id, "status": review.status.value}


def request_labs(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    requested_tests: list[str],
    user_visible_reason: str,
) -> dict[str, object]:
    require_physician(db, physician_id)
    plan = db.scalar(
        select(NutritionWeeklyPlan)
        .where(NutritionWeeklyPlan.id == plan_id)
        .options(selectinload(NutritionWeeklyPlan.review))
        .with_for_update()
    )
    if plan is None or plan.id != expected_plan_revision_id or plan.review is None:
        raise ClinicalError("STALE_PLAN_REVISION")
    if plan.review.physician_user_id not in {None, physician_id}:
        raise ClinicalError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    row = NutritionLabRequest(
        user_id=plan.user_id,
        plan_id=plan.id,
        physician_user_id=physician_id,
        status=NutritionLabRequestStatus.REQUESTED,
        requested_tests=requested_tests,
        notes=user_visible_reason,
    )
    db.add(row)
    plan.review.physician_user_id = physician_id
    plan.review.status = NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION
    plan.review.user_visible_notes = user_visible_reason
    plan.lifecycle_status = NutritionPlanLifecycleStatus.AWAITING_LAB_INFORMATION
    db.flush()
    db.add(
        NutritionReviewAuditEvent(
            review_id=plan.review.id,
            actor_user_id=physician_id,
            action="laboratory_information_requested",
            metadata_snapshot={"request_id": str(row.id), "requested_tests": requested_tests},
        )
    )
    db.commit()
    return {"id": row.id, "status": row.status.value, "requested_tests": requested_tests}


def list_lab_requests(db: Session, user_id: UUID) -> list[dict[str, object]]:
    rows = db.scalars(
        select(NutritionLabRequest)
        .where(NutritionLabRequest.user_id == user_id)
        .order_by(NutritionLabRequest.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "plan_id": row.plan_id,
            "status": row.status.value,
            "requested_tests": row.requested_tests,
            "user_visible_reason": row.notes,
            "created_at": row.created_at,
        }
        for row in rows
    ]
