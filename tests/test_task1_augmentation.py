from __future__ import annotations

from collections import Counter

from nlp_term.classify.augment import build_augmented_rows
from nlp_term.classify.train import load_examples
from nlp_term.paths import data_dir


def test_wp3_template_augmentation_is_deterministic_and_balanced() -> None:
    seed_rows = load_examples(data_dir() / "cls_train_seed.json")

    augmented_once = build_augmented_rows(seed_rows)
    augmented_twice = build_augmented_rows(seed_rows)

    assert [row.model_dump() for row in augmented_once] == [row.model_dump() for row in augmented_twice]
    assert len({row.question for row in augmented_once}) == len(augmented_once)

    generated_rows = [
        row for row in augmented_once if row.metadata.get("sample_type") == "wp3_template_augmentation"
    ]
    assert 400 <= len(generated_rows) <= 800

    distribution = Counter(row.label for row in augmented_once)
    assert max(distribution.values()) / len(augmented_once) <= 0.40

