from __future__ import annotations

import asyncio
import importlib.util
import os
import socket
import subprocess
import sys
import time
import types
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import requests

from sutra.cli import build_parser, main
from sutra.config import load_config
from sutra.models import Evidence, EvidencePack, LlamaResult, ToolCall


@pytest.fixture
def ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", 0))
        return s.getsockname()[1]


def _write_workspace(root: Path) -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        '{"id":"test-1","title":"Test","text":"This is a test document."}\n',
        encoding="utf-8",
    )
    (root / "prompts" / "system.md").write_text("You are a grounded assistant.", encoding="utf-8")
    config_path = root / "sutra.toml"
    config_path.write_text(
        (
            '[workspace]\n'
            'name = "fixture"\n'
            '\n'
            '[runtime]\n'
            'model = "fake-qwen"\n'
            '\n'
            '[rag]\n'
            'index_path = "data/index.jsonl"\n'
            '\n'
            '[prompts]\n'
            'system = "prompts/system.md"\n'
        ),
        encoding="utf-8",
    )
    return config_path


def _ui_module(monkeypatch: pytest.MonkeyPatch):
    chainlit = types.SimpleNamespace()
    session_store = {}
    sent_messages = []
    steps = []

    class Text:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Action:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.actions = getattr(self, "actions", [])
            self.elements = getattr(self, "elements", [])
            self.update_count = 0

        async def send(self):
            sent_messages.append(self)
            return self

        async def update(self):
            self.update_count += 1
            return self

        async def stream_token(self, token):
            self.content = getattr(self, "content", "") + token

    class AskUserMessage(Message):
        pass

    class Step:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        async def __aenter__(self):
            steps.append(self)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def decorator(*args, **kwargs):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def wrap(func):
            return func
        return wrap

    def make_async(func):
        async def wrapped(*args, **kwargs):
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result

        return wrapped

    chainlit.Text = Text
    chainlit.Action = Action
    chainlit.Message = Message
    chainlit.AskUserMessage = AskUserMessage
    chainlit.action_callback = decorator
    chainlit.on_chat_start = decorator
    chainlit.on_message = decorator
    chainlit.make_async = make_async
    chainlit.Step = Step
    chainlit.user_session = types.SimpleNamespace(
        store=session_store,
        get=lambda key, *args, **kwargs: session_store.get(key),
        set=lambda key, value, *args, **kwargs: session_store.__setitem__(key, value),
    )
    chainlit.sent_messages = sent_messages
    chainlit.steps = steps

    monkeypatch.setitem(sys.modules, "chainlit", chainlit)
    sys.modules.pop("sutra.ui", None)
    import sutra.ui as ui
    return ui


