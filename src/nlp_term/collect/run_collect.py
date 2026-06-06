from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.collect.source_inventory import Stage, collect_spec, iter_specs, verify_spec
from nlp_term.paths import ensure_parent
from nlp_term.schemas import RawSource


def run_probe(
    output_path: Path,
    *,
    fetch: bool = False,
    stage: Stage | str = "stage0",
    active_only: bool = True,
) -> None:
    rows = []
    cached_rows = _cached_raw_sources(output_path)
    for spec in iter_specs(stage=stage, active_only=active_only):
        try:
            raw = collect_spec(spec, fetch=fetch)
            fetch_warning = None
        except Exception as exc:
            raw = cached_rows.get(spec.source_id)
            if raw is None or not Path(raw.raw_path).exists():
                raise
            fetch_warning = f"fetch failed; reused cached raw snapshot: {type(exc).__name__}"
        verification = verify_spec(spec, raw)
        if fetch_warning:
            verification.warnings.append(fetch_warning)
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


def _cached_raw_sources(output_path: Path) -> dict[str, RawSource]:
    if not output_path.exists():
        return {}
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, list):
        return {}
    cached = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            raw = RawSource.model_validate(row.get("raw"))
        except Exception:
            continue
        cached[raw.source_id] = raw
    return cached


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
