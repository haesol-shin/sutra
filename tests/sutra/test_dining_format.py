from __future__ import annotations

from sutra.dining_format import DiningMenuRecord, format_dining_day


def test_format_dining_day_matches_clean_daily_document_rules() -> None:
    records = [
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제1학생회관",
            meal="중식",
            audience="학생",
            menu_text="정식(4500)\n김치볶음밥",
            menu_name="정식(4500)",
            price="4500",
        ),
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제2학생회관",
            meal="조식",
            audience="직원",
            menu_text="운영안함",
        ),
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제3학생회관",
            meal="석식",
            audience="직원",
            menu_text="정식(6000)\n마파두부덮밥",
            menu_name="정식(6000)",
            price="6000",
        ),
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제2학생회관",
            meal="조식",
            audience="학생",
            menu_text="정식(1000)\n육개장(beef included)\n깍두기",
            menu_name="정식(1000)",
            price="1000",
        ),
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제2학생회관",
            meal="중식",
            audience="직원",
            menu_text="정식(6000)\n순두부육개장(beef included)",
            menu_name="정식(6000)",
            price="6000",
        ),
    ]

    assert format_dining_day(records, "2026-06-11") == (
        "# 2026-06-11 (목) 학생식당 식단\n"
        "\n"
        "2026-06-11 (목) 학식 메뉴입니다.\n"
        "\n"
        "## 제2학생회관\n"
        "- 아침(학생) 정식 1,000원: 육개장(beef included), 깍두기\n"
        "- 점심(직원) 정식 6,000원: 순두부육개장(beef included)\n"
        "\n"
        "## 제3학생회관\n"
        "- 저녁(직원) 정식 6,000원: 마파두부덮밥"
    )


def test_format_dining_day_skips_blank_menu_text() -> None:
    records = [
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제2학생회관",
            meal="중식",
            audience="학생",
            menu_text="   ",
        ),
        DiningMenuRecord(
            date="2026-06-11",
            cafeteria="제2학생회관",
            meal="석식",
            audience="학생",
            menu_text="정식(5000)\n카레라이스",
            menu_name="정식(5000)",
            price="5000",
        ),
    ]

    text = format_dining_day(records, "2026-06-11")

    assert "- 점심(학생):" not in text
    assert "- 저녁(학생) 정식 5,000원: 카레라이스" in text
