from __future__ import annotations

import json

from nlp_term.prepare.from_sources import parse_source
from nlp_term.prepare.from_sources import build_knowledge_from_probe
from nlp_term.schemas import RawSource


def test_parse_source_records_atomic_aware_chunking_provenance(tmp_path) -> None:
    raw_path = tmp_path / "academic_calendar.html"
    raw_path.write_text(
        """
        <html><body>
          <div class="calen_box">
            03.03(화) 제1학기 개강일
            06.19(금) 제1학기 종강일
            06.22(월) 하기 계절학기 개강
            06.30(화) 하기 계절학기 수강신청 변경기간
            07.15(수) 하기 계절학기 성적발표
          </div>
        </body></html>
        """,
        encoding="utf-8",
    )
    raw = RawSource(
        source_id="academic_calendar",
        label=2,
        domain="academic_calendar",
        url="https://plus.cnu.ac.kr/_prog/academic_calendar/",
        fetched_at="2026-06-08T00:00:00+09:00",
        content_type="text/html",
        raw_path=str(raw_path),
        status_code=200,
        checksum="test-checksum",
    )

    docs, failure = parse_source(raw, chunks_per_source=3)

    assert failure is None
    assert docs
    assert docs[0].metadata["chunking_strategy"] == "atomic_guard"
    assert docs[0].metadata["boundary_type"] == "calendar_row"
    assert docs[0].metadata["chunk_confidence"] == "high"


def test_build_knowledge_from_probe_adds_structured_shuttle_docs(tmp_path) -> None:
    probe_path = tmp_path / "source_probe.json"
    probe_path.write_text(
        json.dumps(
            [
                {
                    "raw": {
                        "source_id": "shuttle_bus",
                        "label": 4,
                        "domain": "shuttle",
                        "url": "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
                        "fetched_at": "2026-06-06T17:55:39+00:00",
                        "content_type": "text/html",
                        "raw_path": "data/raw/shuttle/shuttle_bus.html",
                        "status_code": 200,
                        "checksum": "shuttle-raw-checksum",
                    },
                    "verification": {
                        "source_id": "shuttle_bus",
                        "official_chain_ok": True,
                        "parser_name": "shuttle_stage_inventory",
                        "parser_version": "0.1.0",
                        "evidence": ["https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"],
                        "warnings": [],
                        "verified_at": "2026-06-08T00:00:00+09:00",
                    },
                    "inventory": {
                        "stage": "stage0",
                        "active": True,
                        "parser_type": "shuttle",
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    docs, failures = build_knowledge_from_probe(probe_path, chunks_per_source=1)

    structured_docs = [doc for doc in docs if doc.metadata.get("generation_method") == "structured_row"]
    assert not failures
    assert structured_docs
    assert any(doc.source_id == "shuttle_bus" and doc.metadata["route_name"] == "교내 순환" for doc in structured_docs)
    assert any(doc.metadata.get("generation_method") == "source_parse" for doc in docs)
    for doc in docs:
        assert doc.metadata["source_id"] == "shuttle_bus"
        assert doc.metadata["source_domain"] == "shuttle"
        assert doc.metadata["source_label"] == 4
        assert doc.metadata["official_chain_ok"] is True
        assert doc.metadata["lifecycle_status"] == "index_eligible"
        assert doc.metadata["index_eligible"] is True


def test_build_knowledge_from_probe_adds_structured_notice_docs(tmp_path) -> None:
    probe_path = tmp_path / "source_probe.json"
    probe_path.write_text(
        json.dumps(
            [
                {
                    "raw": {
                        "source_id": "academic_notice_board",
                        "label": 1,
                        "domain": "notices",
                        "url": "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr",
                        "fetched_at": "2026-06-08T00:00:00+09:00",
                        "content_type": "text/html",
                        "raw_path": "data/raw/notices/academic_notice_board.html",
                        "status_code": 200,
                        "checksum": "notice-board-checksum",
                    },
                    "verification": {
                        "source_id": "academic_notice_board",
                        "official_chain_ok": True,
                        "parser_name": "html_stage_inventory",
                        "parser_version": "0.1.0",
                        "evidence": [
                            "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr"
                        ],
                        "warnings": [],
                        "verified_at": "2026-06-08T00:00:01+09:00",
                    },
                    "inventory": {
                        "stage": "stage0",
                        "active": True,
                        "parser_type": "html",
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    docs, failures = build_knowledge_from_probe(probe_path, chunks_per_source=1)

    structured_docs = [doc for doc in docs if doc.metadata.get("generation_method") == "structured_row"]
    assert not failures
    assert any(
        doc.source_id == "academic_notice_board"
        and doc.metadata.get("row_type") == "notice_board_item"
        and doc.metadata.get("posted_date") == "2026-06-05"
        for doc in structured_docs
    )
    for doc in docs:
        assert doc.metadata["lifecycle_status"] == "index_eligible"
        assert doc.metadata["index_eligible"] is True
