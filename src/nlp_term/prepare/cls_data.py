from __future__ import annotations

from collections import Counter
import re

from nlp_term.schemas import ClassificationExample, KnowledgeDoc, LabelAudit


QUESTION_TEMPLATES: dict[int, list[str]] = {
    0: [
        "졸업하려면 어떤 요건을 확인해야 하나요?",
        "전공 학점과 교양 학점 기준을 알고 싶어요.",
        "수료와 졸업 가능 여부는 어디서 확인하나요?",
        "입학년도별 졸업 기준이 궁금해요.",
        "복수전공을 하면 졸업요건이 달라지나요?",
    ],
    1: [
        "최근 학사 공지는 어디서 확인하나요?",
        "장학 관련 공지사항이 올라왔나요?",
        "모집 안내 공지는 어느 게시판을 보면 되나요?",
        "학교에서 올린 안내문을 찾고 싶어요.",
        "학사정보 게시판의 새 공지를 알려줘.",
    ],
    2: [
        "이번 학기 수강신청은 언제 시작하나요?",
        "수강정정 기간을 알려줘.",
        "개강일과 종강일이 언제인지 궁금해요.",
        "휴학 신청 기간은 학사일정에서 확인하나요?",
        "복학 일정은 어디서 볼 수 있나요?",
    ],
    3: [
        "오늘 학생식당 점심 메뉴가 뭐야?",
        "이번 주 학식 식단을 알려줘.",
        "교내 식당 저녁 메뉴를 확인하고 싶어.",
        "아침 식단이 있는지 알려줘.",
        "식당별 메뉴표는 어디서 확인하나요?",
    ],
    4: [
        "셔틀버스 시간표를 알려줘.",
        "통학버스 정류장은 어디인가요?",
        "버스 노선별 운행 시간을 확인하고 싶어요.",
        "학교 셔틀이 오늘 운행하나요?",
        "등교 버스와 하교 버스 안내를 알려줘.",
    ],
}

LABEL_KEYWORDS: dict[int, list[str]] = {
    0: ["졸업", "요건", "학점", "전공", "교양", "수료", "이수"],
    1: ["공지", "게시판", "장학", "모집", "안내문", "학사정보"],
    2: ["일정", "수강", "정정", "개강", "종강", "휴학", "복학"],
    3: ["식단", "메뉴", "학생식당", "점심", "저녁", "아침", "식당"],
    4: ["셔틀", "버스", "통학", "정류장", "노선", "운행", "시간표"],
}

CONTEXT_PREFIXES = [
    "",
    "충남대 기준으로 ",
    "학생 입장에서 ",
    "공식 자료 기준으로 ",
    "이번 학기에 ",
    "충남대학교 공식 안내에서 ",
    "챗봇에게 물어볼 때 ",
    "분류 기준을 정하려고 ",
]

AMBIGUOUS_TEMPLATES: dict[int, list[str]] = {
    0: [
        "학점 기준을 충족했는지 확인하려면 어느 자료를 봐야 해?",
        "전공을 바꿨을 때 끝까지 이수해야 하는 조건이 뭐야?",
        "졸업 가능 여부와 수료 여부가 헷갈려.",
        "교양과 전공 이수구분을 같이 확인하고 싶어.",
        "입학년도에 따라 달라지는 기준을 어디서 봐?",
    ],
    1: [
        "학교에서 새로 올린 안내가 있는지 보고 싶어.",
        "장학이랑 모집 안내가 섞여 있는데 공지로 분류해도 돼?",
        "게시판에 올라온 학사 관련 안내문을 찾고 있어.",
        "특정 부서 공지가 아니라 전체 학사 공지를 보고 싶어.",
        "최근 안내 제목만 보고 어디에 해당하는지 모르겠어.",
    ],
    2: [
        "신청 기간과 정정 기간이 달라서 헷갈려.",
        "학기 중 주요 날짜를 한 번에 확인하고 싶어.",
        "휴학과 복학 날짜가 같은 표에 있는지 궁금해.",
        "개강 전후 일정을 확인하려면 어디로 가야 해?",
        "수업 일정인지 공지사항인지 헷갈리는 질문이야.",
    ],
    3: [
        "오늘 먹을 수 있는 메뉴가 있는지 알고 싶어.",
        "식당 운영 정보와 메뉴가 섞여 있는데 식단으로 보면 돼?",
        "점심이랑 저녁 중 어떤 메뉴가 나오는지 궁금해.",
        "교내에서 밥 먹을 곳의 메뉴표를 보고 싶어.",
        "날짜별 메뉴를 확인하는 질문이야.",
    ],
    4: [
        "등하교 이동 시간표를 어디서 봐야 해?",
        "노선과 정류장 정보가 같이 필요한 질문이야.",
        "버스 운행 여부와 시간을 같이 확인하고 싶어.",
        "캠퍼스 이동용 차량 안내를 찾고 있어.",
        "시간표인지 노선도인지 헷갈리지만 버스 관련 질문이야.",
    ],
}

