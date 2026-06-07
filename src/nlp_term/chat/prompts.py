from __future__ import annotations

from nlp_term.chat.evidence_pack import EvidencePack


TASK2_SYSTEM_PROMPT = """너는 충남대학교 학생을 돕는 캠퍼스 챗봇이다.
역할은 검색된 근거를 바탕으로 자연스럽게, 간결한 한국어 답변을 작성하는 것이다.
도구를 호출하지 않는다.
근거에 없는 날짜, 학점, 장소는 단정하지 않는다.
내부 문서 ID, chunk ID, source 번호를 답변에 노출하지 않는다.
근거가 부족하면 단정하지 말고 공식 출처 확인을 안내한다."""


def build_task2_prompt(pack: EvidencePack) -> str:
    return (
        f"{TASK2_SYSTEM_PROMPT}\n\n"
        f"{pack.to_prompt_text()}\n\n"
        "위 근거만 사용해서 학생에게 바로 보여줄 답변을 작성하세요.\n"
        "답변:"
    )