def test_ui_loads_when_exec_module_does_not_register_module(monkeypatch: pytest.MonkeyPatch) -> None:
    chainlit = types.SimpleNamespace()

    class Text:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Action:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class AskUserMessage(Message):
        pass

    def decorator(*args, **kwargs):
        def wrap(func):
            return func
        return wrap

    chainlit.Text = Text
    chainlit.Action = Action
    chainlit.Message = Message
    chainlit.AskUserMessage = AskUserMessage
    chainlit.action_callback = decorator
    chainlit.on_chat_start = decorator
    chainlit.on_message = decorator
    chainlit.make_async = lambda func: func
    chainlit.Step = object
    chainlit.user_session = types.SimpleNamespace(
        get=lambda *args, **kwargs: None,
        set=lambda *args, **kwargs: None,
    )

    monkeypatch.setitem(sys.modules, "chainlit", chainlit)
    module_name = "sutra_ui_chainlit_loader_probe"
    sys.modules.pop(module_name, None)
    ui_path = Path(__file__).parents[2] / "src" / "sutra" / "ui.py"
    spec = importlib.util.spec_from_file_location(module_name, ui_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


class FrozenMenuResolverDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        value = cls(2026, 6, 13, 9, 0, 0)
        if tz is None:
            return value
        return value.replace(tzinfo=ZoneInfo("Asia/Seoul")).astimezone(tz)

def _evidence(id_: str, score: float | None) -> Evidence:
    return Evidence(id=id_, title=id_, text=f"{id_} text", score=score)


def _config_language(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("language"):
            return stripped.split("=", 1)[1].strip().strip('"')
    return None


def _config_name(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name"):
            return stripped.split("=", 1)[1].strip().strip('"')
    return None


class TestInterfaceLabels:
    def test_ui_labels_are_english(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))

        assert ui.RETRIEVAL_STEP_NAME == "🧠 Knowledge Base"
        assert ui.LIVE_LOOKUP_STEP_NAME == "🔍 Web Search"
        assert [action.label for action in ui._feedback_actions(
            config,
            question="question",
            answer="answer",
        )] == ["👍 Helpful", "👎 Not helpful"]

    def test_source_elements_split_knowledge_base_and_web_search_groups(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        kb_item = Evidence(
            id="source-1",
            title="Academic Calendar",
            text="Semester begins on March 2.",
            source_name="calendar",
            source_url="https://example.edu/calendar",
            metadata={"date": "2026-03-02"},
        )
        web_item = Evidence(
            id="live-1",
            title="Notice",
            text="Scholarship notice.",
            source_name="recent notices",
        )

        elements = ui._source_elements([kb_item], [web_item])

        assert [element.name for element in elements] == [
            "Knowledge Base",
            "[Knowledge Base 1] Academic Calendar",
            "Web Search",
            "[Web Search 1] Notice",
        ]
        assert "Source: calendar" in elements[1].content
        assert "Date: 2026-03-02" in elements[1].content
        assert "Excerpt: Semester begins on March 2." in elements[1].content
        assert "Source: recent notices" in elements[3].content

    def test_source_filter_summary_is_english(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ui = _ui_module(monkeypatch)
        items = [_evidence("top", 10.0), _evidence("hidden", 1.0)]

        summary = ui._source_filter_summary(items, shown_count=1, hidden_count=1)

        assert summary == "2 documents (best score 10)\nshowing 1 of 2 (score filter)"

    def test_source_action_is_english_and_stores_filtered_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        items = [_evidence("top", 10.0), _evidence("hidden", 1.0)]

        actions = ui._source_actions(items, [_evidence("live", None)])

        assert [action.label for action in actions] == ["📚 Sources"]
        assert actions[0].name == "sutra_sources"
        source_key = ui._payload_from_action(actions[0])["source_key"]
        stored = ui.cl.user_session.store[source_key]
        assert [item["name"] for item in stored] == [
            "Knowledge Base",
            "[Knowledge Base 1] top",
            "Web Search",
            "[Web Search 1] live",
        ]
        assert "hidden text" not in stored[0]["content"]

    def test_source_action_is_hidden_without_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)

        assert ui._source_actions([], []) == []

    def test_on_sources_sends_stored_source_elements(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        [action] = ui._source_actions([_evidence("top", 10.0)])

        asyncio.run(ui.on_sources(action))

        [message] = ui.cl.sent_messages
        assert message.content == "Sources"
        assert [element.name for element in message.elements] == [
            "Knowledge Base",
            "[Knowledge Base 1] top",
        ]
        assert "top text" in message.elements[1].content

    def test_replace_source_actions_updates_existing_source_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        [source_action] = ui._source_actions([_evidence("stale", 10.0)])
        source_key = ui._payload_from_action(source_action)["source_key"]
        feedback_action = ui.cl.Action(name="sutra_feedback", label="feedback")
        msg = types.SimpleNamespace(actions=[source_action, feedback_action])

        ui._replace_source_actions(msg, [_evidence("fresh", 10.0)], [_evidence("live", None)])

        source_actions = [
            action for action in msg.actions
            if getattr(action, "name", None) == "sutra_sources"
        ]
        assert source_actions == [source_action]
        assert ui._payload_from_action(source_action)["source_key"] == source_key
        assert sorted(ui.cl.user_session.store) == [source_key]
        assert [item["name"] for item in ui.cl.user_session.store[source_key]] == [
            "Knowledge Base",
            "[Knowledge Base 1] fresh",
            "Web Search",
            "[Web Search 1] live",
        ]

    def test_chainlit_configs_force_english_locale(self) -> None:
        root = Path(__file__).parents[2]

        assert _config_language(
            root / "src" / "sutra" / "resources" / "ui" / "chainlit_config.toml",
        ) == "en-US"

    def test_chainlit_configs_use_temporary_sutra_icon_branding(self) -> None:
        root = Path(__file__).parents[2]

        assert _config_name(
            root / "src" / "sutra" / "resources" / "ui" / "chainlit_config.toml",
        ) == "Sutra"

    def test_chainlit_config_references_packaged_brand_css(self) -> None:
        root = Path(__file__).parents[2]
        config = (
            root / "src" / "sutra" / "resources" / "ui" / "chainlit_config.toml"
        ).read_text(encoding="utf-8")

        assert 'custom_css = "/public/sutra-brand.css"' in config

    def test_packaged_chainlit_public_brand_assets_exist(self) -> None:
        root = Path(__file__).parents[2]
        public = root / "src" / "sutra" / "resources" / "ui" / "public"

        assert (public / "logo_light.svg").exists()
        assert (public / "logo_dark.svg").exists()
        assert (public / "favicon.svg").exists()
        assert (public / "sutra-sparkle.svg").exists()
        assert (public / "sutra-brand.css").exists()

    def test_packaged_chainlit_welcome_readme_is_empty(self) -> None:
        root = Path(__file__).parents[2]

        assert (
            root / "src" / "sutra" / "resources" / "ui" / "chainlit.md"
        ).read_text(encoding="utf-8") == ""


class TestAnswerLocalization:
    def test_chat_start_falls_back_to_default_workspace(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        monkeypatch.delenv("SUTRA_WORKSPACE", raising=False)

        asyncio.run(ui.on_chat_start())

        workspace = ui.cl.user_session.store["workspace"]
        assert workspace == (
            Path(__file__).parents[2] / "examples" / "cnu-campus" / "sutra.toml"
        ).resolve()
        assert ui.cl.sent_messages == []

    def test_chat_start_reports_missing_workspace_in_korean(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        monkeypatch.delenv("SUTRA_WORKSPACE", raising=False)
        monkeypatch.setattr(
            ui,
            "_default_workspace_path",
            lambda: tmp_path / "missing" / "sutra.toml",
            raising=False,
        )

        asyncio.run(ui.on_chat_start())

        assert ui.cl.user_session.store["workspace"] is None
        [message] = ui.cl.sent_messages
        assert message.content.startswith("**오류**:")
        assert "SUTRA_WORKSPACE" in message.content

    def test_on_message_reports_config_errors_in_korean(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        ui.cl.user_session.set("workspace", tmp_path / "missing.toml")
        ui.cl.user_session.set("client", None)

        asyncio.run(ui.on_message(ui.cl.Message(content="test")))

        [message] = ui.cl.sent_messages
        assert message.content.startswith("**오류**:")
        assert "workspace config not found" in message.content

    def test_insufficient_evidence_answer_is_korean(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", None)
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config: EvidencePack(question=question, items=[]),
        )

        asyncio.run(ui.on_message(ui.cl.Message(content="test")))

        [message] = ui.cl.sent_messages
        assert message.content == "제공된 자료에서 확인할 수 있는 근거를 찾지 못했습니다."
        assert "I do not have enough evidence" not in message.content
        assert [action.label for action in message.actions] == [
            "👍 Helpful",
            "👎 Not helpful",
        ]

    def test_comment_feedback_rating_is_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        [action] = [
            ui.cl.Action(name="sutra_feedback", payload={
                "trace_path": str(tmp_path / "trace.jsonl"),
                "question": "q",
                "answer": "a",
                "rating": "comment",
            }),
        ]

        asyncio.run(ui.on_feedback(action))

        [message] = ui.cl.sent_messages
        assert message.content == "Could not record feedback."
        assert not (tmp_path / "trace.jsonl").exists()

    def test_feedback_click_keeps_buttons_and_records_status_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        actions = ui._feedback_actions(config, question="q", answer="a")
        removed = []

        async def remove():
            removed.append(True)

        actions[0].remove = remove

        asyncio.run(ui.on_feedback(actions[0]))

        assert removed == []
        # Recording feedback no longer spawns a chat message; the buttons stay fixed.
        assert ui.cl.sent_messages == []

        trace_path = tmp_path / "logs" / "chat_trace.jsonl"
        rows = trace_path.read_text(encoding="utf-8").splitlines()
        assert '"rating":"helpful"' in rows[-1]

    def test_feedback_click_toggles_status_message_in_place(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        helpful, unhelpful = ui._feedback_actions(config, question="q", answer="a")

        asyncio.run(ui.on_feedback(helpful))
        asyncio.run(ui.on_feedback(unhelpful))

        # Toggling feedback records both ratings without spawning any chat message.
        assert ui.cl.sent_messages == []

        trace_path = tmp_path / "logs" / "chat_trace.jsonl"
        rows = trace_path.read_text(encoding="utf-8").splitlines()
        assert '"rating":"helpful"' in rows[-2]
        assert '"rating":"unhelpful"' in rows[-1]

    def test_tool_no_result_suffix_is_korean(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))

        class ToolNoResultClient:
            def __init__(self) -> None:
                self.calls = 0

            def chat(self, messages, *, model, temperature, max_tokens, tools=None, tool_choice=None):
                self.calls += 1
                if tool_choice is not None:
                    return LlamaResult(
                        content="",
                        model=model,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                function_name="fetch_recent_notices",
                                function_arguments='{"keyword":"장학"}',
                            ),
                        ],
                    )
                return LlamaResult(content="저장된 자료를 기준으로 답변합니다.", model=model)

        client = ToolNoResultClient()
        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", client)
        monkeypatch.setattr(
            ui,
            "route_question",
            lambda question, config: ("notices", "fetch_recent_notices", 1),
        )
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config, **kwargs: EvidencePack(
                question=question,
                items=[_evidence("stored", 1.0)],
            ),
        )
        monkeypatch.setattr(ui, "dispatch", lambda name, arguments: [])

        asyncio.run(ui.on_message(ui.cl.Message(content="test")))

        [message] = ui.cl.sent_messages
        assert client.calls == 2
        assert (
            "(실시간 정보를 가져오지 못해 저장된 자료를 기준으로 답변했습니다.)"
            in message.content
        )
        assert "Unable to fetch live data" not in message.content


class TestRouterUiFlow:
    def test_on_message_uses_router_rag_path_without_web_search_step(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))

        class RagClient:
            def __init__(self) -> None:
                self.calls = []

            def chat(self, messages, *, model, temperature, max_tokens, tools=None, tool_choice=None):
                self.calls.append({
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "max_tokens": max_tokens,
                })
                return LlamaResult(content="rag answer", model=model)

        client = RagClient()
        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", client)
        monkeypatch.setattr(
            ui,
            "route_question",
            lambda question, config: ("academic_calendar", None, 2),
        )
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config: EvidencePack(
                question=question,
                items=[_evidence("stored", 1.0)],
            ),
        )

        asyncio.run(ui.on_message(ui.cl.Message(content="semester dates?")))

        assert [step.name for step in ui.cl.steps] == ["🧠 Knowledge Base"]
        [message] = ui.cl.sent_messages
        assert message.content == "rag answer\n\n📚 Sources"
        assert [element.name for element in message.elements] == ["📚 Sources"]
        assert client.calls == [{
            "tools": None,
            "tool_choice": None,
            "max_tokens": config.runtime.max_tokens,
        }]

    def test_on_message_forces_router_tool_and_splits_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        rag_item = _evidence("stored", 1.0)
        live_item = Evidence(
            id="live",
            title="Live Notice",
            text="Live notice text",
            source_name="recent notices",
        )

        class ForcedToolClient:
            def __init__(self) -> None:
                self.calls = []

            def chat(self, messages, *, model, temperature, max_tokens, tools=None, tool_choice=None):
                self.calls.append({
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "max_tokens": max_tokens,
                })
                if tool_choice is not None:
                    return LlamaResult(
                        content="",
                        model=model,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                function_name="fetch_recent_notices",
                                function_arguments='{"keyword":"장학"}',
                            ),
                        ],
                    )
                return LlamaResult(content="fresh answer", model=model)

        client = ForcedToolClient()
        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", client)
        monkeypatch.setattr(
            ui,
            "route_question",
            lambda question, config: ("notices", "fetch_recent_notices", 1),
        )
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config: EvidencePack(
                question=question,
                items=[rag_item],
            ),
        )
        monkeypatch.setattr(ui, "dispatch", lambda name, arguments: [live_item])

        asyncio.run(ui.on_message(ui.cl.Message(content="장학 공지 알려줘")))

        assert [step.name for step in ui.cl.steps] == [
            "🧠 Knowledge Base",
            "🔍 Web Search",
        ]
        assert ui.cl.steps[1].input == "fetch_recent_notices(keyword=장학)"
        assert ui.cl.steps[1].output == "fetch_recent_notices(keyword=장학) → 1 result"
        assert client.calls[0]["tool_choice"] == {
            "type": "function",
            "function": {"name": "fetch_recent_notices"},
        }
        assert client.calls[0]["max_tokens"] == min(config.runtime.max_tokens, 256)
        [message] = ui.cl.sent_messages
        assert message.content == "fresh answer\n\n📚 Sources"
        assert "Live notice text" in client.calls[1]["messages"][-1].content
        assert "stored text" not in client.calls[1]["messages"][-1].content
        # Fresh-only forced-tool answer: sources are a single side element with the
        # Web Search group only (stale Knowledge Base corpus excluded).
        assert [element.name for element in message.elements] == ["📚 Sources"]
        sources_content = message.elements[0].content
        assert "Web Search" in sources_content
        assert "[1] Live Notice" in sources_content
        assert "Knowledge Base" not in sources_content
        assert [action.label for action in message.actions] == [
            "👍 Helpful",
            "👎 Not helpful",
        ]


    def test_on_message_forced_dining_corrects_dates_and_question_cafeteria(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        live_item = Evidence(
            id="live_cafeteria_menu",
            title="충남대학교 식단",
            text="제2학생회관 2026-06-16 메뉴",
            source_name="충남대학교 식단",
        )

        class DiningClient:
            def __init__(self) -> None:
                self.calls = []

            def chat(self, messages, *, model, temperature, max_tokens, tools=None, tool_choice=None):
                self.calls.append({"messages": messages, "tool_choice": tool_choice, "max_tokens": max_tokens})
                if tool_choice is not None:
                    return LlamaResult(
                        content="",
                        model=model,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                function_name="fetch_cafeteria_menu",
                                function_arguments='{"date":"2026-06-13"}',
                            )
                        ],
                    )
                return LlamaResult(content="2학 answer", model=model)

        dispatch_calls: list[tuple[str, dict[str, object]]] = []
        client = DiningClient()
        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", client)
        monkeypatch.setattr(ui, "route_question", lambda question, config: ("dining", "fetch_cafeteria_menu", 3))
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config, **kwargs: EvidencePack(question=question, items=[]),
        )

        def fake_dispatch(name: str, arguments: dict[str, object]) -> list[Evidence]:
            dispatch_calls.append((name, dict(arguments)))
            return [live_item]

        monkeypatch.setattr(ui, "dispatch", fake_dispatch)
        monkeypatch.setattr("sutra.menu_resolver.datetime", FrozenMenuResolverDateTime)

        asyncio.run(ui.on_message(ui.cl.Message(content="다음주 화요일 2학 메뉴")))

        assert dispatch_calls == [
            (
                "fetch_cafeteria_menu",
                {"cafeteria": "제2학생회관", "dates": ["2026-06-16"]},
            )
        ]
        [message] = ui.cl.sent_messages
        assert message.content == "2학 answer\n\n📚 Sources"
        assert "제2학생회관" in ui.cl.steps[1].output
        assert "2026-06-16" in ui.cl.steps[1].output

    def test_on_message_forced_dining_food_court_uses_fallback_docs(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        food_court_item = Evidence(
            id="dining_food_court_제1학생회관_중식",
            title="제1학생회관 중식",
            text="제1학생회관 푸드코트 중식 메뉴",
            source_name="충남대학교 제1학생회관 푸드코트",
            score=1.0,
        )

        class FoodCourtClient:
            def __init__(self) -> None:
                self.calls = []

            def chat(self, messages, *, model, temperature, max_tokens, tools=None, tool_choice=None):
                self.calls.append({"messages": messages, "tool_choice": tool_choice})
                if tool_choice is not None:
                    return LlamaResult(
                        content="",
                        model=model,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                function_name="fetch_cafeteria_menu",
                                function_arguments='{"cafeteria":"제1학생회관"}',
                            )
                        ],
                    )
                return LlamaResult(content="푸드코트 answer", model=model)

        retrieve_calls: list[dict[str, object]] = []
        dispatch_calls: list[tuple[str, object]] = []
        client = FoodCourtClient()
        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", client)
        monkeypatch.setattr(ui, "route_question", lambda question, config: ("dining", "fetch_cafeteria_menu", 3))

        def fake_retrieve(question, documents, config, **kwargs):  # noqa: ANN001
            retrieve_calls.append(dict(kwargs))
            if kwargs.get("exclude_domains") == set():
                return EvidencePack(question=question, items=[food_court_item])
            return EvidencePack(question=question, items=[])

        monkeypatch.setattr(ui, "retrieve", fake_retrieve)
        monkeypatch.setattr(ui, "dispatch", lambda name, arguments: dispatch_calls.append((name, arguments)) or [])

        asyncio.run(ui.on_message(ui.cl.Message(content="1학 메뉴 뭐야")))

        assert dispatch_calls == []
        assert retrieve_calls == [{}, {"exclude_domains": set()}]
        assert ui.cl.steps[1].output == "fetch_cafeteria_menu() → food-court knowledge-base fallback"
        [message] = ui.cl.sent_messages
        assert message.content == (
            "푸드코트 answer\n\n"
            "(실시간 정보를 가져오지 못해 저장된 자료를 기준으로 답변했습니다.)\n\n"
            "📚 Sources"
        )
        assert "제1학생회관 푸드코트 중식 메뉴" in client.calls[1]["messages"][-1].content
        assert [element.name for element in message.elements] == ["📚 Sources"]

    def test_on_message_attaches_sources_and_feedback_after_streaming_finishes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))
        observed_actions_during_stream: list[list[str]] = []

        class StreamingClient:
            def stream_chat(self, messages, *, model, temperature, max_tokens, tools=None):
                final_msg = ui.cl.sent_messages[-1]
                observed_actions_during_stream.append([
                    getattr(action, "label", "") for action in final_msg.actions
                ])
                yield "streamed"
                yield " answer"

        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", StreamingClient())
        monkeypatch.setattr(
            ui,
            "route_question",
            lambda question, config: ("academic_calendar", None, 2),
        )
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config: EvidencePack(
                question=question,
                items=[_evidence("stored", 1.0)],
            ),
        )

        asyncio.run(ui.on_message(ui.cl.Message(content="semester dates?")))

        assert observed_actions_during_stream == [[]]
        [message] = ui.cl.sent_messages
        assert message.content == "streamed answer\n\n📚 Sources"
        # Sources are a fixed side element (click-to-open); only feedback are actions.
        assert [element.name for element in message.elements] == ["📚 Sources"]
        assert [action.label for action in message.actions] == [
            "👍 Helpful",
            "👎 Not helpful",
        ]

    def test_on_message_forced_tool_empty_rag_uses_router_failure_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ui = _ui_module(monkeypatch)
        config = load_config(_write_workspace(tmp_path))

        class EmptyToolClient:
            def chat(self, messages, *, model, temperature, max_tokens, tools=None, tool_choice=None):
                return LlamaResult(
                    content="",
                    model=model,
                    tool_calls=[
                        ToolCall(
                            id="call-1",
                            function_name="fetch_cafeteria_menu",
                            function_arguments='{"date":"2026-06-12"}',
                        ),
                    ],
                )

        ui.cl.user_session.set("workspace", config)
        ui.cl.user_session.set("client", EmptyToolClient())
        monkeypatch.setattr(
            ui,
            "route_question",
            lambda question, config: ("dining", "fetch_cafeteria_menu", 3),
        )
        monkeypatch.setattr(
            ui,
            "retrieve",
            lambda question, documents, config, **kwargs: EvidencePack(question=question, items=[]),
        )
        monkeypatch.setattr(ui, "dispatch", lambda name, arguments: [])

        asyncio.run(ui.on_message(ui.cl.Message(content="오늘 학식 뭐야?")))

        [message] = ui.cl.sent_messages
        assert message.content == (
            "실시간 조회에 실패했고 저장된 자료에서도 관련 정보를 찾지 못했습니다. "
            "충남대학교 공식 홈페이지를 확인해 주세요."
        )
        assert [action.label for action in message.actions] == [
            "👍 Helpful",
            "👎 Not helpful",
        ]


