from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from sutra.errors import ConfigError

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


class WorkspacePeriod(BaseModel):
    """A named date range a workspace cares about (e.g. a semester, a season).

    Optional, workspace-defined. Lets the engine inject a resolved current-period
    anchor without baking any project-specific calendar into the package."""

    label: str
    start: date
    end: date


class WorkspaceConfig(BaseModel):
    name: str
    description: str = ""
    timezone: str = "UTC"
    periods: list[WorkspacePeriod] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    backend: Literal["llama-server"] = "llama-server"
    base_url: str = "http://127.0.0.1:18080"
    model: str = "local-model"
    model_path: Path | None = None
    reasoning: Literal["on", "off", "auto"] | None = None
    timeout_seconds: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, gt=0)
    chat_template_kwargs: str | None = None


class RagConfig(BaseModel):
    index_path: Path
    top_k: int = Field(default=8, gt=0)
    max_fact_chars: int = Field(default=500, gt=0)
    backend: Literal["bm25", "qwen3", "hybrid", "lexical"] = "bm25"
    token_config: str | None = None


class PromptConfig(BaseModel):
    system: Path


class EvalConfig(BaseModel):
    smoke: Path | None = None
    regression: Path | None = None


DEFAULT_MODEL_FILENAME = "Qwen3.5-9B-Q4_K_M.gguf"


def _default_model_dir() -> Path:
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path.home() / ".cache"
    return base / "sutra" / "models"


def _default_model_path() -> Path:
    return _default_model_dir() / DEFAULT_MODEL_FILENAME


def _resolve_model_path(root: Path, configured_path: Path | None) -> Path:
    if env_path := os.getenv("SUTRA_MODEL_PATH"):
        return Path(env_path).expanduser().resolve()

    if configured_path is not None:
        return _resolve(root, configured_path)

    if env_dir := os.getenv("SUTRA_MODEL_DIR"):
        return (Path(env_dir).expanduser().resolve() / DEFAULT_MODEL_FILENAME)

    return _default_model_path()


class Config(BaseModel):
    path: Path
    root: Path
    workspace: WorkspaceConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    rag: RagConfig
    prompts: PromptConfig
    evals: EvalConfig = Field(default_factory=EvalConfig)


def load_config(path: str | Path | None) -> Config:
    if path is None or (isinstance(path, str) and not path.strip()):
        raise ConfigError("workspace config path is required")

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
    if config.rag.token_config is not None:
        data["rag"]["token_config"] = str(_resolve(root, Path(config.rag.token_config)))
    data["prompts"]["system"] = _resolve(root, config.prompts.system)
    if config.evals.smoke is not None:
        data["evals"]["smoke"] = _resolve(root, config.evals.smoke)
    if config.evals.regression is not None:
        data["evals"]["regression"] = _resolve(root, config.evals.regression)
    data["runtime"]["model_path"] = _resolve_model_path(root, config.runtime.model_path)
    if config.runtime.chat_template_kwargs is not None:
        ctk_path = _resolve(root, Path(config.runtime.chat_template_kwargs))
        if ctk_path.exists():
            data["runtime"]["chat_template_kwargs"] = ctk_path.read_text(encoding="utf-8").strip()
    return Config.model_validate(data)


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (root / path).resolve()


def resolve_input_path(path_str: str, workspace_root: Path | None = None) -> Path:
    """Resolve an input file path.

    Resolution order:
    1. the literal path, when it exists;
    2. workspace_root/data/<relative>, when it exists;
    3. cwd/data/<relative>.

    UNIX-style /data/file.json and data/file.json inputs are stripped before
    the workspace/cwd data lookups.
    """
    literal = Path(path_str).expanduser()
    if literal.exists():
        return literal.resolve()

    posix_str = path_str.replace("\\", "/")
    if posix_str.startswith("/data/"):
        relative = posix_str[len("/data/"):]
    elif posix_str.startswith("data/"):
        relative = posix_str[len("data/"):]
    else:
        relative = path_str

    if workspace_root:
        workspace_candidate = (workspace_root / "data" / relative).resolve()
        if workspace_candidate.exists():
            return workspace_candidate
    return (Path("data") / relative).resolve()


def resolve_output_path(
    path_str: str,
    workspace_root: Path | None = None,
    *,
    prefer_cwd: bool = False,
) -> Path:
    """Resolve an output file path under workspace outputs/.

    Handles UNIX-style absolute paths like /outputs/file.json by stripping the
    /outputs/ prefix. When the corresponding input came from cwd/data, callers
    pass prefer_cwd=True so outputs are written to cwd/outputs.
    """
    literal = Path(path_str).expanduser()
    posix_str = path_str.replace("\\", "/")
    if posix_str.startswith("/outputs/"):
        relative = posix_str[len("/outputs/"):]
    elif posix_str.startswith("outputs/"):
        relative = posix_str[len("outputs/"):]
    else:
        if literal.is_absolute():
            out = literal.resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            return out
        relative = path_str

    if workspace_root and not prefer_cwd:
        out = (workspace_root / "outputs" / relative).resolve()
    else:
        out = (Path("outputs") / relative).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    return out
