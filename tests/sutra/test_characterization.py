"""S0 characterization tests: pin CURRENT engine behavior as byte-stable snapshots.

These exist so that a later (deferred) workspace-plugin refactor can prove zero
regression: the engine still currently hosts the CNU tool registry + Task1
classifier router, and these snapshots lock that observable surface in place.
They assert current reality; they are NOT an endorsement of CNU-in-engine.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from sutra import service
from sutra.tools import (
    CAFETERIA_ENUM,
    INTERNAL_TO_DISPLAY,
    get_tool_definitions,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _params_by_tool() -> dict[str, dict]:
    return {d["function"]["name"]: d["function"]["parameters"] for d in get_tool_definitions()}


def test_tool_names_snapshot() -> None:
    names = [d["function"]["name"] for d in get_tool_definitions()]
    assert names == [
        "fetch_recent_notices",
        "fetch_cafeteria_menu",
        "fetch_academic_calendar",
        "fetch_page_text",
    ]
    # search_knowledge_base is hidden from the default model-facing definitions
    # but is registered and exposed with include_knowledge_base=True.
    assert "search_knowledge_base" not in names
    kb_names = [d["function"]["name"] for d in get_tool_definitions(include_knowledge_base=True)]
    assert kb_names == [
        "search_knowledge_base",
        "fetch_recent_notices",
        "fetch_cafeteria_menu",
        "fetch_academic_calendar",
        "fetch_page_text",
    ]


def test_all_tool_names_route_to_a_handler() -> None:
    """Every advertised tool (incl knowledge base) has a registered dispatch handler."""
    from sutra.tools import _HANDLERS

    advertised = {d["function"]["name"] for d in get_tool_definitions(include_knowledge_base=True)}
    assert advertised <= set(_HANDLERS)
    assert set(_HANDLERS) == {
        "search_knowledge_base",
        "fetch_recent_notices",
        "fetch_cafeteria_menu",
        "fetch_academic_calendar",
        "fetch_page_text",
    }


def test_full_tool_definitions_snapshot() -> None:
    """Byte-stable hash of every tool's full schema (name + description + params)."""
    import json

    payload = json.dumps(
        get_tool_definitions(include_knowledge_base=True), ensure_ascii=False, sort_keys=True
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert digest == "33ed8b24a83c480811ab1446f1f2fe52aa69d5ae371652a14f2232fff2f6b7c2"


def test_fetch_cafeteria_menu_schema_snapshot() -> None:
    props = _params_by_tool()["fetch_cafeteria_menu"]["properties"]
    # date is intentionally NOT advertised (Python param kept for back-compat).
    assert "date" not in props
    dates = props["dates"]
    assert dates["type"] == "array"
    assert dates["items"] == {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
    assert dates["minItems"] == 1
    assert dates["maxItems"] == 5
    assert props["cafeteria"]["enum"] == [
        "전체",
        "제1학생회관",
        "제2학생회관",
        "제3학생회관",
        "제4학생회관",
        "생활과학대학",
    ]
    assert props["cafeteria"]["enum"] == CAFETERIA_ENUM


def test_notices_and_page_enums_snapshot() -> None:
    params = _params_by_tool()
    assert params["fetch_recent_notices"]["properties"]["board"]["enum"] == [
        "학교 학사공지",
        "학교 새소식",
        "학부 학사공지",
        "학부 소식",
        "학부 사업단 소식",
    ]
    assert params["fetch_page_text"]["properties"]["source_id"]["enum"] == [
        "셔틀버스 안내",
        "수강신청 안내",
    ]


def test_router_maps_snapshot() -> None:
    assert service.ROUTER_DOMAINS == {
        0: "graduation",
        1: "notices",
        2: "academic_calendar",
        3: "dining",
        4: "shuttle",
    }
    assert service.ROUTER_FORCED_TOOLS == {
        "dining": "fetch_cafeteria_menu",
        "notices": "fetch_recent_notices",
    }


def test_internal_to_display_snapshot() -> None:
    assert INTERNAL_TO_DISPLAY == {
        "univ_academic": "학교 학사공지",
        "univ_news": "학교 새소식",
        "cs_bachelor": "학부 학사공지",
        "cs_news": "학부 소식",
        "cs_project": "학부 사업단 소식",
        "shuttle": "셔틀버스 안내",
        "course_registration_guide": "수강신청 안내",
        "cs_dept": "학부 학사공지",
    }


def test_public_answer_text_substitutes_internal_ids() -> None:
    assert service._public_answer_text("univ_academic cs_dept") == "학교 학사공지 학부 학사공지"


def test_classifier_artifact_hash_is_pinned() -> None:
    """Pin the frozen classifier.joblib content hash so any change is loud."""
    model_path = _REPO_ROOT / "model" / "classifier.joblib"
    if not model_path.exists():
        pytest.skip("model/classifier.joblib not present in this checkout")
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert digest == "92cb2628f99ed12a16c7c9cb4563f8cf81eaf81422c7f368a2a9e26b9b2aba9a"
