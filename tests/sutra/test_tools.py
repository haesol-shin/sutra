from __future__ import annotations

import json
from concurrent.futures import Future, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from typing import Any

import sutra.tools as tools_module
from requests import Response

from sutra import service
from sutra.models import LlamaResult, Message
from sutra.tools import (
    SOURCE_REGISTRY,
    _get,
    _parse_cafeteria_menu,
    dispatch,
    fetch_academic_calendar,
    fetch_cafeteria_menu,
    fetch_page_text,
    fetch_recent_notices,
    get_tool_definitions,
)


FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def raise_for_status(self) -> None:
        return None


def fake_get_factory(mapping: dict[str, str]):
    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        for key, fixture_name in mapping.items():
            if key in url:
                return FakeResponse((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        raise AssertionError(f"unexpected URL: {url}")

    return fake_get


class RecordingExecutor:
    submit_calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []
    shutdown_calls: list[dict[str, Any]] = []

    def __init__(self, max_workers: int | None = None) -> None:
        self.max_workers = max_workers

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Future:
        self.submit_calls.append((fn, args, kwargs))
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self.shutdown_calls.append({"wait": wait, "cancel_futures": cancel_futures})


def reset_recording_executor() -> None:
    RecordingExecutor.submit_calls = []
    RecordingExecutor.shutdown_calls = []


def test_get_decodes_charsetless_utf8_response(monkeypatch) -> None:
    response = Response()
    response.status_code = 200
    response._content = "2026학년도 학교셔틀버스 운영 안내".encode("utf-8")
    response.encoding = "latin-1"
    response.headers["Content-Type"] = "text/html"

    def fake_get(url: str, **kwargs: Any) -> Response:
        return response

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    assert _get("https://plus.cnu.ac.kr/example") == "2026학년도 학교셔틀버스 운영 안내"


def test_recent_university_notices_separate_pinned_and_sort_regular_by_date(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"_board": "notice_board.html"}),
    )

    evidence = fetch_recent_notices(board="univ_academic", limit=3)

    text = evidence[0].text
    assert "최신 공지" in text
    assert "고정 공지" in text
    recent_section = text.split("고정 공지", 1)[0]
    assert recent_section.index("[2026-06-11]") < recent_section.index("[2026-06-09]")
    assert recent_section.index("[2026-06-09]") < recent_section.index("[2026-06-08]")
    assert "[2026-04-16]" not in recent_section
    assert "[2026-04-16] 2026학년도 하기 계절학기 국내 다른 대학 수학 안내" in text


def test_university_notice_parser_normalizes_dot_dates() -> None:
    html = """
        <table><tbody><tr><td>1</td><td><a href='./?mode=V&amp;no=1'>날짜 형식 변경</a></td>
        <td>학사지원과</td><td>2026.06.11</td></tr></tbody></table>
    """

    items = tools_module._parse_univ_notices(html)

    assert items[0].date == "2026-06-11"


def test_recent_notices_accepts_public_board_label(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"bachelor.do": "dept_cs_notice.html"}),
    )

    evidence = fetch_recent_notices(board="학부 학사공지", limit=1)

    assert evidence[0].title == "컴퓨터인공지능학부 학사공지"
    assert evidence[0].metadata["board"] == "cs_bachelor"


def test_recent_notices_accepts_legacy_cs_dept_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"bachelor.do": "dept_cs_notice.html"}),
    )

    evidence = fetch_recent_notices(board="cs_dept", limit=1)

    assert evidence[0].metadata["board"] == "cs_bachelor"
    assert evidence[0].metadata["board_alias"] == "cs_dept"


