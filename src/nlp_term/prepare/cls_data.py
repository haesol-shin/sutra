from __future__ import annotations

from collections import Counter

from nlp_term.schemas import ClassificationExample, KnowledgeDoc, LabelAudit


QUESTION_TEMPLATES: dict[int, list[str]] = {
    0: ["졸업하려면 몇 학점을 들어야 하나요?", "전공 학점 졸업요건을 알고 싶어요."],
    1: ["최근 학사 공지는 어디서 확인하나요?", "장학 관련 공지사항이 올라왔나요?"],
    2: ["이번 학기 수강신청은 언제 시작하나요?", "수강정정 기간을 알려줘."],
    3: ["오늘 학생식당 점심 메뉴가 뭐야?", "이번 주 학식 식단을 알려줘."],
    4: ["셔틀버스 시간표를 알려줘.", "통학버스 정류장은 어디인가요?"],
}


def build_template_audit(question: str, expected_label: int) -> LabelAudit:
    vote_labels = [expected_label for _ in range(5)]
    counts = Counter(vote_labels)
    final_label, count = counts.most_common(1)[0]
    confidence = count / len(vote_labels)
    return LabelAudit(
        question=question,
        source_doc_id="",
        vote_labels=vote_labels,
        final_label=final_label,
        confidence=confidence,
        decision="accept" if confidence >= 0.8 else "review",
    )


def build_classification_seed(docs: list[KnowledgeDoc]) -> tuple[list[ClassificationExample], list[LabelAudit]]:
    examples: list[ClassificationExample] = []
    audits: list[LabelAudit] = []
    for doc in docs:
        for question in QUESTION_TEMPLATES[doc.label]:
            audit = build_template_audit(question, doc.label)
            audit.source_doc_id = doc.doc_id
            audits.append(audit)
            examples.append(
                ClassificationExample(
                    question=question,
                    label=audit.final_label,
                    source_doc_id=doc.doc_id,
                    generation_method="template",
                    validated=audit.decision == "accept",
                )
            )
    return examples, audits
