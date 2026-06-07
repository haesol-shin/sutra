from __future__ import annotations

from nlp_term.prepare.chunking import split_source_text


def _texts(chunks):
    return [chunk.text for chunk in chunks]


def test_calendar_guard_preserves_date_and_event_name() -> None:
    text = "03.03(화) 제1학기 개강일\n06.19(금) 제1학기 종강일\n06.22(월) 하기 계절학기 개강"

    chunks = split_source_text(text, label=2, max_chunk_chars=80, max_chunks=5)

    assert any("06.19(금) 제1학기 종강일" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "calendar_row" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_calendar_guard_handles_normalized_html_text() -> None:
    text = (
        "01월 January 01.01(목) 신정 01.13(화) 제2학기 성적발표 "
        "05월 May 05.07(목) ~ 05.11(월) 하기 계절학기 수강신청 "
        "06월 June 06.22(월) 하기방학 06.22(월) ~ 07.10(금) 하기 계절학기"
    )

    chunks = split_source_text(text, label=2, max_chunk_chars=100, max_chunks=10)

    assert any("05.07(목) ~ 05.11(월) 하기 계절학기 수강신청" in chunk for chunk in _texts(chunks))
    assert any("06.22(월) ~ 07.10(금) 하기 계절학기" in chunk for chunk in _texts(chunks))
    assert all(chunk.boundary_type == "calendar_row" for chunk in chunks)


def test_dining_guard_preserves_obvious_date_location_meal_and_menu() -> None:
    text = (
        "2026-06-16 2학생회관 중식\n"
        "백반, 된장국, 제육볶음\n"
        "2026-06-16 3학생회관 석식\n"
        "김치찌개, 계란말이"
    )

    chunks = split_source_text(text, label=3, max_chunk_chars=120, max_chunks=5)

    assert any(
        "2026-06-16" in chunk
        and "2학생회관" in chunk
        and "중식" in chunk
        and "제육볶음" in chunk
        for chunk in _texts(chunks)
    )
    assert any(chunk.boundary_type == "dining_menu_row" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_shuttle_guard_preserves_stop_and_departure_times() -> None:
    text = "교내순환 셔틀버스\n월평역: 08:20 09:30 10:30\n도서관: 08:35 09:45 10:45"

    chunks = split_source_text(text, label=4, max_chunk_chars=120, max_chunks=5)

    assert any("월평역" in chunk and "08:20" in chunk and "09:30" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "shuttle_time_row" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_notice_guard_preserves_obvious_title_date_body_block() -> None:
    text = (
        "제목: 2026학년도 하기 계절학기 수강신청 안내\n"
        "작성일: 2026-05-01\n"
        "본문: 수강신청 기간은 2026년 5월 7일부터 5월 9일까지입니다."
    )

    chunks = split_source_text(text, label=1, max_chunk_chars=180, max_chunks=5)

    assert any("하기 계절학기 수강신청 안내" in chunk and "2026-05-01" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "notice_detail" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_graduation_guard_preserves_heading_with_obvious_requirement_line() -> None:
    text = (
        "컴퓨터융합학부 졸업요건\n"
        "2024학번은 프로젝트 관련 전공 교과목 2개 이상을 이수해야 한다.\n"
        "총 졸업학점은 130학점 이상이다."
    )

    chunks = split_source_text(text, label=0, max_chunk_chars=160, max_chunks=5)

    assert any(
        "컴퓨터융합학부 졸업요건" in chunk and "2024학번" in chunk and "2개 이상" in chunk
        for chunk in _texts(chunks)
    )
    assert any(chunk.boundary_type == "graduation_requirement" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_general_prose_uses_recursive_medium_confidence_chunks() -> None:
    text = "졸업요건은 학과와 입학연도에 따라 다릅니다. 본인의 교육과정 적용 연도를 확인해야 합니다."

    chunks = split_source_text(text, label=0, max_chunk_chars=80, max_chunks=5)

    assert chunks
    assert all(chunk.chunk_confidence == "medium" for chunk in chunks)
    assert all(chunk.strategy == "recursive_prose" for chunk in chunks)


def test_unstructured_text_falls_back_with_low_confidence() -> None:
    text = "2026학년도교육과정표전공필수전공선택교양핵심" * 20

    chunks = split_source_text(text, label=0, max_chunk_chars=100, max_chunks=3)

    assert chunks
    assert all(chunk.strategy == "fallback_window" for chunk in chunks)
    assert all(chunk.chunk_confidence == "low" for chunk in chunks)
