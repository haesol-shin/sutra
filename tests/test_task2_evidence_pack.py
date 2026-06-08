from __future__ import annotations

from nlp_term.chat.evidence_pack import build_evidence_pack
from nlp_term.schemas import KnowledgeDoc


def test_evidence_pack_hides_internal_ids_and_keeps_clean_source_material() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="academic_calendar_chunk_1",
            label=2,
            domain="academic_calendar",
            title="학사일정",
            body="2026학년도 제1학기 수강신청은 공식 학사일정에서 확인한다.",
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={"source_name": "충남대학교 학사일정"},
        )
    ]

    pack = build_evidence_pack(
        question="이번 학기 수강신청 일정은 어디서 확인해?",
        label=2,
        domain="academic_calendar",
        docs=docs,
        max_items=1,
    )

    prompt_text = pack.to_prompt_text()
    assert pack.question == "이번 학기 수강신청 일정은 어디서 확인해?"
    assert pack.intent_label == 2
    assert pack.intent_domain == "academic_calendar"
    assert pack.items[0].source_name == "충남대학교 학사일정"
    assert "수강신청" in pack.items[0].facts[0]
    assert "academic_calendar_chunk_1" not in prompt_text
    assert "chunk_" not in prompt_text
    assert "source 1" not in prompt_text.lower()
    assert "https://plus.cnu.ac.kr/calendar" in prompt_text


def test_evidence_pack_sanitizes_generic_source_titles() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="graduation_curriculum_pdf_chunk_3",
            label=0,
            domain="graduation",
            title="graduation source 1",
            body="생화학과 졸업요건은 입학연도별 교육과정표를 함께 확인해야 한다.",
            source_url="https://biochemistry.cnu.ac.kr/grad",
            source_id="graduation_biochemistry_requirements",
            metadata={"source_department": "생화학과", "source_parser_type": "pdf"},
        )
    ]

    pack = build_evidence_pack(
        question="생화학과 졸업요건 알려줘",
        label=0,
        domain="graduation",
        docs=docs,
        max_items=1,
    )

    prompt_text = pack.to_prompt_text()
    assert "graduation source 1" not in prompt_text
    assert "source 1" not in prompt_text.lower()
    assert "chunk_" not in prompt_text
    assert pack.items[0].source_name == "생화학과 졸업요건"


def test_evidence_pack_keeps_later_relevant_context_in_chunk() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="calendar_doc_1",
            label=2,
            domain="academic_calendar",
            title="학사일정",
            body=(
                "학사일정 안내입니다. 수강신청은 2026년 2월에 진행됩니다. "
                "1학기 종강일은 2026년 6월 19일입니다."
            ),
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={"source_name": "충남대학교 학사일정"},
        )
    ]

    pack = build_evidence_pack(
        question="이번 학기 종강일이 언제인가요?",
        label=2,
        domain="academic_calendar",
        docs=docs,
    )

    text = pack.to_prompt_text()

    assert "1학기 종강일은 2026년 6월 19일입니다" in text


def test_evidence_pack_separates_structured_primary_rows_from_supporting_chunks() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="dining_row_1",
            label=3,
            domain="dining",
            title="2학생회관 중식",
            body="2026-06-16 2학생회관 중식: 쌀밥, 된장국.",
            source_url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
            source_id="cnu_mobile_food",
            metadata={"generation_method": "structured_row", "row_type": "dining_menu"},
        ),
        KnowledgeDoc(
            doc_id="dining_notice_chunk_1",
            label=3,
            domain="dining",
            title="식단 안내",
            body="식단은 운영 상황에 따라 변경될 수 있다.",
            source_url="https://plus.cnu.ac.kr/food",
            source_id="cnu_food_notice",
            metadata={"chunking_strategy": "recursive_prose"},
        ),
    ]

    pack = build_evidence_pack(
        question="다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        label=3,
        domain="dining",
        docs=docs,
    )

    text = pack.to_prompt_text()

    assert [item.source_url for item in pack.primary_structured_rows] == ["https://mobileadmin.cnu.ac.kr/food/index.jsp"]
    assert [item.source_url for item in pack.supporting_chunks] == ["https://plus.cnu.ac.kr/food"]
    assert "주요 구조화 근거:" in text
    assert "보조 문서 근거:" in text
