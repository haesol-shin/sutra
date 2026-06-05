from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.collect import academic_calendar, dining, graduation, notices, shuttle
from nlp_term.paths import ensure_parent


COLLECTORS = [graduation, notices, academic_calendar, dining, shuttle]


def run_probe(output_path: Path) -> None:
    rows = []
    for module in COLLECTORS:
        for raw in module.collect():
            verification = module.verify(raw)
            rows.append({"raw": raw.model_dump(), "verification": verification.model_dump()})
    ensure_parent(output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write source probe metadata without final labeling decisions.")
    parser.add_argument("--output", type=Path, default=Path("data/sources/source_probe.json"))
    args = parser.parse_args()
    run_probe(args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
