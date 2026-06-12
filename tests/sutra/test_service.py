from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sutra import ask, chat
from sutra.config import load_config
from sutra.errors import ConfigError
from sutra.llama import EchoClient
from sutra.models import Evidence, LlamaResult, Message, ToolCall
from sutra.service import _predict_router_label, _resolve_classifier_model_path


class FakeClient:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlamaResult:
        self.messages = messages
        assert model == "fake-qwen"
        assert temperature == 0.1
        assert max_tokens == 128
        return LlamaResult(content="수강신청은 2월 1일에 시작합니다.", model=model, usage={"total_tokens": 12})


def test_ask_retrieves_evidence_and_calls_client(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = FakeClient()

    answer = ask("수강신청 언제 시작해?", workspace=workspace, client=client)

    assert answer.answer == "수강신청은 2월 1일에 시작합니다."
    assert answer.workspace == "fixture"
    assert answer.model == "fake-qwen"
    assert answer.backend == "llama-server"
    assert answer.evidence[0].id == "calendar-1"
    assert answer.trace["status"] == "answered"
    assert "수강신청은 2월 1일에 시작합니다." in client.messages[-1].content


def test_ask_replaces_internal_ids_in_returned_answer(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, include_notices=True)

    class LeakyClient(FakeClient):
        def chat(
            self,
            messages: list[Message],
            *,
            model: str | None = None,
            temperature: float = 0.2,
            max_tokens: int = 512,
            tools: list[dict[str, Any]] | None = None,
        ) -> LlamaResult:
            self.messages = messages
            return LlamaResult(
                content="univ_academic와 cs_dept, shuttle, course_registration_guide를 확인하세요.",
                model=model,
            )

    answer = ask("최신 공지 알려줘", workspace=workspace, client=LeakyClient())

    assert answer.answer == "학교 학사공지와 학부 학사공지, 셔틀버스 안내, 수강신청 안내를 확인하세요."


def test_ask_can_append_batch_trace_without_changing_answer(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    trace_path = tmp_path / "logs" / "chat_trace.jsonl"

    answer = ask(
        "수강신청 언제 시작해?",
        workspace=workspace,
        client=FakeClient(),
        trace_source="batch",
        trace_path=trace_path,
    )

    row = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert answer.answer == "수강신청은 2월 1일에 시작합니다."
    assert row["source"] == "batch"
    assert row["question"] == "수강신청 언제 시작해?"
    assert row["answer"] == answer.answer
    assert row["doc_ids"] == ["calendar-1"]
    assert row["doc_scores"] == [3.0]
    assert row["mode"] == "llm"
    assert row["error"] is None


def test_chat_adapts_openai_style_messages_to_ask(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = FakeClient()

    answer = chat(
        [
            {"role": "system", "content": "ignore"},
            {"role": "user", "content": "수강신청 언제 시작해?"},
        ],
        workspace=workspace,
        client=client,
    )

    assert answer.trace["status"] == "answered"


def test_chat_rejects_missing_user_message(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)

    with pytest.raises(ValueError, match="at least one user"):
        chat([{"role": "assistant", "content": "hello"}], workspace=workspace, client=FakeClient())


def test_ask_returns_insufficient_evidence_without_calling_client(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = FakeClient()

    answer = ask("도서관 운영 시간", workspace=workspace, client=client)

    assert answer.answer == "관련 정보를 확인할 수 있는 자료를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요."
    assert answer.trace == {"status": "insufficient_evidence", "retrieved": 0}
    assert client.messages == []


class ToolOnlyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Message], list[dict[str, Any]] | None]] = []

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlamaResult:
        self.calls.append((messages, tools))
        if len(self.calls) == 1:
            return LlamaResult(
                content="",
                model=model,
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function_name="search_knowledge_base",
                        function_arguments='{"query":"수강신청","domain":"calendar"}',
                    )
                ],
            )
        return LlamaResult(content="수강신청은 2월 1일에 시작합니다.", model=model)


class ToolOnlyEmptySearchClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Message], list[dict[str, Any]] | None]] = []

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlamaResult:
        self.calls.append((messages, tools))
        if len(self.calls) == 1:
            return LlamaResult(
                content="",
                model=model,
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function_name="search_knowledge_base",
                        function_arguments='{"query":"졸업요건","domain":"graduation"}',
                    )
                ],
            )
        return LlamaResult(content="제공된 자료에서 확인할 수 있는 근거를 찾지 못했습니다.", model=model)


class ToolOnlyEmptyAnswerClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Message], list[dict[str, Any]] | None]] = []

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlamaResult:
        self.calls.append((messages, tools))
        if len(self.calls) == 1:
            return LlamaResult(
                content="",
                model=model,
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function_name="search_knowledge_base",
                        function_arguments='{"query":"수강신청","domain":"calendar"}',
                    )
                ],
            )
        return LlamaResult(content="", model=model)


def test_ask_tool_only_starts_without_preloaded_evidence_and_uses_tool_results(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = ToolOnlyClient()

    answer = ask("수강신청 언제 시작해?", workspace=workspace, client=client, mode="tool_only")

    first_messages, first_tools = client.calls[0]
    assert first_tools
    assert {item["function"]["name"] for item in first_tools} >= {"search_knowledge_base"}
    assert "Evidence:" not in first_messages[-1].content
    assert "수강신청은 2월 1일에 시작합니다." not in first_messages[-1].content

    second_messages, second_tools = client.calls[1]
    assert second_tools is None
    assert "Evidence:" in second_messages[-1].content
    assert "수강신청은 2월 1일에 시작합니다." in second_messages[-1].content
    assert answer.evidence[0].id == "calendar-1"
    assert answer.trace["tools_called"] == ["search_knowledge_base"]


def test_ask_tool_only_follows_up_and_traces_empty_knowledge_base_results(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = ToolOnlyEmptySearchClient()

    answer = ask("졸업요건 알려줘", workspace=workspace, client=client, mode="tool_only")

    assert len(client.calls) == 2
    second_messages, second_tools = client.calls[1]
    assert second_tools is None
    assert "No evidence was retrieved from the workspace." in second_messages[-1].content
    assert answer.answer
    assert answer.evidence == []
    assert answer.trace["retrieved"] == 0
    assert answer.trace["tools_called"] == ["search_knowledge_base"]


def test_ask_tool_only_uses_korean_message_for_empty_final_answer(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    client = ToolOnlyEmptyAnswerClient()

    answer = ask("수강신청 언제 시작해?", workspace=workspace, client=client, mode="tool_only")

    assert answer.answer == "관련 정보를 확인할 수 있는 자료를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요."
    assert answer.evidence[0].id == "calendar-1"


class RouterClient:
    def __init__(self, first_result: LlamaResult, second_result: LlamaResult | None = None) -> None:
        self.first_result = first_result
        self.second_result = second_result or LlamaResult(content="최종 답변", model="fake-qwen")
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> LlamaResult:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        return self.first_result if len(self.calls) == 1 else self.second_result


def test_ask_router_forces_cafeteria_tool_choice_and_uses_live_evidence_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_dining=True, runtime_max_tokens=512)
    client = RouterClient(
        LlamaResult(
            content="",
            model="fake-qwen",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    function_name="fetch_cafeteria_menu",
                    function_arguments='{"date":"2026-06-11","cafeteria":"제2학생회관"}',
                )
            ],
        ),
        LlamaResult(content="실시간 식단 근거로 답합니다.", model="fake-qwen"),
    )
    live_evidence = Evidence(
        id="live_cafeteria_menu",
        title="충남대학교 식단",
        text="제2학생회관 점심: 칠리치킨까스",
        source_name="충남대학교 식단",
    )
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 3)
    monkeypatch.setattr("sutra.service.dispatch", lambda name, args: [live_evidence])

    answer = ask("오늘 제2학생회관 점심 뭐야?", workspace=workspace, client=client, mode="router")

    assert client.calls[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "fetch_cafeteria_menu"},
    }
    assert client.calls[0]["max_tokens"] == 256
    assert "Current Time:" in client.calls[0]["messages"][-1].content
    assert "Evidence:" not in client.calls[0]["messages"][-1].content
    assert "학생회관 점심 메뉴입니다." not in client.calls[0]["messages"][-1].content
    assert "search_knowledge_base" not in client.calls[0]["messages"][0].content
    assert {tool["function"]["name"] for tool in client.calls[0]["tools"]} >= {"fetch_cafeteria_menu"}
    assert client.calls[1]["tools"] is None
    assert client.calls[1]["tool_choice"] is None
    assert "Evidence:" in client.calls[1]["messages"][-1].content
    assert "제2학생회관 점심: 칠리치킨까스" in client.calls[1]["messages"][-1].content
    assert "학생회관 점심 메뉴입니다." not in client.calls[1]["messages"][-1].content
    assert answer.answer == "실시간 식단 근거로 답합니다."
    assert [item.id for item in answer.evidence] == ["live_cafeteria_menu"]
    assert answer.trace["doc_ids"] == ["live_cafeteria_menu"]
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["forced_tool"] == "fetch_cafeteria_menu"
    assert answer.trace["tools_called"] == ["fetch_cafeteria_menu"]


