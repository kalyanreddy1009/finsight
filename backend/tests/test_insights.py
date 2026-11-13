"""Unit tests for the deterministic insights helpers (no HTTP)."""

import sqlite3
from datetime import date

import pytest

from app.finance import insights


@pytest.mark.parametrize(
    ("minor", "text"),
    [
        (0, "₹0.00"),
        (99, "₹0.99"),
        (100_000, "₹1,000.00"),
        (12_345_600, "₹1,23,456.00"),
        (100_000_000_00, "₹10,00,00,000.00"),
        (-150_050, "-₹1,500.50"),
        (99_999, "₹999.99"),
    ],
)
def test_format_inr_uses_indian_grouping(minor: int, text: str) -> None:
    assert insights.format_inr(minor) == text


@pytest.mark.parametrize("bad", [1.5, "100", True])
def test_format_inr_rejects_non_integers(bad: object) -> None:
    with pytest.raises(TypeError):
        insights.format_inr(bad)  # type: ignore[arg-type]


def test_shift_month_crosses_year_boundaries() -> None:
    assert insights.shift_month(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert insights.shift_month(date(2026, 11, 1), 2) == date(2027, 1, 1)
    assert insights.shift_month(date(2026, 3, 1), -14) == date(2025, 1, 1)


def test_empty_database_gives_zero_filled_trend_and_no_data(conn: sqlite3.Connection) -> None:
    data = insights.spending_summary(conn, date(2026, 1, 15), months=3)
    assert [t["year_month"] for t in data["trend"]] == ["2025-11", "2025-12", "2026-01"]
    assert all(t["income_minor"] == 0 and t["expense_minor"] == 0 for t in data["trend"])
    assert data["categories"] == []
    assert data["net_minor"] == data["previous_expense_minor"] == 0
    assert [h["kind"] for h in data["highlights"]] == ["NO_DATA"]


@pytest.mark.parametrize("months", [0, 13, -1, True])
def test_months_out_of_range_is_rejected(conn: sqlite3.Connection, months: int) -> None:
    with pytest.raises(ValueError):
        insights.spending_summary(conn, date(2026, 1, 15), months=months)


def test_change_thresholds_need_percent_and_rupee_floor() -> None:
    assert insights._is_up(125_000, 100_000) is False  # 25% but only Rs 250
    assert insights._is_up(160_000, 100_000) is True  # 60% and Rs 600
    assert insights._is_up(1_040_000, 1_000_000) is False  # Rs 400 and 4%
    assert insights._is_up(5_000_000, 0) is False  # no previous month to compare
    assert insights._is_down(40_000, 100_000) is True
    assert insights._is_down(100_000, 40_000) is False
