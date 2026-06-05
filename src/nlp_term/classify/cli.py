from __future__ import annotations

import argparse
from pathlib import Path

from nlp_term.classify.predict import predict_file
from nlp_term.paths import default_input_path, default_output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Task 1 classification dry-run inference.")
    parser.add_argument("--input", type=Path, default=default_input_path("test_cls.json"))
    parser.add_argument("--output", type=Path, default=default_output_path("cls_output.json"))
    parser.add_argument("--dry-run", action="store_true", help="Use the deterministic fallback classifier.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    predict_file(args.input, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