def test_ask_router_runs_forced_cafeteria_tool_when_rag_has_no_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path)
    client = RouterClient(
        LlamaResult(
            content="",
            model="fake-qwen",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    function_name="fetch_cafeteria_menu",
                    function_arguments='{"date":"2026-06-11","cafeteria":"제2학생회관"}',
                )
            ],
        ),
        LlamaResult(content="실시간 식단 근거로 답합니다.", model="fake-qwen"),
    )
    live_evidence = Evidence(
        id="live_cafeteria_menu",
        title="충남대학교 식단",
        text="제2학생회관 점심: 칠리치킨까스",
        source_name="충남대학교 식단",
    )
    dispatch_calls: list[tuple[str, str]] = []

    def fake_dispatch(name: str, args: str) -> list[Evidence]:
        dispatch_calls.append((name, args))
        return [live_evidence]

    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 3)
    monkeypatch.setattr("sutra.service.dispatch", fake_dispatch)

    answer = ask("오늘 제2학생회관 점심 뭐야?", workspace=workspace, client=client, mode="router")

    assert len(client.calls) == 2
    assert client.calls[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "fetch_cafeteria_menu"},
    }
    assert dispatch_calls == [
        ("fetch_cafeteria_menu", '{"date":"2026-06-11","cafeteria":"제2학생회관"}')
    ]
    assert answer.answer == "실시간 식단 근거로 답합니다."
    assert answer.evidence == [live_evidence]
    assert answer.trace["retrieved"] == 1
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["forced_tool"] == "fetch_cafeteria_menu"
    assert answer.trace["tools_called"] == ["fetch_cafeteria_menu"]


def test_ask_router_reports_empty_live_and_empty_rag_for_forced_tool_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path)
    client = RouterClient(
        LlamaResult(
            content="",
            model="fake-qwen",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    function_name="fetch_cafeteria_menu",
                    function_arguments='{"date":"2026-06-11"}',
                )
            ],
        ),
        LlamaResult(content="호출되면 안 됩니다.", model="fake-qwen"),
    )
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 3)
    monkeypatch.setattr("sutra.service.dispatch", lambda name, args: [])

    answer = ask("오늘 제2학생회관 점심 뭐야?", workspace=workspace, client=client, mode="router")

    assert len(client.calls) == 1
    assert answer.answer == "실시간 조회에 실패했고 저장된 자료에서도 관련 정보를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요."
    assert answer.evidence == []
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["forced_tool"] == "fetch_cafeteria_menu"
    assert answer.trace["tools_called"] == ["fetch_cafeteria_menu"]


def test_ask_router_keeps_insufficient_evidence_for_empty_non_forced_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path)
    client = RouterClient(LlamaResult(content="호출되면 안 됩니다.", model="fake-qwen"))
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 2)

    answer = ask("완전히없는쿼리", workspace=workspace, client=client, mode="router")

    assert client.calls == []
    assert answer.answer == "관련 정보를 확인할 수 있는 자료를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요."
    assert answer.evidence == []
    assert answer.trace["status"] == "insufficient_evidence"
    assert answer.trace["routed_domain"] == "academic_calendar"
    assert answer.trace["forced_tool"] is None
    assert answer.trace["tools_called"] == []


def test_ask_router_uses_rag_only_for_graduation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_graduation=True)
    client = RouterClient(LlamaResult(content="졸업요건은 저장된 근거로 답합니다.", model="fake-qwen"))
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 0)

    answer = ask("졸업요건 알려줘", workspace=workspace, client=client, mode="router")

    assert len(client.calls) == 1
    assert client.calls[0]["tools"] is None
    assert client.calls[0]["tool_choice"] is None
    assert answer.answer == "졸업요건은 저장된 근거로 답합니다."
    assert answer.evidence[0].id == "graduation-1"
    assert answer.trace["routed_domain"] == "graduation"
    assert answer.trace["forced_tool"] is None
    assert answer.trace["tools_called"] == []