def test_recent_notices_without_board_merges_five_boards_sorted_with_labels(monkeypatch) -> None:
    calls: list[str] = []
    board_html = {
        "sub07_0702": """
            <table><tbody><tr><td>1</td><td><a href='./?mode=V&amp;no=1&amp;code=sub07_0702'>학사 최신</a></td>
            <td>학사지원과</td><td>2026-06-10</td></tr></tbody></table>
        """,
        "sub07_0701": """
            <table><tbody><tr><td>1</td><td><a href='./?mode=V&amp;no=2&amp;code=sub07_0701'>학교 새소식</a></td>
            <td>대외협력실</td><td>2026-06-12</td></tr></tbody></table>
        """,
        "bachelor.do": (FIXTURES / "dept_cs_notice.html").read_text(encoding="utf-8"),
        "notice.do": """
            <table><tbody><tr><td>1</td><td><div class='b-title-box'><a href='?mode=view&amp;articleNo=3'>학부 뉴스</a>
            <div><span class='b-writer'>학부</span><span class='b-date'>26.06.11</span></div></div></td><td>학부</td><td>26.06.11</td></tr></tbody></table>
        """,
        "project.do": """
            <table><tbody><tr><td>1</td><td><div class='b-title-box'><a href='?mode=view&amp;articleNo=4'>사업단 뉴스</a>
            <div><span class='b-writer'>사업단</span><span class='b-date'>26.06.08</span></div></div></td><td>사업단</td><td>26.06.08</td></tr></tbody></table>
        """,
    }

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(url)
        for key, html in board_html.items():
            if key in url:
                return FakeResponse(html)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices()

    assert len(evidence) == 1
    text = evidence[0].text
    assert text.startswith("최신 공지")
    assert text.index("[2026-06-12][학교 새소식]") < text.index("[2026-06-11][학부 소식]")
    assert text.index("[2026-06-11][학부 소식]") < text.index("[2026-06-10][학교 학사공지]")
    assert "[2026-06-08][학부 사업단 소식]" in text
    assert "학부 학사공지" in text
    assert evidence[0].title == "충남대학교/컴퓨터인공지능학부 통합 공지"
    assert evidence[0].metadata["boards"] == [
        "univ_academic",
        "univ_news",
        "cs_bachelor",
        "cs_news",
        "cs_project",
    ]
    assert len(calls) == 5


