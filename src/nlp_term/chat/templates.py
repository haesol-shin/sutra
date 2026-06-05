from __future__ import annotations

from nlp_term.chat.router import RoutedQuestion


FALLBACKS = {
    "graduation": "졸업요건은 충남대학교 교육과정과 소속 학과 기준을 함께 확인해야 합니다.",
    "notices": "학교 공지사항은 충남대학교 학사정보 게시판 source를 기준으로 확인하는 것이 안전합니다.",
    "academic_calendar": "학사일정은 충남대학교 공식 학사일정 페이지를 기준으로 확인해야 합니다.",
    "dining": "식단은 충남대학교 식당메뉴 source를 기준으로 확인해야 하며, 검증 전에는 메뉴를 단정하지 않습니다.",
    "shuttle": "셔틀버스는 충남대학교 학교셔틀버스 페이지의 시간표와 운행 안내를 기준으로 확인해야 합니다.",
}


def fallback_answer(route: RoutedQuestion) -> str:
    return FALLBACKS[route.domain]
