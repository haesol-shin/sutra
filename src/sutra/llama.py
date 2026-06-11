from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

from sutra.errors import LlamaError
from sutra.models import LlamaResult, Message


class EchoClient:
    """Test/echo client that echoes the last message. Ignores generation parameters."""
    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, object]] | None = None,
    ) -> LlamaResult:
        del temperature, max_tokens, tools
        return LlamaResult(content=f"[echo:{model or 'local'}] {messages[-1].content}", model=model)



def locate_llama_server(cli_path: str | Path | None = None) -> Path:
    """DEPRECATED: llama-cpp-python provides its own server via `python -m llama_cpp.server`.
    Binary search is no longer needed. Install llama-cpp-python and use `sutra llama serve` instead."""
    raise LlamaError(
        "llama-server binary is no longer used. "
        "Install llama-cpp-python and use 'python -m llama_cpp.server':\n"
        "  uv pip install -e \".[xpu,rag,ui,legacy]\" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/vulkan\n"
        "  uv run sutra llama serve"
    )


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def download_model(
    dest_dir: Path,
    repo_id: str = "unsloth/Qwen3.5-9B-GGUF",
    filename: str = "Qwen3.5-9B-Q4_K_M.gguf",
) -> Path:
    """Download a GGUF model from Hugging Face."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise LlamaError(
            "The 'huggingface_hub' package is required for downloading models. "
            "Please install it using 'pip install huggingface_hub' "
            "or by syncing optional extras (e.g. 'uv sync --extra rag')."
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=dest_dir,
        local_dir_use_symlinks=False,
    )
    return (dest_dir / filename).resolve()


def start_llama_server(
    model_path: Path,
    port: int = 18080,
    gpu_layers: int = -1,
    chat_template_kwargs: str | None = None,
    dry_run: bool = False,
    n_ctx: int = 2048,
) -> subprocess.Popen | None:
    """Start llama-cpp-python server via `python -m llama_cpp.server`."""
    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", str(model_path),
        "--port", str(port),
        "--n_gpu_layers", str(gpu_layers),
        "--host", "127.0.0.1",
        "--n_ctx", str(n_ctx),
    ]
    if chat_template_kwargs:
        cmd.extend(["--chat_template_kwargs", chat_template_kwargs])

    if dry_run:
        print(f"[dry-run] Command: {' '.join(cmd)}")
        return None

    if not model_path.exists():
        raise LlamaError(
            f"Model file not found at: {model_path}. Please download it first using 'sutra llama download'"
        )

    return subprocess.Popen(cmd)


class LlamaClient:
    """Client for llama-server HTTP API."""
    def __init__(self, base_url: str = "http://127.0.0.1:18080", timeout_seconds: int = 120) -> None:
        self.base_url = normalize_base_url(base_url)
        self.timeout_seconds = timeout_seconds

    def health(self, timeout_seconds: int = 5) -> bool:
        try:
            response = requests.get(f"{self.base_url}/health", timeout=timeout_seconds)
            return response.status_code < 400
        except Exception:
            return False

    def chat(
        self,
        messages: list[Message] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlamaResult:
        payload: dict[str, Any] = {
            "messages": [_dump_message(message) for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if model:
            payload["model"] = model
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
        except LlamaError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise LlamaError("malformed llama-server response") from exc

        content = message.get("content") or ""
        answer = str(content).strip()

        tool_calls: list[ToolCall] = []
        raw_tool_calls = message.get("tool_calls") or []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                type=tc.get("type", "function"),
                function_name=fn.get("name", ""),
                function_arguments=fn.get("arguments", "{}"),
            ))

        if not answer and not tool_calls:
            raise LlamaError("empty llama-server response")
        return LlamaResult(
            content=answer,
            model=body.get("model"),
            usage=body.get("usage"),
            raw=body,
            tool_calls=tool_calls,
        )


def _dump_message(message: Message | dict[str, str]) -> dict[str, str]:
    if isinstance(message, Message):
        return message.model_dump()
    return {"role": message["role"], "content": message["content"]}
