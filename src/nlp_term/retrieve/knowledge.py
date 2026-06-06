from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from nlp_term.paths import data_dir
from nlp_term.prepare.knowledge import build_seed_knowledge
from nlp_term.schemas import KnowledgeDoc


@dataclass(frozen=True)
class KnowledgeLoadResult:
    docs: list[KnowledgeDoc]
    path: Path | None
    fallback_used: bool


def default_knowledge_path() -> Path:
    absolute_path = Path("/") / "data" / "knowledge_seed.json"
    if absolute_path.exists():
        return absolute_path
    return data_dir() / "knowledge_seed.json"


def load_knowledge_with_metadata(path: Path | None = None) -> KnowledgeLoadResult:
    target = path or default_knowledge_path()
    if target.exists():
        with target.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return KnowledgeLoadResult(
            docs=[KnowledgeDoc.model_validate(row) for row in payload],
            path=target,
            fallback_used=False,
        )
    return KnowledgeLoadResult(
        docs=build_seed_knowledge(),
        path=None,
        fallback_used=True,
    )


def load_knowledge(path: Path | None = None) -> list[KnowledgeDoc]:
    return load_knowledge_with_metadata(path).docs
