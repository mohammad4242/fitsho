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
from sqlalchemy import or_, select
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
from app.nutrition.security import audit_security_event


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


def lab_storage_path(root: Path, key: str) -> Path:
    resolved = root.resolve()
    relative = PurePosixPath(key)
    if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
        raise ClinicalError("INVALID_LAB_STORAGE_KEY")
    path = resolved.joinpath(*relative.parts)
    if not path.is_relative_to(resolved):
        raise ClinicalError("INVALID_LAB_STORAGE_KEY")
    return path


def _normalize(
    content: bytes, content_type: str | None, max_pixels: int
) -> tuple[bytes, str, str]:
    if (
        content_type == "application/pdf"
        and content.startswith(b"%PDF-")
        and b"%%EOF" in content[-1024:]
        and not any(marker in content for marker in (b"/JavaScript", b"/Launch", b"/EmbeddedFile"))
    ):
        return content, "application/pdf", ".pdf"
    if content_type not in {"image/jpeg", "image/png"}:
        raise ClinicalError("INVALID_LAB_DOCUMENT")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > max_pixels:
                raise ClinicalError("INVALID_LAB_DOCUMENT")
            image.load()
            output = io.BytesIO()
            image.convert("RGB").save(output, "JPEG", quality=90, optimize=True)
        return output.getvalue(), "image/jpeg", ".jpg"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ClinicalError("INVALID_LAB_DOCUMENT") from error


def _store(root: Path, content: bytes, extension: str) -> str:
    identifier = uuid4().hex
    key = f"{identifier[:2]}/{identifier}{extension}"
    destination = lab_storage_path(root, key)
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
        "reviewed_at": row.reviewed_at,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "review_notes": row.review_notes,
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
    normalized, content_type, extension = _normalize(
        content, file.content_type, settings.nutrition_lab_max_pixels
    )
    digest = hashlib.sha256(normalized).hexdigest()
    duplicate = db.scalar(
        select(NutritionLabDocument).where(
            NutritionLabDocument.user_id == user_id,
            NutritionLabDocument.sha256 == digest,
            NutritionLabDocument.purged_at.is_(None),
        )
    )
    if duplicate is not None:
        audit_security_event(
            db,
            actor_user_id=user_id,
            owner_user_id=user_id,
            event_type="lab_duplicate_reused",
            resource_type="lab_document",
            resource_id=duplicate.id,
            metadata={"content_type": duplicate.content_type, "byte_size": duplicate.byte_size},
        )
        db.commit()
        return {**lab_response(duplicate), "duplicate": True}
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
        sha256=digest,
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
    db.flush()
    audit_security_event(
        db,
        actor_user_id=user_id,
        owner_user_id=user_id,
        event_type="lab_uploaded",
        resource_type="lab_document",
        resource_id=row.id,
        metadata={"content_type": content_type, "byte_size": len(normalized)},
    )
    db.commit()
    db.refresh(row)
    return {**lab_response(row), "duplicate": False}


def list_labs(db: Session, user_id: UUID) -> list[dict[str, object]]:
    return [
        lab_response(row)
        for row in db.scalars(
            select(NutritionLabDocument)
            .where(
                NutritionLabDocument.user_id == user_id,
                NutritionLabDocument.purged_at.is_(None),
            )
            .order_by(NutritionLabDocument.uploaded_at.desc())
        )
    ]


def _assigned_plan(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
) -> NutritionWeeklyPlan:
    require_physician(db, physician_id)
    plan = db.scalar(
        select(NutritionWeeklyPlan)
        .where(NutritionWeeklyPlan.id == plan_id)
        .options(selectinload(NutritionWeeklyPlan.review))
    )
    if plan is None or plan.review is None:
        raise ClinicalError("NUTRITION_PLAN_NOT_FOUND")
    if plan.review.physician_user_id != physician_id:
        raise ClinicalError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    return plan


def list_physician_labs(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
) -> list[dict[str, object]]:
    plan = _assigned_plan(db, physician_id, plan_id)
    return [
        lab_response(row)
        for row in db.scalars(
            select(NutritionLabDocument)
            .where(
                NutritionLabDocument.user_id == plan.user_id,
                NutritionLabDocument.purged_at.is_(None),
            )
            .order_by(NutritionLabDocument.uploaded_at.desc())
        )
    ]


