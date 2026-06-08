from __future__ import annotations

from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.structured.shuttle import ShuttleAdapter


RAW_PATH = Path("data/raw/shuttle/shuttle_bus.html")


def _context(fetched_at: str = "2026-06-08T02:02:37+00:00"):
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "shuttle_bus")
    raw = RawSource(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        fetched_at=fetched_at,
        content_type="text/html; charset=utf-8",
        raw_path=str(RAW_PATH),
        status_code=200,
        checksum="shuttle-raw-checksum",
    )
    verification = SourceVerification(
        source_id=spec.source_id,
        official_chain_ok=spec.official_chain_ok,
        parser_name="shuttle_stage_inventory",
        parser_version=PARSER_VERSION,
        evidence=[spec.url],
        warnings=[],
        verified_at="2026-06-08T02:02:38+00:00",
    )
    return spec, raw, verification


def test_shuttle_adapter_parses_schedule_and_route_rows() -> None:
    spec, raw, verification = _context()

    rows = ShuttleAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert len(rows) == 2
    campus = next(row for row in rows if row.route_key == "campus_loop")
    assert campus.route_name == "교내 순환"
    assert "08:20 (월평역) 등교" in campus.departure_times
    assert "17:30" in campus.departure_times
    assert campus.first_time == "08:30"
    assert campus.last_time == "17:30"
    assert campus.operation_count == "10회"
    assert campus.operation_period == "학기 중 운영 (총 150일)"
    assert campus.operating_days == "학기 중 평일 주간"
    assert campus.non_operating_days == ["평일 야간", "주말", "공휴일", "방학", "수학능력시험일(10시 이전)"]
    assert campus.valid_start == "2026-03-03"
    assert campus.valid_end == "2026-06-21"
    assert "월평역" in campus.stops
    assert "정심화 국제문화회관" in campus.stops


def test_shuttle_knowledge_doc_metadata_contract_and_search() -> None:
    spec, raw, verification = _context()
    adapter = ShuttleAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    docs = adapter.to_knowledge_docs(rows)
    campus_doc = next(doc for doc in docs if doc.metadata["structured"]["route_key"] == "campus_loop")

    assert campus_doc.metadata["structured"]["departure_times"][0] == "08:20 (월평역) 등교"
    assert campus_doc.metadata["route_name"] == "교내 순환"
    assert campus_doc.metadata["valid_start"] == "2026-03-03"
    assert campus_doc.metadata["valid_end"] == "2026-06-21"
    assert campus_doc.metadata["structured_fields"] == [
        "route_key",
        "route_name",
        "departure_times",
        "first_time",
        "last_time",
        "stops",
        "operation_count",
        "operation_period",
        "operating_days",
        "non_operating_days",
        "valid_start",
        "valid_end",
        "notes",
    ]
    assert campus_doc.metadata["verification_official_chain_ok"] is True
    assert "정상 운행" in campus_doc.body
    assert "정류장" in campus_doc.body

    top = rank_docs("다음주에 셔틀버스는 정상 운행하나요?", docs=docs, top_k=1)[0]

    assert top.doc_id == campus_doc.doc_id


def test_shuttle_adapter_row_ids_ignore_fetched_at() -> None:
    spec, raw, verification = _context(fetched_at="2026-06-08T02:02:37+00:00")
    newer_raw = raw.model_copy(update={"fetched_at": "2026-06-09T02:02:37+00:00"})

    first_ids = [row.row_id for row in ShuttleAdapter().parse(spec=spec, raw=raw, verification=verification)]
    second_ids = [row.row_id for row in ShuttleAdapter().parse(spec=spec, raw=newer_raw, verification=verification)]

    assert first_ids == second_ids
