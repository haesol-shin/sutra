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
from unittest.mock import patch

import pytest
import requests

from sutra.cli import build_parser, main
from sutra.config import load_config
from sutra.models import Evidence


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

    class Text:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Action:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        async def send(self):
            sent_messages.append(self)
            return self

        async def update(self):
            return self

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
        store=session_store,
        get=lambda key, *args, **kwargs: session_store.get(key),
        set=lambda key, value, *args, **kwargs: session_store.__setitem__(key, value),
    )
    chainlit.sent_messages = sent_messages

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


def _evidence(id_: str, score: float | None) -> Evidence:
    return Evidence(id=id_, title=id_, text=f"{id_} text", score=score)


def _config_language(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("language"):
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

        assert ui.RETRIEVAL_STEP_NAME == "🔍 검색"
        assert ui.LIVE_LOOKUP_STEP_NAME == "🛠️ 실시간 조회"
        assert [action.label for action in ui._feedback_actions(
            config,
            question="question",
            answer="answer",
        )] == ["👍 도움됨", "👎 도움 안 됨", "💬 의견"]

    def test_source_elements_use_korean_labels(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ui = _ui_module(monkeypatch)
        item = Evidence(
            id="source-1",
            title="Academic Calendar",
            text="Semester begins on March 2.",
            source_name="calendar",
            source_url="https://example.edu/calendar",
            metadata={"date": "2026-03-02"},
        )

        [element] = ui._source_elements([item])

        assert element.name == "[1] Academic Calendar"
        assert "출처: calendar" in element.content
        assert "날짜: 2026-03-02" in element.content
        assert "발췌: Semester begins on March 2." in element.content

    def test_source_filter_summary_is_korean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ui = _ui_module(monkeypatch)
        items = [_evidence("top", 10.0), _evidence("hidden", 1.0)]

        summary = ui._source_filter_summary(items, shown_count=1, hidden_count=1)

        assert summary == "문서 2개 (최고 점수 10)\n2개 중 1개 표시(점수 필터)"

    def test_source_action_is_korean_and_stores_filtered_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        items = [_evidence("top", 10.0), _evidence("hidden", 1.0)]

        actions = ui._source_actions(items)

        assert [action.label for action in actions] == ["📚 출처"]
        assert actions[0].name == "sutra_sources"
        source_key = ui._payload_from_action(actions[0])["source_key"]
        stored = ui.cl.user_session.store[source_key]
        assert [item["name"] for item in stored] == ["[1] top"]
        assert "hidden text" not in stored[0]["content"]

    def test_source_action_is_hidden_without_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)

        assert ui._source_actions([]) == []

    def test_on_sources_sends_stored_source_elements(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        [action] = ui._source_actions([_evidence("top", 10.0)])

        asyncio.run(ui.on_sources(action))

        [message] = ui.cl.sent_messages
        assert message.content == "출처"
        assert [element.name for element in message.elements] == ["[1] top"]
        assert "top text" in message.elements[0].content

    def test_replace_source_actions_updates_existing_source_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ui = _ui_module(monkeypatch)
        [source_action] = ui._source_actions([_evidence("stale", 10.0)])
        source_key = ui._payload_from_action(source_action)["source_key"]
        feedback_action = ui.cl.Action(name="sutra_feedback", label="feedback")
        msg = types.SimpleNamespace(actions=[source_action, feedback_action])

        ui._replace_source_actions(msg, [_evidence("fresh", 10.0)])

        source_actions = [
            action for action in msg.actions
            if getattr(action, "name", None) == "sutra_sources"
        ]
        assert source_actions == [source_action]
        assert ui._payload_from_action(source_action)["source_key"] == source_key
        assert sorted(ui.cl.user_session.store) == [source_key]
        assert [item["name"] for item in ui.cl.user_session.store[source_key]] == ["[1] fresh"]

    def test_chainlit_configs_force_english_locale(self) -> None:
        root = Path(__file__).parents[2]

        assert _config_language(
            root / "src" / "sutra" / "resources" / "ui" / "chainlit_config.toml",
        ) == "en-US"


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