ANCHOR_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
BOILERPLATE_ANCHORS = {
    "2025",
    "042",
    "CNU",
    "Login",
    "ENG",
    "THE",
    "Strong",
    "충남대학교",
    "본문",
    "바로가기",
    "사이드메뉴",
    "주요메뉴",
    "통합검색",
    "사이트맵",
    "대학",
    "대학원",
    "CNU홍보",
    "홍보동영상",
    "홍보브로슈어",
    "조직도",
    "캠퍼스",
}


def build_template_audit(question: str, expected_label: int) -> LabelAudit:
    vote_labels = _vote_labels(question, expected_label)
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
    seen: dict[str, int] = {}
    for doc in docs:
        for index, question in enumerate(_questions_for_doc(doc)):
            key = _normalize_question(question)
            if key in seen:
                if seen[key] != doc.label:
                    continue
                continue
            seen[key] = doc.label
            sample_type = "ambiguous" if question in AMBIGUOUS_TEMPLATES[doc.label] else "template"
            generation_method = "augmented" if sample_type == "ambiguous" else "template"
            audit = build_template_audit(question, doc.label)
            audit.source_doc_id = doc.doc_id
            if audit.decision != "accept":
                continue
            audits.append(audit)
            examples.append(
                ClassificationExample(
                    question=question,
                    label=audit.final_label,
                    source_doc_id=doc.doc_id,
                    generation_method=generation_method,
                    validated=audit.decision == "accept",
                    metadata={
                        "sample_type": sample_type,
                        "source_domain": doc.domain,
                        "template_index": index,
                    },
                )
            )
    return examples, audits


def _questions_for_doc(doc: KnowledgeDoc) -> list[str]:
    questions: list[str] = []
    for prefix in CONTEXT_PREFIXES:
        for template in QUESTION_TEMPLATES[doc.label]:
            questions.append(f"{prefix}{template}")
            questions.append(f"{prefix}{_label_hint(doc.label)} 범위에서 {template}")
    for anchor in _anchors(doc):
        questions.extend(
            [
                f"{_label_hint(doc.label)}에서 {anchor} 관련 내용은 어떻게 확인해?",
                f"{_label_hint(doc.label)} 자료의 {anchor} 정보를 어디서 봐야 하나요?",
                f"{_label_hint(doc.label)} 질문으로 {anchor} 내용을 물어보면 돼?",
            ]
        )
    for phrase in _source_phrases(doc):
        questions.extend(
            [
                f"{phrase} 내용을 묻는다면 어떤 질문 유형인가요?",
                f"{_label_hint(doc.label)} 기준으로 {phrase} 정보를 확인하고 싶어요.",
                f"공식 자료의 {phrase} 부분은 어디에 해당하나요?",
            ]
        )
    questions.extend(AMBIGUOUS_TEMPLATES[doc.label])
    return questions


def _anchors(doc: KnowledgeDoc, *, limit: int = 5) -> list[str]:
    candidates = ANCHOR_RE.findall(f"{doc.title} {doc.body}")
    anchors: list[str] = []
    for candidate in candidates:
        if candidate in BOILERPLATE_ANCHORS or candidate in anchors:
            continue
        if candidate.isdigit():
            continue
        if len(candidate) > 24:
            continue
        if not any(keyword in candidate or candidate in keyword for keyword in LABEL_KEYWORDS[doc.label]):
            continue
        anchors.append(candidate)
        if len(anchors) >= limit:
            break
    return anchors


def _source_phrases(doc: KnowledgeDoc, *, limit: int = 5) -> list[str]:
    phrases: list[str] = []
    keywords = LABEL_KEYWORDS[doc.label]
    tokens = ANCHOR_RE.findall(doc.body)
    for index, token in enumerate(tokens):
        if not any(keyword in token or token in keyword for keyword in keywords):
            continue
        start = max(index - 2, 0)
        end = min(index + 5, len(tokens))
        phrase = " ".join(tokens[start:end])
        if len(phrase) < 8 or len(phrase) > 60:
            continue
        if phrase in phrases:
            continue
        phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases


def _vote_labels(question: str, expected_label: int) -> list[int]:
    scores = {
        label: sum(1 for keyword in keywords if keyword in question)
        for label, keywords in LABEL_KEYWORDS.items()
    }
    best_label, best_score = max(scores.items(), key=lambda item: (item[1], item[0] == expected_label))
    if best_score == 0:
        return [expected_label for _ in range(5)]
    votes = [expected_label, expected_label, best_label]
    if scores[expected_label] >= best_score:
        votes.extend([expected_label, expected_label])
    else:
        votes.extend([best_label, best_label])
    return votes


def _normalize_question(question: str) -> str:
    return " ".join(question.strip().lower().split())


def _label_hint(label: int) -> str:
    return {
        0: "졸업요건",
        1: "학사공지",
        2: "학사일정",
        3: "식단",
        4: "셔틀버스",
    }[label]