def test_recent_notices_without_board_caps_regular_with_each_board_represented_and_pinned_separate(monkeypatch) -> None:
    def fake_fetch(
        board_info: Any,
        *,
        include_label: bool,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> list[Any]:
        board_index = tools_module.NOTICE_BOARD_ORDER.index(board_info.internal)
        regular = [
            tools_module.NoticeItem(
                title=f"{board_info.display} 일반 {idx}",
                author="작성자",
                date=f"2026-06-{30 - board_index * 5 - idx:02d}",
                url=f"https://example.test/{board_info.internal}/regular/{idx}",
                pinned=False,
                board_label=board_info.display if include_label else "",
            )
            for idx in range(5)
        ]
        pinned = [
            tools_module.NoticeItem(
                title=f"{board_info.display} 고정 {idx}",
                author="작성자",
                date=f"2026-05-{30 - board_index * 2 - idx:02d}",
                url=f"https://example.test/{board_info.internal}/pinned/{idx}",
                pinned=True,
                board_label=board_info.display if include_label else "",
            )
            for idx in range(2)
        ]
        return [*regular, *pinned]

    monkeypatch.setattr("sutra.tools._fetch_notice_board", fake_fetch)

    evidence = fetch_recent_notices()

    text = evidence[0].text
    regular_section, pinned_section = text.split("고정 공지", 1)
    assert regular_section.count(" — https://") == 10
    assert pinned_section.count(" — https://") == 5
    for board in tools_module.NOTICE_BOARDS.values():
        assert f"[{board.display}]" in regular_section
    assert evidence[0].source_url == tools_module.UNIV_ACADEMIC_NOTICE_URL


def test_recent_notices_without_board_respects_explicit_limit_below_board_count(monkeypatch) -> None:
    def fake_fetch(
        board_info: Any,
        *,
        include_label: bool,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> list[Any]:
        board_index = tools_module.NOTICE_BOARD_ORDER.index(board_info.internal)
        return [
            tools_module.NoticeItem(
                title=f"{board_info.display} 일반",
                author="작성자",
                date=f"2026-06-{30 - board_index:02d}",
                url=f"https://example.test/{board_info.internal}/regular",
                pinned=False,
                board_label=board_info.display if include_label else "",
            )
        ]

    monkeypatch.setattr("sutra.tools._fetch_notice_board", fake_fetch)

    evidence = fetch_recent_notices(limit=2)

    regular_section = evidence[0].text.split("고정 공지", 1)[0]
    assert regular_section.count(" — https://") == 2


def test_recent_notices_keyword_search_filters_latest_academic_boards_by_title_and_dedupes(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        params = kwargs.get("params")
        calls.append((url, params))
        assert params is None
        if "no=10" in url or "articleNo=10" in url:
            return FakeResponse("<html><body><div class='board-view-content'>장학금 상세 안내</div></body></html>")
        if "articleNo=20" in url:
            return FakeResponse("<html><body><div class='b-content'>설명회 상세 안내</div></body></html>")
        if "sub07_0702" in url:
            return FakeResponse(
                """
                <table><tbody>
                <tr><td>1</td><td><a href='./?mode=V&amp;no=10&amp;code=sub07_0702'>장학금 신청 안내</a></td>
                <td>학생과</td><td>2026-06-11</td></tr>
                <tr><td>2</td><td><a href='./?mode=V&amp;no=11&amp;code=sub07_0702'>등록 일정 안내</a></td>
                <td>학사지원과</td><td>2026-06-10</td></tr>
                </tbody></table>
                """
            )
        if "bachelor.do" in url:
            return FakeResponse(
                """
                <table><tbody>
                <tr><td>1</td><td><div class='b-title-box'><a href='?mode=view&amp;articleNo=10'>장학금 신청 안내</a>
                <div><span class='b-writer'>학부</span><span class='b-date'>26.06.11</span></div></div></td><td>학부</td><td>26.06.11</td></tr>
                <tr><td>2</td><td><div class='b-title-box'><a href='?mode=view&amp;articleNo=20'>SW 장 학 설명회</a>
                <div><span class='b-writer'>학부</span><span class='b-date'>26.06.10</span></div></div></td><td>학부</td><td>26.06.10</td></tr>
                </tbody></table>
                """
            )
        raise AssertionError(f"unexpected URL/params: {url} {params}")

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices(keywords=["장학금", "장학"])

    assert len(evidence) == 1
    text = evidence[0].text
    assert text.count("no=10") == 1
    assert text.count("articleNo=10") == 1
    assert text.count("SW 장 학 설명회") == 1
    assert "등록 일정 안내" not in text
    assert text.index("[2026-06-11][학교 학사공지]") < text.index("[2026-06-10][학부 학사공지]")
    assert [call[0] for call in calls].count(tools_module.UNIV_ACADEMIC_NOTICE_URL) == 1
    assert [call[0] for call in calls].count(tools_module.CS_BACHELOR_NOTICE_URL) == 1
    assert all(params is None for _, params in calls)
    assert evidence[0].metadata["keywords"] == ["장학금", "장학"]
    assert evidence[0].metadata["boards"] == ["univ_academic", "cs_bachelor"]


def test_recent_notices_keyword_search_fetches_latest_boards_once_in_parallel(monkeypatch) -> None:
    reset_recording_executor()
    monkeypatch.setattr("sutra.tools.ThreadPoolExecutor", RecordingExecutor)
    monkeypatch.setattr("sutra.tools._attach_notice_excerpts", lambda items: None)

    def fake_fetch(
        board_info: Any,
        *,
        include_label: bool,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> list[Any]:
        assert params is None
        return [
            tools_module.NoticeItem(
                title=f"{board_info.internal} A",
                author="작성자",
                date="2026-06-12",
                url=f"https://example.test/{board_info.internal}/latest",
                pinned=False,
                board_label=board_info.display if include_label else "",
            )
        ]

    monkeypatch.setattr("sutra.tools._fetch_notice_board", fake_fetch)

    evidence = fetch_recent_notices(keywords=["A", "B", "C"])

    assert evidence
    assert len(RecordingExecutor.submit_calls) == 2
    submitted_params = [call[2]["params"] for call in RecordingExecutor.submit_calls]
    assert submitted_params == [None, None]


def test_recent_notices_keyword_search_uses_requested_board_and_limits_keywords(monkeypatch) -> None:
    calls: list[dict[str, str] | None] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(kwargs.get("params"))
        assert kwargs.get("params") is None
        return FakeResponse(
            """
            <table><tbody><tr><td>1</td><td><div class='b-title-box'><a href='?mode=view&amp;articleNo=30'>키워드 공지</a>
            <div><span class='b-writer'>학부</span><span class='b-date'>26.06.12</span></div></div></td><td>학부</td><td>26.06.12</td></tr></tbody></table>
            """
        )

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices(board="학부 소식", keywords=["A", "B", "C", "D"])

    assert calls[0] is None
    assert all(param is None for param in calls)
    assert evidence[0].metadata["board"] == "cs_news"
    assert evidence[0].metadata["keywords"] == ["A", "B", "C"]


def test_recent_notices_keyword_search_falls_back_to_latest_when_empty(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        params = kwargs.get("params")
        calls.append((url, params))
        assert params is None
        if "sub07_0702" in url:
            return FakeResponse(
                """
                <table><tbody><tr><td>1</td><td><a href='./?mode=V&amp;no=40&amp;code=sub07_0702'>최신 학사</a></td>
                <td>학사지원과</td><td>2026-06-09</td></tr></tbody></table>
                """
            )
        if "bachelor.do" in url:
            return FakeResponse((FIXTURES / "dept_cs_notice.html").read_text(encoding="utf-8"))
        raise AssertionError(f"unexpected URL/params: {url} {params}")

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices(keywords=["등록금"])

    assert evidence[0].text.startswith("'등록금' 관련 최근 공지를 찾지 못해 최신 공지를 표시합니다")
    assert "최신 학사" in evidence[0].text
    assert "2026 하기 계절학기 수강료" in evidence[0].text
    assert len(calls) == 5
    assert all(params is None for _, params in calls)


def test_recent_notices_keyword_search_fans_out_remaining_boards_before_latest_fallback(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str] | None]] = []
    monkeypatch.setattr("sutra.tools._attach_notice_excerpts", lambda items: None)

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        params = kwargs.get("params")
        calls.append((url, params))
        assert params is None
        if "project.do" in url:
            return FakeResponse(
                """
                <table><tbody><tr><td>1</td><td><div class='b-title-box'><a href='?mode=view&amp;articleNo=70'>사업단 프로그램 안내</a>
                <div><span class='b-writer'>사업단</span><span class='b-date'>26.06.12</span></div></div></td><td>사업단</td><td>26.06.12</td></tr></tbody></table>
                """
            )
        if "sub07_0701" in url or "notice.do" in url:
            return FakeResponse("<table><tbody></tbody></table>")
        return FakeResponse("<table><tbody></tbody></table>")

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices(keywords=["사업단", "프로그램"])

    assert "사업단 프로그램 안내" in evidence[0].text
    assert "관련 최근 공지를 찾지 못해 최신 공지를 표시합니다" not in evidence[0].text
    requested_urls = [url for url, _ in calls]
    assert tools_module.UNIV_NEWS_NOTICE_URL in requested_urls
    assert tools_module.CS_NEWS_NOTICE_URL in requested_urls
    assert tools_module.CS_PROJECT_NOTICE_URL in requested_urls
    assert len(calls) == 5
    assert all(params is None for _, params in calls)


def test_recent_notices_keyword_search_includes_top_two_body_excerpts(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(url)
        params = kwargs.get("params")
        if "no=51" in url:
            return FakeResponse("<html><body><div class='board-view-content'>첫 번째 상세 본문입니다.<br>신청 자격과 제출 서류 안내</div></body></html>")
        if "no=52" in url:
            return FakeResponse("<html><body><div class='b-content'>두 번째 상세 본문입니다. 장학금 지급 일정 안내</div></body></html>")
        if "no=53" in url:
            raise AssertionError("third detail page should not be fetched")
        if params is None and "sub07_0702" in url:
            return FakeResponse(
                """
                <table><tbody>
                <tr><td>1</td><td><a href='./?mode=V&amp;no=51&amp;code=sub07_0702'>장학 1</a></td><td>학생과</td><td>2026-06-12</td></tr>
                <tr><td>4</td><td><a href='./?mode=V&amp;no=54&amp;code=sub07_0702'>등록 4</a></td><td>학사지원과</td><td>2026-06-12</td></tr>
                <tr><td>2</td><td><a href='./?mode=V&amp;no=52&amp;code=sub07_0702'>장학 2</a></td><td>학생과</td><td>2026-06-11</td></tr>
                <tr><td>3</td><td><a href='./?mode=V&amp;no=53&amp;code=sub07_0702'>장학 3</a></td><td>학생과</td><td>2026-06-10</td></tr>
                </tbody></table>
                """
            )
        if "bachelor.do" in url:
            return FakeResponse("<table><tbody></tbody></table>")
        raise AssertionError(f"unexpected URL/params: {url} {kwargs}")

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices(board="학교 학사공지", keywords=["장학"])

    text = evidence[0].text
    assert "본문 발췌: 첫 번째 상세 본문입니다. 신청 자격과 제출 서류 안내" in text
    assert "본문 발췌: 두 번째 상세 본문입니다. 장학금 지급 일정 안내" in text
    assert "장학 3" in text
    assert "등록 4" not in text
    assert text.count("본문 발췌:") == 2


def test_notice_body_extracts_plus_and_computer_cms_selectors() -> None:
    plus_html = "<html><body><div class='board-view-content'>플러스 CMS 본문<br>신청 안내</div></body></html>"
    computer_html = "<html><body><div class='b-content-box'><div class='b-content'>컴퓨터 CMS 본문</div></div></body></html>"

    assert tools_module._extract_notice_body(plus_html, parser="plus") == "플러스 CMS 본문 신청 안내"
    assert tools_module._extract_notice_body(computer_html, parser="computer") == "컴퓨터 CMS 본문"


def test_notice_body_omits_noisy_full_html_fallback() -> None:
    noisy_html = """
        <html><body>
        본문 바로가기 로그인 사이트맵 로그인 목록 이전글 다음글 목록
        본문 바로가기 로그인 사이트맵 로그인 목록 이전글 다음글 목록
        <footer>목록 이전글 다음글 사이트맵 로그인</footer>
        </body></html>
    """

    assert tools_module._extract_notice_body(noisy_html, parser="plus") == ""


def test_recent_notices_keyword_search_keeps_headline_when_detail_fetch_fails(monkeypatch) -> None:
    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if "no=61" in url:
            raise RuntimeError("detail unavailable")
        if kwargs.get("params") is None:
            return FakeResponse(
                """
                <table><tbody><tr><td>1</td><td><a href='./?mode=V&amp;no=61&amp;code=sub07_0702'>장학 상세 실패</a></td>
                <td>학생과</td><td>2026-06-12</td></tr></tbody></table>
                """
            )
        raise AssertionError(f"unexpected params: {kwargs.get('params')}")

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_recent_notices(board="학교 학사공지", keywords=["장학"])

    assert "장학 상세 실패" in evidence[0].text
    assert "본문 발췌:" not in evidence[0].text


def test_notice_excerpt_fetch_submits_top_two_details_and_abandons_timeout(monkeypatch) -> None:
    reset_recording_executor()

    class HangingExecutor(RecordingExecutor):
        def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Future:
            self.submit_calls.append((fn, args, kwargs))
            return Future()

    def fake_as_completed(futures: list[Future], timeout: float | None = None) -> list[Future]:
        raise FuturesTimeoutError

    detail_calls = 0

    def fake_get(url: str, **kwargs: Any) -> str:
        nonlocal detail_calls
        detail_calls += 1
        raise AssertionError("detail fetch should run only inside submitted futures")

    monkeypatch.setattr("sutra.tools.ThreadPoolExecutor", HangingExecutor)
    monkeypatch.setattr("sutra.tools.as_completed", fake_as_completed)
    monkeypatch.setattr("sutra.tools._get", fake_get)
    items = [
        tools_module.NoticeItem("상세 1", "작성자", "2026-06-12", "https://example.test/1", False),
        tools_module.NoticeItem("상세 2", "작성자", "2026-06-11", "https://example.test/2", False),
        tools_module.NoticeItem("상세 3", "작성자", "2026-06-10", "https://example.test/3", False),
    ]

    tools_module._attach_notice_excerpts(items)

    assert len(HangingExecutor.submit_calls) == 2
    assert detail_calls == 0
    assert [item.excerpt for item in items] == ["", "", ""]
    assert HangingExecutor.shutdown_calls[-1] == {"wait": False, "cancel_futures": True}


def test_recent_cs_notices_use_department_skin_date_and_absolute_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"bachelor.do": "dept_cs_notice.html"}),
    )

    evidence = fetch_recent_notices(board="cs_dept", limit=2)

    text = evidence[0].text
    assert "[2026-06-01] 2026 하기 계절학기 수강료 추기 납부 안내 (조교 김정화) — https://computer.cnu.ac.kr/computer/notice/bachelor.do?mode=view&articleNo=588027&article.offset=0&articleLimit=10" in text
    assert "고정 공지" in text
    assert "[2026-06-09] [종합설계1] 결과보고서 제출 안내 (조교 김정화)" in text


def test_cafeteria_menu_returns_clean_rag_style_daily_text(monkeypatch) -> None:
    monkeypatch.setattr("sutra.tools._today_kst", lambda: datetime(2026, 6, 11))
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"food": "food.html"}),
    )

    evidence = fetch_cafeteria_menu(date="2026-06-11", cafeteria="제2학생회관")

    text = evidence[0].text
    assert text.startswith("# 2026-06-11 (목) 학생식당 식단")
    assert "## 제2학생회관" in text
    assert "- 아침(학생) 정식 1,000원: 육개장(beef included), 연두부&양념장, 깍두기" in text
    assert "- 점심(학생) 정식 4,500원: 칠리치킨까스(chicken included), 스프" in text
    assert "운영안함" not in text


