"""One-time generator for the local Free Exercise DB Persian translation catalog."""

from __future__ import annotations

import argparse
import json
import pprint
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from app.exercises.free_exercise_db_import import (
    map_body_region,
    map_difficulty,
    map_equipment,
    map_muscle_group,
)
from app.exercises.free_exercise_db_translations import CURATED_TRANSLATIONS

TRANSLATE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
TRANSLATION_MODULE = Path(__file__).with_name("free_exercise_db_translations.py")


def normalize_steps(steps: list[str]) -> list[str]:
    normalized = list(steps)
    while len(normalized) > 6:
        normalized[-2:] = [f"{normalized[-2]} {normalized[-1]}"]
    return normalized


def translate_lines(lines: list[str]) -> list[str]:
    query = urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": "fa",
            "dt": "t",
            "q": "\n".join(lines),
        }
    )
    with urlopen(f"{TRANSLATE_ENDPOINT}?{query}", timeout=30) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    translated = "".join(item[0] for item in payload[0])
    result = [line.strip() for line in translated.splitlines() if line.strip()]
    if len(result) != len(lines):
        raise ValueError(f"Expected {len(lines)} translated lines, received {len(result)}")
    return result


def generate(source_root: Path, *, delay_seconds: float) -> dict[str, dict[str, object]]:
    records = json.loads((source_root / "data" / "exercises.json").read_text(encoding="utf-8"))
    catalog = dict(CURATED_TRANSLATIONS)
    for raw in records:
        if not isinstance(raw, dict):
            continue
        source_id = raw.get("id")
        if not isinstance(source_id, str) or source_id in catalog:
            continue
        body_part = raw.get("bodyPart")
        target = raw.get("target")
        equipment = raw.get("equipment")
        difficulty = raw.get("difficulty")
        name = raw.get("name")
        steps = raw.get("steps")
        if not (
            isinstance(body_part, str)
            and isinstance(target, str)
            and isinstance(equipment, str)
            and isinstance(difficulty, str)
            and isinstance(name, str)
            and isinstance(steps, list)
            and all(isinstance(step, str) and step.strip() for step in steps)
        ):
            continue
        if not all(
            (
                map_body_region(body_part),
                map_muscle_group(target),
                map_equipment(equipment),
                map_difficulty(difficulty),
            )
        ):
            continue
        translated = translate_lines([name, *normalize_steps(steps)])
        catalog[source_id] = {"name_fa": translated[0], "instructions_fa": translated[1:]}
        print(f"translated {source_id}", flush=True)
        time.sleep(delay_seconds)
    return catalog


def write_catalog(catalog: dict[str, dict[str, object]], output: Path) -> None:
    rendered = pprint.pformat(catalog, width=100, sort_dicts=True)
    output.write_text(
        "# ruff: noqa: E501\n\n"
        "type ExerciseTranslationData = dict[str, object]\n\n\n"
        f"CURATED_TRANSLATIONS: dict[str, ExerciseTranslationData] = {rendered}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=TRANSLATION_MODULE)
    parser.add_argument("--delay-seconds", type=float, default=0.15)
    args = parser.parse_args()
    write_catalog(
        generate(args.source_root.resolve(), delay_seconds=args.delay_seconds),
        args.output.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
