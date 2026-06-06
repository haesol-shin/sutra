from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import METADATA_FIELDS, rank_docs
from nlp_term.schemas import KnowledgeDoc, QAExample, RetrievedDoc


EVIDENCE_RE = re.compile(r"'([^']+)'")


def file_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_qa(path: Path) -> list[QAExample]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return [QAExample.model_validate(row) for row in payload]


def _token_hits(excerpt: str, body: str) -> int:
    return sum(1 for token in excerpt.split() if len(token) > 1 and token in body)


def _best_evidence_hit(row: QAExample, docs: list[KnowledgeDoc]) -> int:
    excerpts = EVIDENCE_RE.findall(row.model)
    if not excerpts:
        return 0
    return max((_token_hits(excerpt, doc.body) for excerpt in excerpts for doc in docs), default=0)


def _count_rate(hits: int, total: int) -> float:
    return hits / max(total, 1)


def _per_label_rates(hits: Counter[int], totals: Counter[int]) -> dict[str, float]:
    return {str(label): _count_rate(hits[label], totals[label]) for label in range(5)}


def _is_curriculum_doc(doc_id: str) -> bool:
    return doc_id.startswith("graduation_curriculum_pdf")


def _doc_ids(rows: list[RetrievedDoc]) -> list[str]:
    return [row.doc_id for row in rows]


def evaluate_retrieval(knowledge_path: Path, qa_path: Path) -> dict[str, object]:
    docs = load_knowledge(knowledge_path)
    docs_by_id = {doc.doc_id: doc for doc in docs}
    qa_rows = load_qa(qa_path)
    top1_label_hits = 0
    top3_source_hits = 0
    top3_doc_id_hits = 0
    retrieved_evidence_hits = 0
    expected_evidence_hits = 0
    per_label_totals: Counter[int] = Counter()
    per_label_top1_label_hits: Counter[int] = Counter()
    per_label_top3_source_hits: Counter[int] = Counter()
    per_label_top3_doc_id_hits: Counter[int] = Counter()
    per_label_failure_counts: Counter[int] = Counter()
    graduation_total = 0
    graduation_top3_source_hits = 0
    graduation_top3_doc_id_hits = 0
    graduation_curriculum_total = 0
    graduation_curriculum_hits = 0
    alignment_failures: list[dict[str, object]] = []
    examples: list[dict[str, object]] = []

    for row in qa_rows:
        ranked = rank_docs(row.user, docs=docs, top_k=3)
        top1 = ranked[0] if ranked else None
        top3_doc_ids = {doc.doc_id for doc in ranked}
        top3_docs = [docs_by_id[doc.doc_id] for doc in ranked if doc.doc_id in docs_by_id]
        expected_doc = docs_by_id.get(row.source_doc_id)
        label_hit = top1 is not None and top1.label == row.label
        doc_id_hit = row.source_doc_id in top3_doc_ids
        source_hit = expected_doc is not None and any(
            docs_by_id[doc.doc_id].source_id == expected_doc.source_id
            for doc in ranked
            if doc.doc_id in docs_by_id
        )
        retrieved_evidence_hit = _best_evidence_hit(row, top3_docs)
        expected_evidence_hit = _best_evidence_hit(row, [expected_doc] if expected_doc else [])
        retrieved_evidence_aligned = retrieved_evidence_hit >= 6
        expected_evidence_aligned = expected_evidence_hit >= 6
        per_label_totals[row.label] += 1
        top1_label_hits += int(label_hit)
        top3_source_hits += int(source_hit)
        top3_doc_id_hits += int(doc_id_hit)
        retrieved_evidence_hits += int(retrieved_evidence_aligned)
        expected_evidence_hits += int(expected_evidence_aligned)
        per_label_top1_label_hits[row.label] += int(label_hit)
        per_label_top3_source_hits[row.label] += int(source_hit)
        per_label_top3_doc_id_hits[row.label] += int(doc_id_hit)
        if row.label == 0:
            graduation_total += 1
            graduation_top3_source_hits += int(source_hit)
            graduation_top3_doc_id_hits += int(doc_id_hit)
            if _is_curriculum_doc(row.source_doc_id):
                graduation_curriculum_total += 1
                graduation_curriculum_hits += int(any(_is_curriculum_doc(doc_id) for doc_id in top3_doc_ids))
        if not label_hit or not source_hit:
            per_label_failure_counts[row.label] += 1
        if not retrieved_evidence_aligned:
            alignment_failures.append(
                {
                    "user": row.user,
                    "label": row.label,
                    "source_doc_id": row.source_doc_id,
                "top3_doc_ids": _doc_ids(ranked),
                "retrieved_evidence_token_hits": retrieved_evidence_hit,
                "expected_evidence_token_hits": expected_evidence_hit,
                }
            )
        examples.append(
            {
                "user": row.user,
                "label": row.label,
                "source_doc_id": row.source_doc_id,
                "top1_doc_id": top1.doc_id if top1 else None,
                "top1_label": top1.label if top1 else None,
                "top3_doc_ids": _doc_ids(ranked),
                "top1_label_hit": label_hit,
                "top3_source_hit": source_hit,
                "top3_doc_id_hit": doc_id_hit,
                "retrieved_evidence_aligned": retrieved_evidence_aligned,
                "expected_evidence_aligned": expected_evidence_aligned,
                "retrieved_evidence_token_hits": retrieved_evidence_hit,
                "expected_evidence_token_hits": expected_evidence_hit,
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
        "top3_doc_id_hit_rate": top3_doc_id_hits / total,
        "retrieved_evidence_alignment_rate": retrieved_evidence_hits / total,
        "expected_evidence_alignment_rate": expected_evidence_hits / total,
        "per_label_row_counts": {str(label): per_label_totals[label] for label in range(5)},
        "per_label_top1_label_accuracy": _per_label_rates(per_label_top1_label_hits, per_label_totals),
        "per_label_top3_source_hit_rate": _per_label_rates(per_label_top3_source_hits, per_label_totals),
        "per_label_top3_doc_id_hit_rate": _per_label_rates(per_label_top3_doc_id_hits, per_label_totals),
        "graduation_top3_source_hit_rate": _count_rate(graduation_top3_source_hits, graduation_total),
        "graduation_top3_doc_id_hit_rate": _count_rate(graduation_top3_doc_id_hits, graduation_total),
        "graduation_curriculum_pdf_hit_rate": _count_rate(graduation_curriculum_hits, graduation_curriculum_total),
        "graduation_row_count": graduation_total,
        "graduation_curriculum_row_count": graduation_curriculum_total,
        "per_label_failure_counts": {str(label): per_label_failure_counts[label] for label in range(5)},
        "alignment_failures": alignment_failures,
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