def test_cafeteria_menu_body_text_extracts_only_menu_lines() -> None:
    extract = getattr(tools_module, "_cafeteria_menu_body_text", None)
    assert extract is not None

    today_text = "# 2026-06-11 (목) 학생식당 식단\n\n## 제2학생회관\n- 점심(학생) 정식: A"
    target_same = "# 2026-06-18 (목) 학생식당 식단\n\n## 제2학생회관\n- 점심(학생) 정식: A"
    target_other = "# 2026-06-18 (목) 학생식당 식단\n\n## 제2학생회관\n- 점심(학생) 정식: B"

    assert extract(today_text) == extract(target_same)
    assert extract(today_text) != extract(target_other)
    assert extract("# 2026-06-18 (목) 학생식당 식단") == ""


def test_cafeteria_menu_flags_non_today_identical_body_as_unverified(monkeypatch) -> None:
    monkeypatch.setattr("sutra.tools._today_kst", lambda: datetime(2026, 6, 11))
    calls: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(kwargs["params"]["searchYmd"])
        return FakeResponse((FIXTURES / "food.html").read_text(encoding="utf-8"))

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_cafeteria_menu(date="2026-06-18", cafeteria="제2학생회관")

    assert calls == ["2026.06.18", "2026.06.11"]
    assert len(evidence) == 1
    assert "2026-06-18의 식단은 아직 신뢰 가능한 데이터가 제공되지 않습니다." in evidence[0].text
    assert evidence[0].metadata["unverified_future_data"] is True
    assert evidence[0].metadata["date"] == "2026-06-18"


