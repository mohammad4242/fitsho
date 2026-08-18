"""Explicit CLI entry point for exercise programming metadata backfill."""

import argparse

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.programming_metadata import (
    ProgrammingMetadataBackfillReport,
    backfill_programming_metadata,
)


def format_backfill_report(report: ProgrammingMetadataBackfillReport, *, dry_run: bool) -> str:
    mode = "dry-run" if dry_run else "applied"
    fields = (
        ", ".join(f"{name}={count}" for name, count in sorted(report.field_updates.items()))
        or "none"
    )
    return (
        f"Programming metadata backfill ({mode}): "
        f"inspected={report.inspected}, updated={report.updated}, skipped={report.skipped}, "
        f"field_updates={fields}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="persist inferred values; without this flag the command is a dry-run",
    )
    args = parser.parse_args()
    dry_run = not args.apply
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        report = backfill_programming_metadata(db, dry_run=dry_run)
    print(format_backfill_report(report, dry_run=dry_run))


if __name__ == "__main__":
    main()
