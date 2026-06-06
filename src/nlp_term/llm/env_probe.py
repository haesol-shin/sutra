from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


PACKAGE_NAMES = (
    "torch",
    "transformers",
    "accelerate",
    "bitsandbytes",
    "vllm",
    "auto_gptq",
    "optimum",
    "optimum_quanto",
    "hqq",
    "llama_cpp",
    "sentence_transformers",
    "huggingface_hub",
)
EXECUTABLE_NAMES = (
    "nvidia-smi",
    "sycl-ls",
    "llama-cli",
    "llama-server",
    "ollama",
    "cmake",
    "icx",
    "dpcpp",
)


def package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def executable_path(name: str) -> str | None:
    return shutil.which(name)


def run_command(command: list[str], *, timeout: int = 5) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def windows_gpu_info() -> list[dict[str, Any]]:
    if platform.system().lower() != "windows":
        return []
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json",
    ]
    result = run_command(command)
    if not result.get("ok") or not result.get("stdout"):
        return [{"probe_error": result}]
    payload = json.loads(result["stdout"])
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return [{"probe_error": "unexpected ConvertTo-Json shape"}]
    return payload


def torch_info() -> dict[str, Any]:
    if not package_available("torch"):
        return {"installed": False}
    import torch  # type: ignore[import-not-found]

    info: dict[str, Any] = {
        "installed": True,
        "version": getattr(torch, "__version__", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "xpu_available": False,
        "xpu_device_count": 0,
        "xpu_devices": [],
    }
    xpu = getattr(torch, "xpu", None)
    if xpu is not None:
        try:
            info["xpu_available"] = bool(xpu.is_available())
            info["xpu_device_count"] = int(xpu.device_count()) if info["xpu_available"] else 0
        except Exception as exc:  # pragma: no cover - hardware dependent
            info["xpu_error"] = str(exc)
        for index in range(info["xpu_device_count"]):
            device: dict[str, Any] = {"index": index}
            for attr in ("get_device_name", "get_device_properties"):
                try:
                    value = getattr(xpu, attr)(index)
                except Exception as exc:  # pragma: no cover - hardware dependent
                    value = f"error: {exc}"
                device[attr] = str(value)
            info["xpu_devices"].append(device)
    return info


def infer_capabilities(payload: dict[str, Any]) -> dict[str, Any]:
    packages = payload["packages"]
    executables = payload["executables"]
    gpu_names = " ".join(str(gpu.get("Name", "")) for gpu in payload["windows_gpu_info"]).lower()
    torch_payload = payload["torch"]
    has_cuda = bool(torch_payload.get("cuda_available"))
    has_xpu = bool(torch_payload.get("xpu_available"))
    has_gguf_runner = any(executables[name] for name in ("llama-cli", "llama-server", "ollama")) or packages[
        "llama_cpp"
    ]
    vllm_xpu_fp8_kv_candidate = bool(
        packages["vllm"]
        and packages["torch"]
        and has_xpu
        and payload["environment"].get("VLLM_ATTENTION_BACKEND") == "TRITON_ATTN"
    )

    blockers: list[str] = []
    if not packages["torch"]:
        blockers.append("torch is not installed in the current uv environment")
    if not packages["transformers"]:
        blockers.append("transformers is not installed in the current uv environment")
    if not has_xpu and "intel" in gpu_names:
        blockers.append("Intel GPU exists, but torch.xpu availability is not proven")
    if not has_gguf_runner:
        blockers.append("no GGUF runner executable or llama_cpp Python package was found")
    if not has_cuda:
        blockers.append("CUDA backend is not available locally; CUDA-only FP8 KV paths are not local proof")

    return {
        "primary_target": {
            "model": "Qwen/Qwen3.5-9B",
            "weight_quantization": "int4",
            "kv_cache_quantization": "fp8",
            "max_params_b": 9,
            "context_probe_tokens": [2048, 4096],
            "batch_size": 1,
            "peak_vram_gb_gate": 15,
        },
        "local_gpu_family": "intel_arc_xpu" if "intel" in gpu_names and "arc" in gpu_names else "unknown",
        "pytorch_xpu_stack_available": bool(packages["torch"] and packages["transformers"] and has_xpu),
        "vllm_xpu_fp8_kv_candidate": vllm_xpu_fp8_kv_candidate,
        "cuda_quant_stack_available": bool(
            packages["torch"] and packages["transformers"] and packages["bitsandbytes"] and has_cuda
        ),
        "gguf_runner_available": bool(has_gguf_runner),
        "exact_int4_weight_fp8_kv_supported_locally": False,
        "nearest_supported_kv_cache": None,
        "blockers": blockers,
    }


def build_probe() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "environment": {
            "LEVEL_ZERO_V1_SDK_PATH": os.environ.get("LEVEL_ZERO_V1_SDK_PATH"),
            "ONEAPI_ROOT": os.environ.get("ONEAPI_ROOT"),
            "VLLM_ATTENTION_BACKEND": os.environ.get("VLLM_ATTENTION_BACKEND"),
        },
        "packages": {name: package_available(name) for name in PACKAGE_NAMES},
        "executables": {name: executable_path(name) for name in EXECUTABLE_NAMES},
        "windows_gpu_info": windows_gpu_info(),
        "torch": torch_info(),
    }
    payload["capabilities"] = infer_capabilities(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local LLM backend capability.")
    parser.add_argument("--output", type=Path, default=Path("model/llm_backend_probe.json"))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    capabilities = payload["capabilities"]
    print(f"wrote {args.output}")
    print(f"local_gpu_family={capabilities['local_gpu_family']}")
    print(f"pytorch_xpu_stack_available={capabilities['pytorch_xpu_stack_available']}")
    print(f"gguf_runner_available={capabilities['gguf_runner_available']}")
    print(f"exact_int4_weight_fp8_kv_supported_locally={capabilities['exact_int4_weight_fp8_kv_supported_locally']}")
    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
