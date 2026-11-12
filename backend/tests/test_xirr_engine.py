from datetime import date

import pytest

from app.finance.xirr_engine import compute_portfolio_xirr

ROUNDING_HALF_STEP_PERCENT = 0.005  # The engine rounds to 2 dp of a percent.


def _npv_percent_rate(cashflows: list[tuple[date, int]], rate_percent: float) -> float:
    """NPV in rupees at the given annual rate, using the same 365-day year basis as the engine."""
    t0 = min(day for day, _ in cashflows)
    rate = rate_percent / 100.0
    return sum((amount / 100.0) / (1.0 + rate) ** ((day - t0).days / 365.0) for day, amount in cashflows)


def test_single_year_gain_returns_about_ten_percent():
    # Arrange
    cashflows = [(date(2024, 1, 1), -100_000_00), (date(2025, 1, 1), 110_000_00)]

    # Act
    result = compute_portfolio_xirr(cashflows)

    # Assert
    assert result == pytest.approx(10.0, abs=0.05)


def test_sip_style_cashflows_have_near_zero_npv_at_returned_rate():
    # Arrange
    cashflows = [
        (date(2022, 1, 5), -5_000_00),
        (date(2022, 4, 5), -5_000_00),
        (date(2022, 7, 5), -5_000_00),
        (date(2022, 10, 5), -5_000_00),
        (date(2023, 1, 5), -5_000_00),
        (date(2023, 4, 5), -5_000_00),
        (date(2023, 7, 5), -5_000_00),
        (date(2023, 10, 5), -5_000_00),
        (date(2024, 1, 5), 75_000_00),
    ]

    # Act
    result = compute_portfolio_xirr(cashflows)

    # Assert
    assert result is not None
    assert result > 0
    # The true root lies within half a rounding step of the returned percent, so NPV changes sign there.
    lower_npv = _npv_percent_rate(cashflows, result - ROUNDING_HALF_STEP_PERCENT)
    upper_npv = _npv_percent_rate(cashflows, result + ROUNDING_HALF_STEP_PERCENT)
    assert lower_npv * upper_npv < 0


def test_loss_case_returns_negative_rate():
    # Arrange
    cashflows = [(date(2024, 1, 1), -100_000_00), (date(2025, 1, 1), 80_000_00)]

    # Act
    result = compute_portfolio_xirr(cashflows)

    # Assert
    assert result is not None
    assert result < 0
    assert result == pytest.approx((0.8 ** (365 / 366) - 1) * 100, abs=0.01)


def test_fewer_than_two_cashflows_returns_none():
    assert compute_portfolio_xirr([(date(2024, 1, 1), -100_000_00)]) is None
    assert compute_portfolio_xirr([]) is None


def test_all_same_sign_returns_none():
    # Arrange
    cashflows = [(date(2024, 1, 1), -100_00), (date(2025, 1, 1), -50_00)]

    # Act
    result = compute_portfolio_xirr(cashflows)

    # Assert
    assert result is None


def test_all_zero_amounts_return_none():
    cashflows = [(date(2024, 1, 1), 0), (date(2025, 1, 1), 0)]

    assert compute_portfolio_xirr(cashflows) is None


def test_no_root_in_rate_interval_returns_none():
    # Arrange: a gain of 100x over one day implies a rate far beyond the 10000% upper bound.
    cashflows = [(date(2024, 1, 1), -1_00), (date(2024, 1, 2), 1_000_000_00)]

    # Act
    result = compute_portfolio_xirr(cashflows)

    # Assert
    assert result is None


def test_input_list_is_not_mutated():
    # Arrange
    cashflows = [(date(2025, 1, 1), 110_000_00), (date(2024, 1, 1), -100_000_00)]
    snapshot = list(cashflows)

    # Act
    compute_portfolio_xirr(cashflows)

    # Assert
    assert cashflows == snapshot
