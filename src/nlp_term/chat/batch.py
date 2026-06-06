from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.llama_backend import generate_llama_answer, llama_backend_available
from nlp_term.chat.router import route_question
from nlp_term.llm.llama_compare import DEFAULT_MODEL_PATH
from nlp_term.paths import default_input_path, default_output_path
from nlp_term.schemas import ChatInput, ChatOutput
from nlp_term.validators import read_json, write_json


Backend = Literal["auto", "llama", "deterministic"]


def answer_question(row: ChatInput, *, knowledge_path: Path | None, backend: Backend, model_path: Path) -> ChatOutput:
    route = route_question(row.user)
    if backend == "llama" or (backend == "auto" and llama_backend_available(model_path)):
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
) -> None:
    payload = read_json(input_path)
    inputs = [ChatInput.model_validate(row) for row in payload]
    outputs = [
        answer_question(row, knowledge_path=knowledge_path, backend=backend, model_path=model_path) for row in inputs
    ]
    write_json(output_path, outputs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Task 2 chatbot batch output.")
    parser.add_argument("--input", type=Path, default=default_input_path("test_chat.json"))
    parser.add_argument("--output", type=Path, default=default_output_path("chat_output.json"))
    parser.add_argument("--knowledge", type=Path, default=default_input_path("knowledge_seed.json"))
    parser.add_argument("--backend", choices=["auto", "llama", "deterministic"], default="auto")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic fallback composer.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    backend = "deterministic" if args.dry_run else args.backend
    run_chat_file(args.input, args.output, knowledge_path=args.knowledge, backend=backend, model_path=args.model)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
