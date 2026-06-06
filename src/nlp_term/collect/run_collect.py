from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.collect.source_inventory import Stage, collect_spec, iter_specs, verify_spec
from nlp_term.paths import ensure_parent


def run_probe(
    output_path: Path,
    *,
    fetch: bool = False,
    stage: Stage | str = "stage0",
    active_only: bool = True,
) -> None:
    rows = []
    for spec in iter_specs(stage=stage, active_only=active_only):
        raw = collect_spec(spec, fetch=fetch)
        verification = verify_spec(spec, raw)
        rows.append(
            {
                "raw": raw.model_dump(),
                "verification": verification.model_dump(),
                "inventory": spec.metadata(),
            }
        )
    ensure_parent(output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write source probe metadata without final labeling decisions.")
    parser.add_argument("--output", type=Path, default=Path("data/sources/source_probe.json"))
    parser.add_argument("--fetch", action="store_true", help="Download raw source snapshots before writing metadata.")
    parser.add_argument("--stage", choices=["stage0", "stage1", "stage2", "all"], default="stage0")
    parser.add_argument("--include-inactive", action="store_true", help="Include inactive future inventory rows.")
    args = parser.parse_args()
    run_probe(args.output, fetch=args.fetch, stage=args.stage, active_only=not args.include_inactive)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
