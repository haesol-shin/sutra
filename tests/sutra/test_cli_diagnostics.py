from __future__ import annotations

import json
import pytest

from sutra.cli import main, resolve_workspace_path
from sutra.errors import WorkspaceResolutionError


def test_resolve_workspace_priority(tmp_path, monkeypatch) -> None:
    # Set up directories:
    # tmp_path/workspace_cli/sutra.toml
    # tmp_path/workspace_env/sutra.toml
    # tmp_path/workspace_cwd/sutra.toml
    
    cli_dir = tmp_path / "workspace_cli"
    cli_dir.mkdir()
    cli_toml = cli_dir / "sutra.toml"
    cli_toml.touch()
    
    env_dir = tmp_path / "workspace_env"
    env_dir.mkdir()
    env_toml = env_dir / "sutra.toml"
    env_toml.touch()
    
    cwd_dir = tmp_path / "workspace_cwd"
    cwd_dir.mkdir()
    cwd_toml = cwd_dir / "sutra.toml"
    cwd_toml.touch()
    
    # 1. --workspace beats SUTRA_WORKSPACE and cwd
    monkeypatch.setenv("SUTRA_WORKSPACE", str(env_toml))
    monkeypatch.chdir(cwd_dir)
    resolved = resolve_workspace_path(str(cli_toml))
    assert resolved == cli_toml
    
    # 2. SUTRA_WORKSPACE beats cwd search
    resolved = resolve_workspace_path(None)
    assert resolved == env_toml
    
    # 3. cwd search finds local sutra.toml
    monkeypatch.delenv("SUTRA_WORKSPACE", raising=False)
    resolved = resolve_workspace_path(None)
    assert resolved == cwd_toml
    
    # 4. Upward search finds parent sutra.toml
    nested_dir = cwd_dir / "nested" / "more_nested"
    nested_dir.mkdir(parents=True)
    monkeypatch.chdir(nested_dir)
    resolved = resolve_workspace_path(None)
    assert resolved == cwd_toml
    
    # 5. Not found raises WorkspaceResolutionError
    monkeypatch.chdir(tmp_path)  # tmp_path has no sutra.toml in parents
    with pytest.raises(WorkspaceResolutionError):
        resolve_workspace_path(None)


def test_workspace_validate_does_not_parse_jsonl(tmp_path) -> None:
    # Write a config with system.md and a corrupt index.jsonl (which exists but is invalid JSON)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    
    index_path = tmp_path / "data" / "index.jsonl"
    index_path.write_text("CORRUPTED INVALID JSON LINE!", encoding="utf-8")
    
    system_path = tmp_path / "prompts" / "system.md"
    system_path.write_text("You are helpful.", encoding="utf-8")
    
    config_path = tmp_path / "sutra.toml"
    config_path.write_text("""
[workspace]
name = "test_validate"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(), encoding="utf-8")

    exit_code = main(["workspace", "validate", "--workspace", str(config_path)])
    assert exit_code == 0


def test_docs_check_detects_data_issues(tmp_path, capsys) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    
    # index.jsonl contains:
    # 1. Valid line
    # 2. Duplicate ID line
    # 3. Empty text row
    # 4. Invalid JSON line
    # 5. Schema violation line (missing id/text)
    index_path = tmp_path / "data" / "index.jsonl"
    index_path.write_text(
        '{"id": "doc1", "text": "Hello", "source_name": "src1", "source_url": "url1"}\n'
        '{"id": "doc1", "text": "Duplicate ID"}\n'
        '{"id": "doc2", "text": "   "}\n'  # empty text
        'INVALID JSON LINE!!!\n'
        '{"id": "doc3"}\n',  # missing text (schema violation)
        encoding="utf-8"
    )
    
    system_path = tmp_path / "prompts" / "system.md"
    system_path.write_text("You are helpful.", encoding="utf-8")
    
    config_path = tmp_path / "sutra.toml"
    config_path.write_text("""
[workspace]
name = "test_docs"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(), encoding="utf-8")

    exit_code = main(["docs", "check", "--workspace", str(config_path), "--json"])
    assert exit_code == 1
    
    out = capsys.readouterr().out
    res = json.loads(out)
    assert res["status"] == "fail"
    assert res["exit_code"] == 1
    
    report = res["report"]
    assert report["total_documents"] == 3
    assert report["invalid_lines"] == 2
    assert report["duplicate_ids"] == 1
    assert report["empty_text_rows"] == 1
    assert report["missing_source_name"] == 2
    assert report["missing_source_url"] == 2


def test_llama_health_unreachable(tmp_path, capsys) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text('{"id":"1","text":"ok"}\n', encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    
    config_path = tmp_path / "sutra.toml"
    config_path.write_text("""
[workspace]
name = "test_llama"

[runtime]
base_url = "http://127.0.0.1:54321"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(), encoding="utf-8")

    exit_code = main(["llama", "health", "--workspace", str(config_path), "--json"])
    assert exit_code == 3
    
    out = capsys.readouterr().out
    res = json.loads(out)
    assert res["status"] == "fail"
    assert res["exit_code"] == 3
    assert res["reachable"] is False
    assert res["error_detail"] is not None


def test_doctor_only_llama_unavailable(tmp_path, capsys) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text('{"id":"1","text":"ok"}\n', encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    
    config_path = tmp_path / "sutra.toml"
    config_path.write_text("""
[workspace]
name = "test_doctor"

[runtime]
base_url = "http://127.0.0.1:54321"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(), encoding="utf-8")

    exit_code = main(["doctor", "--workspace", str(config_path), "--json"])
    assert exit_code == 3
    
    out = capsys.readouterr().out
    res = json.loads(out)
    assert res["status"] == "fail"
    assert res["exit_code"] == 3
    
    components = res["components"]
    assert components["workspace"]["status"] == "ok"
    assert components["docs"]["status"] == "ok"
    assert components["llama"]["status"] == "fail"


def test_ask_no_workspace_arg_in_workspace_dir(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text('{"id":"1","text":"ok"}\n', encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    
    config_path = tmp_path / "sutra.toml"
    config_path.write_text("""
[workspace]
name = "test_ask"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    
    exit_code = main(["ask", "--echo", "ok"])
    assert exit_code == 0
    
    out = capsys.readouterr().out
    assert "[echo:local-model]" in out
