from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from nlp_term.chat.answer_validation import Task2AnswerValidationResult, validate_task2_answer
from nlp_term.chat.evidence_pack import build_evidence_pack
from nlp_term.chat.llama_server_backend import generate_with_llama_server
from nlp_term.chat.prompts import build_task2_prompt
from nlp_term.chat.router import DOMAINS, route_question
from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import Domain, Task2AnswerEvalGoldExample, Task2FactGoldExample
from nlp_term.validators import file_checksum, read_json


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


def run_task2_vertical_slice(
    *,
    gold_path: Path,
    facts_path: Path,
    knowledge_path: Path,
    output_path: Path,
    generator: Callable[[str], str] | None = None,
    llama_server_url: str = "http://127.0.0.1:8080",
    limit: int | None = None,
    route_label_override_for_test: int | None = None,
) -> dict[str, object]:
    gold_rows = _load_gold(gold_path)
    if limit is not None:
        gold_rows = gold_rows[:limit]
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
        raise ValueError(f"task2-vertical-slice: missing expected fact ids: {missing_fact_ids}")

    knowledge_docs = load_knowledge(knowledge_path)
    docs_by_id = {doc.doc_id: doc for doc in knowledge_docs}
    rows: list[dict[str, object]] = []
    success_count = 0
    generation_failure_count = 0
    validation_pass_count = 0

    for gold in gold_rows:
        route = route_question(gold.user)
        route_label = route_label_override_for_test if route_label_override_for_test is not None else route.label
        route_domain = cast(Domain, DOMAINS[route_label])
        retrieved = rank_docs(gold.user, docs=knowledge_docs, top_k=3)
        retrieved_docs = [docs_by_id[doc.doc_id] for doc in retrieved if doc.doc_id in docs_by_id]
        evidence_pack = build_evidence_pack(
            question=gold.user,
            label=route_label,
            domain=route_domain,
            docs=retrieved_docs,
        )
        prompt = build_task2_prompt(evidence_pack)
        generation_error: str | None = None
        answer = ""

        try:
            if generator is not None:
                answer = generator(prompt)
            else:
                answer = generate_with_llama_server(prompt=prompt, base_url=llama_server_url)
            status = "generated"
        except Exception as exc:
            status = "generation_failed"
            generation_error = str(exc) or exc.__class__.__name__
            generation_failure_count += 1

        if status == "generated":
            validation = validate_task2_answer(
                answer,
                must_not_claim=gold.must_not_claim,
                evidence_texts=[evidence_pack.to_prompt_text()],
            )
            success_count += 1
            validation_pass_count += int(validation.passed)
        else:
            validation = Task2AnswerValidationResult(
                passed=False,
                failures=["generation_failed"],
                answer_chars=0,
                must_not_claim_violations=[],
            )

        rows.append(
            {
                "user": gold.user,
                "status": status,
                "route_label": route_label,
                "route_domain": route_domain,
                "route_used_as": "soft_hint",
                "retrieved_doc_ids": [doc.doc_id for doc in retrieved],
                "retrieved_scores": [doc.score for doc in retrieved],
                "retrieved_label_match_count": sum(1 for doc in retrieved if doc.label == route_label),
                "retrieved_label_mismatch_count": sum(1 for doc in retrieved if doc.label != route_label),
                "evidence_items": [item.model_dump() for item in evidence_pack.items],
                "prompt": prompt,
                "answer": answer,
                "validation": validation.model_dump(),
                "generation_error": generation_error,
            }
        )

    row_count = len(gold_rows)
    metrics = {
        "evaluation_set_type": "task2_gold",
        "dataset_origin": "task2_gold",
        "claim_level": "qualitative_check",
        "evaluation_scope": "task2_vertical_slice",
        "input_path": str(gold_path),
        "input_checksum": file_checksum(gold_path),
        "facts_path": str(facts_path),
        "facts_checksum": file_checksum(facts_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "generation_backend": "injected" if generator is not None else "llama_server",
        "llama_server_url": llama_server_url if generator is None else None,
        "fallback_used": False,
        "row_count": row_count,
        "success_count": success_count,
        "generation_failure_count": generation_failure_count,
        "validation_pass_rate": validation_pass_count / row_count if row_count else 0.0,
        "route_policy": "classifier_label_is_recorded_as_soft_hint_not_hard_filter",
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Task 2 retrieval-to-answer vertical slice.")
    parser.add_argument("--gold", type=Path, default=data_dir() / "gold" / "task2_answer_eval_gold.json")
    parser.add_argument("--facts", type=Path, default=data_dir() / "gold" / "task2_fact_gold.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "task2_vertical_slice.json")
    parser.add_argument("--llama-server-url", default="http://127.0.0.1:8080")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    run_task2_vertical_slice(
        gold_path=args.gold,
        facts_path=args.facts,
        knowledge_path=args.knowledge,
        output_path=args.output,
        llama_server_url=args.llama_server_url,
        limit=args.limit,
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
