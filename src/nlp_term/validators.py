from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from nlp_term.schemas import (
    ChatInput,
    ChatOutput,
    ClassificationInput,
    ClassificationOutput,
    RealtimeOutput,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, rows: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [row.model_dump() for row in rows]
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def validate_rows(path: Path, model_type: type[ModelT], *, required: bool = True) -> list[ModelT]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [model_type.model_validate(row) for row in payload]


def validate_inputs(data_dir: Path, *, require_realtime: bool = False) -> None:
    validate_rows(data_dir / "test_cls.json", ClassificationInput, required=True)
    validate_rows(data_dir / "test_chat.json", ChatInput, required=True)
    validate_rows(data_dir / "test_realtime.json", ChatInput, required=require_realtime)


def validate_outputs(outputs_dir: Path, *, require_realtime: bool = False) -> None:
    validate_rows(outputs_dir / "cls_output.json", ClassificationOutput, required=True)
    validate_rows(outputs_dir / "chat_output.json", ChatOutput, required=True)
    validate_rows(outputs_dir / "realtime_output.json", RealtimeOutput, required=require_realtime)


def validate_all(data_dir: Path, outputs_dir: Path, *, require_outputs: bool, require_realtime: bool) -> None:
    validate_inputs(data_dir, require_realtime=require_realtime)
    if require_outputs:
        validate_outputs(outputs_dir, require_realtime=require_realtime)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate NLP term project JSON contracts.")
    parser.add_argument("--check-all", action="store_true", help="Validate known input/output files.")
    parser.add_argument("--inputs-only", action="store_true", help="Only validate required input fixtures.")
    parser.add_argument("--require-realtime", action="store_true", help="Require realtime input/output files.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.check_all and not args.inputs_only:
        parser.error("--check-all or --inputs-only is required")
    try:
        if args.inputs_only:
            validate_inputs(args.data_dir, require_realtime=args.require_realtime)
        else:
            validate_all(
                args.data_dir,
                args.outputs_dir,
                require_outputs=True,
                require_realtime=args.require_realtime,
            )
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        raise SystemExit(f"validation failed: {exc}") from exc
    print("validation-ok")


if __name__ == "__main__":
    main()
