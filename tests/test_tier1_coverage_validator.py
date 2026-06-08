from __future__ import annotations

import json
from pathlib import Path

import pytest

from nlp_term.validators import validate_tier1_coverage


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _probe_row(
    source_id: str,
    *,
    domain: str,
    label: int,
    official_chain_ok: bool = True,
    freshness_policy: str = "static",
    index_eligible: bool = True,
) -> dict:
    return {
        "raw": {
            "source_id": source_id,
            "label": label,
            "domain": domain,
            "url": f"https://plus.cnu.ac.kr/{source_id}",
            "fetched_at": "2026-06-08T00:00:00+09:00",
            "content_type": "text/html",
            "raw_path": f"data/raw/{domain}/{source_id}.html",
            "status_code": 200,
            "checksum": f"{source_id}-checksum",
        },
        "verification": {
            "source_id": source_id,
            "official_chain_ok": official_chain_ok,
            "parser_name": "test_parser",
            "parser_version": "0.1.0",
            "evidence": [f"https://plus.cnu.ac.kr/{source_id}"],
            "warnings": [],
            "verified_at": "2026-06-08T00:00:00+09:00",
        },
        "inventory": {
            "stage": "stage0",
            "active": True,
            "freshness_policy": freshness_policy,
            "index_eligible": index_eligible,
        },
    }


def _doc(
    doc_id: str,
    *,
    source_id: str,
    domain: str,
    label: int,
    row_type: str | None = None,
    title: str | None = None,
) -> dict:
    metadata = {
        "generation_method": "structured_row" if row_type else "source_parse",
        "index_eligible": True,
        "lifecycle_status": "index_eligible",
        "source_domain": domain,
    }
    if row_type:
        metadata["row_type"] = row_type
    return {
        "doc_id": doc_id,
        "label": label,
        "domain": domain,
        "title": title or doc_id,
        "body": f"{doc_id} body text with enough project-backed information.",
        "date": "2026-06-08",
        "source_url": f"https://plus.cnu.ac.kr/{source_id}",
        "source_id": source_id,
        "section": None,
        "metadata": metadata,
    }


def test_validate_tier1_coverage_accepts_balanced_index_eligible_docs(tmp_path: Path) -> None:
    probe_path = tmp_path / "source_probe.json"
    _write_json(
        probe_path,
        [
            _probe_row("graduation_ai", domain="graduation", label=0),
            _probe_row("calendar", domain="academic_calendar", label=2),
            _probe_row("dining", domain="dining", label=3, official_chain_ok=False, freshness_policy="short_ttl"),
        ],
    )
    _write_json(
        tmp_path / "knowledge_seed.json",
        [
            _doc("grad-1", source_id="graduation_ai", domain="graduation", label=0, row_type="graduation_requirement"),
            _doc("grad-2", source_id="graduation_ai", domain="graduation", label=0, row_type="graduation_requirement"),
            _doc("cal-1", source_id="calendar", domain="academic_calendar", label=2, row_type="academic_calendar_event"),
            _doc("dining-1", source_id="dining", domain="dining", label=3, row_type="dining_menu"),
            _doc("notice-1", source_id="notice", domain="notices", label=1, row_type="notice_board_item"),
            _doc("shuttle-1", source_id="shuttle", domain="shuttle", label=4, row_type="shuttle_route"),
        ],
    )

    validate_tier1_coverage(
        data_dir=tmp_path,
        source_probe_path=probe_path,
        min_index_eligible_sources=3,
        min_raw_sources=3,
        min_accepted_docs=6,
        min_structured_rows=5,
        min_index_chunk_candidates=6,
        min_graduation_docs=2,
        min_graduation_rows=2,
        min_notice_docs=1,
        max_notice_docs=2,
        max_notice_doc_ratio=0.30,
        max_notice_duplicate_ratio=0.05,
        max_source_concentration=0.35,
        min_calendar_rows=1,
        min_dining_rows=1,
        min_shuttle_rows=1,
    )


def test_validate_tier1_coverage_rejects_notice_dominance(tmp_path: Path) -> None:
    probe_path = tmp_path / "source_probe.json"
    _write_json(probe_path, [_probe_row("notice", domain="notices", label=1)])
    docs = [
        _doc(f"notice-{index}", source_id="notice", domain="notices", label=1, row_type="notice_board_item")
        for index in range(4)
    ]
    docs.extend(
        [
            _doc("grad-1", source_id="graduation_ai", domain="graduation", label=0, row_type="graduation_requirement"),
            _doc("cal-1", source_id="calendar", domain="academic_calendar", label=2, row_type="academic_calendar_event"),
        ]
    )
    _write_json(tmp_path / "knowledge_seed.json", docs)

    with pytest.raises(ValueError, match="notice doc ratio"):
        validate_tier1_coverage(
            data_dir=tmp_path,
            source_probe_path=probe_path,
            min_accepted_docs=6,
            max_notice_doc_ratio=0.30,
        )


def test_validate_tier1_coverage_rejects_single_source_concentration(tmp_path: Path) -> None:
    probe_path = tmp_path / "source_probe.json"
    _write_json(probe_path, [_probe_row("calendar", domain="academic_calendar", label=2)])
    _write_json(
        tmp_path / "knowledge_seed.json",
        [
            _doc(f"cal-{index}", source_id="calendar", domain="academic_calendar", label=2, row_type="academic_calendar_event")
            for index in range(5)
        ]
        + [
            _doc("grad-1", source_id="graduation_ai", domain="graduation", label=0, row_type="graduation_requirement"),
        ],
    )

    with pytest.raises(ValueError, match="source concentration"):
        validate_tier1_coverage(
            data_dir=tmp_path,
            source_probe_path=probe_path,
            min_accepted_docs=6,
            max_source_concentration=0.50,
        )


def test_validate_tier1_coverage_counts_raw_but_not_index_ineligible_sources(tmp_path: Path) -> None:
    probe_path = tmp_path / "source_probe.json"
    _write_json(
        probe_path,
        [
            _probe_row("graduation_ai", domain="graduation", label=0),
            _probe_row("candidate_notice", domain="notices", label=1, index_eligible=False),
        ],
    )
    _write_json(
        tmp_path / "knowledge_seed.json",
        [
            _doc("grad-1", source_id="graduation_ai", domain="graduation", label=0, row_type="graduation_requirement"),
            _doc("notice-candidate", source_id="candidate_notice", domain="notices", label=1, row_type="notice_board_item"),
        ],
    )

    with pytest.raises(ValueError, match="index-eligible sources 1 below 2"):
        validate_tier1_coverage(
            data_dir=tmp_path,
            source_probe_path=probe_path,
            min_index_eligible_sources=2,
            min_raw_sources=2,
        )
