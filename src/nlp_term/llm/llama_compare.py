from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.router import route_question
from nlp_term.llm.env_probe import executable_path
from nlp_term.llm.prompt_eval import RETRIEVAL_SYSTEM_PROMPT, SYSTEM_PROMPT, build_context, context_text
from nlp_term.paths import data_dir, model_dir
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.schemas import ChatInput
from nlp_term.validators import read_json


DEFAULT_MODEL_PATH = model_dir() / "generator" / "Qwen3.5-9B-Q4_K_M.gguf"
THROUGHPUT_RE = re.compile(r"\[ Prompt: (?P<prompt>[\d.]+) t/s \| Generation: (?P<generation>[\d.]+) t/s \]")
ANSWER_ANCHORS = (
    "근거를 우선 반영해서 한국어로 짧고 자연스럽게 답하세요.",
    "한국어로 짧고 자연스럽게 답하세요.",
)


def build_no_context_prompt(question: str) -> str:
    return f"{SYSTEM_PROMPT}\n\n질문: {question}\n\n한국어로 짧고 자연스럽게 답하세요.\n\n답변:"


def build_retrieval_prompt(question: str, context: str) -> str:
    return (
        f"{RETRIEVAL_SYSTEM_PROMPT}\n\n"
        f"질문: {question}\n\n"
        f"근거:\n{context}\n\n"
        "근거를 우선 반영해서 한국어로 짧고 자연스럽게 답하세요.\n\n답변:"
    )


def extract_answer(stdout: str, prompt: str) -> str:
    text = stdout.replace("\r\n", "\n")
    if "[ Prompt:" in text:
        text = text.split("[ Prompt:", 1)[0]
    if prompt in text:
        text = text.split(prompt, 1)[-1]
    elif "\n> " in text:
        text = text.split("\n> ")[-1]
    for anchor in ANSWER_ANCHORS:
        if anchor in text:
            text = text.rsplit(anchor, 1)[-1]
            break
    if "본문:" in text and "(truncated)" in text:
        text = text.rsplit("(truncated)", 1)[-1]
    for prefix in ("Loading model...", "Exiting..."):
        text = text.replace(prefix, "")
    if "답변:" in text:
        text = text.rsplit("답변:", 1)[-1]
    return text.strip()


def run_llama(
    llama_path: str,
    model_path: Path,
    prompt: str,
    *,
    context_size: int,
    max_new_tokens: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as prompt_file:
        prompt_file.write(prompt)
        prompt_path = Path(prompt_file.name)
    command = [
        llama_path,
        "-m",
        str(model_path),
        "-f",
        str(prompt_path),
        "-n",
        str(max_new_tokens),
        "-c",
        str(context_size),
        "-ngl",
        "auto",
        "--cache-type-k",
        "q8_0",
        "--cache-type-v",
        "q8_0",
        "--temp",
        "0.2",
        "--no-display-prompt",
        "--single-turn",
        "--simple-io",
        "--reasoning",
        "off",
        "--reasoning-budget",
        "0",
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    elapsed = time.perf_counter() - started
    prompt_path.unlink(missing_ok=True)
    throughput_match = THROUGHPUT_RE.search(completed.stdout)
    return {
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "answer": extract_answer(completed.stdout, prompt),
        "prompt_tokens_per_second": float(throughput_match.group("prompt")) if throughput_match else None,
        "generation_tokens_per_second": float(throughput_match.group("generation")) if throughput_match else None,
        "contains_thinking_marker": "[Start thinking]" in completed.stdout or "<think>" in completed.stdout,
    }


def compare_generation(
    input_path: Path,
    knowledge_path: Path,
    output_path: Path,
    *,
    model_path: Path,
    context_size: int,
    max_new_tokens: int,
    timeout_seconds: int,
    limit: int | None,
) -> dict[str, Any]:
    llama_path = executable_path("llama-cli")
    if llama_path is None:
        raise RuntimeError("llama-cli was not found")
    if not model_path.exists():
        raise FileNotFoundError(model_path)

    inputs = [ChatInput.model_validate(row) for row in read_json(input_path)]
    if limit is not None:
        inputs = inputs[:limit]
    knowledge_docs = load_knowledge(knowledge_path)
    rows = []
    for item in inputs:
        route = route_question(item.user)
        selected_docs = build_context(item.user, knowledge_docs, top_k=3, max_doc_chars=700)
        context = context_text(selected_docs).replace("\ufffd", " ")
        no_context_result = run_llama(
            llama_path,
            model_path,
            build_no_context_prompt(item.user),
            context_size=context_size,
            max_new_tokens=max_new_tokens,
            timeout_seconds=timeout_seconds,
        )
        retrieval_result = run_llama(
            llama_path,
            model_path,
            build_retrieval_prompt(item.user, context),
            context_size=context_size,
            max_new_tokens=max_new_tokens,
            timeout_seconds=timeout_seconds,
        )
        rows.append(
            {
                "user": item.user,
                "route_label": route.label,
                "route_domain": route.domain,
                "retrieved_doc_ids": [doc.doc_id for doc in selected_docs],
                "deterministic_answer": compose_answer(route, knowledge_path=knowledge_path),
                "no_context": no_context_result,
                "retrieval_context": retrieval_result,
            }
        )

    output = {
        "evaluation_scope": "task2_llama_cpp_generation_compare",
        "backend": "llama.cpp",
        "model_path": str(model_path),
        "model_quantization": "Q4_K_M GGUF",
        "kv_cache": {"k": "q8_0", "v": "q8_0", "note": "nearest llama.cpp KV option, not FP8"},
        "context_size": context_size,
        "max_new_tokens": max_new_tokens,
        "input_path": str(input_path),
        "knowledge_path": str(knowledge_path),
        "row_count": len(rows),
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare llama.cpp no-context and retrieval-context Task 2 outputs.")
    parser.add_argument("--input", type=Path, default=data_dir() / "test_chat.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "llama_task2_generation_compare.json")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--context-size", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = compare_generation(
        args.input,
        args.knowledge,
        args.output,
        model_path=args.model,
        context_size=args.context_size,
        max_new_tokens=args.max_new_tokens,
        timeout_seconds=args.timeout_seconds,
        limit=args.limit,
    )
    summary = {
        "row_count": output["row_count"],
        "no_context_returncodes": [row["no_context"]["returncode"] for row in output["rows"]],
        "retrieval_context_returncodes": [row["retrieval_context"]["returncode"] for row in output["rows"]],
        "no_context_generation_tps": [row["no_context"]["generation_tokens_per_second"] for row in output["rows"]],
        "retrieval_context_generation_tps": [
            row["retrieval_context"]["generation_tokens_per_second"] for row in output["rows"]
        ],
    }
    print(f"wrote {args.output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
