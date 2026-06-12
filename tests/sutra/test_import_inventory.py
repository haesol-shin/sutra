"""S0 import-inventory safety net.

Every public symbol that current importers (engine, UI, CLI, workspace scripts,
tests) rely on must keep resolving. When the deferred workspace-plugin refactor
relocates CNU code, re-export shims must keep these names importable until all
importers migrate. This test fails loudly if a name disappears.
"""

from __future__ import annotations

import importlib

import pytest

# module -> attributes that must remain importable
_PUBLIC_SURFACE: dict[str, tuple[str, ...]] = {
    "sutra.tools": (
        "CAFETERIAS",
        "CAFETERIA_MENU_CHOICES",
        "CAFETERIA_ENUM",
        "INTERNAL_TO_DISPLAY",
        "get_tool_definitions",
        "dispatch",
        "tool",
        # fetch_* handlers imported directly by scripts/tool_live_smoke.py
        "fetch_recent_notices",
        "fetch_cafeteria_menu",
        "fetch_academic_calendar",
        "fetch_page_text",
    ),
    "sutra.dining_router": ("run_forced_cafeteria_call",),
    "sutra.menu_resolver": ("resolve_menu_dates", "resolve_cafeteria"),
    "sutra.dining_format": (
        "DiningMenuRecord",
        "CAFETERIA_ORDER",
        # helpers/constants imported by examples/cnu-campus/scripts/build_dining_index.py
        "AUDIENCE_ORDER",
        "MEAL_LABELS",
        "MEAL_ORDER",
        "active_dining_cafeterias",
        "format_price",
        "is_closed_record",
        "format_dining_day",
        "format_dining_multi",
        "format_dining_line",
    ),
    "sutra.service": ("ask", "route_question"),
    "sutra.cli": ("main",),
}


@pytest.mark.parametrize(
    ("module_name", "attribute"),
    [(module, attr) for module, attrs in _PUBLIC_SURFACE.items() for attr in attrs],
)
def test_public_symbol_resolves(module_name: str, attribute: str) -> None:
    module = importlib.import_module(module_name)
    assert hasattr(module, attribute), f"{module_name}.{attribute} no longer importable"


def test_ui_module_imports() -> None:
    # ui imports chainlit lazily-ish; importing the module must not raise.
    module = importlib.import_module("sutra.ui")
    assert hasattr(module, "on_message")
