from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import requests

from sutra.errors import LlamaError
from sutra.models import LlamaResult, Message



def locate_llama_server(cli_path: str | Path | None = None) -> Path:
    if cli_path:
        resolved = Path(cli_path).expanduser().resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
        raise LlamaError(
            f"llama-server binary not found at explicitly configured path: {resolved}"
        )

    env_path = os.getenv("LLAMA_SERVER_PATH")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
        raise LlamaError(
            f"llama-server binary not found at env var LLAMA_SERVER_PATH: {resolved}"
        )

    which_path = shutil.which("llama-server")
    if which_path is not None:
        resolved = Path(which_path).resolve()
        if resolved.exists() and resolved.is_file():
            return resolved

    raise LlamaError(
        "llama-server binary not found. "
        "Download it from https://github.com/ggerganov/llama.cpp/releases "
        "and place it on your PATH, or set the LLAMA_SERVER_PATH environment variable."
    )


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def download_model(
    dest_path: Path,
    repo_id: str = "unsloth/Qwen3.5-9B-GGUF",
    filename: str = "Qwen3.5-9B-Q4_K_M.gguf",
) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise LlamaError(
            "The 'huggingface_hub' package is required for downloading models. "
            "Please install it using 'pip install huggingface_hub' "
            "or by syncing optional extras (e.g. 'uv sync --extra rag')."
        )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=dest_path.parent,
        local_dir_use_symlinks=False,
    )
    return dest_path.resolve()


class LlamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout_seconds: int = 120) -> None:
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
    ) -> LlamaResult:
        payload: dict[str, Any] = {
            "messages": [_dump_message(message) for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if model:
            payload["model"] = model

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except LlamaError:
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            if message in {"'choices'", "list index out of range", "'message'", "'content'"}:
                message = "malformed llama-server response"
            raise LlamaError(message) from exc

        answer = str(content).strip()
        if not answer:
            raise LlamaError("empty llama-server response")
        return LlamaResult(content=answer, model=body.get("model"), usage=body.get("usage"), raw=body)


def _dump_message(message: Message | dict[str, str]) -> dict[str, str]:
    if isinstance(message, Message):
        return message.model_dump()
    return {"role": message["role"], "content": message["content"]}
