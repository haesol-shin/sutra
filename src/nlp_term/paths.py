from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return Path(os.environ.get("NLP_TERM_DATA_DIR", PROJECT_ROOT / "data"))


def outputs_dir() -> Path:
    return Path(os.environ.get("NLP_TERM_OUTPUTS_DIR", PROJECT_ROOT / "outputs"))


def model_dir() -> Path:
    return Path(os.environ.get("NLP_TERM_MODEL_DIR", PROJECT_ROOT / "model"))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def default_input_path(filename: str) -> Path:
    absolute_path = Path("/") / "data" / filename
    if absolute_path.exists():
        return absolute_path
    local_path = data_dir() / filename
    if local_path.exists():
        return local_path
    return local_path


def default_output_path(filename: str) -> Path:
    absolute_dir = Path("/") / "outputs"
    if absolute_dir.exists():
        return absolute_dir / filename
    return outputs_dir() / filename
