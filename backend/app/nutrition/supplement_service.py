from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.clinical_service import ClinicalError, require_physician
from app.nutrition.enums import NutritionSupplementOrderStatus
from app.nutrition.models import (
    NutritionEstimateMicronutrientTarget,
    NutritionMedication,
    NutritionPlanPhysicianReview,
    NutritionSafetyDecision,
    NutritionSupplementCatalogue,
    NutritionSupplementOrder,
    NutritionSupplementOrderAudit,
    NutritionWeeklyPlan,
)


class SupplementError(Exception):
    def __init__(self, code: str, details: dict[str, object] | None = None) -> None:
        self.code = code
        self.details = details or {}


def save_catalogue(db: Session, payload: dict[str, object]) -> dict[str, object]:
    slug = str(payload["slug"])
    row = db.scalar(
        select(NutritionSupplementCatalogue).where(NutritionSupplementCatalogue.slug == slug)
    )
    if row is None:
        row = NutritionSupplementCatalogue(slug=slug)
        db.add(row)
    for key, value in payload.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return catalogue_response(row)


def catalogue_response(row: NutritionSupplementCatalogue) -> dict[str, object]:
    return {
        "id": row.id,
        "slug": row.slug,
        "name_fa": row.name_fa,
        "name_en": row.name_en,
        "verification_status": row.verification_status,
        "source_name": row.source_name,
        "source_reference": row.source_reference,
        "active_ingredients": row.active_ingredients,
        "nutrient_contribution_per_unit": row.nutrient_contribution_per_unit,
        "contraindication_codes": row.contraindication_codes,
        "allergen_codes": row.allergen_codes,
        "interaction_codes": row.interaction_codes,
        "upper_bound_rules": row.upper_bound_rules,
    }


def list_catalogue(db: Session) -> list[dict[str, object]]:
    return [
        catalogue_response(row)
        for row in db.scalars(
            select(NutritionSupplementCatalogue)
            .where(NutritionSupplementCatalogue.verification_status == "verified")
            .order_by(NutritionSupplementCatalogue.name_fa)
        )
    ]


def _daily_contribution(
    supplement: NutritionSupplementCatalogue, daily_units: Decimal
) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for code, value in supplement.nutrient_contribution_per_unit.items():
        if not isinstance(value, dict) or "amount" not in value:
            raise SupplementError("INVALID_SUPPLEMENT_COMPOSITION")
        result[code] = Decimal(str(value["amount"])) * daily_units
    return result


def _safety_check(
    db: Session,
    plan: NutritionWeeklyPlan,
    supplement: NutritionSupplementCatalogue,
    daily_units: Decimal,
    *,
    excluding_order_id: UUID | None = None,
) -> dict[str, object]:
    safety = db.scalar(
        select(NutritionSafetyDecision)
        .where(NutritionSafetyDecision.id == plan.safety_decision_id)
        .options(selectinload(NutritionSafetyDecision.reasons))
    )
    reason_codes = {reason.code for reason in safety.reasons} if safety else set()
    contraindications = sorted(reason_codes.intersection(supplement.contraindication_codes))
    medications = {
        row.name.casefold()
        for row in db.scalars(
            select(NutritionMedication).where(NutritionMedication.user_id == plan.user_id)
        )
    }
    interactions = sorted(
        code for code in supplement.interaction_codes if code.casefold() in medications
    )
    if contraindications or interactions:
        raise SupplementError(
            "SUPPLEMENT_SAFETY_HARD_BLOCK",
            {"contraindications": contraindications, "interactions": interactions},
        )
    contribution = _daily_contribution(supplement, daily_units)
    active_orders = db.scalars(
        select(NutritionSupplementOrder).where(
            NutritionSupplementOrder.user_id == plan.user_id,
            NutritionSupplementOrder.status == NutritionSupplementOrderStatus.ACTIVE,
        )
    ).all()
    supplement_totals: dict[str, Decimal] = dict(contribution)
    for order in active_orders:
        if order.id == excluding_order_id:
            continue
        for code, value in order.nutrient_contribution.items():
            supplement_totals[code] = supplement_totals.get(code, Decimal()) + Decimal(str(value))
    food_daily = {row.nutrient_code: row.planned_value / Decimal("7") for row in plan.nutrients}
    targets = db.scalars(
        select(NutritionEstimateMicronutrientTarget).where(
            NutritionEstimateMicronutrientTarget.estimate_id == plan.estimate_id,
            NutritionEstimateMicronutrientTarget.upper_limit_value.is_not(None),
            NutritionEstimateMicronutrientTarget.upper_limit_scope == "total_intake",
        )
    ).all()
    violations: list[dict[str, object]] = []
    combined: dict[str, str] = {}
    for target in targets:
        code = f"{target.nutrient_code}_{target.unit.casefold().replace('µ', 'u')}"
        total = food_daily.get(code, Decimal()) + supplement_totals.get(code, Decimal())
        combined[code] = str(total)
        if target.upper_limit_value is not None and total > target.upper_limit_value:
            violations.append(
                {
                    "nutrient_code": code,
                    "combined": str(total),
                    "upper_limit": str(target.upper_limit_value),
                }
            )
    if violations:
        raise SupplementError("SUPPLEMENT_UPPER_LIMIT_HARD_BLOCK", {"violations": violations})
    return {
        "food_contribution": {code: str(value) for code, value in food_daily.items()},
        "supplement_contribution": {code: str(value) for code, value in supplement_totals.items()},
        "combined_exposure": combined,
        "hard_blocks": [],
    }


