from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.router import route_question
from nlp_term.paths import default_input_path, default_output_path, ensure_parent
from nlp_term.schemas import ChatInput, ChatOutput


def run_chat_file(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    inputs = [ChatInput.model_validate(row) for row in payload]
    outputs = []
    for row in inputs:
        route = route_question(row.user)
        outputs.append(ChatOutput(user=row.user, model=compose_answer(route)))
    ensure_parent(output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump([row.model_dump() for row in outputs], file, ensure_ascii=False, indent=2)
        file.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Task 2 chatbot batch output.")
    parser.add_argument("--input", type=Path, default=default_input_path("test_chat.json"))
    parser.add_argument("--output", type=Path, default=default_output_path("chat_output.json"))
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic fallback composer.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_chat_file(args.input, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
