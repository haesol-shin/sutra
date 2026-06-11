from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from sutra.cli import build_parser, main
from sutra.config import load_config


def test_cli_ask_uses_echo_client(tmp_path: Path, capsys) -> None:
    workspace = _write_workspace(tmp_path)

    assert main(["ask", "--workspace", str(workspace), "--echo", "수강신청 언제?"]) == 0

    output = capsys.readouterr().out
    assert "[echo:fake-qwen]" in output
    assert "수강신청은 2월 1일입니다." in output


def _write_workspace(root: Path, base_url: str | None = None, reasoning: str | None = None) -> Path:
    (root / "data").mkdir()
    (root / "prompts").mkdir()
    (root / "data" / "index.jsonl").write_text(
        '{"id":"calendar-1","title":"수강신청","text":"수강신청은 2월 1일입니다."}\n',
        encoding="utf-8",
    )
    (root / "prompts" / "system.md").write_text("You are a grounded assistant.", encoding="utf-8")
    config_path = root / "sutra.toml"
    lines = [
        '[workspace]',
        'name = "fixture"',
        '',
        '[runtime]',
        'model = "fake-qwen"',
    ]
    if base_url is not None:
        lines.append(f'base_url = "{base_url}"')
    if reasoning is not None:
        lines.append(f'reasoning = "{reasoning}"')
    lines += [
        '',
        '[rag]',
        'index_path = "data/index.jsonl"',
        '',
        '[prompts]',
        'system = "prompts/system.md"',
    ]
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return config_path


# --- Argument parsing tests ---

def test_llama_serve_parse_args() -> None:
    parser = build_parser()

    args = parser.parse_args([
        "llama", "serve",
        "--port", "12345",
        "--gpu-layers", "20",
        "--dry-run",
        "--workspace", "/fake/ws",
        "--n-ctx", "4096",
    ])
    assert args.command == "llama"
    assert args.subcommand == "serve"
    assert args.port == 12345
    assert args.gpu_layers == 20
    assert args.dry_run is True
    assert args.workspace == "/fake/ws"
    assert args.n_ctx == 4096

    args = parser.parse_args(["llama", "serve"])
    assert args.port is None
    assert args.gpu_layers == -1
    assert args.dry_run is False
    assert args.workspace is None
    assert args.n_ctx == 2048


def test_llama_download_parse_args() -> None:
    parser = build_parser()

    args = parser.parse_args([
        "llama", "download",
        "--dest", "/fake/dest",
        "--repo-id", "foo/bar",
        "--filename", "baz.gguf",
        "--json",
        "--workspace", "/fake/ws",
    ])
    assert args.command == "llama"
    assert args.subcommand == "download"
    assert args.dest == "/fake/dest"
    assert args.repo_id == "foo/bar"
    assert args.filename == "baz.gguf"
    assert args.json is True

    args = parser.parse_args(["llama", "download"])
    assert args.dest is None
    assert args.repo_id == "unsloth/Qwen3.5-9B-GGUF"
    assert args.filename == "Qwen3.5-9B-Q4_K_M.gguf"
    assert args.json is False


# --- Routing tests ---

def test_llama_serve_routes_correctly(tmp_path: Path, capsys) -> None:
    workspace = _write_workspace(tmp_path)

    with patch("sutra.cli.start_llama_server", return_value=None) as mock_start:
        result = main([
            "llama", "serve",
            "--workspace", str(workspace),
            "--port", "9999",
            "--gpu-layers", "10",
            "--n-ctx", "4096",
            "--dry-run",
        ])

    mock_start.assert_called_once()
    assert mock_start.call_args[1]["port"] == 9999
    assert mock_start.call_args[1]["gpu_layers"] == 10
    assert mock_start.call_args[1]["dry_run"] is True
    assert mock_start.call_args[1]["n_ctx"] == 4096
    assert result == 0


def test_llama_serve_port_fallback(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, base_url="http://127.0.0.1:18080")

    with patch("sutra.cli.start_llama_server", return_value=None) as mock_start:
        main(["llama", "serve", "--workspace", str(workspace), "--dry-run"])

    assert mock_start.call_args[1]["port"] == 18080


def test_llama_serve_port_default_fallback(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, base_url="http://127.0.0.1")

    with patch("sutra.cli.start_llama_server", return_value=None) as mock_start:
        main(["llama", "serve", "--workspace", str(workspace), "--dry-run"])

    assert mock_start.call_args[1]["port"] == 18080


