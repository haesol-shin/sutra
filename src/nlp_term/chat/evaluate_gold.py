from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean

from nlp_term.chat.batch import Backend, _select_backend
from nlp_term.chat.composer import compose_answer
from nlp_term.chat.llama_backend import generate_llama_answer
from nlp_term.chat.router import route_question
from nlp_term.llm.llama_compare import DEFAULT_MODEL_PATH
from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import Task2AnswerEvalGoldExample, Task2FactGoldExample
from nlp_term.validators import file_checksum, read_json


INTERNAL_ID_RE = re.compile(r"(chunk_\d+|doc_\d+|source\s+\d+)", re.IGNORECASE)


def _load_gold(path: Path) -> list[Task2AnswerEvalGoldExample]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [Task2AnswerEvalGoldExample.model_validate(row) for row in payload]


def _load_facts(path: Path) -> dict[str, Task2FactGoldExample]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    facts = [Task2FactGoldExample.model_validate(row) for row in payload]
    return {fact.fact_id: fact for fact in facts}


def _naturalness_failures(answer: str) -> list[str]:
    stripped = answer.strip()
    failures: list[str] = []
    if len(stripped) < 30:
        failures.append("answer_too_short")
    if stripped.startswith(("{", "[")):
        failures.append("raw_json_or_template_text")
    if INTERNAL_ID_RE.search(stripped):
        failures.append("internal_id_exposed")
    if "fallback" in stripped.lower() or "system" in stripped.lower():
        failures.append("fallback_or_system_wording")
    if stripped.count("'") >= 4 and len(stripped) < 120:
        failures.append("mostly_quoted_evidence")
    return failures


def _answer_covers_fact(answer: str, retrieved_doc_ids: set[str], fact: Task2FactGoldExample) -> bool:
    return (
        fact.source_doc_id in retrieved_doc_ids
        or fact.evidence_quote in answer
        or fact.claim in answer
    )


def evaluate_task2_gold_answers(
    *,
    gold_path: Path,
    facts_path: Path,
    knowledge_path: Path,
    output_path: Path,
    backend: Backend = "deterministic",
    model_path: Path = DEFAULT_MODEL_PATH,
) -> dict[str, object]:
    gold_rows = _load_gold(gold_path)
    facts = _load_facts(facts_path)
    missing_fact_ids = sorted(
        {
            fact_id
            for row in gold_rows
            for fact_id in row.expected_fact_ids
            if fact_id not in facts
        }
    )
    if missing_fact_ids:
        raise ValueError(f"task2-answer-eval: missing expected fact ids: {missing_fact_ids}")

    knowledge_docs = load_knowledge(knowledge_path)
    selected_backend, fallback_used, fallback_reason = _select_backend(backend, model_path)
    rows: list[dict[str, object]] = []
    total_expected_facts = 0
    total_matched_facts = 0
    must_not_claim_violation_count = 0
    source_hint_count = 0
    naturalness_pass_count = 0
    answer_lengths: list[int] = []

    for gold in gold_rows:
        route = route_question(gold.user)
        if selected_backend == "llama":
            answer = generate_llama_answer(route, knowledge_path=knowledge_path, model_path=model_path)
        else:
            answer = compose_answer(route, knowledge_path=knowledge_path)
        retrieved = rank_docs(gold.user, docs=knowledge_docs, top_k=3)
        retrieved_doc_ids = {doc.doc_id for doc in retrieved}
        retrieved_urls = {doc.source_url for doc in retrieved}
        expected_facts = [facts[fact_id] for fact_id in gold.expected_fact_ids]
        matched_fact_ids = [
            fact.fact_id
            for fact in expected_facts
            if _answer_covers_fact(answer, retrieved_doc_ids, fact)
        ]
        violations = [claim for claim in gold.must_not_claim if claim and claim in answer]
        naturalness_failures = _naturalness_failures(answer)
        source_hint = any(url and url in answer for url in retrieved_urls) or "http" in answer

        total_expected_facts += len(expected_facts)
        total_matched_facts += len(matched_fact_ids)
        must_not_claim_violation_count += len(violations)
        source_hint_count += int(source_hint)
        naturalness_pass_count += int(not naturalness_failures)
        answer_lengths.append(len(answer))
        rows.append(
            {
                "user": gold.user,
                "answer": answer,
                "expected_fact_ids": gold.expected_fact_ids,
                "matched_fact_ids": matched_fact_ids,
                "missing_fact_ids": [
                    fact_id for fact_id in gold.expected_fact_ids if fact_id not in matched_fact_ids
                ],
                "must_not_claim_violations": violations,
                "retrieved_doc_ids": [doc.doc_id for doc in retrieved],
                "retrieved_source_urls": [doc.source_url for doc in retrieved],
                "source_hint": source_hint,
                "naturalness_heuristic_pass": not naturalness_failures,
                "naturalness_failures": naturalness_failures,
                "answer_chars": len(answer),
            }
        )

    row_count = len(gold_rows)
    metrics = {
        "evaluation_set_type": "task2_gold",
        "dataset_origin": "task2_gold",
        "claim_level": "qualitative_check",
        "evaluation_scope": "task2_answer_gold_eval",
        "input_path": str(gold_path),
        "input_checksum": file_checksum(gold_path),
        "facts_path": str(facts_path),
        "facts_checksum": file_checksum(facts_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "backend_requested": backend,
        "backend_used": selected_backend,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "model_path": str(model_path),
        "model_checksum": file_checksum(model_path) if model_path.exists() else None,
        "row_count": row_count,
        "expected_fact_count": total_expected_facts,
        "matched_fact_count": total_matched_facts,
        "fact_recall": total_matched_facts / total_expected_facts if total_expected_facts else 0.0,
        "must_not_claim_violation_count": must_not_claim_violation_count,
        "source_hint_rate": source_hint_count / row_count if row_count else 0.0,
        "naturalness_heuristic_pass_rate": naturalness_pass_count / row_count if row_count else 0.0,
        "answer_length_stats": {
            "min": min(answer_lengths) if answer_lengths else 0,
            "max": max(answer_lengths) if answer_lengths else 0,
            "mean": mean(answer_lengths) if answer_lengths else 0,
        },
        "interpretation_allowed": "qualitative_precheck_not_final_chatbot_performance",
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Task 2 answers against gold fact prompts.")
    parser.add_argument("--gold", type=Path, default=data_dir() / "gold" / "task2_answer_eval_gold.json")
    parser.add_argument("--facts", type=Path, default=data_dir() / "gold" / "task2_fact_gold.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "task2_gold_answer_eval.json")
    parser.add_argument("--backend", choices=["auto", "llama", "deterministic"], default="deterministic")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    evaluate_task2_gold_answers(
        gold_path=args.gold,
        facts_path=args.facts,
        knowledge_path=args.knowledge,
        output_path=args.output,
        backend=args.backend,
        model_path=args.model,
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