def test_cafeteria_menu_returns_non_today_data_when_body_differs(monkeypatch) -> None:
    monkeypatch.setattr("sutra.tools._today_kst", lambda: datetime(2026, 6, 11))
    today_html = (FIXTURES / "food.html").read_text(encoding="utf-8")
    target_html = today_html.replace("칠리치킨까스(chicken included)", "수제돈까스")

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if kwargs["params"]["searchYmd"] == "2026.06.18":
            return FakeResponse(target_html)
        return FakeResponse(today_html)

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_cafeteria_menu(date="2026-06-18", cafeteria="제2학생회관")

    assert len(evidence) == 1
    assert "수제돈까스" in evidence[0].text
    assert "unverified_future_data" not in evidence[0].metadata


def test_cafeteria_menu_returns_empty_for_non_today_empty_target(monkeypatch) -> None:
    monkeypatch.setattr("sutra.tools._today_kst", lambda: datetime(2026, 6, 11))

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if kwargs["params"]["searchYmd"] == "2026.06.18":
            return FakeResponse("<html><body>메뉴는 준비중입니다.</body></html>")
        return FakeResponse((FIXTURES / "food.html").read_text(encoding="utf-8"))

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    assert fetch_cafeteria_menu(date="2026-06-18", cafeteria="제2학생회관") == []


