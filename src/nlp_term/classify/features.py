from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer


def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1)