def review_lab_document(
    db: Session,
    physician_id: UUID,
    document_id: UUID,
    review_status: str,
    notes: str | None,
) -> dict[str, object]:
    require_physician(db, physician_id)
    row = authorize_lab_access(db, physician_id, document_id)
    assigned = db.scalar(
        select(NutritionPlanPhysicianReview)
        .join(NutritionWeeklyPlan, NutritionWeeklyPlan.id == NutritionPlanPhysicianReview.plan_id)
        .where(
            NutritionWeeklyPlan.user_id == row.user_id,
            NutritionPlanPhysicianReview.physician_user_id == physician_id,
            NutritionPlanPhysicianReview.status.in_(
                [
                    NutritionPlanReviewStatus.IN_REVIEW,
                    NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION,
                ]
            ),
        )
    )
    if assigned is None:
        raise ClinicalError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    row.review_status = review_status
    row.reviewed_at = datetime.now(UTC)
    row.reviewed_by_user_id = physician_id
    row.review_notes = notes
    if row.request_id is not None:
        request = db.get(NutritionLabRequest, row.request_id)
        if request is not None and request.physician_user_id == physician_id:
            request.status = NutritionLabRequestStatus.REVIEWED
            request.reviewed_at = row.reviewed_at
    audit_security_event(
        db,
        actor_user_id=physician_id,
        owner_user_id=row.user_id,
        event_type="lab_reviewed",
        resource_type="lab_document",
        resource_id=row.id,
        metadata={"review_status": review_status},
    )
    db.commit()
    db.refresh(row)
    return lab_response(row)


def authorize_lab_access(db: Session, actor_id: UUID, document_id: UUID) -> NutritionLabDocument:
    row = db.get(NutritionLabDocument, document_id)
    if row is None or row.purged_at is not None:
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
    return row


def open_lab(
    db: Session, actor_id: UUID, document_id: UUID, settings: Settings
) -> tuple[BinaryIO, str, str]:
    row = authorize_lab_access(db, actor_id, document_id)
    try:
        handle = lab_storage_path(settings.nutrition_lab_storage_root, row.storage_key).open("rb")
    except OSError as error:
        raise ClinicalError("LAB_STORAGE_UNAVAILABLE") from error
    audit_security_event(
        db,
        actor_user_id=actor_id,
        owner_user_id=row.user_id,
        event_type="lab_accessed",
        resource_type="lab_document",
        resource_id=row.id,
    )
    db.commit()
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
    lab_storage_path(settings.nutrition_lab_storage_root, row.storage_key).unlink(missing_ok=True)
    row.purged_at = datetime.now(UTC)
    audit_security_event(
        db,
        actor_user_id=user_id,
        owner_user_id=user_id,
        event_type="lab_deleted",
        resource_type="lab_document",
        resource_id=row.id,
    )
    db.commit()


def review_queue(db: Session, physician_id: UUID) -> list[dict[str, object]]:
    require_physician(db, physician_id)
    now = datetime.now(UTC)
    reviews = db.scalars(
        select(NutritionPlanPhysicianReview)
        .where(
            or_(
                NutritionPlanPhysicianReview.physician_user_id.is_(None),
                NutritionPlanPhysicianReview.physician_user_id == physician_id,
            ),
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
    if review.status not in {
        NutritionPlanReviewStatus.PENDING,
        NutritionPlanReviewStatus.CHANGES_REQUESTED,
        NutritionPlanReviewStatus.IN_REVIEW,
    }:
        raise ClinicalError("INVALID_REVIEW_TRANSITION")
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
    if plan.review.physician_user_id != physician_id:
        raise ClinicalError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    if plan.review.status != NutritionPlanReviewStatus.IN_REVIEW:
        raise ClinicalError("REVIEW_NOT_IN_PROGRESS")
    row = NutritionLabRequest(
        user_id=plan.user_id,
        plan_id=plan.id,
        physician_user_id=physician_id,
        status=NutritionLabRequestStatus.REQUESTED,
        requested_tests=requested_tests,
        notes=user_visible_reason,
    )
    db.add(row)
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
            "reviewed_at": row.reviewed_at,
            "cancelled_at": row.cancelled_at,
        }
        for row in rows
    ]


def transition_lab_request(
    db: Session,
    physician_id: UUID,
    request_id: UUID,
    status: NutritionLabRequestStatus,
) -> dict[str, object]:
    require_physician(db, physician_id)
    row = db.scalar(
        select(NutritionLabRequest)
        .where(NutritionLabRequest.id == request_id)
        .with_for_update()
    )
    if row is None:
        raise ClinicalError("LAB_REQUEST_NOT_FOUND")
    if row.physician_user_id != physician_id:
        raise ClinicalError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    now = datetime.now(UTC)
    if (
        status is NutritionLabRequestStatus.REVIEWED
        and row.status is NutritionLabRequestStatus.UPLOADED
    ):
        row.status = status
        row.reviewed_at = now
    elif status is NutritionLabRequestStatus.CANCELLED and row.status in {
        NutritionLabRequestStatus.REQUESTED,
        NutritionLabRequestStatus.UPLOADED,
    }:
        row.status = status
        row.cancelled_at = now
    else:
        raise ClinicalError("INVALID_LAB_REQUEST_TRANSITION")
    db.commit()
    return {"id": row.id, "status": row.status.value}