def order_response(row: NutritionSupplementOrder) -> dict[str, object]:
    return {
        "id": row.id,
        "plan_id": row.plan_id,
        "supplement_id": row.supplement_id,
        "name": row.name,
        "dose_amount": float(row.dose_amount) if row.dose_amount is not None else None,
        "dose_unit": row.dose_unit,
        "daily_units": float(row.daily_units) if row.daily_units is not None else None,
        "frequency": row.frequency,
        "duration_days": row.duration_days,
        "starts_on": row.starts_on,
        "ends_on": row.ends_on,
        "instructions": row.instructions,
        "rationale": row.rationale if row.rationale_user_visible else None,
        "status": row.status.value,
        "linked_gap_codes": row.linked_gap_codes,
        "linked_lab_document_ids": row.linked_lab_document_ids,
        "food_nutrient_contribution": {},
        "supplement_nutrient_contribution": row.nutrient_contribution,
        "combined_exposure_safety": row.audit_metadata.get("pre_activation_exposure", {}),
        "acknowledged_at": row.acknowledged_at,
    }


def _audit_snapshot(row: NutritionSupplementOrder) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(order_response(row), default=str)))


def create_order(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    supplement_id: UUID,
    payload: dict[str, object],
) -> dict[str, object]:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise SupplementError("PHYSICIAN_ROLE_REQUIRED") from error
    plan = db.scalar(
        select(NutritionWeeklyPlan)
        .where(NutritionWeeklyPlan.id == plan_id)
        .options(selectinload(NutritionWeeklyPlan.nutrients))
    )
    supplement = db.get(NutritionSupplementCatalogue, supplement_id)
    if plan is None or supplement is None or supplement.verification_status != "verified":
        raise SupplementError("VERIFIED_SUPPLEMENT_OR_PLAN_NOT_FOUND")
    review = db.scalar(
        select(NutritionPlanPhysicianReview).where(
            NutritionPlanPhysicianReview.plan_id == plan.id,
            NutritionPlanPhysicianReview.physician_user_id == physician_id,
        )
    )
    if review is None:
        raise SupplementError("ASSIGNED_REVIEW_REQUIRED")
    daily_units = Decimal(str(payload["daily_units"]))
    exposure = _safety_check(db, plan, supplement, daily_units)
    contribution = _daily_contribution(supplement, daily_units)
    starts_on = cast(date | None, payload.get("starts_on")) or date.today()
    duration_days = int(str(payload["duration_days"]))
    linked_gap_codes = cast(list[str], payload.get("linked_gap_codes", []))
    linked_lab_document_ids = cast(list[UUID], payload.get("linked_lab_document_ids", []))
    row = NutritionSupplementOrder(
        user_id=plan.user_id,
        plan_id=plan.id,
        supplement_id=supplement.id,
        physician_user_id=physician_id,
        name=supplement.name_fa,
        dose=f"{payload['dose_amount']} {payload['dose_unit']}",
        dose_amount=Decimal(str(payload["dose_amount"])),
        dose_unit=str(payload["dose_unit"]),
        daily_units=daily_units,
        frequency=str(payload["frequency"]),
        duration_days=duration_days,
        starts_on=starts_on,
        ends_on=starts_on + timedelta(days=duration_days - 1),
        instructions=str(payload["instructions"]),
        rationale=str(payload["rationale"]),
        rationale_user_visible=bool(payload["rationale_user_visible"]),
        linked_gap_codes=list(linked_gap_codes),
        linked_lab_document_ids=[str(value) for value in linked_lab_document_ids],
        status=NutritionSupplementOrderStatus.PRESCRIBED,
        nutrient_contribution={code: str(value) for code, value in contribution.items()},
        audit_metadata={"pre_activation_exposure": exposure},
    )
    db.add(row)
    db.flush()
    db.add(
        NutritionSupplementOrderAudit(
            order_id=row.id,
            actor_user_id=physician_id,
            action="prescribed",
            snapshot=_audit_snapshot(row),
        )
    )
    db.commit()
    db.refresh(row)
    return order_response(row)


