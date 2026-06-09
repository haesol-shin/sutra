from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
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


def start_llama_server(
    executable_path: Path,
    model_path: Path,
    port: int = 18080,
    gpu_layers: int = 0,
    reasoning: str | None = None,
    dry_run: bool = False,
) -> subprocess.Popen | None:
    cmd = [
        str(executable_path),
        "--model",
        str(model_path),
        "--port",
        str(port),
    ]
    if reasoning is not None:
        cmd.extend(["--reasoning", reasoning])
    if gpu_layers > 0:
        cmd.extend(["-ngl", str(gpu_layers)])

    if dry_run:
        print(f"[dry-run] Command: {' '.join(cmd)}")
        return None

    if not model_path.exists():
        raise LlamaError(
            f"Model file not found at: {model_path}. Please download it first using 'sutra llama download'"
        )
    if not executable_path.exists():
        raise LlamaError(f"llama-server binary not found at: {executable_path}")

    process = subprocess.Popen(cmd)

    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_void_p),
                ("MaximumWorkingSetSize", ctypes.c_void_p),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_void_p),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_void_p),
                ("JobMemoryLimit", ctypes.c_void_p),
                ("PeakProcessMemoryUsed", ctypes.c_void_p),
                ("PeakJobMemoryUsed", ctypes.c_void_p),
            ]

        h_job = kernel32.CreateJobObjectW(None, None)

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        kernel32.SetInformationJobObject(
            h_job,
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )

        kernel32.AssignProcessToJobObject(h_job, process._handle)
        process._job_handle = h_job

    return process


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
