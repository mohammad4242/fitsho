"""Seed the approved Iranian base-food vocabulary without prepared foods."""

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        seed_base_iranian_food_catalogue(db)


if __name__ == "__main__":
    main()
