from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

from nlp_term.classify.evaluate import summarize_classification
from nlp_term.classify.features import build_vectorizer
from nlp_term.paths import data_dir, model_dir
from nlp_term.schemas import ClassificationExample


def load_examples(path: Path) -> list[ClassificationExample]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return [ClassificationExample.model_validate(row) for row in payload]


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", build_vectorizer()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def train_baseline(rows: list[ClassificationExample]) -> tuple[Pipeline, dict[str, object]]:
    questions = [row.question for row in rows]
    labels = [row.label for row in rows]
    train_questions, test_questions, train_labels, test_labels = train_test_split(
        questions,
        labels,
        test_size=0.5,
        random_state=42,
        stratify=labels,
    )
    eval_model = build_pipeline()
    eval_model.fit(train_questions, train_labels)
    predictions = eval_model.predict(test_questions).tolist()
    metrics = summarize_classification(test_labels, predictions)
    metrics["evaluation_scope"] = "held_out_seed_sanity"
    metrics["train_rows"] = len(train_questions)
    metrics["eval_rows"] = len(test_questions)
    final_model = build_pipeline()
    final_model.fit(questions, labels)
    return final_model, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Task 1 baseline classifier.")
    parser.add_argument("--input", type=Path, default=data_dir() / "cls_train_seed.json")
    parser.add_argument("--model-output", type=Path, default=model_dir() / "classifier.joblib")
    parser.add_argument("--metrics-output", type=Path, default=model_dir() / "classifier_metrics.json")
    args = parser.parse_args()

    rows = load_examples(args.input)
    model, metrics = train_baseline(rows)
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model_output)
    with args.metrics_output.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"wrote {args.model_output}")


if __name__ == "__main__":
    main()
