"""Seed the approved Food and Meal Catalogues."""

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
from app.nutrition.meal_catalogue import seed_meal_catalogue


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        seed_base_iranian_food_catalogue(db, commit=False)
        seed_meal_catalogue(db)


if __name__ == "__main__":
    main()
