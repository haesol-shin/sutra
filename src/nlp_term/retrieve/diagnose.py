from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import Task2FactGoldExample
from nlp_term.validators import file_checksum, read_json


def _load_facts(path: Path) -> list[Task2FactGoldExample]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [Task2FactGoldExample.model_validate(row) for row in payload]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _per_label_rate(hits: Counter[int], totals: Counter[int]) -> dict[str, float]:
    return {str(label): _rate(hits[label], totals[label]) for label in range(5)}


def _query_for_fact(fact: Task2FactGoldExample) -> str:
    return f"{fact.claim} {fact.evidence_quote}"


def diagnose_retrieval_bottlenecks(
    *,
    facts_path: Path,
    knowledge_path: Path,
    output_path: Path,
    top_k: int = 3,
) -> dict[str, object]:
    facts = _load_facts(facts_path)
    docs = load_knowledge(knowledge_path)
    docs_by_id = {doc.doc_id: doc for doc in docs}
    total = len(facts)
    hit_at_1_count = 0
    hit_at_k_count = 0
    source_coverage_gap_count = 0
    ranking_failure_count = 0
    per_label_totals: Counter[int] = Counter()
    per_label_hit_at_1: Counter[int] = Counter()
    per_label_hit_at_k: Counter[int] = Counter()
    per_label_coverage_gaps: Counter[int] = Counter()
    per_label_ranking_failures: Counter[int] = Counter()
    missing_source_doc_ids: list[str] = []
    rows: list[dict[str, object]] = []

    for fact in facts:
        query = _query_for_fact(fact)
        ranked = rank_docs(query, docs=docs, top_k=top_k)
        top_doc_id = ranked[0].doc_id if ranked else None
        top_doc_ids = [doc.doc_id for doc in ranked]
        expected_doc_exists = fact.source_doc_id in docs_by_id
        hit_at_1 = top_doc_id == fact.source_doc_id
        hit_at_k = fact.source_doc_id in top_doc_ids
        if not expected_doc_exists:
            bottleneck_type = "source_coverage_gap"
            source_coverage_gap_count += 1
            missing_source_doc_ids.append(fact.source_doc_id)
            per_label_coverage_gaps[fact.label] += 1
        elif not hit_at_k:
            bottleneck_type = "ranking_failure"
            ranking_failure_count += 1
            per_label_ranking_failures[fact.label] += 1
        else:
            bottleneck_type = "none"

        per_label_totals[fact.label] += 1
        per_label_hit_at_1[fact.label] += int(hit_at_1)
        per_label_hit_at_k[fact.label] += int(hit_at_k)
        hit_at_1_count += int(hit_at_1)
        hit_at_k_count += int(hit_at_k)
        rows.append(
            {
                "fact_id": fact.fact_id,
                "label": fact.label,
                "answerable_scope": fact.answerable_scope,
                "source_doc_id": fact.source_doc_id,
                "source_doc_exists": expected_doc_exists,
                "query": query,
                "top_doc_ids": top_doc_ids,
                "hit_at_1": hit_at_1,
                "hit_at_k": hit_at_k,
                "bottleneck_type": bottleneck_type,
            }
        )

    report = {
        "evaluation_scope": "task2_fact_retrieval_bottleneck",
        "evaluation_set_type": "task2_gold",
        "dataset_origin": "task2_gold",
        "claim_level": "sanity",
        "retrieval_strategy": "lexical_metadata_label_hint",
        "input_path": str(facts_path),
        "input_checksum": file_checksum(facts_path),
        "facts_path": str(facts_path),
        "facts_checksum": file_checksum(facts_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "top_k": top_k,
        "fact_count": total,
        "knowledge_doc_count": len(docs),
        "hit_at_1": _rate(hit_at_1_count, total),
        "hit_at_3": _rate(hit_at_k_count, total) if top_k == 3 else _rate(hit_at_k_count, total),
        "source_coverage_gap_count": source_coverage_gap_count,
        "ranking_failure_count": ranking_failure_count,
        "missing_source_doc_ids": sorted(missing_source_doc_ids),
        "per_label_fact_counts": {str(label): per_label_totals[label] for label in range(5)},
        "per_label_hit_at_1": _per_label_rate(per_label_hit_at_1, per_label_totals),
        "per_label_hit_at_k": _per_label_rate(per_label_hit_at_k, per_label_totals),
        "per_label_source_coverage_gap_counts": {
            str(label): per_label_coverage_gaps[label] for label in range(5)
        },
        "per_label_ranking_failure_counts": {
            str(label): per_label_ranking_failures[label] for label in range(5)
        },
        "interpretation_allowed": "retrieval_diagnostic_not_final_rag_performance",
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose retrieval bottlenecks over Task 2 fact gold.")
    parser.add_argument("--facts", type=Path, default=data_dir() / "gold" / "task2_fact_gold.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "retrieval_bottleneck_diagnosis.json")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    diagnose_retrieval_bottlenecks(
        facts_path=args.facts,
        knowledge_path=args.knowledge,
        output_path=args.output,
        top_k=args.top_k,
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
