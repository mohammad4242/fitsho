import argparse
import sys
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.admin.exceptions import AdminUserNotFoundError
from app.admin.service import grant_admin
from app.config import get_settings
from app.database.session import get_engine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grant Fitsho administrator access")
    parser.add_argument("email", help="Email address of an existing Fitsho user")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    try:
        with Session(get_engine(settings.database_url)) as db:
            user = grant_admin(db, args.email)
    except AdminUserNotFoundError:
        print("User not found.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Administrator access could not be granted.", file=sys.stderr)
        return 1

    print(f"Administrator access granted to {user.email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
