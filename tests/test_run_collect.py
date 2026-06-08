from __future__ import annotations

import json
from pathlib import Path

from nlp_term.collect import run_collect
from nlp_term.collect.source_inventory import SourceSpec


def test_run_probe_records_cached_fetch_failure_evidence(tmp_path: Path, monkeypatch) -> None:
    raw_path = tmp_path / "cached.html"
    raw_path.write_text("cached source", encoding="utf-8")
    output_path = tmp_path / "source_probe.json"
    output_path.write_text(
        json.dumps(
            [
                {
                    "raw": {
                        "source_id": "academic_calendar",
                        "label": 2,
                        "domain": "academic_calendar",
                        "url": "https://plus.cnu.ac.kr/calendar",
                        "fetched_at": "2026-06-08T00:00:00+09:00",
                        "content_type": "text/html",
                        "raw_path": str(raw_path),
                        "status_code": 200,
                        "checksum": "cached-checksum",
                    },
                    "verification": {
                        "source_id": "academic_calendar",
                        "official_chain_ok": True,
                        "parser_name": "calendar_stage_inventory",
                        "parser_version": "0.1.0",
                        "evidence": ["https://plus.cnu.ac.kr/calendar"],
                        "warnings": [],
                        "verified_at": "2026-06-08T00:00:00+09:00",
                    },
                    "inventory": {"stage": "stage0", "active": True, "freshness_policy": "snapshot"},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    failures_path = tmp_path / "collection_failures.json"
    spec = SourceSpec(
        source_id="academic_calendar",
        label=2,
        domain="academic_calendar",
        url="https://plus.cnu.ac.kr/calendar",
        parser_type="calendar",
        official_chain_ok=True,
    )

    monkeypatch.setattr(run_collect, "iter_specs", lambda *, stage, active_only: [spec])

    def _raise_collect_spec(spec: SourceSpec, *, fetch: bool):
        raise RuntimeError("network timeout")

    monkeypatch.setattr(run_collect, "collect_spec", _raise_collect_spec)

    run_collect.run_probe(output_path, fetch=True, failure_output_path=failures_path)

    probe = json.loads(output_path.read_text(encoding="utf-8"))
    warnings = probe[0]["verification"]["warnings"]
    assert any("reused cached raw snapshot" in warning for warning in warnings)
    failures = json.loads(failures_path.read_text(encoding="utf-8"))
    assert failures == [
        {
            "source_id": "academic_calendar",
            "url": "https://plus.cnu.ac.kr/calendar",
            "stage": "stage0",
            "active": True,
            "exception_type": "RuntimeError",
            "reason": "network timeout",
            "reused_cached_raw": True,
            "cached_raw_path": str(raw_path),
            "cached_checksum": "cached-checksum",
        }
    ]
