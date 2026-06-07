from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.classify.evaluate import summarize_classification
from nlp_term.classify.predict import predict_rows
from nlp_term.paths import data_dir, model_dir
from nlp_term.schemas import ClassificationInput, Task1HumanGoldExample
from nlp_term.validators import file_checksum, read_json


def load_gold_rows(path: Path) -> list[Task1HumanGoldExample]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [Task1HumanGoldExample.model_validate(row) for row in payload]


def evaluate_gold_file(input_path: Path, output_path: Path) -> dict[str, object]:
    rows = load_gold_rows(input_path)
    inputs = [ClassificationInput(question=row.question) for row in rows]
    predictions = predict_rows(inputs)
    metrics = summarize_classification(
        [row.label for row in rows],
        [row.label for row in predictions],
    )
    metrics.update(
        {
            "evaluation_set_type": "human_gold",
            "dataset_origin": "human_gold",
            "claim_level": "heldout_eval",
            "evaluation_scope": "task1_human_gold",
            "input_path": str(input_path),
            "input_checksum": file_checksum(input_path),
            "row_count": len(rows),
            "label_distribution": {
                str(label): sum(1 for row in rows if row.label == label)
                for label in range(5)
            },
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Task 1 classifier on human-style gold data.")
    parser.add_argument("--input", type=Path, default=data_dir() / "gold" / "task1_human_gold.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "gold_classifier_metrics.json")
    args = parser.parse_args()
    evaluate_gold_file(args.input, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
