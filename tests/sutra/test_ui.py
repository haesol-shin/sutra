from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from sutra.cli import build_parser, main


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


@pytest.mark.skip(reason="integration test requires chainlit which is not installed in base+dev sync")
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
