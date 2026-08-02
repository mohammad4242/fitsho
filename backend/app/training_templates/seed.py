from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.training_templates.service import seed_training_program_templates


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        result = seed_training_program_templates(db)
    print(
        f"Seeded {result.templates} templates, {result.linked_slots} linked slots, "
        f"and {result.placeholder_slots} placeholders."
    )


if __name__ == "__main__":
    main()
