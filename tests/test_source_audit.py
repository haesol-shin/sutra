from __future__ import annotations

import json
from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_audit import OfficialLinkEvidence, build_source_audit
from nlp_term.collect.source_inventory import iter_specs


def test_source_audit_freezes_stage0_active_sources() -> None:
    report = build_source_audit(
        source_probe_path=Path("data/sources/source_probe.json"),
        official_link_evidence=[],
    )

    assert report.stage0_active_count == 10
    stage0_rows = [row for row in report.rows if row.stage == "stage0" and row.active]
    assert len(stage0_rows) == 10
    assert {row.decision for row in stage0_rows} == {"retain"}


def test_source_audit_defers_inactive_candidates() -> None:
    report = build_source_audit(
        source_probe_path=Path("data/sources/source_probe.json"),
        official_link_evidence=[],
    )

    inactive_rows = [row for row in report.rows if not row.active]
    assert inactive_rows
    assert {row.decision for row in inactive_rows} == {"defer"}


def test_source_audit_records_verified_dining_with_official_link_evidence() -> None:
    report = build_source_audit(
        source_probe_path=Path("data/sources/source_probe.json"),
        official_link_evidence=[
            OfficialLinkEvidence(
                source_id="cnu_mobile_food",
                linking_source_url="https://plus.cnu.ac.kr/html/kr/sub05/sub05_050401.html",
                linked_url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
                evidence_text="CNU welfare page links to 금주의식단",
            )
        ],
    )

    dining = next(row for row in report.rows if row.source_id == "cnu_mobile_food")
    assert dining.official_chain_status == "verified"
    assert any("plus.cnu.ac.kr" in item and "mobileadmin.cnu.ac.kr" in item for item in dining.official_chain_evidence)


def test_source_audit_raw_rows_have_required_provenance_when_probe_exists(tmp_path: Path) -> None:
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "academic_calendar")
    raw_path = tmp_path / "academic_calendar.html"
    raw_path.write_text("학사일정", encoding="utf-8")
    probe_path = tmp_path / "source_probe.json"
    probe_path.write_text(
        json.dumps(
            [
                {
                    "raw": {
                        "source_id": spec.source_id,
                        "label": spec.label,
                        "domain": spec.domain,
                        "url": spec.url,
                        "fetched_at": "2026-06-08T00:00:00+00:00",
                        "content_type": "text/html",
                        "raw_path": str(raw_path),
                        "status_code": 200,
                        "checksum": "abc",
                    },
                    "verification": {
                        "source_id": spec.source_id,
                        "official_chain_ok": True,
                        "parser_name": "calendar_stage_inventory",
                        "parser_version": PARSER_VERSION,
                        "evidence": [spec.url],
                        "warnings": [],
                        "verified_at": "2026-06-08T00:00:00+00:00",
                    },
                    "inventory": spec.metadata(),
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_source_audit(source_probe_path=probe_path)

    row = next(item for item in report.rows if item.source_id == "academic_calendar")
    assert row.raw_status_code == 200
    assert row.raw_checksum == "abc"
    assert row.raw_fetched_at == "2026-06-08T00:00:00+00:00"
    assert row.parser_name == "calendar_stage_inventory"
    assert row.parser_version == PARSER_VERSION
    assert row.official_chain_status == "verified"
