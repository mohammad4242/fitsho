from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.retention import cleanup_private_nutrition_files


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        result = cleanup_private_nutrition_files(db, settings)
    print(
        f"food_photos_purged={result.food_photos_purged} "
        f"lab_documents_purged={result.lab_documents_purged}"
    )


if __name__ == "__main__":
    main()
