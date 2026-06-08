from __future__ import annotations

from pathlib import Path

import joblib

from nlp_term.paths import ensure_parent, model_dir
from nlp_term.schemas import ClassificationInput, ClassificationOutput
from nlp_term.validators import read_json, write_json


KEYWORD_LABELS: list[tuple[int, tuple[str, ...]]] = [
    (0, ("졸업", "학점", "전공", "교양", "수료", "요건")),
    (1, ("공지", "장학", "모집", "안내문", "게시", "학사정보")),
    (2, ("학사일정", "수강신청", "수강 신청", "수강정정", "개강", "종강", "휴학", "복학")),
    (3, ("식단", "학식", "메뉴", "학생식당", "점심", "저녁", "아침")),
    (4, ("셔틀", "통학", "버스", "정류장", "시간표", "운행")),
]


def predict_label(question: str) -> int:
    compact = question.replace(" ", "")
    if _is_notice_post_query(compact):
        return 1
    if _is_graduation_requirement_query(compact):
        return 0
    for label, keywords in KEYWORD_LABELS:
        if any(keyword.replace(" ", "") in compact for keyword in keywords):
            return label
    return 1


def _is_notice_post_query(compact: str) -> bool:
    notice_cues = ("공지", "공지사항", "게시", "올라온", "새글", "글")
    action_cues = ("찾", "어디", "최신", "최근", "이번주", "지난주", "있", "올라왔")
    return any(cue in compact for cue in notice_cues) and any(cue in compact for cue in action_cues)


def _is_graduation_requirement_query(compact: str) -> bool:
    graduation_cues = ("졸업", "졸업요건", "졸업인증", "학점", "전공필수", "전공선택", "교양필수", "교육과정")
    version_cues = ("학번", "입학", "교육과정")
    project_course_cues = ("프로젝트수업", "프로젝트교과목", "프로젝트")
    return any(cue in compact for cue in graduation_cues) or (
        any(cue in compact for cue in version_cues) and any(cue in compact for cue in project_course_cues)
    )


def predict_rows(rows: list[ClassificationInput]) -> list[ClassificationOutput]:
    model_path = model_dir() / "classifier.joblib"
    if model_path.exists():
        model = joblib.load(model_path)
        questions = [row.question for row in rows]
        labels = model.predict(questions).tolist()
        return [ClassificationOutput(question=row.question, label=int(label)) for row, label in zip(rows, labels)]
    return [ClassificationOutput(question=row.question, label=predict_label(row.question)) for row in rows]


def predict_file(input_path: Path, output_path: Path) -> None:
    payload = read_json(input_path)
    rows = [ClassificationInput.model_validate(row) for row in payload]
    outputs = predict_rows(rows)
    ensure_parent(output_path)
    write_json(output_path, outputs)
