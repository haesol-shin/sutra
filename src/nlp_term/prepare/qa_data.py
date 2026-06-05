from __future__ import annotations

from nlp_term.schemas import KnowledgeDoc, QAExample


ANSWER_PREFIX: dict[int, str] = {
    0: "졸업요건은 학과와 입학연도에 따라 달라질 수 있어 공식 졸업요건 자료를 기준으로 확인해야 합니다.",
    1: "공지사항은 충남대학교 공식 학사정보 게시판 기준으로 확인하는 것이 안전합니다.",
    2: "학사일정은 공식 학사일정 페이지의 해당 학기 일정을 기준으로 확인해야 합니다.",
    3: "식단은 교내 식단 페이지의 날짜별 메뉴를 기준으로 확인해야 합니다.",
    4: "셔틀과 통학버스 정보는 공식 시간표와 운행 안내를 기준으로 확인해야 합니다.",
}


def build_qa_seed(docs: list[KnowledgeDoc]) -> list[QAExample]:
    rows: list[QAExample] = []
    for doc in docs:
        rows.append(
            QAExample(
                user=f"{doc.title}에 대해 알려줘.",
                model=f"{ANSWER_PREFIX[doc.label]} 참고 출처: {doc.source_url}",
                source_doc_id=doc.doc_id,
                source_url=doc.source_url,
                label=doc.label,
                validated=True,
            )
        )
    return rows

