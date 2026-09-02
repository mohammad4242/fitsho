"""Approved manual Food Catalogue price snapshot and its atomic application."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.nutrition.catalogue_seed_data import APPROVED_FOODS
from app.nutrition.enums import FoodVerificationStatus
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionFoodPriceOverride,
)
from app.nutrition.price_mass_conversion import (
    VALID_PRICE_CANONICAL_UNITS,
    PriceCanonicalUnit,
    PriceMassConversionError,
    planner_price_irr_per_gram,
)
from app.nutrition.price_overrides import create_price_override
from app.nutrition.schemas import FoodPriceOverrideInput

PRICE_SNAPSHOT_VERSION: Final = "iran-retail-1405-06-11-v1"
PRICE_SNAPSHOT_AS_OF_DATE: Final = date(2026, 9, 2)
PRICE_SNAPSHOT_REASON: Final = (
    "قیمت مرجع دستی تأییدشده بازار ایران؛ "
    f"snapshot={PRICE_SNAPSHOT_VERSION}; as_of={PRICE_SNAPSHOT_AS_OF_DATE.isoformat()}"
)


@dataclass(frozen=True)
class ApprovedFoodPriceSnapshotEntry:
    slug: str
    reference_price_toman: Decimal
    canonical_unit: PriceCanonicalUnit


def _entry(
    slug: str, reference_price_toman: str, canonical_unit: PriceCanonicalUnit
) -> ApprovedFoodPriceSnapshotEntry:
    return ApprovedFoodPriceSnapshotEntry(
        slug=slug,
        reference_price_toman=Decimal(reference_price_toman),
        canonical_unit=canonical_unit,
    )


APPROVED_PRICE_SNAPSHOT: Final[tuple[ApprovedFoodPriceSnapshotEntry, ...]] = (
    _entry("chicken-breast", "630000", "TOMAN_PER_KG"),
    _entry("chicken-thigh-skinless", "460000", "TOMAN_PER_KG"),
    _entry("ground-beef", "1420000", "TOMAN_PER_KG"),
    _entry("beef-chuck-stew-meat", "1600000", "TOMAN_PER_KG"),
    _entry("lamb", "1800000", "TOMAN_PER_KG"),
    _entry("white-fish", "630000", "TOMAN_PER_KG"),
    _entry("rainbow-trout", "650000", "TOMAN_PER_KG"),
    _entry("canned-tuna", "1130000", "TOMAN_PER_KG"),
    _entry("egg", "21000", "TOMAN_PER_UNIT"),
    _entry("lentils", "400000", "TOMAN_PER_KG"),
    _entry("chickpeas", "430000", "TOMAN_PER_KG"),
    _entry("pinto-beans", "610000", "TOMAN_PER_KG"),
    _entry("red-kidney-beans", "500000", "TOMAN_PER_KG"),
    _entry("white-beans", "540000", "TOMAN_PER_KG"),
    _entry("black-eyed-peas", "500000", "TOMAN_PER_KG"),
    _entry("split-peas", "480000", "TOMAN_PER_KG"),
    _entry("mung-beans", "525000", "TOMAN_PER_KG"),
    _entry("soybeans", "500000", "TOMAN_PER_KG"),
    _entry("basmati-rice", "350000", "TOMAN_PER_KG"),
    _entry("sangak-bread", "15500", "TOMAN_PER_UNIT"),
    _entry("barbari-bread", "10000", "TOMAN_PER_UNIT"),
    _entry("lavash-bread", "2700", "TOMAN_PER_UNIT"),
    _entry("taftoon-bread", "4500", "TOMAN_PER_UNIT"),
    _entry("oats", "370000", "TOMAN_PER_KG"),
    _entry("wheat-flour", "140000", "TOMAN_PER_KG"),
    _entry("barley", "250000", "TOMAN_PER_KG"),
    _entry("potato", "95000", "TOMAN_PER_KG"),
    _entry("corn", "130000", "TOMAN_PER_KG"),
    _entry("pasta", "100000", "TOMAN_PER_KG"),
    _entry("milk", "120000", "TOMAN_PER_LITER"),
    _entry("plain-yogurt", "135000", "TOMAN_PER_KG"),
    _entry("low-fat-cheese", "520000", "TOMAN_PER_KG"),
    _entry("mozzarella", "1750000", "TOMAN_PER_KG"),
    _entry("tomato", "72000", "TOMAN_PER_KG"),
    _entry("tomato-paste", "200000", "TOMAN_PER_KG"),
    _entry("cucumber", "75000", "TOMAN_PER_KG"),
    _entry("onion", "56000", "TOMAN_PER_KG"),
    _entry("carrot", "126000", "TOMAN_PER_KG"),
    _entry("lettuce", "67000", "TOMAN_PER_KG"),
    _entry("cabbage", "60000", "TOMAN_PER_KG"),
    _entry("spinach", "60000", "TOMAN_PER_KG"),
    _entry("zucchini", "58000", "TOMAN_PER_KG"),
    _entry("eggplant", "90000", "TOMAN_PER_KG"),
    _entry("bell-pepper", "86000", "TOMAN_PER_KG"),
    _entry("mushroom", "170000", "TOMAN_PER_KG"),
    _entry("celery", "82000", "TOMAN_PER_KG"),
    _entry("broccoli", "115000", "TOMAN_PER_KG"),
    _entry("green-beans", "106000", "TOMAN_PER_KG"),
    _entry("cauliflower", "60000", "TOMAN_PER_KG"),
    _entry("mixed-herbs", "156000", "TOMAN_PER_KG"),
    _entry("olive-oil", "1400000", "TOMAN_PER_LITER"),
    _entry("vegetable-oil", "410000", "TOMAN_PER_LITER"),
    _entry("butter", "1100000", "TOMAN_PER_KG"),
    _entry("walnuts", "3200000", "TOMAN_PER_KG"),
    _entry("almonds", "3500000", "TOMAN_PER_KG"),
    _entry("peanuts", "950000", "TOMAN_PER_KG"),
    _entry("creamy-peanut-butter", "1160000", "TOMAN_PER_KG"),
    _entry("sesame", "765000", "TOMAN_PER_KG"),
    _entry("tahini", "785000", "TOMAN_PER_KG"),
    _entry("apple", "150000", "TOMAN_PER_KG"),
    _entry("banana", "225000", "TOMAN_PER_KG"),
    _entry("orange", "70000", "TOMAN_PER_KG"),
    _entry("tangerine", "70000", "TOMAN_PER_KG"),
    _entry("kiwi", "125000", "TOMAN_PER_KG"),
    _entry("pomegranate", "80000", "TOMAN_PER_KG"),
    _entry("grapes", "150000", "TOMAN_PER_KG"),
    _entry("dates", "500000", "TOMAN_PER_KG"),
    _entry("raisins", "1100000", "TOMAN_PER_KG"),
    _entry("barberries", "1480000", "TOMAN_PER_KG"),
    _entry("strawberries", "325000", "TOMAN_PER_KG"),
    _entry("watermelon", "30000", "TOMAN_PER_KG"),
    _entry("melon", "65000", "TOMAN_PER_KG"),
)


@dataclass(frozen=True)
class ApprovedPriceSnapshotValidation:
    entry_count: int
    missing_slugs: tuple[str, ...]
    extra_slugs: tuple[str, ...]
    duplicate_slugs: tuple[str, ...]
    invalid_prices: tuple[str, ...]
    invalid_units: tuple[str, ...]
    missing_price_mass_conversions: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not any(
            (
                self.missing_slugs,
                self.extra_slugs,
                self.duplicate_slugs,
                self.invalid_prices,
                self.invalid_units,
                self.missing_price_mass_conversions,
            )
        )


@dataclass(frozen=True)
class ApprovedPriceSnapshotCatalogueValidation:
    snapshot: ApprovedPriceSnapshotValidation
    matched_verified_foods: int
    missing_catalogue_foods: tuple[str, ...]
    extra_catalogue_foods: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return (
            self.snapshot.is_valid
            and not self.missing_catalogue_foods
            and not self.extra_catalogue_foods
        )


class ApprovedPriceSnapshotError(ValueError):
    pass


class ApprovedPriceSnapshotValidationError(ApprovedPriceSnapshotError):
    def __init__(self, report: ApprovedPriceSnapshotValidation) -> None:
        self.report = report
        super().__init__("Approved price snapshot validation failed")


class ApprovedPriceSnapshotCatalogueMismatchError(ApprovedPriceSnapshotError):
    def __init__(self, report: ApprovedPriceSnapshotCatalogueValidation) -> None:
        self.report = report
        detail = ", ".join(
            (
                f"missing={','.join(report.missing_catalogue_foods) or '0'}",
                f"extra={','.join(report.extra_catalogue_foods) or '0'}",
            )
        )
        super().__init__(f"Approved price snapshot catalogue mismatch: {detail}")


class ApprovedPriceSnapshotAdminError(ApprovedPriceSnapshotError):
    pass


@dataclass(frozen=True)
class ApprovedPriceSnapshotApplyResult:
    snapshot_version: str
    matched_verified_foods: int
    created_count: int
    replaced_count: int
    skipped_count: int


def validate_approved_price_snapshot(
    entries: Sequence[ApprovedFoodPriceSnapshotEntry] = APPROVED_PRICE_SNAPSHOT,
) -> ApprovedPriceSnapshotValidation:
    snapshot_slugs = {entry.slug for entry in entries}
    approved_slugs = {food.slug for food in APPROVED_FOODS}
    counts = Counter(entry.slug for entry in entries)
    duplicate_slugs = tuple(sorted(slug for slug, count in counts.items() if count > 1))
    invalid_prices: list[str] = []
    invalid_units: list[str] = []
    missing_conversions: list[str] = []
    for entry in entries:
        if (
            not isinstance(entry.reference_price_toman, Decimal)
            or not entry.reference_price_toman.is_finite()
            or entry.reference_price_toman <= Decimal("0")
        ):
            invalid_prices.append(entry.slug)
        if entry.canonical_unit not in VALID_PRICE_CANONICAL_UNITS:
            invalid_units.append(entry.slug)
            continue
        if entry.canonical_unit == "TOMAN_PER_KG":
            continue
        try:
            planner_price_irr_per_gram(
                food_slug=entry.slug,
                reference_price_toman=entry.reference_price_toman,
                canonical_unit=entry.canonical_unit,
            )
        except (PriceMassConversionError, TypeError, ValueError):
            missing_conversions.append(entry.slug)
    return ApprovedPriceSnapshotValidation(
        entry_count=len(entries),
        missing_slugs=tuple(sorted(approved_slugs - snapshot_slugs)),
        extra_slugs=tuple(sorted(snapshot_slugs - approved_slugs)),
        duplicate_slugs=duplicate_slugs,
        invalid_prices=tuple(invalid_prices),
        invalid_units=tuple(invalid_units),
        missing_price_mass_conversions=tuple(dict.fromkeys(sorted(missing_conversions))),
    )


def validate_snapshot_against_catalogue(
    db: Session,
    entries: Sequence[ApprovedFoodPriceSnapshotEntry] = APPROVED_PRICE_SNAPSHOT,
) -> ApprovedPriceSnapshotCatalogueValidation:
    snapshot = validate_approved_price_snapshot(entries)
    verified_slugs = set(
        db.scalars(
            select(NutritionCatalogueFood.slug).where(
                NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED
            )
        ).all()
    )
    snapshot_slugs = {entry.slug for entry in entries}
    return ApprovedPriceSnapshotCatalogueValidation(
        snapshot=snapshot,
        matched_verified_foods=len(snapshot_slugs & verified_slugs),
        missing_catalogue_foods=tuple(sorted(snapshot_slugs - verified_slugs)),
        extra_catalogue_foods=(),
    )


def resolve_snapshot_admin(db: Session, *, admin_email: str | None = None) -> User:
    if admin_email is not None:
        user = db.scalar(select(User).where(User.email == admin_email))
        if user is None:
            raise ApprovedPriceSnapshotAdminError(f"Admin user not found: {admin_email}")
        if not user.is_admin:
            raise ApprovedPriceSnapshotAdminError(f"User is not an admin: {admin_email}")
        return user
    admins = db.scalars(select(User).where(User.is_admin.is_(True)).order_by(User.email)).all()
    if not admins:
        raise ApprovedPriceSnapshotAdminError("No admin user exists")
    if len(admins) > 1:
        emails = ", ".join(str(admin.email) for admin in admins)
        raise ApprovedPriceSnapshotAdminError(f"Multiple admin users exist: {emails}")
    return admins[0]


def _has_same_snapshot_value(
    override: NutritionFoodPriceOverride,
    entry: ApprovedFoodPriceSnapshotEntry,
) -> bool:
    return (
        override.reference_price_toman == entry.reference_price_toman
        and override.canonical_unit == entry.canonical_unit
        and f"snapshot={PRICE_SNAPSHOT_VERSION}" in override.reason
    )


def apply_approved_price_snapshot(
    db: Session,
    *,
    admin_email: str | None = None,
    entries: Sequence[ApprovedFoodPriceSnapshotEntry] = APPROVED_PRICE_SNAPSHOT,
    created_at: datetime | None = None,
) -> ApprovedPriceSnapshotApplyResult:
    catalogue_report = validate_snapshot_against_catalogue(db, entries)
    if not catalogue_report.snapshot.is_valid:
        raise ApprovedPriceSnapshotValidationError(catalogue_report.snapshot)
    if not catalogue_report.is_valid:
        raise ApprovedPriceSnapshotCatalogueMismatchError(catalogue_report)
    admin = resolve_snapshot_admin(db, admin_email=admin_email)
    foods = {
        food.slug: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(
                NutritionCatalogueFood.slug.in_([entry.slug for entry in entries]),
                NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
            )
        ).all()
    }
    timestamp = created_at or datetime.now(UTC)
    created_count = 0
    replaced_count = 0
    skipped_count = 0
    try:
        for entry in entries:
            food = foods[entry.slug]
            active = db.scalars(
                select(NutritionFoodPriceOverride).where(
                    NutritionFoodPriceOverride.food_id == food.id,
                    NutritionFoodPriceOverride.active.is_(True),
                )
            ).all()
            if len(active) == 1 and _has_same_snapshot_value(active[0], entry):
                skipped_count += 1
                continue
            if active:
                replaced_count += 1
            create_price_override(
                db,
                food=food,
                admin_user_id=admin.id,
                payload=FoodPriceOverrideInput(
                    reference_price_toman=entry.reference_price_toman,
                    canonical_unit=entry.canonical_unit,
                    reason=PRICE_SNAPSHOT_REASON,
                ),
                created_at=timestamp,
                commit=False,
            )
            created_count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ApprovedPriceSnapshotApplyResult(
        snapshot_version=PRICE_SNAPSHOT_VERSION,
        matched_verified_foods=catalogue_report.matched_verified_foods,
        created_count=created_count,
        replaced_count=replaced_count,
        skipped_count=skipped_count,
    )
