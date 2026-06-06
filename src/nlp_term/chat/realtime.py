from __future__ import annotations

import argparse
from pathlib import Path

from nlp_term.chat.router import route_question
from nlp_term.paths import default_input_path, default_output_path
from nlp_term.schemas import ChatInput, RealtimeOutput
from nlp_term.validators import read_json, write_json


def realtime_fallback(user: str) -> RealtimeOutput:
    route = route_question(user)
    message = (
        f"{route.domain} 영역은 정보가 자주 바뀔 수 있어 저장된 출처 스냅샷만으로 현재 상태를 단정하지 않습니다. "
        "확인 가능한 출처 내용을 기준으로 안내하되, 날짜·메뉴·공지 제목처럼 변동되는 내용은 실제 이용 전에 해당 페이지에서 다시 확인하세요."
    )
    return RealtimeOutput(user=user, model=message)


def run_realtime_file(input_path: Path, output_path: Path) -> None:
    payload = read_json(input_path)
    inputs = [ChatInput.model_validate(row) for row in payload]
    outputs = [realtime_fallback(row.user) for row in inputs]
    write_json(output_path, outputs)


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
