"""Seed the deterministic Nutrition Engine catalogue used by CI audits."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

# Register every SQLAlchemy model before the User relationship is configured.
import app.main  # noqa: F401
from app.auth.models import User
from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
from app.nutrition.meal_catalogue import seed_meal_catalogue
from app.nutrition.seed_program_catalogue import seed_program_catalogue

BENCHMARK_ADMIN_EMAIL = "ci-nutrition-benchmark-admin@example.com"


def seed_nutrition_benchmark(db: Session) -> None:
    """Create all verified nutrition inputs needed by the CI audit suite."""
    seed_base_iranian_food_catalogue(db, commit=False)
    seed_meal_catalogue(db, commit=False)

    admin = db.scalar(
        select(User)
        .where(User.is_admin.is_(True))
        .order_by(User.email.asc())
    )
    if admin is None:
        admin = User(
            email=BENCHMARK_ADMIN_EMAIL,
            password_hash="ci-nutrition-benchmark-placeholder",
            is_admin=True,
        )
        db.add(admin)
        db.flush()
    db.commit()

    apply_approved_price_snapshot(db, admin_email=admin.email)
    seed_program_catalogue(db)


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        seed_nutrition_benchmark(db)
    print("Seeded nutrition benchmark catalogue, prices, and programs.")


if __name__ == "__main__":
    main()