def test_cafeteria_menu_fetches_today_once(monkeypatch) -> None:
    monkeypatch.setattr("sutra.tools._today_kst", lambda: datetime(2026, 6, 11))
    calls: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(kwargs["params"]["searchYmd"])
        return FakeResponse((FIXTURES / "food.html").read_text(encoding="utf-8"))

    monkeypatch.setattr("sutra.tools.requests.get", fake_get)

    evidence = fetch_cafeteria_menu(date="2026-06-11", cafeteria="제2학생회관")

    assert calls == ["2026.06.11"]
    assert len(evidence) == 1


def test_cafeteria_menu_parser_preserves_rowspanned_cafeteria_columns() -> None:
    html = (FIXTURES / "food.html").read_text(encoding="utf-8")

    records = _parse_cafeteria_menu(html, "2026-06-11", "제2학생회관")

    breakfast = [
        record
        for record in records
        if record.cafeteria == "제2학생회관" and record.meal == "조식" and record.audience == "학생"
    ]
    assert len(breakfast) == 1
    assert breakfast[0].menu_name == "정식(1000)"
    assert "육개장(beef included)" in breakfast[0].menu_text


def test_academic_calendar_filters_requested_month(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"academic_calendar": "calendar.html"}),
    )

    evidence = fetch_academic_calendar(month=6)

    text = evidence[0].text
    assert text.startswith("오늘:")
    assert "[06.09~06.12] 정기휴업일 수업결손 보충강의" in text
    assert "[06.22~07.10] 하기 계절학기" in text
    assert "05.07" not in text


