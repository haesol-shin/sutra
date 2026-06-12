from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import requests

from sutra.errors import LlamaError
from sutra.models import LlamaResult, Message, ToolCall


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
        tool_choice: dict[str, Any] | str | None = None,
    ) -> LlamaResult:
        del temperature, max_tokens, tools, tool_choice
        return LlamaResult(content=f"[echo:{model or 'local'}] {messages[-1].content}", model=model)

    def stream_chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, object]] | None = None,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> Iterator[str]:
        del temperature, max_tokens, tools, tool_choice
        yield f"[echo:{model or 'local'}] {messages[-1].content}"



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


def _free_gpu_from_stale_servers() -> None:
    """Terminate any prior `python -m llama_cpp.server` still holding the GPU.

    A server started in a previous run keeps its VRAM (the process outlives the
    shell that backgrounded it), so a fresh server OOMs on a runtime that already
    has one loaded or mid-load. Best-effort: matches only the server child by its
    command line (never this `sutra.cli llama serve` process) and is a no-op where
    pgrep/pkill are unavailable (e.g. Windows).
    """
    if shutil.which("pgrep") is None or shutil.which("pkill") is None:
        return
    try:
        found = subprocess.run(
            ["pgrep", "-f", "llama_cpp.server"],
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return
    pids = [pid for pid in found.stdout.split() if pid.strip()]
    if not pids:
        return
    subprocess.run(["pkill", "-9", "-f", "llama_cpp.server"], check=False, capture_output=True)
    print(f"Freed GPU: terminated {len(pids)} stale llama_cpp.server process(es) before start.")
    time.sleep(3)


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

    _free_gpu_from_stale_servers()
    return subprocess.Popen(cmd)


class LlamaClient:
    """Client for llama-server HTTP API."""
    def __init__(self, base_url: str = "http://127.0.0.1:18080", timeout_seconds: int = 120) -> None:
        self.base_url = normalize_base_url(base_url)
        self.timeout_seconds = timeout_seconds

    def health(self, timeout_seconds: int = 5) -> bool:
        try:
            response = requests.get(f"{self.base_url}/health", timeout=timeout_seconds)
            if response.status_code < 400:
                return True
            if response.status_code == 404:
                # llama-cpp-python's OpenAI-compatible server exposes no /health route.
                response = requests.get(f"{self.base_url}/v1/models", timeout=timeout_seconds)
                return response.status_code < 400
            return False
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
        tool_choice: dict[str, Any] | str | None = None,
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
            payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"

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
        raw_answer = str(content)
        answer = raw_answer.strip()

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

        if not tool_calls:
            parsed_tool_calls, parsed_content, has_unparsed_tool_call = (
                _parse_qwen_tool_call_text(raw_answer)
            )
            if parsed_tool_calls:
                tool_calls = parsed_tool_calls
                answer = parsed_content.strip()
            elif has_unparsed_tool_call:
                answer = raw_answer

        if not answer and not tool_calls:
            raise LlamaError("empty llama-server response")
        return LlamaResult(
            content=answer,
            model=body.get("model"),
            usage=body.get("usage"),
            raw=body,
            tool_calls=tool_calls,
        )

    def stream_chat(
        self,
        messages: list[Message] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "messages": [_dump_message(message) for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if model:
            payload["model"] = model
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"

        response = None
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout_seconds,
                stream=True,
            )
            response.raise_for_status()
            yield from stream_chat_tokens_from_sse_lines(response.iter_lines())
        except LlamaError:
            raise
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LlamaError("malformed llama-server stream response") from exc
        finally:
            if response is not None:
                close = getattr(response, "close", None)
                if close is not None:
                    close()


def _dump_message(message: Message | dict[str, str]) -> dict[str, str]:
    if isinstance(message, Message):
        return message.model_dump()
    return {"role": message["role"], "content": message["content"]}


def stream_chat_tokens_from_sse_lines(lines: Iterable[bytes | str]) -> Iterator[str]:
    """Yield content deltas from OpenAI-compatible chat-completion SSE lines."""
    for raw_line in lines:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            break
        body = json.loads(data)
        choice = body["choices"][0]
        delta = choice.get("delta") or {}
        content = delta.get("content")
        if content:
            yield str(content)


def has_stream_tool_call_marker(content: str) -> bool:
    return "<tool_call" in content.lower()


_TOOL_CALL_RE = re.compile(
    r"<tool_call\b[^>]*>(?P<body>.*?)</tool_call>",
    re.DOTALL | re.IGNORECASE,
)
_FUNCTION_RE = re.compile(
    r"<function\s*=\s*(?P<name>[^>\s]+)\s*>(?P<body>.*?)</function>",
    re.DOTALL | re.IGNORECASE,
)
_PARAMETER_RE = re.compile(
    r"<parameter\s*=\s*(?P<name>[^>\s]+)\s*>(?P<value>.*?)</parameter>",
    re.DOTALL | re.IGNORECASE,
)


def _parse_qwen_tool_call_text(content: str) -> tuple[list[ToolCall], str, bool]:
    tool_calls: list[ToolCall] = []
    spans_to_remove: list[tuple[int, int]] = []
    saw_tool_call_block = False

    for match in _TOOL_CALL_RE.finditer(content):
        saw_tool_call_block = True
        tool_call = _parse_qwen_tool_call_block(match.group("body"))
        if tool_call is None:
            continue
        tool_calls.append(tool_call)
        spans_to_remove.append(match.span())

    if not tool_calls:
        has_unparsed_tool_call = saw_tool_call_block or _has_incomplete_tool_call_block(content)
        return [], content, has_unparsed_tool_call

    parts: list[str] = []
    last_end = 0
    for start, end in spans_to_remove:
        parts.append(content[last_end:start])
        last_end = end
    parts.append(content[last_end:])
    return tool_calls, "".join(parts), False


def _parse_qwen_tool_call_block(body: str) -> ToolCall | None:
    stripped_body = body.strip()
    if not stripped_body:
        return None

    json_tool_call = _parse_json_tool_call(stripped_body)
    if json_tool_call is not None:
        return json_tool_call

    function_match = _FUNCTION_RE.fullmatch(stripped_body)
    if function_match is None:
        return None

    function_name = function_match.group("name").strip()
    if not function_name:
        return None

    arguments = {
        parameter.group("name").strip(): parameter.group("value").strip()
        for parameter in _PARAMETER_RE.finditer(function_match.group("body"))
        if parameter.group("name").strip()
    }
    return ToolCall(
        id="",
        type="function",
        function_name=function_name,
        function_arguments=_dump_tool_arguments(arguments),
    )


def _parse_json_tool_call(body: str) -> ToolCall | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
        arguments = {}

    return ToolCall(
        id="",
        type="function",
        function_name=name.strip(),
        function_arguments=_dump_tool_arguments(arguments),
    )


def _dump_tool_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))


def _has_incomplete_tool_call_block(content: str) -> bool:
    opened = len(re.findall(r"<tool_call\b[^>]*>", content, re.IGNORECASE))
    closed = len(re.findall(r"</tool_call>", content, re.IGNORECASE))
    return opened > closed
