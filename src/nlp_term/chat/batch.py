from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.llama_backend import generate_llama_answer, llama_backend_available
from nlp_term.chat.router import route_question
from nlp_term.llm.llama_compare import DEFAULT_MODEL_PATH
from nlp_term.paths import default_input_path, default_output_path
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import ChatInput, ChatOutput
from nlp_term.validators import read_json, write_json


Backend = Literal["auto", "llama", "deterministic"]


def _file_checksum(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256(path.read_bytes()).hexdigest()


def _provenance_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.provenance{output_path.suffix}")


def _select_backend(backend: Backend, model_path: Path) -> tuple[Literal["llama", "deterministic"], bool, str | None]:
    available = llama_backend_available(model_path)
    if backend == "llama":
        return "llama", False, None
    if backend == "deterministic":
        return "deterministic", False, None
    if available:
        return "llama", False, None
    return "deterministic", True, "auto backend selected deterministic because llama backend is unavailable"


def _retrieval_provenance(question: str, *, knowledge_path: Path | None) -> list[dict[str, object]]:
    docs = load_knowledge(knowledge_path)
    return [
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "source_url": doc.source_url,
            "label": doc.label,
            "score": doc.score,
        }
        for doc in rank_docs(question, docs=docs, top_k=3)
    ]


def answer_question(row: ChatInput, *, knowledge_path: Path | None, backend: Backend, model_path: Path) -> ChatOutput:
    route = route_question(row.user)
    selected_backend, _, _ = _select_backend(backend, model_path)
    if selected_backend == "llama":
        return ChatOutput(
            user=row.user,
            model=generate_llama_answer(route, knowledge_path=knowledge_path, model_path=model_path),
        )
    return ChatOutput(user=row.user, model=compose_answer(route, knowledge_path=knowledge_path))


def run_chat_file(
    input_path: Path,
    output_path: Path,
    *,
    knowledge_path: Path | None = None,
    backend: Backend = "auto",
    model_path: Path = DEFAULT_MODEL_PATH,
    provenance_output_path: Path | None = None,
) -> None:
    payload = read_json(input_path)
    inputs = [ChatInput.model_validate(row) for row in payload]
    selected_backend, fallback_used, fallback_reason = _select_backend(backend, model_path)
    outputs: list[ChatOutput] = []
    provenance_rows: list[dict[str, object]] = []
    for row in inputs:
        route = route_question(row.user)
        if selected_backend == "llama":
            answer = generate_llama_answer(route, knowledge_path=knowledge_path, model_path=model_path)
        else:
            answer = compose_answer(route, knowledge_path=knowledge_path)
        outputs.append(ChatOutput(user=row.user, model=answer))
        provenance_rows.append(
            {
                "user": row.user,
                "route_label": route.label,
                "route_domain": route.domain,
                "retrieved": _retrieval_provenance(row.user, knowledge_path=knowledge_path),
            }
        )
    write_json(output_path, outputs)
    provenance_path = provenance_output_path or _provenance_output_path(output_path)
    provenance = {
        "evaluation_scope": "task2_chat_batch_provenance",
        "input_path": str(input_path),
        "input_checksum": _file_checksum(input_path),
        "output_path": str(output_path),
        "output_checksum": _file_checksum(output_path),
        "knowledge_path": str(knowledge_path) if knowledge_path is not None else None,
        "knowledge_checksum": _file_checksum(knowledge_path) if knowledge_path is not None else None,
        "backend_requested": backend,
        "backend_used": selected_backend,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "llama_backend_available": llama_backend_available(model_path),
        "model_path": str(model_path),
        "model_checksum": _file_checksum(model_path),
        "row_count": len(outputs),
        "rows": provenance_rows,
    }
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Task 2 chatbot batch output.")
    parser.add_argument("--input", type=Path, default=default_input_path("test_chat.json"))
    parser.add_argument("--output", type=Path, default=default_output_path("chat_output.json"))
    parser.add_argument("--knowledge", type=Path, default=default_input_path("knowledge_seed.json"))
    parser.add_argument("--backend", choices=["auto", "llama", "deterministic"], default="auto")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--provenance-output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic fallback composer.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    backend = "deterministic" if args.dry_run else args.backend
    run_chat_file(
        args.input,
        args.output,
        knowledge_path=args.knowledge,
        backend=backend,
        model_path=args.model,
        provenance_output_path=args.provenance_output,
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