def test_page_text_registry_extracts_shuttle_text_and_strips_noise(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"sub05_050403": "shuttle.html"}),
    )

    evidence = fetch_page_text(source_id="shuttle")

    text = evidence[0].text
    assert text.startswith("2026학년도 학교셔틀버스 운영 안내")
    assert "학교셔틀버스 운영 안내" in text
    assert "월평역" in text
    assert "08:20" in text
    assert "사이트맵" not in text
    assert "window.noise" not in text
    assert len(text) <= 3000


def test_page_text_accepts_public_source_label(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"sub05_050403": "shuttle.html"}),
    )

    evidence = fetch_page_text(source_id="셔틀버스 안내")

    assert evidence[0].title == "충남대학교 학교셔틀버스 운행 안내"
    assert evidence[0].metadata["source_id"] == "shuttle"


def test_source_registry_excludes_unverified_graduation_curriculum_url() -> None:
    assert "graduation_curriculum" not in SOURCE_REGISTRY
    assert all("graduation.do" not in source["url"] for source in SOURCE_REGISTRY.values())


def test_tool_schemas_enum_constrain_string_arguments() -> None:
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in get_tool_definitions()}
    experimental_schemas = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in get_tool_definitions(include_knowledge_base=True)
    }

    assert schemas["fetch_recent_notices"]["properties"]["board"]["enum"] == [
        "학교 학사공지",
        "학교 새소식",
        "학부 학사공지",
        "학부 소식",
        "학부 사업단 소식",
    ]
    assert schemas["fetch_recent_notices"]["properties"]["keywords"]["type"] == "array"
    assert schemas["fetch_recent_notices"]["properties"]["keywords"]["minItems"] == 1
    assert schemas["fetch_recent_notices"]["properties"]["keywords"]["maxItems"] == 3
    notice_schema_text = json.dumps(schemas["fetch_recent_notices"], ensure_ascii=False)
    assert "최신 공지 알려줘 → 인자 생략" in notice_schema_text
    assert "장학금 공지 찾아줘 → keywords=[장학금, 장학]" in notice_schema_text
    assert "사업단 공지 → board=학부 사업단 소식" in notice_schema_text
    assert "최근 공지 중 해당 주제어가 제목에 포함된 것" in notice_schema_text
    assert schemas["fetch_cafeteria_menu"]["properties"]["cafeteria"]["enum"] == [
        "제2학생회관",
        "제3학생회관",
        "제4학생회관",
        "생활과학대학",
        None,
    ]
    assert schemas["fetch_page_text"]["properties"]["source_id"]["enum"] == ["셔틀버스 안내", "수강신청 안내"]
    exposed = json.dumps([schemas["fetch_recent_notices"], schemas["fetch_page_text"]], ensure_ascii=False)
    assert "univ_academic" not in exposed
    assert "cs_dept" not in exposed
    assert "컴퓨터융합학부" not in exposed
    assert "컴퓨터인공지능학부" in exposed
    assert "course_registration_guide" not in exposed
    assert "search_knowledge_base" not in schemas
    assert experimental_schemas["search_knowledge_base"]["properties"]["domain"]["enum"] == [
        "academic_calendar",
        "calendar",
        "dining",
        "graduation",
        "shuttle",
        None,
    ]