def transition_order(
    db: Session, physician_id: UUID, order_id: UUID, target: NutritionSupplementOrderStatus
) -> dict[str, object]:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise SupplementError("PHYSICIAN_ROLE_REQUIRED") from error
    row = db.scalar(
        select(NutritionSupplementOrder).where(
            NutritionSupplementOrder.id == order_id,
            NutritionSupplementOrder.physician_user_id == physician_id,
        )
    )
    if row is None or row.supplement_id is None or row.daily_units is None:
        raise SupplementError("SUPPLEMENT_ORDER_NOT_FOUND")
    allowed = {
        NutritionSupplementOrderStatus.PRESCRIBED: {
            NutritionSupplementOrderStatus.ACTIVE,
            NutritionSupplementOrderStatus.CANCELLED,
        },
        NutritionSupplementOrderStatus.ACTIVE: {
            NutritionSupplementOrderStatus.COMPLETED,
            NutritionSupplementOrderStatus.DISCONTINUED,
        },
    }
    if target not in allowed.get(row.status, set()):
        raise SupplementError("INVALID_SUPPLEMENT_ORDER_TRANSITION")
    if target == NutritionSupplementOrderStatus.ACTIVE:
        plan = db.scalar(
            select(NutritionWeeklyPlan)
            .where(NutritionWeeklyPlan.id == row.plan_id)
            .options(selectinload(NutritionWeeklyPlan.nutrients))
        )
        supplement = db.get(NutritionSupplementCatalogue, row.supplement_id)
        if plan is None or supplement is None:
            raise SupplementError("SUPPLEMENT_ORDER_NOT_FOUND")
        row.audit_metadata = {
            **row.audit_metadata,
            "activation_exposure": _safety_check(
                db, plan, supplement, row.daily_units, excluding_order_id=row.id
            ),
        }
    row.status = target
    db.add(
        NutritionSupplementOrderAudit(
            order_id=row.id,
            actor_user_id=physician_id,
            action=target.value,
            snapshot=_audit_snapshot(row),
        )
    )
    db.commit()
    return order_response(row)


def list_physician_orders(
    db: Session, physician_id: UUID, plan_id: UUID
) -> list[dict[str, object]]:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise SupplementError("PHYSICIAN_ROLE_REQUIRED") from error
    review = db.scalar(
        select(NutritionPlanPhysicianReview).where(
            NutritionPlanPhysicianReview.plan_id == plan_id,
            NutritionPlanPhysicianReview.physician_user_id == physician_id,
        )
    )
    if review is None:
        raise SupplementError("ASSIGNED_REVIEW_REQUIRED")
    return [
        order_response(row)
        for row in db.scalars(
            select(NutritionSupplementOrder)
            .where(NutritionSupplementOrder.plan_id == plan_id)
            .order_by(NutritionSupplementOrder.created_at.desc())
        )
    ]


