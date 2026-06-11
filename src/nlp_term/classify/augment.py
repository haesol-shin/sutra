from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from nlp_term.classify.train import load_examples
from nlp_term.paths import data_dir
from nlp_term.schemas import ClassificationExample


PROBE_V2_QUESTIONS: set[str] = {
    "복수전공하면 졸업학점 어떻게 돼?",
    "교직이수 졸업 조건 뭐야?",
    "졸업논문 대신 작품전 되나?",
    "영어 점수 없으면 졸업 안 돼?",
    "이수 학점 모자란데 졸업 가능해?",
    "교양 필수 뭐 들어야 졸업돼?",
    "졸업유예 하려면 어떻게 해?",
    "등록금 분할납부 안내 올라왔어?",
    "근로장학 모집 공지 봤어?",
    "수강신청 변경 안내문 어디 있어?",
    "기숙사 입사 공지 떴나?",
    "학과 사무실에서 새 글 올렸어?",
    "교환학생 모집 공고 찾아줘",
    "휴학 신청 방법 공지 링크 줘",
    "종강 언제야?",
    "중간고사 기간 알려줘",
    "계절학기 언제 시작해?",
    "복학 신청 기간 지났어?",
    "다음 학기 개강일이 며칠이지?",
    "성적 정정 기간 언제까지야?",
    "수강 포기 가능한 기간은?",
    "오늘 3학 저녁 뭐 나옴?",
    "내일 점심 학식 메뉴 알려줘",
    "이번주 생과대 식단표 보여줘",
    "아침 하는 식당 있어?",
    "학식 가격 얼마야?",
    "금요일 1학생회관 메뉴 뭐야?",
    "직원식당 오늘 메뉴 알려줘",
    "막차 몇 시야?",
    "월평역에서 학교 가는 버스 언제 와?",
    "시험기간에도 버스 다녀?",
    "보운캠퍼스 가는 차 있어?",
    "등교 버스 어디서 타?",
    "방학 때 셔틀 운행해?",
    "노선도 보여줘",
}


def _gold_questions() -> set[str]:
    path = data_dir() / "gold" / "task1_human_gold.json"
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as file:
        return {row["question"] for row in json.load(file)}


def _make_example(question: str, label: int, index: int) -> ClassificationExample:
    return ClassificationExample(
        question=question,
        label=label,
        source_doc_id=f"wp3_template_label_{label}",
        generation_method="augmented",
        validated=True,
        metadata={
            "sample_type": "wp3_template_augmentation",
            "template_index": index,
            "label_first": True,
        },
    )


def _label3_date_dining_questions() -> Iterable[tuple[str, int]]:
    dates = ["오늘", "내일", "이번주 금요일", "6월 12일", "2026년 6월 13일"]
    places = ["1학생회관", "2학생회관", "3학생회관", "4학생회관", "생활과학대학", "학식", "학생식당", "직원식당"]
    asks = ["조식", "점심", "중식", "저녁", "석식", "메뉴", "뭐 나와", "가격"]
    index = 0
    for date in dates:
        for place in places:
            for ask in asks:
                yield f"{date} {place} {ask} 알려줘", index
                index += 1


def _label4_shuttle_questions() -> Iterable[tuple[str, int]]:
    index = 0
    for period in ["주말", "공휴일", "야간", "방학", "시험기간"]:
        for suffix in ["운행 여부 알려줘", "에도 셔틀 다녀", "통학버스 운행해"]:
            yield f"{period} {suffix}?", index
            index += 1
    for endpoint in ["첫차", "막차"]:
        for suffix in ["시간 알려줘", "몇 시에 출발해", "운행 시간 확인해줘"]:
            yield f"셔틀 {endpoint} {suffix}", index
            index += 1
    for place in ["월평역", "유성", "보운캠퍼스"]:
        for target in ["노선", "정류장", "가는 셔틀", "출발 위치"]:
            yield f"{place} {target} 알려줘", index
            index += 1
    for phrase in ["통학 차", "등하교 버스", "교내 순환", "학교버스"]:
        for suffix in ["시간표 알려줘", "어디서 타", "운행 정보 보여줘", "노선 확인해줘"]:
            yield f"{phrase} {suffix}", index
            index += 1


