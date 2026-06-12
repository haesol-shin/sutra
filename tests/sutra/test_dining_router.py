from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from sutra import menu_resolver
from sutra.dining_router import run_forced_cafeteria_call
from sutra.models import Evidence, LlamaResult, ToolCall


class FrozenMenuResolverDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        value = cls(2026, 6, 13, 9, 0, 0)
        if tz is None:
            return value
        return value.replace(tzinfo=ZoneInfo("Asia/Seoul")).astimezone(tz)


@pytest.fixture(autouse=True)
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(menu_resolver, "datetime", FrozenMenuResolverDateTime)


@pytest.fixture
def config() -> SimpleNamespace:
    return SimpleNamespace(workspace=SimpleNamespace(timezone="Asia/Seoul"))


def _tool_call(arguments: str) -> ToolCall:
    return ToolCall(id="call-1", function_name="fetch_cafeteria_menu", function_arguments=arguments)


def _evidence() -> Evidence:
    return Evidence(id="live_cafeteria_menu", title="충남대학교 식단", text="menu")


def test_dispatches_next_week_tuesday_to_selected_cafeteria(config: SimpleNamespace) -> None:
    dispatch_calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch_fn(name: str, args: dict[str, Any]) -> list[Evidence]:
        dispatch_calls.append((name, dict(args)))
        return [_evidence()]

    outcome = run_forced_cafeteria_call(
        question="다음 주 화요일 2학 메뉴",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"제2학생회관"}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=dispatch_fn,
    )

    assert dispatch_calls == [("fetch_cafeteria_menu", {"cafeteria": "제2학생회관", "dates": ["2026-06-16"]})]
    assert outcome.refused is False
    assert outcome.evidence


def test_total_maps_to_all_daily_cafeterias_for_next_week(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []

    outcome = run_forced_cafeteria_call(
        question="다음 주 학식",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"전체"}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=lambda name, args: dispatch_calls.append(dict(args)) or [_evidence()],
    )

    assert dispatch_calls == [
        {
            "cafeteria": None,
            "dates": ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"],
        }
    ]
    assert outcome.refused is False


def test_today_total_dispatches_resolved_today(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []

    outcome = run_forced_cafeteria_call(
        question="오늘 학식",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"전체"}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=lambda name, args: dispatch_calls.append(dict(args)) or [_evidence()],
    )

    assert dispatch_calls == [{"cafeteria": None, "dates": ["2026-06-13"]}]
    assert outcome.refused is False


def test_food_court_uses_kb_fallback_without_dispatch(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []

    outcome = run_forced_cafeteria_call(
        question="어제 1학",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"제1학생회관"}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=lambda name, args: dispatch_calls.append(dict(args)) or [_evidence()],
    )

    assert dispatch_calls == []
    assert outcome.use_kb_fallback is True
    assert outcome.called_tools == ["fetch_cafeteria_menu:food_court_skip"]
    assert outcome.tool_args == [{"cafeteria": "제1학생회관", "_sutra_skip": "food_court"}]


def test_unresolvable_model_date_retries_once_then_refuses(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []
    retry_calls = 0

    def call_model() -> LlamaResult:
        nonlocal retry_calls
        retry_calls += 1
        return LlamaResult(content="", tool_calls=[_tool_call('{"cafeteria":"전체","dates":["2026-06-17"]}')])

    outcome = run_forced_cafeteria_call(
        question="학식 메뉴",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"전체","dates":["2026-06-17"]}')],
        call_model=call_model,
        dispatch_fn=lambda name, args: dispatch_calls.append(dict(args)) or [_evidence()],
    )

    assert retry_calls == 1
    assert dispatch_calls == []
    assert outcome.refused is True
    assert outcome.refusal_text


def test_model_date_mismatch_uses_server_resolved_date(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []

    outcome = run_forced_cafeteria_call(
        question="오늘 학식",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"전체","dates":["2026-06-17"]}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=lambda name, args: dispatch_calls.append(dict(args)) or [_evidence()],
    )

    assert dispatch_calls == [{"cafeteria": None, "dates": ["2026-06-13"]}]
    assert outcome.refused is False


def test_question_cafeteria_overrides_wrong_model_enum(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []

    def dispatch_fn(name: str, args: dict[str, Any]) -> list[Evidence]:
        dispatch_calls.append(dict(args))
        return [_evidence()]

    # Model wrongly emits 전체, but the question names 3학 -> server uses 제3학생회관.
    outcome = run_forced_cafeteria_call(
        question="오늘 3학 메뉴",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"전체"}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=dispatch_fn,
    )

    assert dispatch_calls == [{"cafeteria": "제3학생회관", "dates": ["2026-06-13"]}]
    assert outcome.refused is False


def test_question_food_court_overrides_wrong_model_daily_enum(config: SimpleNamespace) -> None:
    dispatch_calls: list[dict[str, Any]] = []

    def dispatch_fn(name: str, args: dict[str, Any]) -> list[Evidence]:
        dispatch_calls.append(dict(args))
        return [_evidence()]

    # Model wrongly emits a daily cafeteria, but the question names 1학 (food court).
    outcome = run_forced_cafeteria_call(
        question="내일 1학",
        config=config,
        tool_calls=[_tool_call('{"cafeteria":"제2학생회관"}')],
        call_model=lambda: LlamaResult(content="", tool_calls=[]),
        dispatch_fn=dispatch_fn,
    )

    assert dispatch_calls == []
    assert outcome.use_kb_fallback is True
    assert outcome.called_tools == ["fetch_cafeteria_menu:food_court_skip"]
