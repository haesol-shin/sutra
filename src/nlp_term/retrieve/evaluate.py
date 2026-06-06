from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import METADATA_FIELDS, rank_docs
from nlp_term.schemas import QAExample


def file_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_qa(path: Path) -> list[QAExample]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return [QAExample.model_validate(row) for row in payload]


def evaluate_retrieval(knowledge_path: Path, qa_path: Path) -> dict[str, object]:
    docs = load_knowledge(knowledge_path)
    qa_rows = load_qa(qa_path)
    top1_label_hits = 0
    top3_source_hits = 0
    per_label_failure_counts: Counter[int] = Counter()
    examples: list[dict[str, object]] = []

    for row in qa_rows:
        ranked = rank_docs(row.user, docs=docs, top_k=3)
        top1 = ranked[0] if ranked else None
        top3_doc_ids = {doc.doc_id for doc in ranked}
        label_hit = top1 is not None and top1.label == row.label
        source_hit = row.source_doc_id in top3_doc_ids
        top1_label_hits += int(label_hit)
        top3_source_hits += int(source_hit)
        if not label_hit or not source_hit:
            per_label_failure_counts[row.label] += 1
        examples.append(
            {
                "user": row.user,
                "label": row.label,
                "source_doc_id": row.source_doc_id,
                "top1_doc_id": top1.doc_id if top1 else None,
                "top1_label": top1.label if top1 else None,
                "top3_doc_ids": list(top3_doc_ids),
                "top1_label_hit": label_hit,
                "top3_source_hit": source_hit,
            }
        )

    total = max(len(qa_rows), 1)
    return {
        "evaluation_scope": "qa_seed_retrieval_sanity",
        "retrieval_strategy": "lexical_metadata_label_hint",
        "metadata_fields": list(METADATA_FIELDS),
        "knowledge_path": str(knowledge_path),
        "qa_path": str(qa_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "qa_checksum": file_checksum(qa_path),
        "row_count": len(qa_rows),
        "top1_label_accuracy": top1_label_hits / total,
        "top3_source_hit_rate": top3_source_hits / total,
        "per_label_failure_counts": {str(label): per_label_failure_counts[label] for label in range(5)},
        "examples": examples,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate deterministic retrieval over QA seed rows.")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--qa", type=Path, default=data_dir() / "qa_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "retrieval_metrics.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    metrics = evaluate_retrieval(args.knowledge, args.qa)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
