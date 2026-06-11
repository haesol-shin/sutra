from __future__ import annotations

from sutra.tools import (
    fetch_academic_calendar,
    fetch_cafeteria_menu,
    fetch_page_text,
    fetch_recent_notices,
)


def _print_result(name: str, text: str) -> None:
    print(f"\n## {name}")
    print(text if text else "(empty)")


def main() -> None:
    checks = [
        ("fetch_recent_notices(univ_academic)", lambda: fetch_recent_notices(board="univ_academic", limit=5)),
        ("fetch_recent_notices(cs_dept)", lambda: fetch_recent_notices(board="cs_dept", limit=5)),
        ("fetch_cafeteria_menu()", lambda: fetch_cafeteria_menu()),
        ("fetch_academic_calendar()", lambda: fetch_academic_calendar()),
        ("fetch_page_text(shuttle)", lambda: fetch_page_text(source_id="shuttle")),
    ]
    for name, fn in checks:
        evidence = fn()
        _print_result(name, evidence[0].text if evidence else "")


if __name__ == "__main__":
    main()
