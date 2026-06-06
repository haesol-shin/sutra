from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from nlp_term.paths import data_dir
from nlp_term.prepare.cls_data import build_classification_seed
from nlp_term.prepare.knowledge import build_seed_knowledge
from nlp_term.prepare.qa_data import build_qa_seed
from nlp_term.schemas import KnowledgeDoc


def dump_rows(path: Path, rows: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump([row.model_dump() for row in rows], file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_existing_knowledge(path: Path) -> list[KnowledgeDoc] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    docs = [KnowledgeDoc.model_validate(row) for row in payload]
    if any(doc.metadata.get("generation_method") == "source_parse" for doc in docs):
        return docs
    return None


def build_all(output_dir: Path) -> None:
    knowledge_path = output_dir / "knowledge_seed.json"
    docs = load_existing_knowledge(knowledge_path) or build_seed_knowledge()
    cls_examples, audits = build_classification_seed(docs)
    qa_examples = build_qa_seed(docs)
    dump_rows(knowledge_path, docs)
    dump_rows(output_dir / "cls_train_seed.json", cls_examples)
    dump_rows(output_dir / "label_audit_seed.json", audits)
    dump_rows(output_dir / "qa_seed.json", qa_examples)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic seed datasets.")
    parser.add_argument("--output-dir", type=Path, default=data_dir())
    args = parser.parse_args()
    build_all(args.output_dir)
    print(f"wrote seed datasets to {args.output_dir}")


if __name__ == "__main__":
    main()
