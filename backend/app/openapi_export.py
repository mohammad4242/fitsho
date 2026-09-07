from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import app


def export_openapi(output: Path) -> None:
    document = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Fitsho's deterministic OpenAPI document")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_openapi(args.output)


if __name__ == "__main__":
    main()
