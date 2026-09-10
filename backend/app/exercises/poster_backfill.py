from __future__ import annotations

import json

from app.config import get_settings
from app.exercises.media_storage import backfill_exercise_video_posters


def main() -> int:
    report = backfill_exercise_video_posters(settings=get_settings())
    print(
        json.dumps(
            {
                "created": report.created,
                "failed": report.failed,
                "failures": report.failures,
                "reused": report.reused,
                "scanned": report.scanned,
            },
            ensure_ascii=False,
        )
    )
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
