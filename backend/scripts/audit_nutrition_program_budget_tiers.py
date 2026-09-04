"""Audit reference monthly costs and derive budget tier hints for nutrition programs."""

from __future__ import annotations

import os
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Ensure models are loaded
import app.main  # noqa: F401
from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
from app.nutrition.meal_catalogue import seed_meal_catalogue
from app.nutrition.plan_service import _planner_foods, _planner_meal_templates
from app.nutrition.program_catalogue import list_programs
from app.nutrition.program_costing import estimate_program_cost
from app.nutrition.seed_program_catalogue import seed_program_catalogue

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho",
)


def run_budget_tier_audit(db: Session) -> list[dict[str, object]]:
    from sqlalchemy import select

    from app.auth.models import User

    # Ensure admin user exists for price snapshot provenance
    admin = db.scalar(select(User).where(User.is_admin.is_(True)))
    if admin is None:
        admin = User(
            email="audit-admin@example.com",
            password_hash="mock-password-not-real",
            is_admin=True,
        )
        db.add(admin)
        db.flush()

    from app.nutrition.catalogue_seed_data import APPROVED_FOODS
    from app.nutrition.enums import FoodVerificationStatus
    from app.nutrition.models import NutritionCatalogueFood

    # Ensure any approved foods previously marked retired in database are restored
    approved_slugs = {item.slug for item in APPROVED_FOODS}
    for food in db.scalars(select(NutritionCatalogueFood)).all():
        if (
            food.slug in approved_slugs
            and food.verification_status is FoodVerificationStatus.RETIRED
        ):
            food.verification_status = FoodVerificationStatus.VERIFIED
    db.commit()

    # Ensure dependencies and programs exist
    seed_base_iranian_food_catalogue(db, commit=True)
    apply_approved_price_snapshot(db)
    seed_meal_catalogue(db)
    seed_program_catalogue(db)

    foods_tuple, _, _ = _planner_foods(db)
    templates_tuple, _ = _planner_meal_templates(db)

    foods_by_id = {food.food_id: food for food in foods_tuple}
    templates_by_id = {tpl.meal_id: tpl for tpl in templates_tuple}

    programs = list_programs(db)
    results: list[dict[str, object]] = []

    header = (
        f"{'Program':<10} {'Diet Style':<20} {'Ref Cost (Toman)':<18} "
        f"{'Min Cost (Toman)':<18} {'Tier Hint':<12} {'Coverage':<10}"
    )
    print(header)
    print("-" * 90)

    for program in sorted(programs, key=lambda p: p.code):
        estimate = estimate_program_cost(
            program,
            main_meal_slots=3,
            snack_slots=1,
            daily_kcal=Decimal("2200"),
            meal_templates_by_id=templates_by_id,
            foods_by_id=foods_by_id,
        )

        ref_cost_toman = int(estimate.estimated_monthly_cost_irr // Decimal("10"))
        min_cost_toman = (
            int(estimate.minimum_adapted_monthly_cost_irr // Decimal("10"))
            if estimate.minimum_adapted_monthly_cost_irr is not None
            else "N/A"
        )
        coverage_str = "complete" if estimate.price_coverage_complete else "partial"

        row = (
            f"{program.code:<10} {program.diet_style.value:<20} "
            f"{ref_cost_toman:<18} {str(min_cost_toman):<18} "
            f"{estimate.effective_budget_tier:<12} {coverage_str:<10}"
        )
        print(row)

        results.append(
            {
                "program_code": program.code,
                "diet_style": program.diet_style.value,
                "reference_monthly_cost_toman": ref_cost_toman,
                "minimum_adapted_monthly_cost_toman": min_cost_toman,
                "budget_tier_hint": estimate.effective_budget_tier,
                "price_coverage": coverage_str,
            }
        )

    return results


def main() -> None:
    engine = create_engine(DATABASE_URL)
    with Session(engine) as db:
        run_budget_tier_audit(db)


if __name__ == "__main__":
    main()
