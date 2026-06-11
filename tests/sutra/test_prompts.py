from __future__ import annotations

from pathlib import Path

from sutra.config import load_config
from sutra.models import Evidence, EvidencePack
from sutra.prompts import render_prompt


def test_render_prompt_does_not_inline_tool_listing(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)
    config = load_config(workspace)
    evidence = EvidencePack(
        question="최신 공지 알려줘",
        items=[
            Evidence(
                id="notice-1",
                title="최신 공지",
                text="수강신청 안내입니다.",
                source_name="학사공지",
            )
        ],
    )

    prompt = render_prompt("최신 공지 알려줘", evidence, config)

    assert prompt.messages[0].content == "You are a grounded assistant."
    assert "You have access to the following tools" not in prompt.messages[0].content
    assert "fetch_recent_notices" not in prompt.messages[0].content
    assert "Evidence:" in prompt.messages[1].content
    assert "수강신청 안내입니다." in prompt.messages[1].content


def _write_workspace(root: Path) -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        '{"id":"notice-1","title":"최신 공지","text":"수강신청 안내입니다.","source_name":"학사공지"}\n',
        encoding="utf-8",
    )
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
