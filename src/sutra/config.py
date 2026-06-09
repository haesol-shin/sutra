from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from sutra.errors import ConfigError

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


class WorkspaceConfig(BaseModel):
    name: str
    description: str = ""
    timezone: str = "UTC"


class RuntimeConfig(BaseModel):
    backend: Literal["llama-server"] = "llama-server"
    base_url: str = "http://127.0.0.1:8080"
    model: str = "local-model"
    model_path: Path | None = None
    timeout_seconds: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, gt=0)


class RagConfig(BaseModel):
    index_path: Path
    top_k: int = Field(default=8, gt=0)
    max_fact_chars: int = Field(default=500, gt=0)


class PromptConfig(BaseModel):
    system: Path
    answer: Path | None = None


class EvalConfig(BaseModel):
    smoke: Path | None = None
    regression: Path | None = None


class Config(BaseModel):
    path: Path
    root: Path
    workspace: WorkspaceConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    rag: RagConfig
    prompts: PromptConfig
    evals: EvalConfig = Field(default_factory=EvalConfig)


def load_config(path: str | Path) -> Config:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise ConfigError(f"workspace config not found: {config_path}")

    try:
        payload: dict[str, Any] = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"failed to read workspace config: {config_path}") from exc

    root = config_path.parent
    try:
        config = Config(
            path=config_path,
            root=root,
            workspace=payload["workspace"],
            runtime=_runtime_payload(payload.get("runtime", {})),
            rag=payload["rag"],
            prompts=payload["prompts"],
            evals=payload.get("evals", {}),
        )
    except KeyError as exc:
        raise ConfigError(f"missing required config section: {exc.args[0]}") from exc
    except Exception as exc:
        raise ConfigError(f"invalid workspace config: {config_path}") from exc

    return _resolve_paths(config)


def _runtime_payload(payload: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(payload)
    if base_url := os.getenv("SUTRA_BASE_URL"):
        runtime["base_url"] = base_url
    if model := os.getenv("SUTRA_MODEL"):
        runtime["model"] = model
    return runtime


def _resolve_paths(config: Config) -> Config:
    data = config.model_dump()
    root = config.root
    data["rag"]["index_path"] = _resolve(root, config.rag.index_path)
    data["prompts"]["system"] = _resolve(root, config.prompts.system)
    if config.prompts.answer is not None:
        data["prompts"]["answer"] = _resolve(root, config.prompts.answer)
    if config.evals.smoke is not None:
        data["evals"]["smoke"] = _resolve(root, config.evals.smoke)
    if config.evals.regression is not None:
        data["evals"]["regression"] = _resolve(root, config.evals.regression)
    if config.runtime.model_path is not None:
        data["runtime"]["model_path"] = _resolve(root, config.runtime.model_path)
    else:
        data["runtime"]["model_path"] = _resolve(
            root, Path("model/generator/Qwen3.5-9B-Q4_K_M.gguf")
        )
    return Config.model_validate(data)


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (root / path).resolve()
