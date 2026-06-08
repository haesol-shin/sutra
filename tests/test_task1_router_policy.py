from __future__ import annotations

from nlp_term.classify.predict import predict_label


def test_graduation_requirement_question_routes_to_graduation() -> None:
    assert predict_label("충남대학교 인공지능학과 24학번의 경우 프로젝트 수업을 몇 개 들어야 하나요?") == 0


def test_graduation_notice_search_routes_to_notices() -> None:
    assert predict_label("졸업요건 변경 안내 공지가 공지사항에 올라왔는지 찾아줘") == 1


def test_department_graduation_latest_notice_routes_to_notices() -> None:
    assert predict_label("컴퓨터융합학부 졸업요건 관련 최신 학과 공지 있어?") == 1


def test_semester_end_question_routes_to_academic_calendar() -> None:
    assert predict_label("이번 학기 종강일이 언제인가요?") == 2