class TestSourceScoreFilter:
    def test_source_filter_uses_relative_ratio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ui = _ui_module(monkeypatch)
        items = [
            _evidence("top", 3.7),
            _evidence("below", 1.3),
            _evidence("low-a", 1.1),
            _evidence("low-b", 1.0),
        ]

        filtered, hidden = ui._filter_source_evidence(items, rel_ratio=0.4, abs_floor=0.0)

        assert [item.id for item in filtered] == ["top"]
        assert hidden == 3

    def test_source_filter_keeps_top_item_if_all_scores_are_filtered(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        items = [
            _evidence("top", 3.7),
            _evidence("second", 1.3),
        ]

        filtered, hidden = ui._filter_source_evidence(items, rel_ratio=0.4, abs_floor=4.0)

        assert [item.id for item in filtered] == ["top"]
        assert hidden == 1

    def test_source_filter_keeps_items_without_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ui = _ui_module(monkeypatch)
        items = [
            _evidence("top", 3.7),
            _evidence("unknown", None),
            _evidence("below", 1.3),
        ]

        filtered, hidden = ui._filter_source_evidence(items, rel_ratio=0.4, abs_floor=0.0)

        assert [item.id for item in filtered] == ["top", "unknown"]
        assert hidden == 1

    def test_source_filter_preserves_zero_score_top_item(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        items = [
            _evidence("zero", 0.0),
            _evidence("negative", -1.0),
        ]

        filtered, hidden = ui._filter_source_evidence(items, rel_ratio=0.4, abs_floor=1.0)

        assert [item.id for item in filtered] == ["zero"]
        assert hidden == 1


class TestArgParse:
    def test_ui_parse_all_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "ui", "--workspace", "/fake/ws", "--echo",
            "--host", "0.0.0.0", "--port", "9000",
        ])
        assert args.command == "ui"
        assert args.workspace == "/fake/ws"
        assert args.echo is True
        assert args.host == "0.0.0.0"
        assert args.port == 9000

    def test_ui_parse_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["ui"])
        assert args.command == "ui"
        assert args.workspace is None
        assert args.echo is False
        assert args.host == "127.0.0.1"
        assert args.port == 8000

    def test_ui_echo_flag_off_by_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["ui"])
        assert args.echo is False


