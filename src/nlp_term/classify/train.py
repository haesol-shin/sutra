from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

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


def _input_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source_hash(source_doc_id: str) -> str:
    return sha256(source_doc_id.encode("utf-8")).hexdigest()[:16]


def _source_disjoint_split(rows: list[ClassificationExample]) -> tuple[list[ClassificationExample], list[ClassificationExample]]:
    rows_by_label_source: dict[int, dict[str, list[ClassificationExample]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if not row.source_doc_id:
            raise ValueError("source-disjoint split requires every row to have source_doc_id")
        rows_by_label_source[row.label][row.source_doc_id].append(row)

    train_rows: list[ClassificationExample] = []
    eval_rows: list[ClassificationExample] = []
    for label in range(5):
        source_groups = rows_by_label_source.get(label, {})
        if len(source_groups) < 2:
            raise ValueError(f"source-disjoint split requires at least 2 source docs for label {label}")
        eval_source = sorted(source_groups.items(), key=lambda item: (len(item[1]), item[0]))[0][0]
        for source_id, source_rows in source_groups.items():
            if source_id == eval_source:
                eval_rows.extend(source_rows)
            else:
                train_rows.extend(source_rows)
    return train_rows, eval_rows


def train_baseline(rows: list[ClassificationExample]) -> tuple[Pipeline, dict[str, object]]:
    train_rows, eval_rows = _source_disjoint_split(rows)
    train_questions = [row.question for row in train_rows]
    train_labels = [row.label for row in train_rows]
    test_questions = [row.question for row in eval_rows]
    test_labels = [row.label for row in eval_rows]
    eval_model = build_pipeline()
    eval_model.fit(train_questions, train_labels)
    predictions = eval_model.predict(test_questions).tolist()
    metrics = summarize_classification(test_labels, predictions)
    train_sources = sorted({row.source_doc_id or "" for row in train_rows})
    eval_sources = sorted({row.source_doc_id or "" for row in eval_rows})
    metrics["evaluation_scope"] = "source_disjoint"
    metrics["split_strategy"] = "per_label_holdout_source_doc"
    metrics["train_rows"] = len(train_questions)
    metrics["eval_rows"] = len(test_questions)
    metrics["train_source_ids"] = train_sources
    metrics["eval_source_ids"] = eval_sources
    metrics["train_source_hashes"] = [_source_hash(source_id) for source_id in train_sources]
    metrics["eval_source_hashes"] = [_source_hash(source_id) for source_id in eval_sources]
    metrics["source_overlap_count"] = len(set(train_sources) & set(eval_sources))
    metrics["label_distribution"] = {
        "all": dict(sorted(Counter(row.label for row in rows).items())),
        "train": dict(sorted(Counter(train_labels).items())),
        "eval": dict(sorted(Counter(test_labels).items())),
    }
    final_model = build_pipeline()
    final_model.fit([row.question for row in rows], [row.label for row in rows])
    return final_model, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Task 1 baseline classifier.")
    parser.add_argument("--input", type=Path, default=data_dir() / "cls_train_seed.json")
    parser.add_argument("--model-output", type=Path, default=model_dir() / "classifier.joblib")
    parser.add_argument("--metrics-output", type=Path, default=model_dir() / "classifier_metrics.json")
    args = parser.parse_args()

    rows = load_examples(args.input)
    model, metrics = train_baseline(rows)
    metrics["input_path"] = str(args.input)
    metrics["input_checksum"] = _input_checksum(args.input)
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model_output)
    with args.metrics_output.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"wrote {args.model_output}")


if __name__ == "__main__":
    main()
