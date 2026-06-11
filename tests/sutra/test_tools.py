from __future__ import annotations

from pathlib import Path
from typing import Any

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


def test_source_registry_excludes_unverified_graduation_curriculum_url() -> None:
    assert "graduation_curriculum" not in SOURCE_REGISTRY
    assert all("graduation.do" not in source["url"] for source in SOURCE_REGISTRY.values())


def test_tool_schemas_enum_constrain_string_arguments() -> None:
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in get_tool_definitions()}
    experimental_schemas = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in get_tool_definitions(include_knowledge_base=True)
    }

    assert schemas["fetch_recent_notices"]["properties"]["board"]["enum"] == ["univ_academic", "cs_dept"]
    assert schemas["fetch_cafeteria_menu"]["properties"]["cafeteria"]["enum"] == [
        "제2학생회관",
        "제3학생회관",
        "제4학생회관",
        "생활과학대학",
        None,
    ]
    assert schemas["fetch_page_text"]["properties"]["source_id"]["enum"] == [
        "shuttle",
        "course_registration_guide",
    ]
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
