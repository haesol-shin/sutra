from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.router import route_question
from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import ChatInput, KnowledgeDoc
from nlp_term.validators import read_json


DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
SYSTEM_PROMPT = (
    "너는 충남대학교 학생을 돕는 캠퍼스 챗봇이다. "
    "질문 의도에 맞게 한국어로 자연스럽고 간결하게 답한다."
)
RETRIEVAL_SYSTEM_PROMPT = (
    "너는 충남대학교 학생을 돕는 캠퍼스 챗봇이다. "
    "아래 근거를 우선 사용하되, 답변은 자연스럽게 작성한다. "
    "근거에 없는 세부사항은 단정하지 않는다."
)


def load_tokenizer(model_name: str) -> Any:
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Install the llm extra first: uv sync --extra llm") from exc
    return AutoTokenizer.from_pretrained(model_name, trust_remote_code=False)


def render_chat(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def count_tokens(tokenizer: Any, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def build_context(question: str, docs: list[KnowledgeDoc], *, top_k: int, max_doc_chars: int) -> list[KnowledgeDoc]:
    docs_by_id = {doc.doc_id: doc for doc in docs}
    route = route_question(question)
    ranked = rank_docs(question, docs=docs, top_k=max(top_k * 2, top_k))
    selected: list[KnowledgeDoc] = []
    for row in ranked:
        doc = docs_by_id[row.doc_id]
        if doc.label != route.label:
            continue
        clipped = doc.model_copy(update={"body": doc.body[:max_doc_chars]})
        selected.append(clipped)
        if len(selected) >= top_k:
            break
    return selected


def context_text(docs: list[KnowledgeDoc]) -> str:
    if not docs:
        return "근거 없음"
    chunks = []
    for index, doc in enumerate(docs, start=1):
        chunks.append(f"[{index}] {doc.title}\nURL: {doc.source_url}\n본문: {doc.body}")
    return "\n\n".join(chunks)


def evaluate_prompts(
    input_path: Path,
    knowledge_path: Path,
    *,
    model_name: str,
    context_windows: list[int],
    max_new_tokens: int,
    top_k: int,
    max_doc_chars: int,
) -> dict[str, Any]:
    tokenizer = load_tokenizer(model_name)
    inputs = [ChatInput.model_validate(row) for row in read_json(input_path)]
    docs = load_knowledge(knowledge_path)
    rows: list[dict[str, Any]] = []

    for item in inputs:
        route = route_question(item.user)
        selected_docs = build_context(item.user, docs, top_k=top_k, max_doc_chars=max_doc_chars)
        no_context_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": item.user},
        ]
        retrieval_messages = [
            {"role": "system", "content": RETRIEVAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"질문: {item.user}\n\n근거:\n{context_text(selected_docs)}",
            },
        ]
        no_context_prompt = render_chat(tokenizer, no_context_messages)
        retrieval_prompt = render_chat(tokenizer, retrieval_messages)
        no_context_tokens = count_tokens(tokenizer, no_context_prompt)
        retrieval_context_tokens = count_tokens(tokenizer, retrieval_prompt)
        rows.append(
            {
                "user": item.user,
                "route_label": route.label,
                "route_domain": route.domain,
                "retrieved_doc_count": len(selected_docs),
                "retrieved_doc_ids": [doc.doc_id for doc in selected_docs],
                "retrieved_source_urls": [doc.source_url for doc in selected_docs],
                "no_context_prompt_tokens": no_context_tokens,
                "retrieval_context_prompt_tokens": retrieval_context_tokens,
                "deterministic_answer_chars": len(compose_answer(route, knowledge_path=knowledge_path)),
                "fits": {
                    str(window): {
                        "no_context": no_context_tokens + max_new_tokens <= window,
                        "retrieval_context": retrieval_context_tokens + max_new_tokens <= window,
                    }
                    for window in context_windows
                },
            }
        )

    no_context_counts = [row["no_context_prompt_tokens"] for row in rows]
    retrieval_counts = [row["retrieval_context_prompt_tokens"] for row in rows]
    return {
        "evaluation_scope": "task2_prompt_preflight_no_inference",
        "model_name": model_name,
        "input_path": str(input_path),
        "knowledge_path": str(knowledge_path),
        "row_count": len(rows),
        "top_k": top_k,
        "max_doc_chars": max_doc_chars,
        "max_new_tokens": max_new_tokens,
        "context_windows": context_windows,
        "summary": {
            "no_context_max_prompt_tokens": max(no_context_counts, default=0),
            "retrieval_context_max_prompt_tokens": max(retrieval_counts, default=0),
            "no_context_avg_prompt_tokens": mean(no_context_counts) if no_context_counts else 0,
            "retrieval_context_avg_prompt_tokens": mean(retrieval_counts) if retrieval_counts else 0,
            "retrieval_has_source_rate": sum(1 for row in rows if row["retrieved_doc_count"] > 0)
            / max(len(rows), 1),
        },
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preflight Task 2 prompts for local LLM context budgets.")
    parser.add_argument("--input", type=Path, default=data_dir() / "test_chat.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "task2_prompt_preflight.json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--context-window", type=int, action="append", default=[2048, 4096])
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-doc-chars", type=int, default=700)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    metrics = evaluate_prompts(
        args.input,
        args.knowledge,
        model_name=args.model,
        context_windows=args.context_window,
        max_new_tokens=args.max_new_tokens,
        top_k=args.top_k,
        max_doc_chars=args.max_doc_chars,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(json.dumps(metrics["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
