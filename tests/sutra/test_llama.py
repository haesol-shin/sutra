from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from sutra.errors import LlamaError
from sutra.llama import (
    LlamaClient,
    download_model,
    locate_llama_server,
    start_llama_server,
)
from sutra.models import Message


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.text)


def test_llama_client_reads_openai_compatible_chat_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        assert json["model"] == "qwen"
        assert json["messages"] == [{"role": "user", "content": "질문"}]
        return FakeResponse(
            200,
            {
                "model": "qwen",
                "choices": [{"message": {"content": "답변"}}],
                "usage": {"total_tokens": 3},
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient("http://127.0.0.1:8080/").chat(
        [Message(role="user", content="질문")],
        model="qwen",
    )

    assert result.content == "답변"
    assert result.model == "qwen"
    assert result.usage == {"total_tokens": 3}


def test_llama_client_rejects_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": []})

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(LlamaError, match="malformed"):
        LlamaClient().chat([{"role": "user", "content": "질문"}])


def test_llama_client_health_uses_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/health"
        return FakeResponse(200, {"status": "ok"})

    monkeypatch.setattr("requests.get", fake_get)

    assert LlamaClient("http://127.0.0.1:8080").health() is True


# --- locate_llama_server tests ---


def test_locate_cli_path_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    fake_path = "C:/fake/llama-server.exe"
    result = locate_llama_server(fake_path)
    assert result == Path(fake_path).resolve()


def test_locate_cli_path_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    with pytest.raises(LlamaError, match="explicitly configured path"):
        locate_llama_server("C:/fake/missing.exe")


def test_locate_empty_cli_path_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.delenv("LLAMA_SERVER_PATH", raising=False)
    with pytest.raises(LlamaError):
        locate_llama_server("")


def test_locate_env_var_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    monkeypatch.setenv("LLAMA_SERVER_PATH", "D:/llama/llama-server.exe")
    result = locate_llama_server()
    assert result == Path("D:/llama/llama-server.exe").resolve()


def test_locate_env_var_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    monkeypatch.setenv("LLAMA_SERVER_PATH", "D:/llama/missing.exe")
    with pytest.raises(LlamaError, match="LLAMA_SERVER_PATH"):
        locate_llama_server()


def test_locate_system_path_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    monkeypatch.setattr("shutil.which", lambda cmd: "C:/bin/llama-server.exe")
    monkeypatch.delenv("LLAMA_SERVER_PATH", raising=False)
    result = locate_llama_server()
    assert result == Path("C:/bin/llama-server.exe").resolve()


def test_locate_all_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.delenv("LLAMA_SERVER_PATH", raising=False)
    with pytest.raises(LlamaError, match="github.com/ggerganov/llama.cpp/releases"):
        locate_llama_server()


# --- download_model tests ---


def test_download_model_raises_if_huggingface_hub_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "huggingface_hub":
            raise ImportError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(LlamaError, match="huggingface_hub"):
        download_model(dest_dir=Path("/tmp/models"))


def test_download_model_calls_hf_hub_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dest_dir = tmp_path / "models"

    called: dict[str, object] = {}

    def fake_hf_download(
        repo_id: str,
        filename: str,
        local_dir: Path,
        local_dir_use_symlinks: bool,
    ) -> str:
        called["repo_id"] = repo_id
        called["filename"] = filename
        called["local_dir"] = local_dir
        called["local_dir_use_symlinks"] = local_dir_use_symlinks
        return str(local_dir / filename)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_hf_download)

    result = download_model(dest_dir=dest_dir)

    assert called["repo_id"] == "unsloth/Qwen3.5-9B-GGUF"
    assert called["filename"] == "Qwen3.5-9B-Q4_K_M.gguf"
    assert called["local_dir"] == dest_dir
    assert called["local_dir_use_symlinks"] is False
    assert result == (dest_dir / "Qwen3.5-9B-Q4_K_M.gguf").resolve()


# --- start_llama_server tests ---


def test_start_llama_server_dry_run_basic(capsys: pytest.CaptureFixture) -> None:
    exe = Path("/usr/bin/llama-server")
    model = Path("/models/qwen.gguf")
    result = start_llama_server(
        executable_path=exe,
        model_path=model,
        port=18080,
        gpu_layers=0,
        dry_run=True,
    )
    captured = capsys.readouterr()
    assert result is None
    assert "[dry-run] Command:" in captured.out
    assert str(exe) in captured.out
    assert "--model" in captured.out
    assert str(model) in captured.out
    assert "--port" in captured.out
    assert "18080" in captured.out
    assert "-ngl" not in captured.out


def test_start_llama_server_dry_run_with_gpu(capsys: pytest.CaptureFixture) -> None:
    result = start_llama_server(
        executable_path=Path("llama-server.exe"),
        model_path=Path("model.gguf"),
        port=18080,
        gpu_layers=24,
        dry_run=True,
    )
    captured = capsys.readouterr()
    assert result is None
    assert "-ngl" in captured.out
    assert "24" in captured.out


def test_start_llama_server_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    with pytest.raises(LlamaError, match="Model file not found"):
        start_llama_server(
            executable_path=Path("llama-server.exe"),
            model_path=Path("missing.gguf"),
            dry_run=False,
        )


def test_start_llama_server_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_exists(self: Path) -> bool:
        return "model" in str(self) or "gguf" in str(self)

    monkeypatch.setattr("pathlib.Path.exists", fake_exists)
    with pytest.raises(LlamaError, match="llama-server binary not found"):
        start_llama_server(
            executable_path=Path("missing.exe"),
            model_path=Path("model.gguf"),
            dry_run=False,
        )


def test_start_llama_server_spawns_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("sys.platform", "linux")

    mock_process = mock.MagicMock(spec=subprocess.Popen)
    captured_cmd: list[list[str]] = []

    def fake_popen(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        captured_cmd.append(cmd)
        return mock_process

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = start_llama_server(
        executable_path=Path("/usr/bin/llama-server"),
        model_path=Path("/models/qwen.gguf"),
        port=18080,
        gpu_layers=24,
        reasoning="off",
        dry_run=False,
    )

    assert result is mock_process
    assert captured_cmd[0][0] == str(Path("/usr/bin/llama-server"))
    assert captured_cmd[0][1] == "--model"
    assert captured_cmd[0][2] == str(Path("/models/qwen.gguf"))
    assert captured_cmd[0][3] == "--port"
    assert captured_cmd[0][4] == "18080"
    assert captured_cmd[0][5] == "--reasoning"
    assert captured_cmd[0][6] == "off"
    assert captured_cmd[0][7] == "-ngl"
    assert captured_cmd[0][8] == "24"


def test_start_llama_server_win32_job_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

    mock_process = mock.MagicMock(spec=subprocess.Popen)
    mock_process._handle = 12345

    def fake_popen(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        return mock_process

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    mock_kernel32 = mock.MagicMock()
    mock_h_job = mock.MagicMock()
    mock_kernel32.CreateJobObjectW.return_value = mock_h_job
    mock_kernel32.SetInformationJobObject.return_value = True
    mock_kernel32.AssignProcessToJobObject.return_value = True

    monkeypatch.setattr("ctypes.WinDLL", lambda name, use_last_error=True: mock_kernel32)

    result = start_llama_server(
        executable_path=Path("llama-server.exe"),
        model_path=Path("model.gguf"),
        dry_run=False,
    )

    assert result is mock_process
    mock_kernel32.CreateJobObjectW.assert_called_once_with(None, None)
    mock_kernel32.SetInformationJobObject.assert_called_once()
    mock_kernel32.AssignProcessToJobObject.assert_called_once_with(mock_h_job, 12345)
    assert mock_process._job_handle is mock_h_job