def test_ask_router_falls_back_to_rag_when_classifier_import_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path)
    client = RouterClient(LlamaResult(content="저장된 학사일정 근거로 답합니다.", model="fake-qwen"))
    real_import = __import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "nlp_term.classify.predict":
            raise ImportError("classifier package missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    answer = ask("수강신청 언제 시작해?", workspace=workspace, client=client, mode="router")

    assert len(client.calls) == 1
    assert client.calls[0]["tools"] is None
    assert client.calls[0]["tool_choice"] is None
    assert answer.trace["routed_domain"] == "unknown"
    assert answer.trace["forced_tool"] is None
    assert answer.trace["classifier_fallback"] is True


def test_ask_router_routes_standalone_greeting_through_classifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_graduation=True)
    client = RouterClient(LlamaResult(content="인사 답변", model="fake-qwen"))
    calls: list[str] = []

    def fake_predict(question: str, **kwargs: Any) -> int:
        calls.append(question)
        return 0

    monkeypatch.setattr("sutra.service._predict_router_label", fake_predict)

    answer = ask("안녕하세요!", workspace=workspace, client=client, mode="router")

    assert calls == ["안녕하세요!"]
    assert client.calls == []
    assert answer.answer == "관련 정보를 확인할 수 있는 자료를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요."
    assert answer.trace["routed_domain"] == "graduation"
    assert answer.trace["forced_tool"] is None
    assert answer.trace["classifier_fallback"] is False


def test_ask_router_routes_mixed_greeting_question_through_classifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_dining=True)
    client = RouterClient(LlamaResult(content="식단 답변", model="fake-qwen"))
    calls: list[str] = []

    def fake_predict(question: str, **kwargs: Any) -> int:
        calls.append(question)
        return 3

    monkeypatch.setattr("sutra.service._predict_router_label", fake_predict)
    monkeypatch.setattr("sutra.service.dispatch", lambda name, args: [])

    answer = ask("안녕, 오늘 학식 뭐야?", workspace=workspace, client=client, mode="router")

    assert calls == ["안녕, 오늘 학식 뭐야?"]
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["classifier_fallback"] is False


def test_predict_router_label_returns_none_when_prediction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenPredictModule:
        @staticmethod
        def predict_label(question: str, model_path: Path) -> int:
            raise RuntimeError("missing classifier model")

    real_import = __import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "nlp_term.classify.predict":
            return BrokenPredictModule
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert _predict_router_label("오늘 식단 알려줘") is None


def test_resolve_classifier_model_path_prefers_env_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = _write_workspace(workspace_root)
    env_model = tmp_path / "env" / "classifier.joblib"
    workspace_model = tmp_path / "workspace" / "model" / "classifier.joblib"
    env_model.parent.mkdir()
    workspace_model.parent.mkdir()
    env_model.write_text("env", encoding="utf-8")
    workspace_model.write_text("workspace", encoding="utf-8")
    monkeypatch.setenv("SUTRA_CLASSIFIER_PATH", str(env_model))

    assert _resolve_classifier_model_path(load_config(workspace)) == env_model.resolve()


def test_resolve_classifier_model_path_prefers_workspace_before_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cwd = tmp_path / "cwd"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = _write_workspace(workspace_root)
    cwd_model = cwd / "model" / "classifier.joblib"
    workspace_model = workspace_root / "model" / "classifier.joblib"
    cwd_model.parent.mkdir(parents=True)
    workspace_model.parent.mkdir()
    cwd_model.write_text("cwd", encoding="utf-8")
    workspace_model.write_text("workspace", encoding="utf-8")
    monkeypatch.chdir(cwd)
    monkeypatch.delenv("SUTRA_CLASSIFIER_PATH", raising=False)

    assert _resolve_classifier_model_path(load_config(workspace)) == workspace_model.resolve()


def test_resolve_classifier_model_path_returns_none_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = _write_workspace(workspace_root)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SUTRA_CLASSIFIER_PATH", raising=False)

    assert _resolve_classifier_model_path(load_config(workspace)) is None


def test_predict_router_label_uses_resolved_classifier_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = _write_workspace(workspace_root)
    classifier_path = tmp_path / "workspace" / "model" / "classifier.joblib"
    classifier_path.parent.mkdir()
    classifier_path.write_text("classifier", encoding="utf-8")
    seen_paths: list[Path] = []

    class PredictModule:
        @staticmethod
        def predict_label(question: str, model_path: Path | None = None) -> int:
            seen_paths.append(model_path)
            return 3

    real_import = __import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "nlp_term.classify.predict":
            return PredictModule
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert _predict_router_label("오늘 학식 뭐야?", config=load_config(workspace)) == 3
    assert seen_paths == [classifier_path.resolve()]


