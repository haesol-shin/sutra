from __future__ import annotations

from pathlib import Path

from sutra.cli import main


def test_cli_ask_uses_echo_client(tmp_path: Path, capsys) -> None:
    workspace = _write_workspace(tmp_path)

    assert main(["ask", "--workspace", str(workspace), "--echo", "수강신청 언제?"]) == 0

    output = capsys.readouterr().out
    assert "[echo:fake-qwen]" in output
    assert "수강신청은 2월 1일입니다." in output


def _write_workspace(root: Path) -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        '{"id":"calendar-1","title":"수강신청","text":"수강신청은 2월 1일입니다."}\n',
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

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )
    return config_path
