from __future__ import annotations

from collections import defaultdict
import re
import unicodedata

from nlp_term.schemas import KnowledgeDoc, QAExample


ANSWER_PREFIX: dict[int, str] = {
    0: "졸업요건은 학과와 입학연도에 따라 달라질 수 있어 공식 졸업요건 자료를 기준으로 확인해야 합니다.",
    1: "공지사항은 충남대학교 공식 학사정보 게시판 기준으로 확인하는 것이 안전합니다.",
    2: "학사일정은 공식 학사일정 페이지의 해당 학기 일정을 기준으로 확인해야 합니다.",
    3: "식단은 교내 식단 페이지의 날짜별 메뉴를 기준으로 확인해야 합니다.",
    4: "셔틀과 통학버스 정보는 공식 시간표와 운행 안내를 기준으로 확인해야 합니다.",
}

BOILERPLATE_TERMS = (
    "본문 바로가기",
    "사이드메뉴 바로가기",
    "사이드메뉴",
    "주요메뉴 바로가기",
    "주요메뉴",
    "통합검색",
    "사이트맵",
    "CNU홍보",
    "CNU 홍보브로슈어",
    "사이버투어",
    "THE STRONG CNU",
    "미래 사회를 선도할",
    "홍보동영상",
    "홍보브로슈어",
    "캠퍼스투어",
    "대학/대학원",
    "열기 버튼",
    "닫기버튼",
    "All Rights Reserved",
    "Login",
    "ENG",
)
GENERIC_FALLBACK_PHRASE = "공식 source에서 확인한 해당 주제의 안내 범위와 근거"
MOJIBAKE_RE = re.compile(r"[泲湮ȯմϴбտαøũĴ�]+")
MIN_HANGUL_CHARS = 20
MIN_SPAN_CHARS = 40
TARGET_QA_PER_LABEL = 10

LABEL_KEYWORDS: dict[int, tuple[str, ...]] = {
    0: ("졸업", "교양", "전공", "학점", "교육과정", "이수"),
    1: ("공지", "학사정보", "게시", "백마광장", "학사지원과", "작성일", "조회수", "수강신청", "휴학", "복학"),
    2: ("학사일정", "일정", "학기"),
    3: ("식단", "메뉴", "학생회관", "조식", "중식", "석식"),
    4: ("셔틀", "버스", "통학", "시간표", "운행"),
}

QUESTION_VARIANTS: dict[int, list[str]] = {
    0: [
        "졸업요건 근거를 요약해줘.",
        "졸업 관련 기준은 어떤 자료를 봐야 해?",
        "이 자료에서 졸업 질문에 쓸 근거가 뭐야?",
        "졸업요건 답변에 인용할 부분을 알려줘.",
        "졸업 기준 확인에 필요한 핵심 문구가 뭐야?",
    ],
    1: [
        "학사 공지 근거를 요약해줘.",
        "공지사항 확인은 어떤 자료를 봐야 해?",
        "이 자료에서 공지 질문에 쓸 근거가 뭐야?",
        "학사 공지 답변에 쓸 출처 내용을 알려줘.",
        "공지 확인 질문에 인용할 부분이 뭐야?",
    ],
    2: [
        "학사일정 근거를 요약해줘.",
        "일정 확인은 어떤 자료를 봐야 해?",
        "이 자료에서 일정 질문에 쓸 근거가 뭐야?",
        "학사일정 답변에 필요한 출처 문구를 알려줘.",
        "학기 일정 확인에 인용할 내용이 뭐야?",
    ],
    3: [
        "식단 근거를 요약해줘.",
        "메뉴 확인은 어떤 자료를 봐야 해?",
        "이 자료에서 식단 질문에 쓸 근거가 뭐야?",
        "식단 답변에 인용할 메뉴 관련 내용을 알려줘.",
        "교내 식당 질문에 필요한 출처 문구가 뭐야?",
    ],
    4: [
        "셔틀버스 근거를 요약해줘.",
        "버스 시간 확인은 어떤 자료를 봐야 해?",
        "이 자료에서 셔틀 질문에 쓸 근거가 뭐야?",
        "셔틀버스 답변에 인용할 운행 내용을 알려줘.",
        "통학버스 질문에 필요한 출처 문구가 뭐야?",
    ],
}