def test_ask_router_forces_recent_notices_tool_choice_and_persists_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_notices=True)
    trace_path = tmp_path / "logs" / "router_trace.jsonl"
    client = RouterClient(
        LlamaResult(
            content="",
            model="fake-qwen",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    function_name="fetch_recent_notices",
                    function_arguments='{"board":"cs_dept","limit":3}',
                )
            ],
        ),
        LlamaResult(content="실시간 공지와 저장된 공지 근거로 답합니다.", model="fake-qwen"),
    )
    live_evidence = Evidence(
        id="live_notices_cs_dept",
        title="컴퓨터인공지능학부 학사공지",
        text="최신 공지: 수강신청 안내",
        source_name="컴퓨터인공지능학부 학사공지",
    )
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 1)
    monkeypatch.setattr("sutra.service.dispatch", lambda name, args: [live_evidence])

    answer = ask(
        "최신 공지 알려줘",
        workspace=workspace,
        client=client,
        mode="router",
        trace_source="batch",
        trace_path=trace_path,
    )

    assert client.calls[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "fetch_recent_notices"},
    }
    assert answer.evidence[0].id == "live_notices_cs_dept"
    assert answer.trace["routed_domain"] == "notices"
    assert answer.trace["forced_tool"] == "fetch_recent_notices"
    assert answer.trace["classifier_fallback"] is False
    row = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["routed_domain"] == "notices"
    assert row["forced_tool"] == "fetch_recent_notices"
    assert row["classifier_fallback"] is False


@pytest.mark.parametrize(
    ("label", "question", "workspace_kwargs", "expected_doc_id", "expected_domain"),
    [
        (2, "수강신청 언제 시작해?", {}, "calendar-1", "academic_calendar"),
        (4, "셔틀버스 운행 알려줘", {"include_shuttle": True}, "shuttle-1", "shuttle"),
    ],
)
def test_ask_router_uses_rag_only_for_non_forced_domains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: int,
    question: str,
    workspace_kwargs: dict[str, bool],
    expected_doc_id: str,
    expected_domain: str,
) -> None:
    workspace = _write_workspace(tmp_path, **workspace_kwargs)
    client = RouterClient(LlamaResult(content="저장된 근거로 답합니다.", model="fake-qwen"))
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: label)

    answer = ask(question, workspace=workspace, client=client, mode="router")

    assert len(client.calls) == 1
    assert client.calls[0]["tools"] is None
    assert client.calls[0]["tool_choice"] is None
    assert answer.evidence[0].id == expected_doc_id
    assert answer.trace["routed_domain"] == expected_domain
    assert answer.trace["forced_tool"] is None


def test_ask_router_ignores_tool_evidence_from_unexpected_tool_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_graduation=True)
    client = RouterClient(
        LlamaResult(
            content="",
            model="fake-qwen",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    function_name="fetch_recent_notices",
                    function_arguments='{"board":"cs_dept","limit":3}',
                )
            ],
        ),
        LlamaResult(content="저장된 졸업 근거로 답합니다.", model="fake-qwen"),
    )
    live_evidence = Evidence(
        id="live_notices_cs_dept",
        title="컴퓨터인공지능학부 학사공지",
        text="최신 공지: 수강신청 안내",
        source_name="컴퓨터인공지능학부 학사공지",
    )
    dispatch_calls: list[str] = []

    def fake_dispatch(name: str, args: str) -> list[Evidence]:
        dispatch_calls.append(name)
        return [live_evidence]

    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 3)
    monkeypatch.setattr("sutra.service.dispatch", fake_dispatch)

    answer = ask("졸업요건 알려줘", workspace=workspace, client=client, mode="router")

    assert dispatch_calls == []
    assert answer.evidence[0].id == "graduation-1"
    assert all(item.id != "live_notices_cs_dept" for item in answer.evidence)
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["forced_tool"] == "fetch_cafeteria_menu"
    assert answer.trace["tools_called"] == ["fetch_recent_notices"]


