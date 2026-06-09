import json
from pathlib import Path

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.router import RoutedQuestion


def test_compose_answer_searches_beyond_top_three_before_same_label_filter(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    rows = [
        {
            "doc_id": f"calendar_doc_{index}",
            "label": 2,
            "domain": "academic_calendar",
            "title": "오늘 학식 관련 일정",
            "body": "오늘 학식이라는 표현이 들어 있지만 실제로는 학사일정 문서입니다.",
            "source_url": f"https://plus.cnu.ac.kr/calendar/{index}",
            "source_id": "calendar",
        }
        for index in range(4)
    ]
    rows.append(
        {
            "doc_id": "dining_doc",
            "label": 3,
            "domain": "dining",
            "title": "식단 안내",
            "body": "충남대학교 학생회관 식단 메뉴는 공식 식단 페이지에서 확인합니다.",
            "source_url": "https://mobileadmin.cnu.ac.kr/food/index.jsp",
            "source_id": "cnu_mobile_food",
        }
    )
    knowledge_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    answer = compose_answer(
        RoutedQuestion(user="오늘 학식 뭐 나와요?", label=3, domain="dining"),
        knowledge_path=knowledge_path,
    )

    assert "근거 후보: 식단 안내" in answer
