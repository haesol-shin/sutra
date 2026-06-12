from __future__ import annotations

from pathlib import Path

from sutra.config import load_config
from sutra.models import Evidence, EvidencePack
from sutra.prompts import build_relative_date_anchors, build_temporal_context, render_prompt


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


def _cnu_periods():
    from datetime import date

    from sutra.config import WorkspacePeriod

    return [
        WorkspacePeriod(label="2026학년도 제1학기", start=date(2026, 3, 3), end=date(2026, 6, 21)),
        WorkspacePeriod(label="하기방학", start=date(2026, 6, 22), end=date(2026, 8, 31)),
        WorkspacePeriod(label="2026학년도 제2학기", start=date(2026, 9, 1), end=date(2026, 12, 20)),
    ]


def test_build_temporal_context_resolves_configured_period() -> None:
    from datetime import date

    ctx = build_temporal_context(date(2026, 6, 13), _cnu_periods())  # Saturday in 제1학기
    assert "현재 기간: 2026학년도 제1학기" in ctx
    assert "이번 주: 2026-06-08(월) ~ 2026-06-14(일)" in ctx
    assert "다음 주: 2026-06-15(월) ~ 2026-06-21(일)" in ctx


def test_build_temporal_context_resolves_second_semester() -> None:
    from datetime import date

    ctx = build_temporal_context(date(2026, 9, 15), _cnu_periods())
    assert "현재 기간: 2026학년도 제2학기" in ctx


def test_build_temporal_context_without_periods_emits_only_weeks() -> None:
    from datetime import date

    ctx = build_temporal_context(date(2026, 6, 13), None)
    assert "현재 기간" not in ctx
    assert "이번 주:" in ctx
    assert "다음 주:" in ctx


def test_render_prompt_injects_temporal_context(tmp_path: Path) -> None:
    from datetime import date
    from unittest.mock import patch

    workspace = _write_workspace(tmp_path)
    config = load_config(workspace)
    evidence = EvidencePack(question="q", items=[])
    with patch("sutra.prompts.get_current_date", return_value=date(2026, 6, 13)):
        prompt = render_prompt("이번 학기 종강일", evidence, config)
    assert "현재 기간: 2026학년도 제1학기" in prompt.messages[1].content
    assert "이번 주:" in prompt.messages[1].content


def test_answer_and_forced_tool_prompts_share_temporal_anchors(tmp_path: Path) -> None:
    from datetime import date
    from unittest.mock import patch

    from sutra.service import _render_router_tool_request_messages

    workspace = _write_workspace(tmp_path)
    config = load_config(workspace)
    evidence = EvidencePack(question="q", items=[])
    anchor_line = build_relative_date_anchors(date(2026, 6, 13))

    with patch("sutra.prompts.get_current_date", return_value=date(2026, 6, 13)), patch(
        "sutra.service.get_current_date", return_value=date(2026, 6, 13)
    ):
        answer_prompt = render_prompt("오늘 학식", evidence, config)
        forced_messages = _render_router_tool_request_messages("오늘 학식", config)

    answer_user = answer_prompt.messages[1].content
    forced_user = forced_messages[1].content
    assert anchor_line in answer_user
    assert anchor_line in forced_user
    for line in ("이번 주:", "다음 주:"):
        assert line in answer_user
        assert line in forced_user


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

[[workspace.periods]]
label = "2026학년도 제1학기"
start = 2026-03-03
end = 2026-06-21

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
