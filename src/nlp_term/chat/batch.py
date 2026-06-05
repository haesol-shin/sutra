from __future__ import annotations

import argparse
from pathlib import Path

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.router import route_question
from nlp_term.paths import default_input_path, default_output_path
from nlp_term.schemas import ChatInput, ChatOutput
from nlp_term.validators import read_json, write_json


def run_chat_file(input_path: Path, output_path: Path) -> None:
    payload = read_json(input_path)
    inputs = [ChatInput.model_validate(row) for row in payload]
    outputs = []
    for row in inputs:
        route = route_question(row.user)
        outputs.append(ChatOutput(user=row.user, model=compose_answer(route)))
    write_json(output_path, outputs)


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