@pytest.mark.skip(reason="--llama-path arg removed; locate_llama_server is deprecated")
def test_llama_serve_with_llama_path(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path)

    with (
        patch("sutra.cli.locate_llama_server", return_value=Path("/custom/llama-server")) as mock_locate,
        patch("sutra.cli.start_llama_server", return_value=None),
    ):
        main([
            "llama", "serve",
            "--workspace", str(workspace),
            "--llama-path", "/custom/path",
            "--dry-run",
        ])

    mock_locate.assert_called_once_with("/custom/path")


@pytest.mark.skip(reason="--reasoning arg removed; use --chat-template-kwargs instead")
def test_llama_serve_reasoning_fallback_and_override(tmp_path: Path) -> None:
    workspace = _write_workspace(tmp_path, reasoning="off")

    with (
        patch("sutra.cli.locate_llama_server", return_value=Path("/fake/llama-server")),
        patch("sutra.cli.start_llama_server", return_value=None) as mock_start,
    ):
        main(["llama", "serve", "--workspace", str(workspace), "--dry-run"])

    assert mock_start.call_args[1]["reasoning"] == "off"

    with (
        patch("sutra.cli.locate_llama_server", return_value=Path("/fake/llama-server")),
        patch("sutra.cli.start_llama_server", return_value=None) as mock_start,
    ):
        main(["llama", "serve", "--workspace", str(workspace), "--reasoning", "on", "--dry-run"])

    assert mock_start.call_args[1]["reasoning"] == "on"


def test_llama_serve_dry_run_shows_resolved_model_path(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    workspace = _write_workspace(tmp_path)

    with patch("sutra.cli.start_llama_server", return_value=None):
        main(["llama", "serve", "--workspace", str(workspace), "--dry-run"])

    out = capsys.readouterr().out
    expected_path = (tmp_path / ".cache" / "sutra" / "models" / "Qwen3.5-9B-Q4_K_M.gguf").resolve()
    assert "Resolved model path:" in out
    assert str(expected_path) in out


def test_llama_download_routes_correctly(tmp_path: Path, capsys) -> None:
    workspace = _write_workspace(tmp_path)
    dest_dir = tmp_path / "custom_models"

    with patch("sutra.cli.download_model") as mock_download:
        result = main([
            "llama", "download",
            "--workspace", str(workspace),
            "--dest", str(dest_dir),
        ])

    mock_download.assert_called_once()
    assert mock_download.call_args[0][0] == dest_dir.resolve()
    assert result == 0


def test_llama_download_default_dest_is_cache_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    workspace = _write_workspace(tmp_path)
    expected_dir = tmp_path / ".cache" / "sutra" / "models"

    with patch("sutra.cli.download_model") as mock_download:
        main(["llama", "download", "--workspace", str(workspace)])

    mock_download.assert_called_once()
    assert mock_download.call_args[0][0] == expected_dir.resolve()


def test_llama_download_json_mode(tmp_path: Path, capsys) -> None:
    workspace = _write_workspace(tmp_path)
    fake_path = tmp_path / "model" / "generator" / "Qwen3.5-9B-Q4_K_M.gguf"

    with patch("sutra.cli.download_model", return_value=fake_path):
        result = main([
            "llama", "download",
            "--workspace", str(workspace),
            "--json",
        ])

    import json
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "ok"
    assert payload["downloaded_path"] == str(fake_path.resolve())
    assert payload["repo_id"] == "unsloth/Qwen3.5-9B-GGUF"
    assert payload["filename"] == "Qwen3.5-9B-Q4_K_M.gguf"
    assert result == 0


def test_cnu_workspace_resolves_to_default_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    cnu_dir = tmp_path / "cnu"
    (cnu_dir / "data" / "processed").mkdir(parents=True)
    (cnu_dir / "prompts").mkdir(parents=True)
    (cnu_dir / "data" / "processed" / "knowledge-index.jsonl").write_text("", encoding="utf-8")
    (cnu_dir / "prompts" / "system.md").write_text("system", encoding="utf-8")
    (cnu_dir / "prompts" / "answer.md").write_text("answer", encoding="utf-8")
    config_path = cnu_dir / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "cnu-campus"

[runtime]
base_url = "http://127.0.0.1:18080"
model = "qwen-local"

[rag]
index_path = "data/processed/knowledge-index.jsonl"
top_k = 8

[prompts]
system = "prompts/system.md"
answer = "prompts/answer.md"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    expected = (tmp_path / ".cache" / "sutra" / "models" / "Qwen3.5-9B-Q4_K_M.gguf").resolve()
    assert config.runtime.model_path == expected
