from __future__ import annotations

from sklearn.metrics import classification_report, f1_score


def summarize_classification(y_true: list[int], y_pred: list[int]) -> dict[str, object]:
    return {
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted"),
        "report": classification_report(y_true, y_pred, output_dict=True, zero_division=0),
    }