def update_order(
    db: Session,
    physician_id: UUID,
    order_id: UUID,
    supplement_id: UUID,
    payload: dict[str, object],
) -> dict[str, object]:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise SupplementError("PHYSICIAN_ROLE_REQUIRED") from error
    row = db.scalar(
        select(NutritionSupplementOrder).where(
            NutritionSupplementOrder.id == order_id,
            NutritionSupplementOrder.physician_user_id == physician_id,
        )
    )
    if row is None or row.status not in {
        NutritionSupplementOrderStatus.PRESCRIBED,
        NutritionSupplementOrderStatus.ACTIVE,
    }:
        raise SupplementError("SUPPLEMENT_ORDER_NOT_FOUND")
    plan = db.scalar(
        select(NutritionWeeklyPlan)
        .where(NutritionWeeklyPlan.id == row.plan_id)
        .options(selectinload(NutritionWeeklyPlan.nutrients))
    )
    supplement = db.get(NutritionSupplementCatalogue, supplement_id)
    if plan is None or supplement is None or supplement.verification_status != "verified":
        raise SupplementError("VERIFIED_SUPPLEMENT_OR_PLAN_NOT_FOUND")
    daily_units = Decimal(str(payload["daily_units"]))
    exposure = _safety_check(
        db, plan, supplement, daily_units, excluding_order_id=row.id
    )
    starts_on = cast(date | None, payload.get("starts_on")) or row.starts_on or date.today()
    duration_days = int(str(payload["duration_days"]))
    row.supplement_id = supplement.id
    row.name = supplement.name_fa
    row.dose_amount = Decimal(str(payload["dose_amount"]))
    row.dose_unit = str(payload["dose_unit"])
    row.dose = f"{payload['dose_amount']} {payload['dose_unit']}"
    row.daily_units = daily_units
    row.frequency = str(payload["frequency"])
    row.duration_days = duration_days
    row.starts_on = starts_on
    row.ends_on = starts_on + timedelta(days=duration_days - 1)
    row.instructions = str(payload["instructions"])
    row.rationale = str(payload["rationale"])
    row.rationale_user_visible = bool(payload["rationale_user_visible"])
    row.linked_gap_codes = list(cast(list[str], payload.get("linked_gap_codes", [])))
    row.linked_lab_document_ids = [
        str(value) for value in cast(list[UUID], payload.get("linked_lab_document_ids", []))
    ]
    row.nutrient_contribution = {
        code: str(value) for code, value in _daily_contribution(supplement, daily_units).items()
    }
    row.audit_metadata = {**row.audit_metadata, "pre_activation_exposure": exposure}
    db.add(
        NutritionSupplementOrderAudit(
            order_id=row.id,
            actor_user_id=physician_id,
            action="modified",
            snapshot=_audit_snapshot(row),
        )
    )
    db.commit()
    return order_response(row)


def list_user_orders(db: Session, user_id: UUID) -> list[dict[str, object]]:
    return [
        order_response(row)
        for row in db.scalars(
            select(NutritionSupplementOrder)
            .where(NutritionSupplementOrder.user_id == user_id)
            .order_by(NutritionSupplementOrder.created_at.desc())
        )
    ]


def acknowledge_order(
    db: Session, user_id: UUID, order_id: UUID, adherence_note: str | None
) -> dict[str, object]:
    row = db.scalar(
        select(NutritionSupplementOrder).where(
            NutritionSupplementOrder.id == order_id,
            NutritionSupplementOrder.user_id == user_id,
        )
    )
    if row is None:
        raise SupplementError("SUPPLEMENT_ORDER_NOT_FOUND")
    row.acknowledged_at = datetime.now(UTC)
    row.adherence_note = adherence_note
    db.commit()
    return order_response(row)
