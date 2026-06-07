from __future__ import annotations

import argparse
import json
from pathlib import Path

from nlp_term.classify.evaluate import summarize_classification
from nlp_term.classify.evaluate_gold import load_gold_rows
from nlp_term.classify.predict import predict_rows
from nlp_term.paths import data_dir, model_dir
from nlp_term.schemas import ClassificationInput
from nlp_term.validators import file_checksum


LABELS = range(5)


def _empty_label_counts() -> dict[str, int]:
    return {str(label): 0 for label in LABELS}


def analyze_gold_errors_file(input_path: Path, output_path: Path) -> dict[str, object]:
    rows = load_gold_rows(input_path)
    inputs = [ClassificationInput(question=row.question) for row in rows]
    predictions = predict_rows(inputs)
    expected = [row.label for row in rows]
    predicted = [row.label for row in predictions]
    metrics = summarize_classification(expected, predicted)

    confusion = {str(label): _empty_label_counts() for label in LABELS}
    false_negative_counts = _empty_label_counts()
    false_positive_counts = _empty_label_counts()
    per_difficulty_failure_counts: dict[str, int] = {}
    errors: list[dict[str, object]] = []
    for row, prediction in zip(rows, predictions):
        expected_label = row.label
        predicted_label = prediction.label
        confusion[str(expected_label)][str(predicted_label)] += 1
        if expected_label == predicted_label:
            continue
        difficulty = row.difficulty
        false_negative_counts[str(expected_label)] += 1
        false_positive_counts[str(predicted_label)] += 1
        per_difficulty_failure_counts[difficulty] = per_difficulty_failure_counts.get(difficulty, 0) + 1
        errors.append(
            {
                "question": row.question,
                "expected_label": expected_label,
                "predicted_label": predicted_label,
                "difficulty": difficulty,
                "ambiguous_reason": row.ambiguous_reason,
                "error_type": f"{expected_label}->{predicted_label}",
            }
        )

    classifier_path = model_dir() / "classifier.joblib"
    report = {
        "evaluation_set_type": "human_gold",
        "dataset_origin": "human_gold",
        "claim_level": "heldout_eval",
        "evaluation_scope": "task1_human_gold_error_report",
        "input_path": str(input_path),
        "input_checksum": file_checksum(input_path),
        "row_count": len(rows),
        "model_path": str(classifier_path),
        "model_available": classifier_path.exists(),
        "macro_f1": metrics["macro_f1"],
        "weighted_f1": metrics["weighted_f1"],
        "classification_report": metrics["report"],
        "confusion_matrix": confusion,
        "false_negative_counts": false_negative_counts,
        "false_positive_counts": false_positive_counts,
        "per_difficulty_failure_counts": per_difficulty_failure_counts,
        "error_count": len(errors),
        "errors": errors,
        "interpretation_allowed": "diagnostic_only_not_final_generalization",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 1 classifier errors on human-style gold data.")
    parser.add_argument("--input", type=Path, default=data_dir() / "gold" / "task1_human_gold.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "task1_gold_error_analysis.json")
    args = parser.parse_args()
    analyze_gold_errors_file(args.input, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
