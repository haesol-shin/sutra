from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.chat.router import route_question
from nlp_term.paths import default_input_path, default_output_path, ensure_parent
from nlp_term.schemas import ChatInput, RealtimeOutput


def realtime_fallback(user: str) -> RealtimeOutput:
    route = route_question(user)
    message = (
        f"현재 dry-run에서는 {route.domain} 실시간 source를 호출하지 않습니다. "
        "제출 구현에서는 검증된 공식 source를 우선 사용하고 실패 시 cached/static fallback을 제공합니다."
    )
    return RealtimeOutput(user=user, model=message)


def run_realtime_file(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    inputs = [ChatInput.model_validate(row) for row in payload]
    outputs = [realtime_fallback(row.user) for row in inputs]
    ensure_parent(output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump([row.model_dump() for row in outputs], file, ensure_ascii=False, indent=2)
        file.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run optional Task 3 realtime fallback output.")
    parser.add_argument("--input", type=Path, default=default_input_path("test_realtime.json"))
    parser.add_argument("--output", type=Path, default=default_output_path("realtime_output.json"))
    parser.add_argument("--dry-run", action="store_true", help="Use cached/static fallback only.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_realtime_file(args.input, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