def _label2_event_questions() -> Iterable[tuple[str, int]]:
    events = ["학위수여식", "성적발표", "계절학기", "중간고사", "기말고사", "개강", "종강", "수강 정정", "수강 포기", "등록금 납부"]
    asks = ["언제", "기간", "날짜", "며칠"]
    index = 0
    for event in events:
        for ask in asks:
            yield f"{event} {ask}인지 알려줘", index
            index += 1


def _label1_notice_boundary_questions() -> Iterable[tuple[str, int, int]]:
    topics = ["휴학 신청", "복학", "출석인정", "장학금", "등록금 분할납부", "교환학생 모집"]
    notice_words = ["공지", "안내", "글", "공고"]
    actions = ["올라왔어", "어디서 봐", "찾아줘", "떴어"]
    index = 0
    for topic in topics:
        for notice_word in notice_words:
            for action in actions:
                yield f"{topic} {notice_word} {action}?", 1, index
                index += 1
    for topic in topics:
        yield f"{topic} 신청 기간 언제야?", 2, index
        index += 1


def _label0_requirement_questions() -> Iterable[tuple[str, int]]:
    topics = ["복수전공", "부전공", "교직이수", "졸업유예", "졸업논문", "영어인증", "교양필수"]
    for index, topic in enumerate(topics):
        yield f"{topic} 졸업 요건 기준 알려줘", index


def generate_template_rows(forbidden_questions: set[str] | None = None) -> list[ClassificationExample]:
    forbidden = set(forbidden_questions or set()) | PROBE_V2_QUESTIONS | _gold_questions()
    rows: list[ClassificationExample] = []
    seen: set[str] = set()

    def add(question: str, label: int, index: int) -> None:
        if question in seen or question in forbidden:
            return
        seen.add(question)
        rows.append(_make_example(question, label, index))

    for question, index in _label3_date_dining_questions():
        add(question, 3, index)
    for question, index in _label4_shuttle_questions():
        add(question, 4, index)
    for question, index in _label2_event_questions():
        add(question, 2, index)
    for question, label, index in _label1_notice_boundary_questions():
        add(question, label, index)
    for question, index in _label0_requirement_questions():
        add(question, 0, index)

    return rows


def build_augmented_rows(seed_rows: list[ClassificationExample]) -> list[ClassificationExample]:
    augmented: list[ClassificationExample] = []
    seen: set[str] = set()
    for row in seed_rows:
        if row.question in seen:
            continue
        seen.add(row.question)
        augmented.append(row)
    for row in generate_template_rows():
        if row.question in seen:
            continue
        seen.add(row.question)
        augmented.append(row)

    distribution = Counter(row.label for row in augmented)
    max_share = max(distribution.values()) / len(augmented)
    if max_share > 0.40:
        raise ValueError(f"augmented label distribution exceeds 40% cap: {dict(distribution)}")
    return augmented


def write_rows(rows: list[ClassificationExample], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump([row.model_dump() for row in rows], file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WP3 Task 1 deterministic template augmentation.")
    parser.add_argument("--input", type=Path, default=data_dir() / "cls_train_seed.json")
    parser.add_argument("--output", type=Path, default=data_dir() / "cls_train_augmented.json")
    args = parser.parse_args()

    seed_rows = load_examples(args.input)
    rows = build_augmented_rows(seed_rows)
    write_rows(rows, args.output)
    distribution = Counter(row.label for row in rows)
    print(f"wrote {args.output}")
    print(f"rows={len(rows)} labels={dict(sorted(distribution.items()))}")


if __name__ == "__main__":
    main()
