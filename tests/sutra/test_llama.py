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


def test_llama_client_parses_qwen_xmlish_tool_call_with_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "model": "qwen",
                "choices": [
                    {
                        "message": {
                            "content": (
                                "확인하겠습니다.\n"
                                "<tool_call>\n"
                                "<function=fetch_cafeteria_menu>\n"
                                "<parameter=date>\n"
                                "today\n"
                                "</parameter>\n"
                                "<parameter=location>\n"
                                "global lounge\n"
                                "</parameter>\n"
                                "</function>\n"
                                "</tool_call>\n"
                            )
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "오늘 글로벌 라운지 메뉴"}])

    assert result.content == "확인하겠습니다."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].function_name == "fetch_cafeteria_menu"
    assert result.tool_calls[0].function_arguments == '{"date":"today","location":"global lounge"}'


def test_llama_client_parses_qwen_xmlish_tool_call_without_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "<tool_call>\n"
                                "<function=fetch_latest_notices>\n"
                                "</function>\n"
                                "</tool_call>"
                            )
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "최신 공지"}])

    assert result.content == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].function_name == "fetch_latest_notices"
    assert result.tool_calls[0].function_arguments == "{}"


def test_llama_client_parses_qwen_json_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '<tool_call>\n{"name": "fetch_calendar", '
                                '"arguments": {"date": "2026-06-11"}}\n</tool_call>'
                            )
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "오늘 학사일정"}])

    assert result.content == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].function_name == "fetch_calendar"
    assert result.tool_calls[0].function_arguments == '{"date":"2026-06-11"}'


def test_llama_client_parses_multiple_text_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "<tool_call><function=fetch_cafeteria_menu></function></tool_call>\n"
                                "and\n"
                                '<tool_call>{"name":"fetch_latest_notices","arguments":{"limit":2}}</tool_call>'
                            )
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "오늘 식단과 최신 공지"}])

    assert result.content == "and"
    assert [tool.function_name for tool in result.tool_calls] == [
        "fetch_cafeteria_menu",
        "fetch_latest_notices",
    ]
    assert [tool.function_arguments for tool in result.tool_calls] == [
        "{}",
        '{"limit":2}',
    ]


def test_llama_client_leaves_plain_content_without_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": [{"message": {"content": "일반 답변"}}]})

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "안녕"}])

    assert result.content == "일반 답변"
    assert result.tool_calls == []


def test_llama_client_ignores_incomplete_text_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = "<tool_call>\n<function=fetch_cafeteria_menu>\n"

    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "오늘 식단"}])

    assert result.content == content
    assert result.tool_calls == []


def test_llama_client_ignores_unparseable_text_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = "<tool_call>\nnot json or xml\n</tool_call>\n"

    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "오늘 식단"}])

    assert result.content == content
    assert result.tool_calls == []


def test_llama_client_keeps_server_tool_calls_without_text_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "<tool_call><function=fetch_cafeteria_menu></function></tool_call>"
                            ),
                            "tool_calls": [
                                {
                                    "id": "server-call",
                                    "type": "function",
                                    "function": {
                                        "name": "server_tool",
                                        "arguments": '{"source":"server"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient().chat([{"role": "user", "content": "오늘 식단"}])

    assert result.content == "<tool_call><function=fetch_cafeteria_menu></function></tool_call>"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "server-call"
    assert result.tool_calls[0].function_name == "server_tool"
    assert result.tool_calls[0].function_arguments == '{"source":"server"}'


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


def test_locate_cli_path_found() -> None:
    """locate_llama_server is deprecated—always raises LlamaError."""
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
        locate_llama_server("C:/fake/llama-server.exe")


def test_locate_cli_path_not_found() -> None:
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
        locate_llama_server("C:/fake/missing.exe")


def test_locate_empty_cli_path_raises() -> None:
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
        locate_llama_server("")


def test_locate_env_var_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLAMA_SERVER_PATH", "D:/llama/llama-server.exe")
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
        locate_llama_server()


def test_locate_env_var_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLAMA_SERVER_PATH", "D:/llama/missing.exe")
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
        locate_llama_server()


def test_locate_system_path_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: "C:/bin/llama-server.exe")
    monkeypatch.delenv("LLAMA_SERVER_PATH", raising=False)
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
        locate_llama_server()


def test_locate_all_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.delenv("LLAMA_SERVER_PATH", raising=False)
    with pytest.raises(LlamaError, match="llama-server binary is no longer used"):
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
    pytest.importorskip("huggingface_hub")
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
    model = Path("/models/qwen.gguf")
    result = start_llama_server(
        model_path=model,
        port=18080,
        gpu_layers=0,
        dry_run=True,
    )
    captured = capsys.readouterr()
    assert result is None
    assert "[dry-run] Command:" in captured.out
    assert "--model" in captured.out
    assert str(model) in captured.out
    assert "--port" in captured.out
    assert "18080" in captured.out
    assert "--n_gpu_layers" in captured.out
    assert "--n_ctx" in captured.out
    assert "2048" in captured.out


def test_start_llama_server_dry_run_with_gpu(capsys: pytest.CaptureFixture) -> None:
    result = start_llama_server(
        model_path=Path("model.gguf"),
        port=18080,
        gpu_layers=24,
        dry_run=True,
    )
    captured = capsys.readouterr()
    assert result is None
    assert "--n_gpu_layers" in captured.out
    assert "24" in captured.out
    assert "--n_ctx" in captured.out


def test_start_llama_server_dry_run_with_custom_n_ctx(capsys: pytest.CaptureFixture) -> None:
    result = start_llama_server(
        model_path=Path("model.gguf"),
        port=18080,
        dry_run=True,
        n_ctx=4096,
    )
    captured = capsys.readouterr()
    assert result is None
    assert "--n_ctx" in captured.out
    assert "4096" in captured.out


def test_start_llama_server_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    with pytest.raises(LlamaError, match="Model file not found"):
        start_llama_server(
            model_path=Path("missing.gguf"),
            dry_run=False,
        )


def test_start_llama_server_missing_binary() -> None:
    pytest.skip("Binary existence check removed; server now uses python -m llama_cpp.server")


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
        model_path=Path("/models/qwen.gguf"),
        port=18080,
        gpu_layers=24,
        n_ctx=4096,
        dry_run=False,
    )

    assert result is mock_process
    cmd = captured_cmd[0]
    assert "--model" in cmd
    assert str(Path("/models/qwen.gguf")) in cmd
    assert "--port" in cmd
    assert "18080" in cmd
    assert "--n_gpu_layers" in cmd
    assert "24" in cmd
    assert "--n_ctx" in cmd
    assert "4096" in cmd


@pytest.mark.skip(reason="Win32 job object wrapping removed; server now uses python -m llama_cpp.server without job object assignment")
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
        model_path=Path("model.gguf"),
        dry_run=False,
    )

    assert result is mock_process
    mock_kernel32.CreateJobObjectW.assert_called_once_with(None, None)
    mock_kernel32.SetInformationJobObject.assert_called_once()
    mock_kernel32.AssignProcessToJobObject.assert_called_once_with(mock_h_job, 12345)
    assert mock_process._job_handle is mock_h_job
