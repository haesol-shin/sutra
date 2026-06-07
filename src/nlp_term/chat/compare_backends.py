from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nlp_term.chat.evaluate_gold import evaluate_task2_gold_answers
from nlp_term.chat.llama_backend import llama_backend_available
from nlp_term.llm.llama_compare import DEFAULT_MODEL_PATH
from nlp_term.paths import data_dir, model_dir
from nlp_term.validators import file_checksum


def _run_metrics_subset(metrics: dict[str, object]) -> dict[str, object]:
    return {
        "status": "ran",
        "backend_requested": metrics["backend_requested"],
        "backend_used": metrics["backend_used"],
        "fallback_used": metrics["fallback_used"],
        "fallback_reason": metrics["fallback_reason"],
        "row_count": metrics["row_count"],
        "fact_recall": metrics["fact_recall"],
        "must_not_claim_violation_count": metrics["must_not_claim_violation_count"],
        "source_hint_rate": metrics["source_hint_rate"],
        "naturalness_heuristic_pass_rate": metrics["naturalness_heuristic_pass_rate"],
        "answer_length_stats": metrics["answer_length_stats"],
    }


def _unavailable_llama_run(model_path: Path) -> dict[str, object]:
    return {
        "status": "unavailable",
        "backend_requested": "llama",
        "backend_used": None,
        "fallback_used": False,
        "fallback_reason": None,
        "row_count": 0,
        "fact_recall": None,
        "must_not_claim_violation_count": None,
        "source_hint_rate": None,
        "naturalness_heuristic_pass_rate": None,
        "answer_length_stats": None,
        "unavailable_reason": f"llama backend unavailable for model path: {model_path}",
    }


def _failed_llama_run(model_path: Path, error: Exception) -> dict[str, object]:
    return {
        "status": "failed",
        "backend_requested": "llama",
        "backend_used": None,
        "fallback_used": False,
        "fallback_reason": None,
        "row_count": 0,
        "fact_recall": None,
        "must_not_claim_violation_count": None,
        "source_hint_rate": None,
        "naturalness_heuristic_pass_rate": None,
        "answer_length_stats": None,
        "model_path": str(model_path),
        "error_type": type(error).__name__,
        "error": str(error),
    }


def compare_task2_backends(
    *,
    gold_path: Path,
    facts_path: Path,
    knowledge_path: Path,
    output_path: Path,
    model_path: Path = DEFAULT_MODEL_PATH,
    llama_limit: int = 3,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    deterministic_output = output_path.with_name(f"{output_path.stem}.deterministic.json")
    deterministic_metrics = evaluate_task2_gold_answers(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=deterministic_output,
        backend="deterministic",
        model_path=model_path,
    )

    llama_available = llama_backend_available(model_path)
    if not llama_available:
        llama_run = _unavailable_llama_run(model_path)
    else:
        llama_output = output_path.with_name(f"{output_path.stem}.llama.json")
        try:
            llama_metrics = evaluate_task2_gold_answers(
                gold_path=gold_path,
                facts_path=facts_path,
                knowledge_path=knowledge_path,
                output_path=llama_output,
                backend="llama",
                model_path=model_path,
                limit=llama_limit,
            )
            llama_run = _run_metrics_subset(llama_metrics)
            llama_run["llama_limit"] = llama_limit
        except Exception as error:  # noqa: BLE001 - evidence should capture local backend failures.
            llama_run = _failed_llama_run(model_path, error)

    backend_runs = [_run_metrics_subset(deterministic_metrics), llama_run]
    comparison = {
        "evaluation_scope": "task2_backend_comparison",
        "evaluation_set_type": "task2_gold",
        "dataset_origin": "task2_gold",
        "claim_level": "qualitative_check",
        "input_path": str(gold_path),
        "input_checksum": file_checksum(gold_path),
        "facts_path": str(facts_path),
        "facts_checksum": file_checksum(facts_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "model_path": str(model_path),
        "model_checksum": file_checksum(model_path) if model_path.exists() else None,
        "llama_backend_available": llama_available,
        "llama_limit": llama_limit,
        "backend_count": len(backend_runs),
        "backend_runs": backend_runs,
        "llama_quality_claim_allowed": llama_run["status"] == "ran" and llama_run["fallback_used"] is False,
        "interpretation_allowed": "backend_separation_precheck_not_final_chatbot_performance",
    }
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare deterministic and llama Task 2 backend evidence.")
    parser.add_argument("--gold", type=Path, default=data_dir() / "gold" / "task2_answer_eval_gold.json")
    parser.add_argument("--facts", type=Path, default=data_dir() / "gold" / "task2_fact_gold.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "task2_backend_comparison.json")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--llama-limit", type=int, default=3)
    args = parser.parse_args()
    comparison = compare_task2_backends(
        gold_path=args.gold,
        facts_path=args.facts,
        knowledge_path=args.knowledge,
        output_path=args.output,
        model_path=args.model,
        llama_limit=args.llama_limit,
    )
    print(f"wrote {args.output}")
    print(json.dumps({"backend_runs": comparison["backend_runs"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
