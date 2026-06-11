from __future__ import annotations

import re
import codecs
import pytest
from pathlib import Path
from unittest import mock

from sutra.models import Document, Evidence, EvidencePack
from sutra.prompts import get_current_time_str
from sutra.retrieval import (
    _KIWI_AVAILABLE,
    _BM25S_AVAILABLE,
    tokenize_korean,
    _get_or_build_bm25,
    rank,
    retrieve,
)
import sutra.retrieval as _retrieval
from sutra.config import Config, PromptConfig, RagConfig, RuntimeConfig, WorkspaceConfig


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
    
    # Reset the module-level warning flag so we get a fresh DeprecationWarning
    _retrieval._legacy_warned = False
    
    # Mocking availability to force legacy fallback
    with mock.patch("sutra.retrieval._KIWI_AVAILABLE", False), \
         mock.patch("sutra.retrieval._BM25S_AVAILABLE", False):
        
        with pytest.deprecated_call():
            rank(_u("\\uc81c\\ubaa91"), docs, k=1)


def _test_config(backend: str = "bm25") -> Config:
    return Config(
        path=Path("sutra.toml"),
        root=Path("."),
        workspace=WorkspaceConfig(name="test", timezone="Asia/Seoul"),
        runtime=RuntimeConfig(),
        rag=RagConfig(index_path=Path("index.jsonl"), top_k=2, backend=backend),
        prompts=PromptConfig(system=Path("system.md")),
    )


def test_expand_relative_date_query_appends_kst_date(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_time_str(timezone_name: str) -> str:
        assert timezone_name == "Asia/Seoul"
        return "2026-06-11 Thursday (목요일)"

    monkeypatch.setattr("sutra.prompts.get_current_time_str", fake_time_str)

    assert (
        _retrieval._expand_relative_date_query("오늘 저녁 학식", "Asia/Seoul")
        == "오늘 저녁 학식 2026-06-11"
    )
    assert (
        _retrieval._expand_relative_date_query("금일 학식", "Asia/Seoul")
        == "금일 학식 2026-06-11"
    )
    assert (
        _retrieval._expand_relative_date_query("내일 학식", "Asia/Seoul")
        == "내일 학식 2026-06-12"
    )
    assert (
        _retrieval._expand_relative_date_query("명일 학식", "Asia/Seoul")
        == "명일 학식 2026-06-12"
    )
    assert (
        _retrieval._expand_relative_date_query("모레 학식", "Asia/Seoul")
        == "모레 학식 2026-06-13"
    )
    assert (
        _retrieval._expand_relative_date_query("어제 학식", "Asia/Seoul")
        == "어제 학식 2026-06-10"
    )


def test_expand_relative_date_query_leaves_absolute_query_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sutra.prompts.get_current_time_str",
        lambda timezone_name: "2026-06-11 Thursday (목요일)",
    )

    assert _retrieval._expand_relative_date_query("6월 학식", "Asia/Seoul") == "6월 학식"
    assert (
        _retrieval._expand_relative_date_query("오늘 2026-06-12 학식", "Asia/Seoul")
        == "오늘 2026-06-12 학식"
    )
    assert (
        _retrieval._expand_relative_date_query("오늘 2026-06-11 학식", "Asia/Seoul")
        == "오늘 2026-06-11 학식"
    )


def test_retrieve_preserves_original_question_while_bm25_uses_expanded_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sutra.prompts.get_current_time_str",
        lambda timezone_name: "2026-06-11 Thursday (목요일)",
    )
    monkeypatch.setattr(_retrieval, "_KIWI_AVAILABLE", True)
    monkeypatch.setattr(_retrieval, "_BM25S_AVAILABLE", True)
    monkeypatch.setattr(_retrieval, "_get_or_build_bm25", lambda documents, token_config=None: object())
    seen_queries: list[str] = []

    def fake_bm25_retrieve(query, documents, bm25, config, token_config=None):
        seen_queries.append(query)
        return EvidencePack(
            question=query,
            items=[Evidence(id="dining-11", title="2026-06-11 학생식당 식단", text="학식 저녁 메뉴")],
        )

    monkeypatch.setattr(_retrieval, "bm25_retrieve", fake_bm25_retrieve)

    pack = retrieve(
        "오늘 학식",
        [Document(id="dining-11", title="2026-06-11 학생식당 식단", text="학식 저녁 메뉴")],
        _test_config(),
    )

    assert seen_queries == ["오늘 학식 2026-06-11"]
    assert pack.question == "오늘 학식"
    assert [item.id for item in pack.items] == ["dining-11"]


def test_retrieve_relative_today_query_prioritizes_today_dining_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sutra.prompts.get_current_time_str",
        lambda timezone_name: "2026-06-11 Thursday (목요일)",
    )
    docs = [
        Document(id="dining-10", title="2026-06-10 학생식당 식단", text="학식 저녁 메뉴"),
        Document(id="dining-11", title="2026-06-11 학생식당 식단", text="학식 저녁 메뉴"),
        Document(id="dining-12", title="2026-06-12 학생식당 식단", text="학식 저녁 메뉴"),
    ]

    pack = retrieve("오늘 학식", docs, _test_config())

    assert [item.id for item in pack.items] == ["dining-11", "dining-10"]
