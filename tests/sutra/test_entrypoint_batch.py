from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from sutra.cli import main
from sutra.config import resolve_input_path, resolve_output_path


def test_resolve_input_path_falls_back_to_cwd_data(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = tmp_path / "workspace"
    (repo_root / "data").mkdir(parents=True)
    workspace_root.mkdir()
    expected = repo_root / "data" / "test_chat.json"
    expected.write_text("[]", encoding="utf-8")
    monkeypatch.chdir(repo_root)

    assert resolve_input_path("/data/test_chat.json", workspace_root) == expected.resolve()
    assert resolve_output_path("/outputs/chat_output.json", workspace_root, prefer_cwd=True) == (
        repo_root / "outputs" / "chat_output.json"
    ).resolve()


def test_resolve_input_path_prefers_workspace_data_when_present(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = tmp_path / "workspace"
    (repo_root / "data").mkdir(parents=True)
    (workspace_root / "data").mkdir(parents=True)
    expected = workspace_root / "data" / "test_chat.json"
    expected.write_text("[]", encoding="utf-8")
    monkeypatch.chdir(repo_root)

    assert resolve_input_path("/data/test_chat.json", workspace_root) == expected.resolve()
    assert resolve_output_path("/outputs/chat_output.json", workspace_root) == (
        workspace_root / "outputs" / "chat_output.json"
    ).resolve()


def test_resolve_input_path_preserves_existing_absolute_path(tmp_path: Path) -> None:
    absolute = tmp_path / "custom" / "input.json"
    absolute.parent.mkdir()
    absolute.write_text("[]", encoding="utf-8")

    assert resolve_input_path(str(absolute), tmp_path / "workspace") == absolute.resolve()


def test_batch_echo_writes_cwd_outputs_and_provenance(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = tmp_path / "workspace"
    workspace = _write_workspace(workspace_root)
    (repo_root / "data").mkdir(parents=True)
    (repo_root / "data" / "test_chat.json").write_text(
        json.dumps([{"user": "수강신청 언제 시작해?"}], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo_root)

    assert main(
        [
            "batch",
            "--workspace",
            str(workspace),
            "--input",
            "data/test_chat.json",
            "--output",
            "outputs/chat_output.json",
            "--echo",
        ]
    ) == 0

    output_path = repo_root / "outputs" / "chat_output.json"
    provenance_path = repo_root / "outputs" / "chat_output.provenance.json"
    rows = json.loads(output_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    assert rows == [{"user": "수강신청 언제 시작해?", "model": rows[0]["model"]}]
    assert rows[0]["model"]
    assert "[echo:fake-qwen]" in rows[0]["model"]
    assert provenance == [{"index": 0, "mode": "llm", "error": ""}]


def test_batch_falls_back_after_retry_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = tmp_path / "workspace"
    workspace = _write_workspace(workspace_root)
    (repo_root / "data").mkdir(parents=True)
    (repo_root / "data" / "test_chat.json").write_text(
        json.dumps([{"user": "수강신청 언제 시작해?"}], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo_root)

    with patch("sutra.cli.ask", side_effect=RuntimeError("server down")):
        assert main(
            [
                "batch",
                "--workspace",
                str(workspace),
                "--input",
                "data/test_chat.json",
                "--output",
                "outputs/chat_output.json",
            ]
        ) == 0

    rows = json.loads((repo_root / "outputs" / "chat_output.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (repo_root / "outputs" / "chat_output.provenance.json").read_text(encoding="utf-8")
    )
    stderr = capsys.readouterr().err

    assert len(rows) == 1
    assert rows[0]["user"] == "수강신청 언제 시작해?"
    assert "2월 1일" in rows[0]["model"]
    assert "https://example.test/calendar" in rows[0]["model"]
    assert provenance == [{"index": 0, "mode": "fallback", "error": "server down"}]
    assert "WARNING: Item 0 used deterministic fallback" in stderr


def _write_workspace(root: Path) -> Path:
    (root / "data").mkdir(parents=True)
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        (
            '{"id":"calendar-1","title":"수강신청 일정",'
            '"text":"수강신청은 2월 1일에 시작합니다.",'
            '"source_name":"학사일정","source_url":"https://example.test/calendar",'
            '"metadata":{"label":"calendar"}}\n'
        ),
        encoding="utf-8",
    )
    (root / "prompts" / "system.md").write_text("You are a grounded assistant.", encoding="utf-8")
    config_path = root / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
model = "fake-qwen"

[rag]
index_path = "data/index.jsonl"
backend = "lexical"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )
    return config_path