def test_dispatch_passes_tool_arguments(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"_board": "notice_board.html"}),
    )

    evidence = dispatch("fetch_recent_notices", '{"board":"univ_academic","limit":1}')

    assert len(evidence) == 1
    assert evidence[0].text.count("[2026-06-") == 1


def test_dispatch_accepts_legacy_internal_tool_arguments(monkeypatch) -> None:
    monkeypatch.setattr(
        "sutra.tools.requests.get",
        fake_get_factory({"_board": "notice_board.html"}),
    )

    evidence = dispatch("fetch_recent_notices", '{"board":"univ_academic","limit":1}')

    assert len(evidence) == 1
    assert evidence[0].metadata["board"] == "univ_academic"


def test_dispatch_search_knowledge_base_returns_workspace_evidence(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)

    evidence = dispatch("search_knowledge_base", {"query": "수강신청"}, workspace=workspace)

    assert len(evidence) == 1
    assert evidence[0].id == "calendar-1"
    assert evidence[0].metadata["tool"] == "search_knowledge_base"


def test_dispatch_search_knowledge_base_filters_by_domain(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, include_dining=True)

    evidence = dispatch(
        "search_knowledge_base",
        {"query": "학생회관", "domain": "dining"},
        workspace=workspace,
    )

    assert [item.id for item in evidence] == ["dining-1"]


def test_dispatch_search_knowledge_base_filters_multiword_domain_from_document_id(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, include_academic_calendar=True)

    evidence = dispatch(
        "search_knowledge_base",
        {"query": "개강", "domain": "academic_calendar"},
        workspace=workspace,
    )

    assert [item.id for item in evidence] == ["academic_calendar-1"]


def test_dispatch_search_knowledge_base_returns_empty_for_no_matches_and_invalid_query(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)

    no_domain_matches = dispatch(
        "search_knowledge_base",
        {"query": "수강신청", "domain": "graduation"},
        workspace=workspace,
    )
    blank_query = dispatch("search_knowledge_base", {"query": "   "}, workspace=workspace)
    missing_query = dispatch("search_knowledge_base", {"domain": "calendar"}, workspace=workspace)

    assert no_domain_matches == []
    assert blank_query == []
    assert missing_query == []


class CapturingClient:
    def __init__(self) -> None:
        self.tools: list[dict[str, Any]] | None = None

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlamaResult:
        self.tools = tools
        return LlamaResult(content="답변", model=model)


def test_service_ask_injects_tools_even_when_live_false(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = CapturingClient()

    service.ask("수강신청 언제 시작해?", workspace=workspace, client=client, live=False)

    assert client.tools
    assert {item["function"]["name"] for item in client.tools} >= {
        "fetch_recent_notices",
        "fetch_cafeteria_menu",
        "fetch_academic_calendar",
        "fetch_page_text",
    }


def _write_workspace(
    root: Path,
    *,
    include_dining: bool = False,
    include_academic_calendar: bool = False,
) -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    docs = [
        '{"id":"calendar-1","title":"수강신청 일정","text":"수강신청은 2월 1일에 시작합니다.","source_name":"학사일정","metadata":{"label":"calendar"}}',
    ]
    if include_dining:
        docs.append(
            '{"id":"dining-1","title":"식단","text":"학생회관 점심 메뉴입니다.","source_name":"식단","metadata":{"label":"dining"}}'
        )
    if include_academic_calendar:
        docs.append(
            '{"id":"academic_calendar-1","title":"개강 일정","text":"개강은 3월 2일입니다.","source_name":"학사일정","metadata":{}}'
        )
    (root / "data" / "index.jsonl").write_text("\n".join(docs) + "\n", encoding="utf-8")
    (root / "prompts" / "system.md").write_text("You are a grounded assistant.", encoding="utf-8")
    (root / "prompts" / "answer.md").write_text("Use the evidence context.", encoding="utf-8")
    config_path = root / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"
timezone = "Asia/Seoul"

[runtime]
backend = "llama-server"
base_url = "http://127.0.0.1:18080"
model = "fake-qwen"
temperature = 0.1
max_tokens = 128

[rag]
index_path = "data/index.jsonl"
top_k = 1
max_fact_chars = 120
backend = "lexical"

[prompts]
system = "prompts/system.md"
answer = "prompts/answer.md"
""".strip(),
        encoding="utf-8",
    )
    return config_path
