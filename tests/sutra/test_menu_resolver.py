from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from sutra import menu_resolver
from sutra.menu_resolver import normalize_cafeteria, resolve_menu_dates


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        value = cls(2026, 6, 13, 9, 0, 0)
        if tz is None:
            return value
        return value.replace(tzinfo=ZoneInfo("Asia/Seoul")).astimezone(tz)


@pytest.fixture(autouse=True)
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(menu_resolver, "datetime", FrozenDateTime)


@pytest.fixture
def config() -> SimpleNamespace:
    return SimpleNamespace(workspace=SimpleNamespace(timezone="Asia/Seoul"))


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("오늘 학식", ["2026-06-13"]),
        ("내일 학식", ["2026-06-14"]),
        ("모레 학식", ["2026-06-15"]),
        ("어제 학식", ["2026-06-12"]),
        ("내일모레 학식", ["2026-06-15"]),
    ],
)
def test_relative_days(question: str, expected: list[str], config: SimpleNamespace) -> None:
    assert resolve_menu_dates(question, config) == expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("다음주 화요일 학식", ["2026-06-16"]),
        ("다음주 월요일 화요일 학식", ["2026-06-15", "2026-06-16"]),
        ("다음주 월, 수 학식", ["2026-06-15", "2026-06-17"]),
        ("다음 주 월요일 학식", ["2026-06-15"]),
        ("담주 화요일 학식", ["2026-06-16"]),
    ],
)
def test_weekday_terms_use_resolved_week(question: str, expected: list[str], config: SimpleNamespace) -> None:
    assert resolve_menu_dates(question, config) == expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "다음주 식단",
            ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"],
        ),
        (
            "이번주 식단",
            ["2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"],
        ),
        (
            "주간 식단표",
            ["2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"],
        ),
        (
            "다음주 평일 식단",
            ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"],
        ),
        (
            "다음주 주중 식단",
            ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"],
        ),
        ("이번 주말 식단", ["2026-06-13", "2026-06-14"]),
        ("다음 주말 식단", ["2026-06-20", "2026-06-21"]),
    ],
)
def test_week_ranges_and_groups(question: str, expected: list[str], config: SimpleNamespace) -> None:
    assert resolve_menu_dates(question, config) == expected


def test_weekday_range_defaults_to_current_week(config: SimpleNamespace) -> None:
    assert resolve_menu_dates("월요일~수요일 학식", config) == [
        "2026-06-08",
        "2026-06-09",
        "2026-06-10",
    ]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("6월 16일 학식", ["2026-06-16"]),
        ("2026-06-16 학식", ["2026-06-16"]),
        ("16일 메뉴", ["2026-06-16"]),
        ("내일 메뉴", ["2026-06-14"]),
        ("금일 메뉴", ["2026-06-13"]),
        ("일요일 메뉴", ["2026-06-14"]),
    ],
)
def test_masking_prevents_weekday_false_positives(
    question: str,
    expected: list[str],
    config: SimpleNamespace,
) -> None:
    assert resolve_menu_dates(question, config) == expected


@pytest.mark.parametrize("question", ["6월 메뉴", "11월 메뉴"])
def test_month_only_does_not_resolve_to_monday(question: str, config: SimpleNamespace) -> None:
    result = resolve_menu_dates(question, config)
    assert result is None or result != ["2026-06-08"]


def test_dateless_question_returns_none(config: SimpleNamespace) -> None:
    assert resolve_menu_dates("학식 메뉴 뭐 있어", config) is None


def test_mixed_week_terms_use_first_week_only(config: SimpleNamespace) -> None:
    assert resolve_menu_dates("이번주 월요일이랑 다음주 화요일", config) == ["2026-06-08"]


def test_sort_dedup_and_cap_five(config: SimpleNamespace) -> None:
    assert resolve_menu_dates("다음주 금, 월, 월, 수, 토, 일", config) == [
        "2026-06-15",
        "2026-06-17",
        "2026-06-19",
        "2026-06-20",
        "2026-06-21",
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, (None, False)),
        ("", (None, False)),
        ("2학", ("제2학생회관", False)),
        ("3학", ("제3학생회관", False)),
        ("4학", ("제4학생회관", False)),
        ("생활과학대학", ("생활과학대학", False)),
        ("제2학생회관", ("제2학생회관", False)),
        ("제3학생회관", ("제3학생회관", False)),
        ("제4학생회관", ("제4학생회관", False)),
        ("1학", (None, True)),
        ("제1학생회관", (None, True)),
        ("1학,2학", ("제2학생회관", False)),
        ("중앙도서관", (None, False)),
    ],
)
def test_normalize_cafeteria(raw: str | None, expected: tuple[str | None, bool]) -> None:
    assert normalize_cafeteria(raw) == expected