def build_qa_seed(docs: list[KnowledgeDoc]) -> list[QAExample]:
    evidence_by_label: dict[int, list[tuple[KnowledgeDoc, str]]] = defaultdict(list)
    for doc in docs:
        for span in _evidence_spans(doc):
            evidence_by_label[doc.label].append((doc, span))

    rows: list[QAExample] = []
    for label in range(5):
        evidence_pool = evidence_by_label[label]
        for index in range(TARGET_QA_PER_LABEL):
            if not evidence_pool:
                break
            doc, excerpt = evidence_pool[index % len(evidence_pool)]
            question = QUESTION_VARIANTS[label][index % len(QUESTION_VARIANTS[label])]
            rows.append(
                QAExample(
                    user=f"{doc.title}: {question}",
                    model=_answer_for_doc(doc, excerpt=excerpt, variant=index),
                    source_doc_id=doc.doc_id,
                    source_url=doc.source_url,
                    label=label,
                    validated=True,
                )
            )
    return rows


def _answer_for_doc(doc: KnowledgeDoc, *, excerpt: str, variant: int) -> str:
    title_hint = f"출처 제목: {doc.title}."
    url_hint = f"참고 출처: {doc.source_url}"
    if variant % 3 == 0:
        return f"{ANSWER_PREFIX[doc.label]} {title_hint} 핵심 근거는 '{excerpt}'입니다. {url_hint}"
    if variant % 3 == 1:
        return f"{doc.title} 자료의 핵심 근거는 '{excerpt}'입니다. {ANSWER_PREFIX[doc.label]} {url_hint}"
    return f"질문 범위는 {doc.title}와 연결됩니다. 자료 내용 일부는 '{excerpt}'이며, {url_hint}"


def _evidence_spans(doc: KnowledgeDoc, *, max_spans: int = 3) -> list[str]:
    candidates: list[tuple[int, int, str]] = []
    tokens = [_clean_token(word) for word in doc.body.split()]
    tokens = [token for token in tokens if token and not _is_noisy_token(token)]
    for start in range(0, len(tokens), 10):
        span = " ".join(tokens[start : start + 28]).strip()
        score = _span_score(span, doc.label)
        if score > 0:
            candidates.append((score, start, span))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    spans: list[str] = []
    seen: set[str] = set()
    for _, _, span in candidates:
        key = span.casefold()
        if key in seen:
            continue
        spans.append(span)
        seen.add(key)
        if len(spans) >= max_spans:
            break
    return spans


def _span_score(span: str, label: int) -> int:
    if len(span) < MIN_SPAN_CHARS:
        return 0
    if _contains_noise(span):
        return 0
    hangul_count = sum(1 for char in span if "가" <= char <= "힣")
    if hangul_count < MIN_HANGUL_CHARS:
        return 0
    keyword_hits = sum(1 for keyword in LABEL_KEYWORDS[label] if keyword in span)
    if keyword_hits < 1:
        return 0
    return hangul_count + keyword_hits * 20


def _is_noisy_token(word: str) -> bool:
    if len(word) == 1:
        return True
    if word.isdigit():
        return True
    if sum(1 for char in word if char in "·") > 5:
        return True
    if MOJIBAKE_RE.search(word):
        return True
    if word.lower() in {"login", "eng", "copyright"}:
        return True
    if _contains_private_use(word):
        return True
    return False


def _clean_token(word: str) -> str:
    token = word.strip(" \t\r\n'\"“”‘’,;:()[]{}<>")
    return re.sub(r"[·.]{3,}", " ", token).strip()


def _contains_noise(text: str) -> bool:
    folded = text.casefold()
    if any(term.casefold() in folded for term in BOILERPLATE_TERMS):
        return True
    if GENERIC_FALLBACK_PHRASE.casefold() in folded:
        return True
    if MOJIBAKE_RE.search(text):
        return True
    return _contains_private_use(text)


def _contains_private_use(text: str) -> bool:
    return any(unicodedata.category(char) == "Co" for char in text)
