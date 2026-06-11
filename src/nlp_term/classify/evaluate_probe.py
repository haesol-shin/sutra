from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, f1_score

from nlp_term.classify.train import load_examples
from nlp_term.paths import data_dir, model_dir
from nlp_term.schemas import ClassificationExample, Task1HumanGoldExample


@dataclass(frozen=True)
class EvalRow:
    question: str
    label: int


@dataclass(frozen=True)
class EvalResult:
    name: str
    row_count: int
    accuracy: float
    macro_f1: float
    per_class_f1: dict[int, float]
    wrong: list[dict[str, int | str]]

    @property
    def min_class_f1(self) -> float:
        return min(self.per_class_f1.values())


def _load_json(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return payload


def load_eval_rows(path: Path) -> list[EvalRow]:
    payload = _load_json(path)
    if path.name == "qwen_v2_diagnostic.json":
        return [
            EvalRow(question=str(row["question"]), label=int(row["label"]))
            for row in payload
            if int(row["label"]) == 3
        ]
    rows = [Task1HumanGoldExample.model_validate(row) for row in payload]
    return [EvalRow(question=row.question, label=row.label) for row in rows]


def assert_no_eval_leakage(
    train_rows: list[ClassificationExample],
    eval_sets: list[list[Task1HumanGoldExample | EvalRow]],
) -> None:
    train_questions = {row.question for row in train_rows}
    leaked = sorted(
        {
            row.question
            for eval_rows in eval_sets
            for row in eval_rows
            if row.question in train_questions
        }
    )
    if leaked:
        sample = "; ".join(leaked[:5])
        raise ValueError(f"evaluation leakage: held-out questions appear in training data: {sample}")


def evaluate_model_on_rows(model_path: Path, name: str, rows: list[Task1HumanGoldExample | EvalRow]) -> EvalResult:
    model = joblib.load(model_path)
    questions = [row.question for row in rows]
    y_true = [row.label for row in rows]
    predictions = model.predict(questions)
    raw_predictions = predictions.tolist() if hasattr(predictions, "tolist") else list(predictions)
    y_pred = [int(label) for label in raw_predictions]
    labels = sorted(set(y_true))
    per_class = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    wrong = [
        {"question": row.question, "gold": row.label, "pred": pred}
        for row, pred in zip(rows, y_pred)
        if row.label != pred
    ]
    return EvalResult(
        name=name,
        row_count=len(rows),
        accuracy=accuracy_score(y_true, y_pred),
        macro_f1=f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
        per_class_f1={label: float(score) for label, score in zip(labels, per_class)},
        wrong=wrong,
    )


def _print_result(model_name: str, result: EvalResult) -> None:
    per_class = ", ".join(f"{label}:{score:.3f}" for label, score in result.per_class_f1.items())
    print(
        f"{model_name}\t{result.name}\trows={result.row_count}\t"
        f"accuracy={result.accuracy:.3f}\tmacro_f1={result.macro_f1:.3f}\t"
        f"min_class_f1={result.min_class_f1:.3f}\t"
        f"per_class={per_class}"
    )
    if result.wrong:
        print("wrong:")
        for item in result.wrong:
            print(f"  gold={item['gold']} pred={item['pred']} question={item['question']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Task 1 models on held-out probe files.")
    parser.add_argument("--model", type=Path, action="append", required=True)
    parser.add_argument("--train-input", type=Path, default=data_dir() / "cls_train_augmented.json")
    parser.add_argument(
        "--eval",
        type=Path,
        action="append",
        default=[
            data_dir() / "gold" / "task1_human_gold.json",
            data_dir() / "gold" / "task1_probe_v2.json",
            Path("tmp") / "qwen_v2_diagnostic.json",
        ],
    )
    args = parser.parse_args()

    train_rows = load_examples(args.train_input)
    eval_sets = [(path.stem, load_eval_rows(path)) for path in args.eval]
    assert_no_eval_leakage(train_rows, [rows for _, rows in eval_sets])
    for model_path in args.model:
        for name, rows in eval_sets:
            result = evaluate_model_on_rows(model_path, name, rows)
            _print_result(model_path.name, result)


if __name__ == "__main__":
    main()
