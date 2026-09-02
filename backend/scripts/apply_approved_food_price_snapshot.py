"""Validate or atomically apply the approved Food Catalogue price snapshot."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.approved_price_snapshot import (
    APPROVED_PRICE_SNAPSHOT,
    PRICE_SNAPSHOT_VERSION,
    ApprovedPriceSnapshotError,
    apply_approved_price_snapshot,
    resolve_snapshot_admin,
    validate_snapshot_against_catalogue,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate or apply Fitsho's approved food price snapshot."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; this is also the default mode.",
    )
    mode.add_argument("--apply", action="store_true", help="Apply the snapshot atomically.")
    parser.add_argument(
        "--admin-email",
        help="Admin email to record as created_by_user_id.",
    )
    return parser


def _print_validation(report) -> None:
    snapshot = report.snapshot
    print(f"snapshot version = {PRICE_SNAPSHOT_VERSION}")
    print(f"snapshot entries = {snapshot.entry_count}")
    print(f"matched verified foods = {report.matched_verified_foods}")
    print(f"missing = {len(snapshot.missing_slugs) + len(report.missing_catalogue_foods)}")
    print(f"extra = {len(snapshot.extra_slugs)}")
    print(f"duplicate slugs = {len(snapshot.duplicate_slugs)}")
    print(f"invalid prices = {len(snapshot.invalid_prices)}")
    print(f"invalid units = {len(snapshot.invalid_units)}")
    print(
        "missing price-mass conversions for non-KG snapshot foods = "
        f"{len(snapshot.missing_price_mass_conversions)}"
    )
    if snapshot.missing_slugs:
        print(f"snapshot missing approved slugs = {', '.join(snapshot.missing_slugs)}")
    if snapshot.extra_slugs:
        print(f"snapshot extra slugs = {', '.join(snapshot.extra_slugs)}")
    if report.missing_catalogue_foods:
        print(
            "catalogue missing approved slugs = "
            f"{', '.join(report.missing_catalogue_foods)}"
        )


def main() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        report = validate_snapshot_against_catalogue(db, APPROVED_PRICE_SNAPSHOT)
        _print_validation(report)
        if not report.is_valid:
            print("snapshot validation failed; no apply performed", file=sys.stderr)
            return 1
        try:
            resolve_snapshot_admin(db, admin_email=args.admin_email)
            if args.apply:
                result = apply_approved_price_snapshot(
                    db,
                    admin_email=args.admin_email,
                    entries=APPROVED_PRICE_SNAPSHOT,
                )
                print(f"created overrides = {result.created_count}")
                print(f"replaced overrides = {result.replaced_count}")
                print(f"skipped overrides = {result.skipped_count}")
            else:
                print("dry-run only; no mutation performed")
        except ApprovedPriceSnapshotError as error:
            print(str(error), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
