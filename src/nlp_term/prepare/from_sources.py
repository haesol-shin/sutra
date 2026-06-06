from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from nlp_term.paths import PROJECT_ROOT
from nlp_term.prepare.document_parsers import document_to_text
from nlp_term.prepare.normalize import clip_text
from nlp_term.prepare.parsers import html_to_text, source_doc_from_text
from nlp_term.schemas import KnowledgeDoc, RawSource
from nlp_term.validators import read_json


class SourceParseFailure(BaseModel):
    source_id: str
    raw_path: str
    reason: str


def parse_source(raw: RawSource, *, chunks_per_source: int = 3) -> tuple[list[KnowledgeDoc], SourceParseFailure | None]:
    raw_path = PROJECT_ROOT / Path(raw.raw_path)
    try:
        text = _extract_text(raw, raw_path)
        chunks = _chunk_text(text, chunks_per_source=chunks_per_source)
        docs = [
            source_doc_from_text(
                raw,
                title=f"{raw.domain} source {index + 1}",
                body=chunk,
                section=f"chunk_{index + 1}",
                parser_name=_parser_name(raw),
            )
            for index, chunk in enumerate(chunks)
        ]
        return docs, None
    except Exception as exc:
        return [], SourceParseFailure(source_id=raw.source_id, raw_path=str(raw_path), reason=str(exc))


def build_knowledge_from_probe(source_probe_path: Path) -> tuple[list[KnowledgeDoc], list[SourceParseFailure]]:
    payload = read_json(source_probe_path)
    if not isinstance(payload, list):
        raise ValueError(f"{source_probe_path} must contain a JSON list")
    docs: list[KnowledgeDoc] = []
    failures: list[SourceParseFailure] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{source_probe_path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        parsed_docs, failure = parse_source(raw)
        docs.extend(parsed_docs)
        if failure:
            failures.append(failure)
    return docs, failures


def write_payload(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build source-backed knowledge docs from raw source snapshots.")
    parser.add_argument("--source-probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failures-output", type=Path, default=Path("data/source_parse_failures.json"))
    args = parser.parse_args()

    docs, failures = build_knowledge_from_probe(args.source_probe)
    write_payload(args.output, [doc.model_dump() for doc in docs])
    write_payload(args.failures_output, [failure.model_dump() for failure in failures])
    print(f"wrote {len(docs)} knowledge docs to {args.output}")
    if failures:
        print(f"wrote {len(failures)} parse failures to {args.failures_output}")


def _extract_text(raw: RawSource, raw_path: Path) -> str:
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    suffix = raw_path.suffix.lower()
    content_type = raw.content_type.lower()
    if suffix in {".pdf", ".hwp", ".hwpx"} or any(kind in content_type for kind in ("pdf", "hwp", "hwpx")):
        return document_to_text(raw_path, content_type=raw.content_type)
    return html_to_text(raw_path.read_bytes())


def _chunk_text(text: str, *, chunks_per_source: int, chunk_chars: int = 300) -> list[str]:
    clipped = clip_text(text, max_chars=chunks_per_source * chunk_chars * 2)
    chunks: list[str] = []
    cursor = 0
    while cursor < len(clipped) and len(chunks) < chunks_per_source:
        chunk = clipped[cursor : cursor + chunk_chars].strip()
        if len(chunk) >= 80:
            chunks.append(chunk)
        cursor += chunk_chars
    if not chunks and len(clipped) >= 80:
        chunks.append(clipped)
    if not chunks:
        raise ValueError("extracted text is shorter than 80 characters")
    return chunks


def _parser_name(raw: RawSource) -> str:
    suffix = Path(raw.raw_path).suffix.lower().lstrip(".") or "html"
    return f"{suffix}_source_parse"


if __name__ == "__main__":
    main()
