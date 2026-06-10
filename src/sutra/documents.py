from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from sutra.config import Config
from sutra.errors import ConfigError
from sutra.models import Document


def load_documents(config_or_path: Config | str | Path) -> list[Document]:
    """Load documents from the configured index path."""
    path = config_or_path.rag.index_path if isinstance(config_or_path, Config) else Path(config_or_path)
    if not path.exists():
        raise ConfigError(f"document index not found: {path}")

    documents: list[Document] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            documents.append(Document.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ConfigError(f"invalid document at {path}:{line_number}") from exc
    return documents
