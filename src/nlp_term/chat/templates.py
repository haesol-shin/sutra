from __future__ import annotations

from nlp_term.chat.router import RoutedQuestion


FALLBACKS = {
    "graduation": "졸업요건은 충남대학교 교육과정과 소속 학과 기준을 함께 확인해야 합니다. 현재 dry-run에서는 공통 졸업요건 source를 연결하기 전입니다.",
    "notices": "학교 공지사항은 충남대학교 학사정보 게시판 source를 기준으로 확인할 예정입니다. 현재 dry-run에서는 최신 공지 live fetch를 수행하지 않습니다.",
    "academic_calendar": "학사일정은 충남대학교 공식 학사일정 페이지를 기준으로 답변할 예정입니다. 현재 dry-run에서는 수집된 일정 snapshot이 없어 확인 안내만 제공합니다.",
    "dining": "식단은 충남대학교 식당메뉴 후보 source를 검증한 뒤 답변합니다. 현재 dry-run에서는 공식 식단 parser 검증 전이므로 메뉴를 단정하지 않습니다.",
    "shuttle": "셔틀버스는 충남대학교 학교셔틀버스 페이지를 기준으로 답변할 예정입니다. 현재 dry-run에서는 수집된 시간표 snapshot이 없어 공식 페이지 확인 안내만 제공합니다.",
}


def fallback_answer(route: RoutedQuestion) -> str:
    return FALLBACKS[route.domain]
