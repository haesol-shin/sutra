from __future__ import annotations

import re
import codecs
import pytest
from unittest import mock

from sutra.models import Document
from sutra.prompts import get_current_time_str
from sutra.retrieval import (
    _KIWI_AVAILABLE,
    _BM25S_AVAILABLE,
    tokenize_korean,
    _get_or_build_bm25,
    rank,
)


def _u(s: str) -> str:
    """Helper to safely decode double-escaped unicode strings to prevent CP949 compile-time errors."""
    return codecs.decode(s, "unicode_escape")


def test_get_current_time_str() -> None:
    time_str = get_current_time_str("Asia/Seoul")
    # Expected pattern: YYYY-MM-DD EnglishWeekday (KoreanWeekday)
    # e.g., 2026-06-10 Wednesday (수요일)
    # Using unicode escape for Korean character range [가-힣]
    pattern = r"^\d{4}-\d{2}-\d{2} [A-Za-z]+ \([" + _u("\\uac00-\\ud7a3") + r"]+\)$"
    assert re.match(pattern, time_str) is not None

    # Test fallback for invalid timezone
    time_str_fallback = get_current_time_str("Invalid/Timezone")
    assert re.match(pattern, time_str_fallback) is not None


def test_tokenize_korean() -> None:
    if not _KIWI_AVAILABLE:
        pytest.skip("kiwipiepy not available")
    
    # "수강신청은 2월 1일에 시작합니다."
    text = _u("\\uc218\\uac15\\uc2e0\\uccad\\uc740 2\\uc6d4 1\\uc77c\\uc5d0 \\uc2dc\\uc791\\ud569\\ub2c8\\ub2e4.")
    tokens = tokenize_korean(text)
    
    # "수강", "신청", "시작", "은", "에"
    assert _u("\\uc218\\uac15") in tokens
    assert _u("\\uc2e0\\uccad") in tokens
    assert _u("\\uc2dc\\uc791") in tokens
    assert _u("\\uc740") not in tokens
    assert _u("\\uc5d0") not in tokens


def test_bm25_cache() -> None:
    if not _KIWI_AVAILABLE or not _BM25S_AVAILABLE:
        pytest.skip("kiwipiepy or bm25s not available")

    # "제목", "내용"
    docs_1 = [
        Document(id="doc-1", title=_u("\\uc81c\\ubaa91"), text=_u("\\ub0b4\\uc6a91")),
        Document(id="doc-2", title=_u("\\uc81c\\ubaa92"), text=_u("\\ub0b4\\uc6a92")),
    ]
    docs_2 = [
        Document(id="doc-1", title=_u("\\uc81c\\ubaa91"), text=_u("\\ub0b4\\uc6a91")),
        Document(id="doc-3", title=_u("\\uc81c\\ubaa93"), text=_u("\\ub0b4\\uc6a93")),
    ]

    # First build
    bm25_a = _get_or_build_bm25(docs_1)
    # Second build (should hit cache)
    bm25_b = _get_or_build_bm25(docs_1)
    assert bm25_a is bm25_b

    # Third build with different corpus (should rebuild)
    bm25_c = _get_or_build_bm25(docs_2)
    assert bm25_a is not bm25_c


def test_legacy_fallback_warning() -> None:
    # "제목", "내용"
    docs = [
        Document(id="doc-1", title=_u("\\uc81c\\ubaa91"), text=_u("\\ub0b4\\uc6a91")),
    ]
    
    # Mocking availability to force legacy fallback
    with mock.patch("sutra.retrieval._KIWI_AVAILABLE", False), \
         mock.patch("sutra.retrieval._BM25S_AVAILABLE", False):
        
        with pytest.deprecated_call():
            rank(_u("\\uc81c\\ubaa91"), docs, k=1)
