"""Export the frozen sklearn router classifier to a pickle-free numpy artifact.

Schema written to ``examples/cnu-campus/model/router_classifier.npz`` with
``numpy.savez`` and loadable through ``numpy.load(path, allow_pickle=False)``:

- ``schema_version``: int64 scalar, currently ``1``.
- ``source_classifier_sha256``: unicode scalar string containing the SHA-256
  digest of the source ``model/classifier.joblib`` bytes.
- ``terms``: 1-D numpy unicode string array of length 5986. Element ``terms[i]``
  is the ngram whose TfidfVectorizer vocabulary column is ``i``.
- ``idf``: float64 array with shape ``(5986,)`` copied from
  ``TfidfVectorizer.idf_``.
- ``coef``: float64 array with shape ``(5, 5986)`` copied from the
  LogisticRegression classifier.
- ``intercept``: float64 array with shape ``(5,)`` copied from the
  LogisticRegression classifier.
- ``classes``: int64 array with shape ``(5,)`` copied from
  ``LogisticRegression.classes_``.

The exporter intentionally reads the legacy joblib/sklearn model only at export
or parity-check time. Sutra runtime prediction consumes only this npz artifact.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import joblib
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = REPO_ROOT / "model" / "classifier.joblib"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "model" / "router_classifier.npz"


def _pipeline_step(model: Any, name: str) -> Any:
    try:
        return model.named_steps[name]
    except AttributeError as exc:  # pragma: no cover - defensive export failure
        raise TypeError("expected sklearn Pipeline with named_steps") from exc
    except KeyError as exc:  # pragma: no cover - defensive export failure
        raise KeyError(f"missing pipeline step: {name}") from exc


def export_router_classifier(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT) -> Path:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()

    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    model = joblib.load(source)
    vectorizer = _pipeline_step(model, "tfidf")
    classifier = _pipeline_step(model, "clf")

    vocabulary = vectorizer.vocabulary_
    feature_count = len(vocabulary)
    ordered_terms = [None] * feature_count
    for term, index in vocabulary.items():
        ordered_terms[int(index)] = str(term)
    if any(term is None for term in ordered_terms):
        missing = [index for index, term in enumerate(ordered_terms) if term is None]
        raise ValueError(f"vocabulary is not contiguous; missing columns: {missing[:10]}")

    max_term_len = max(len(term) for term in ordered_terms)
    terms = np.asarray(ordered_terms, dtype=f"<U{max_term_len}")
    idf = np.asarray(vectorizer.idf_, dtype=np.float64)
    coef = np.asarray(classifier.coef_, dtype=np.float64)
    intercept = np.asarray(classifier.intercept_, dtype=np.float64)
    classes = np.asarray(classifier.classes_, dtype=np.int64)

    expected_feature_count = 5986
    if terms.shape != (expected_feature_count,):
        raise ValueError(f"expected {expected_feature_count} terms, got {terms.shape}")
    if idf.shape != terms.shape:
        raise ValueError(f"idf shape mismatch: {idf.shape} vs {terms.shape}")
    if coef.shape != (5, expected_feature_count):
        raise ValueError(f"coef shape mismatch: {coef.shape}")
    if intercept.shape != (5,):
        raise ValueError(f"intercept shape mismatch: {intercept.shape}")
    if classes.shape != (5,):
        raise ValueError(f"classes shape mismatch: {classes.shape}")

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output,
        schema_version=np.asarray(1, dtype=np.int64),
        source_classifier_sha256=np.asarray(source_sha256, dtype=f"<U{len(source_sha256)}"),
        terms=terms,
        idf=idf,
        coef=coef,
        intercept=intercept,
        classes=classes,
    )

    with np.load(output, allow_pickle=False) as exported:
        for key in ("schema_version", "source_classifier_sha256", "terms", "idf", "coef", "intercept", "classes"):
            _ = exported[key]
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = export_router_classifier(args.source, args.output)
    print(f"exported={output}")


if __name__ == "__main__":
    main()