class TestDependencyCheck:
    def test_ui_reports_missing_chainlit(self, tmp_path: Path) -> None:
        workspace = _write_workspace(tmp_path)

        with patch("importlib.util.find_spec", return_value=None):
            result = main(["ui", "--workspace", str(workspace), "--echo", "--port", "8999"])

        assert result == 1

    def test_ui_proceeds_when_chainlit_installed(self, tmp_path: Path) -> None:
        workspace = _write_workspace(tmp_path)

        with (
            patch("importlib.util.find_spec", return_value=True),
            patch("subprocess.Popen") as mock_popen,
        ):
            mock_proc = mock_popen.return_value
            mock_proc.wait.return_value = 0
            mock_proc.returncode = 0
            result = main(["ui", "--workspace", str(workspace), "--echo", "--port", "8999"])

        assert result == 0


@pytest.mark.skipif(importlib.util.find_spec("chainlit") is None, reason="requires chainlit (ui extra)")
@pytest.mark.integration
def test_ui_echo_server_starts_and_responds(tmp_path: Path, ephemeral_port: int) -> None:
    workspace = _write_workspace(tmp_path)
    port = ephemeral_port
    host = "127.0.0.1"

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0

    proc = subprocess.Popen(
        [sys.executable, "-m", "sutra.cli", "ui",
         "--workspace", str(workspace), "--echo", "--port", str(port)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        deadline = time.time() + 25
        server_ok = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                resp = requests.get(f"http://{host}:{port}/", timeout=2)
                if resp.status_code < 500:
                    server_ok = True
                    break
            except (requests.ConnectionError, requests.Timeout):
                time.sleep(1)

        assert server_ok, (
            f"Chainlit server did not start within 25s "
            f"(proc exited with code {proc.poll()})"
        )
    finally:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
