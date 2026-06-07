from __future__ import annotations

from typing import Any

import requests


class LlamaServerUnavailable(RuntimeError):
    """Raised when llama-server cannot produce a usable answer."""


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def check_llama_server_health(base_url: str, timeout_seconds: int = 5) -> bool:
    try:
        response = requests.get(f"{_normalize_base_url(base_url)}/health", timeout=timeout_seconds)
        return response.status_code < 400
    except Exception:
        return False


def generate_with_llama_server(
    *,
    prompt: str,
    base_url: str = "http://127.0.0.1:8080",
    timeout_seconds: int = 120,
    temperature: float = 0.2,
    max_tokens: int = 256,
) -> str:
    payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(
            f"{_normalize_base_url(base_url)}/v1/chat/completions",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except LlamaServerUnavailable:
        raise
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        if not message or message in {"'choices'", "list index out of range", "'message'", "'content'"}:
            message = "malformed llama-server response"
        raise LlamaServerUnavailable(message) from exc

    answer = str(content).strip()
    if not answer:
        raise LlamaServerUnavailable("empty llama-server response")
    return answer
