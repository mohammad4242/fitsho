from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.focus_manifest import (
    MANIFEST_PATH,
    FocusManifestEntry,
    UnresolvedMuscleFocusError,
    manifest_entry_for_exercise,
)
from app.exercises.models import Exercise
from app.exercises.taxonomy import is_compatible_muscle_focus


@dataclass(frozen=True)
class FocusAuditReport:
    entries: tuple[FocusManifestEntry, ...]
    unresolved: tuple[str, ...]
    incompatible: tuple[str, ...]

    @property
    def total(self) -> int:
        return len(self.entries) + len(self.unresolved)

    @property
    def known_primary_count(self) -> int:
        return sum(entry.primary_muscle is not None for entry in self.entries)

    @property
    def classified_count(self) -> int:
        return sum(entry.muscle_focus is not None for entry in self.entries)


def audit_catalogue(db: Session) -> FocusAuditReport:
    entries: list[FocusManifestEntry] = []
    unresolved: list[str] = []
    incompatible: list[str] = []
    exercises = db.scalars(select(Exercise).order_by(Exercise.slug.asc(), Exercise.id.asc()))
    for exercise in exercises:
        try:
            entry = manifest_entry_for_exercise(exercise)
        except UnresolvedMuscleFocusError as error:
            unresolved.append(str(error))
            continue
        entries.append(entry)
        if not is_compatible_muscle_focus(entry.primary_muscle, entry.muscle_focus):
            incompatible.append(entry.key)
    return FocusAuditReport(
        entries=tuple(entries),
        unresolved=tuple(unresolved),
        incompatible=tuple(incompatible),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit exercise muscle-focus classification")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        report = audit_catalogue(db)
    summary = {
        "total": report.total,
        "known_primary": report.known_primary_count,
        "classified": report.classified_count,
        "null_primary": sum(entry.primary_muscle is None for entry in report.entries),
        "unresolved": list(report.unresolved),
        "incompatible": list(report.incompatible),
    }
    if report.unresolved or report.incompatible:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1
    if arguments.format == "json":
        arguments.output.write_text(
            json.dumps(
                [entry.as_json() for entry in report.entries],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
