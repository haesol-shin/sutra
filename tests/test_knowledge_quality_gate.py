from __future__ import annotations

import json

import pytest

from nlp_term.validators import validate_knowledge_quality


def _doc(doc_id: str, body: str, *, label: int = 3, domain: str = "dining", metadata: dict | None = None) -> dict:
    return {
        "doc_id": doc_id,
        "label": label,
        "domain": domain,
        "title": doc_id,
        "body": body,
        "source_url": "https://mobileadmin.cnu.ac.kr/food/index.jsp",
        "source_id": "cnu_mobile_food",
        "metadata": metadata or {},
    }


def test_min_body_chars_does_not_reject_short_structured_rows(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "dining-row",
                    "2026-06-16 제2학생회관 중식: 치즈닭갈비덮밥.",
                    metadata={"generation_method": "structured_row", "row_type": "dining_menu", "menu_date": "2026-06-16"},
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_structured_rows_do_not_need_prose_source_signal(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "calendar-structured-row",
                    "2026학년도 학사일정: 동기 계절학기는 2025-12-22부터 2026-01-13까지입니다.",
                    label=2,
                    domain="academic_calendar",
                    metadata={
                        "generation_method": "structured_row",
                        "row_type": "academic_calendar_event",
                        "date_span": "2025-12-22/2026-01-13",
                    },
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_page_chrome_detection_does_not_reject_english_word_fragment(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "graduation-english",
                    "공통 2024 교육과정의 교양 요건: 대학영어 1, 2 (舊 Global English 1 ~ 4)를 이수합니다.",
                    label=0,
                    domain="graduation",
                    metadata={"generation_method": "structured_row", "row_type": "graduation_requirement"},
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_min_body_chars_rejects_short_prose_chunks(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps([_doc("notice-chrome", "목록", metadata={"generation_method": "source_parse"})], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="notice-chrome body is shorter than 80 chars"):
        validate_knowledge_quality(path, min_body_chars=80)


def test_min_body_chars_does_not_reject_short_atomic_source_parse_rows(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "calendar-row",
                    "06.19(금) 제1학기 종강일",
                    label=2,
                    domain="academic_calendar",
                    metadata={
                        "generation_method": "source_parse",
                        "chunking_strategy": "atomic_guard",
                        "boundary_type": "calendar_row",
                    },
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_min_body_chars_allows_short_prose_with_source_specific_signal(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "scholarship-summary",
                    "국가 장학금 국가장학금 안내 표로 명칭, 장학금액, 선발기준, 인원, 비고를 안내합니다.",
                    label=1,
                    domain="notices",
                    metadata={"generation_method": "source_parse", "chunking_strategy": "recursive_prose"},
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_notice_body_procedure_text_counts_as_source_specific_signal(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "notice-procedure",
                    "충남대학교 포털 통합정보시스템에서 학점교류 신청서를 작성하고 지원서를 출력하여 소속 학과에 제출합니다.",
                    label=1,
                    domain="notices",
                    metadata={"generation_method": "source_parse", "chunking_strategy": "recursive_prose"},
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_calendar_month_day_text_counts_as_source_specific_signal(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "calendar-module",
                    "6월 22(월) 하기방학 6.22(월)~10(금) 하기 계절학기 등록 일정입니다.",
                    label=2,
                    domain="academic_calendar",
                    metadata={"generation_method": "source_parse", "chunking_strategy": "recursive_prose"},
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)


def test_dining_ingredient_notice_counts_as_source_specific_signal(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps(
            [
                _doc(
                    "dining-ingredient",
                    "쌀은 국내산이며 교직원과 학생들의 건강을 위하여 신선한 식재료를 사용하고 MSG가 없는 조미료를 사용합니다.",
                    label=3,
                    domain="dining",
                    metadata={"generation_method": "source_parse", "chunking_strategy": "recursive_prose"},
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validate_knowledge_quality(path, min_body_chars=80)
