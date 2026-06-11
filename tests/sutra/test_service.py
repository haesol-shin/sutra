from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sutra import ask, chat
from sutra.config import load_config
from sutra.models import LlamaResult, Message
from sutra.errors import ConfigError


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

    assert answer.trace == {"status": "insufficient_evidence", "retrieved": 0}
    assert client.messages == []


@pytest.mark.skip(reason="answer prompt validation removed; render_prompt no longer checks answer prompt existence")
def test_ask_rejects_missing_configured_answer_prompt(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, answer_prompt="prompts/missing.md")

    with pytest.raises(ConfigError, match="configured answer prompt not found"):
        ask("수강신청 언제 시작해?", workspace=workspace, client=FakeClient())


def _write_workspace(root: Path, *, answer_prompt: str = "prompts/answer.md") -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        "\n".join(
            [
                '{"id":"calendar-1","title":"수강신청 일정","text":"수강신청은 2월 1일에 시작합니다.","source_name":"학사일정","metadata":{"label":"calendar"}}',
                '{"id":"dining-1","title":"식단","text":"학생회관 점심 메뉴입니다.","source_name":"식단","metadata":{"label":"dining"}}',
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
max_tokens = 128

[rag]
index_path = "data/index.jsonl"
top_k = 2
max_fact_chars = 120

[prompts]
system = "prompts/system.md"
answer = "{answer_prompt}"
""".strip(),
        encoding="utf-8",
    )
    # Ensure the fixture is valid at creation time.
    load_config(config_path)
    return config_path
