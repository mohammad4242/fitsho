from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.nutrition.clinical_service import lab_storage_path
from app.nutrition.food_photo_service import food_photo_storage_path
from app.nutrition.models import NutritionFoodPhotoEstimate, NutritionLabDocument
from app.nutrition.security import audit_security_event, record_operational_event


@dataclass(frozen=True)
class RetentionCleanupResult:
    food_photos_purged: int
    lab_documents_purged: int


def cleanup_private_nutrition_files(
    db: Session, settings: Settings, *, now: datetime | None = None
) -> RetentionCleanupResult:
    current = now or datetime.now(UTC)
    photos = db.scalars(
        select(NutritionFoodPhotoEstimate).where(
            NutritionFoodPhotoEstimate.expires_at < current,
            NutritionFoodPhotoEstimate.deleted_at.is_(None),
        )
    ).all()
    for photo in photos:
        food_photo_storage_path(settings.food_photo_storage_root, photo.storage_key).unlink(
            missing_ok=True
        )
        photo.status = "expired"
        photo.deleted_at = current
        photo.raw_estimate = {}
        photo.mapped_items = []
        audit_security_event(
            db,
            actor_user_id=None,
            owner_user_id=photo.user_id,
            event_type="food_photo_retention_purged",
            resource_type="food_photo_estimate",
            resource_id=photo.id,
        )
    labs = db.scalars(
        select(NutritionLabDocument).where(
            NutritionLabDocument.retained_until < current.date(),
            NutritionLabDocument.purged_at.is_(None),
        )
    ).all()
    for lab in labs:
        lab_storage_path(settings.nutrition_lab_storage_root, lab.storage_key).unlink(
            missing_ok=True
        )
        lab.purged_at = current
        audit_security_event(
            db,
            actor_user_id=None,
            owner_user_id=lab.user_id,
            event_type="lab_retention_purged",
            resource_type="lab_document",
            resource_id=lab.id,
        )
    record_operational_event(
        db,
        category="retention",
        event_name="private_file_cleanup",
        status="completed",
        counters={"food_photos": len(photos), "lab_documents": len(labs)},
    )
    db.commit()
    return RetentionCleanupResult(len(photos), len(labs))