def test_ask_router_falls_back_to_rag_when_forced_tool_returns_no_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_dining=True)
    client = RouterClient(
        LlamaResult(
            content="",
            model="fake-qwen",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    function_name="fetch_cafeteria_menu",
                    function_arguments='{"date":"2026-06-11"}',
                )
            ],
        ),
        LlamaResult(content="저장된 식단 근거로 답합니다.", model="fake-qwen"),
    )
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 3)
    monkeypatch.setattr("sutra.service.dispatch", lambda name, args: [])

    answer = ask("오늘 학생회관 점심 뭐야?", workspace=workspace, client=client, mode="router")

    assert len(client.calls) == 2
    assert client.calls[1]["tools"] is None
    assert answer.answer == (
        "저장된 식단 근거로 답합니다."
        "\n\n(실시간 정보를 가져오지 못해 저장된 자료를 기준으로 답변했습니다.)"
    )
    assert answer.evidence[0].id == "dining-1"
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["forced_tool"] == "fetch_cafeteria_menu"
    assert answer.trace["tools_called"] == ["fetch_cafeteria_menu"]


def test_ask_router_echo_client_accepts_forced_tool_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _write_workspace(tmp_path, include_dining=True)
    monkeypatch.setattr("sutra.service._predict_router_label", lambda question, **kwargs: 3)

    answer = ask("오늘 학생회관 점심 뭐야?", workspace=workspace, client=EchoClient(), mode="router")

    assert "[echo:fake-qwen]" in answer.answer
    assert answer.evidence[0].id == "dining-1"
    assert answer.trace["routed_domain"] == "dining"
    assert answer.trace["forced_tool"] == "fetch_cafeteria_menu"
    assert answer.trace["tools_called"] == []


@pytest.mark.skip(reason="answer prompt validation removed; render_prompt no longer checks answer prompt existence")
def test_ask_rejects_missing_configured_answer_prompt(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, answer_prompt="prompts/missing.md")

    with pytest.raises(ConfigError, match="configured answer prompt not found"):
        ask("수강신청 언제 시작해?", workspace=workspace, client=FakeClient())


def _write_workspace(
    root: Path,
    *,
    answer_prompt: str = "prompts/answer.md",
    include_dining: bool = False,
    include_graduation: bool = False,
    include_notices: bool = False,
    include_shuttle: bool = False,
    runtime_max_tokens: int = 128,
) -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        "\n".join(
            [
                '{"id":"calendar-1","title":"수강신청 일정","text":"수강신청은 2월 1일에 시작합니다.","source_name":"학사일정","metadata":{"label":"calendar"}}',
                *(
                    [
                        '{"id":"dining-1","title":"식단","text":"학생회관 점심 메뉴입니다.","source_name":"식단","metadata":{"label":"dining"}}',
                    ]
                    if include_dining
                    else []
                ),
                *(
                    [
                        '{"id":"graduation-1","title":"졸업요건","text":"졸업에는 전공 학점과 교양 학점이 필요합니다.","source_name":"졸업요건","metadata":{"label":"graduation"}}',
                    ]
                    if include_graduation
                    else []
                ),
                *(
                    [
                        '{"id":"notice-1","title":"최신 공지","text":"컴퓨터인공지능학부 최신 공지는 수강신청 안내입니다.","source_name":"학사공지","metadata":{"label":"notices"}}',
                    ]
                    if include_notices
                    else []
                ),
                *(
                    [
                        '{"id":"shuttle-1","title":"셔틀버스","text":"셔틀버스는 순환 노선으로 운행합니다.","source_name":"셔틀 안내","metadata":{"label":"shuttle"}}',
                    ]
                    if include_shuttle
                    else []
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "prompts" / "system.md").write_text("You are a grounded assistant.", encoding="utf-8")
    (root / "prompts" / "answer.md").write_text("Use the evidence context.", encoding="utf-8")
    config_path = root / "sutra.toml"
    config_path.write_text(
        f"""
[workspace]
name = "fixture"
timezone = "Asia/Seoul"

[runtime]
backend = "llama-server"
base_url = "http://127.0.0.1:18080"
model = "fake-qwen"
temperature = 0.1
max_tokens = {runtime_max_tokens}

[rag]
index_path = "data/index.jsonl"
top_k = 2
max_fact_chars = 120
backend = "lexical"

[prompts]
system = "prompts/system.md"
answer = "{answer_prompt}"
""".strip(),
        encoding="utf-8",
    )
    # Ensure the fixture is valid at creation time.
    load_config(config_path)
    return config_path
