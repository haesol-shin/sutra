from __future__ import annotations

from nlp_term.prepare.from_sources import parse_source
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
