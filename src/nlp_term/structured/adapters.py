from __future__ import annotations

from typing import Protocol

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.structured.rows import BaseStructuredRow


class SourceAdapter(Protocol):
    source_id: str

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[BaseStructuredRow]:
        ...

    def to_knowledge_docs(self, rows: list[BaseStructuredRow]) -> list[KnowledgeDoc]:
        ...
