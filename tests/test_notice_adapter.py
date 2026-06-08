from __future__ import annotations

from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.structured.notices import NoticeAdapter


RAW_PATH = Path("data/raw/notices/academic_notice_board.html")


def _context(fetched_at: str = "2026-06-08T00:00:00+09:00"):
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "academic_notice_board")
    raw = RawSource(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        fetched_at=fetched_at,
        content_type="text/html",
        raw_path=str(RAW_PATH),
        status_code=200,
        checksum="notice-board-checksum",
    )
    verification = SourceVerification(
        source_id=spec.source_id,
        official_chain_ok=spec.official_chain_ok,
        parser_name="html_stage_inventory",
        parser_version=PARSER_VERSION,
        evidence=[spec.url],
        warnings=[],
        verified_at="2026-06-08T00:00:01+09:00",
    )
    return spec, raw, verification


def test_notice_adapter_parses_board_rows_with_posted_dates() -> None:
    spec, raw, verification = _context()

    rows = NoticeAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert len(rows) >= 8
    latest = next(row for row in rows if row.notice_no == "1814")
    assert latest.title == "2026학년도 하기 계절학기 수강신청 취소(1~3차)기간 안내"
    assert latest.posted_date == "2026-06-05"
    assert latest.author == "학사지원과"
    assert latest.detail_url.startswith("https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2513490")
    assert latest.is_pinned is False


def test_notice_adapter_row_ids_ignore_fetched_at() -> None:
    spec, raw, verification = _context()
    newer_raw = raw.model_copy(update={"fetched_at": "2026-06-08T12:00:00+09:00"})

    first_ids = [row.row_id for row in NoticeAdapter().parse(spec=spec, raw=raw, verification=verification)]
    second_ids = [row.row_id for row in NoticeAdapter().parse(spec=spec, raw=newer_raw, verification=verification)]

    assert first_ids == second_ids


def test_notice_knowledge_doc_metadata_contract() -> None:
    spec, raw, verification = _context()
    adapter = NoticeAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    doc = next(doc for doc in adapter.to_knowledge_docs(rows) if doc.metadata["notice_no"] == "1814")

    assert doc.date == "2026-06-05"
    assert doc.metadata["posted_date"] == "2026-06-05"
    assert doc.metadata["notice_title"] == "2026학년도 하기 계절학기 수강신청 취소(1~3차)기간 안내"
    assert doc.metadata["author"] == "학사지원과"
    assert doc.metadata["detail_url"].startswith("https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2513490")
    assert doc.metadata["structured_fields"] == [
        "notice_no",
        "title",
        "posted_date",
        "author",
        "detail_url",
        "is_pinned",
        "hits",
        "has_attachment",
    ]
    assert doc.metadata["verification_official_chain_ok"] is True
    assert "게시일은 2026-06-05" in doc.body


def test_latest_notice_row_is_retrievable_by_recent_notice_question() -> None:
    spec, raw, verification = _context()
    adapter = NoticeAdapter()
    docs = adapter.to_knowledge_docs(adapter.parse(spec=spec, raw=raw, verification=verification))

    top = rank_docs("가장 최근에 올라온 공지사항은 언제 게시되었나요?", docs=docs, top_k=3)

    assert any(row.doc_id.startswith("academic_notice_board__notice_board_item__1814") for row in top)
