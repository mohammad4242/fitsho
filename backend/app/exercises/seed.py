from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.service import SeedResult, seed_exercises


def format_seed_result(result: SeedResult) -> str:
    alternative_label = "alternative" if result.alternatives == 1 else "alternatives"
    return f"Seeded {result.exercises} exercises and {result.alternatives} {alternative_label}."


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        result = seed_exercises(db)
    print(format_seed_result(result))


if __name__ == "__main__":
    main()
