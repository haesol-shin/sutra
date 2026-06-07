from __future__ import annotations

from nlp_term.chat.evidence_pack import EvidenceItem, EvidencePack
from nlp_term.chat.prompts import build_task2_prompt


def test_task2_prompt_defines_llm_as_natural_answer_writer_not_tool_agent() -> None:
    pack = EvidencePack(
        question="졸업 전공 학점 기준 알려줘",
        intent_label=0,
        intent_domain="graduation",
        items=[
            EvidenceItem(
                source_name="생화학과 졸업요건",
                source_url="https://biochemistry.cnu.ac.kr/grad",
                facts=["졸업 기준은 전공과 교양 이수 기준을 함께 확인해야 한다."],
                cautions=["근거에 없는 세부 학점 숫자는 단정하지 않는다."],
            )
        ],
    )

    prompt = build_task2_prompt(pack)

    assert "충남대학교 학생을 돕는 캠퍼스 챗봇" in prompt
    assert "자연스럽게" in prompt
    assert "도구를 호출하지 않는다" in prompt
    assert "근거에 없는 날짜, 학점, 장소는 단정하지 않는다" in prompt
    assert "내부 문서 ID" in prompt
    assert "academic_calendar_chunk_1" not in prompt
    assert "생화학과 졸업요건" in prompt
    assert "https://biochemistry.cnu.ac.kr/grad" in prompt
