"""Portfolio XIRR engine: Newton-Raphson with a bisection fallback over dated cashflows."""

from collections.abc import Callable
from datetime import date, datetime

_DAYS_PER_YEAR = 365.0
_INITIAL_RATE = 0.12  # Initial guess: 12% p.a.
_RATE_LOWER_BOUND = -0.9999
_RATE_UPPER_BOUND = 100.0
_NEWTON_TOLERANCE = 1e-10
_BISECTION_TOLERANCE = 1e-12
_BISECTION_MAX_ITERATIONS = 500
_PERCENT_PRECISION = 2
_MINOR_PER_MAJOR = 100.0


def _npv(rate: float, amounts: list[float], years: list[float]) -> float:
    base = 1.0 + rate
    return sum(amount * base ** (-year) for amount, year in zip(amounts, years, strict=True))


def _npv_derivative(rate: float, amounts: list[float], years: list[float]) -> float:
    base = 1.0 + rate
    return sum(-year * amount * base ** (-year - 1.0) for amount, year in zip(amounts, years, strict=True))


def _newton_raphson(amounts: list[float], years: list[float], max_iterations: int) -> float | None:
    rate = _INITIAL_RATE
    for _ in range(max_iterations):
        try:
            value = _npv(rate, amounts, years)
            derivative = _npv_derivative(rate, amounts, years)
        except (OverflowError, ZeroDivisionError):
            return None
        if derivative == 0.0 or derivative != derivative:
            return None
        step = value / derivative
        rate -= step
        if not (_RATE_LOWER_BOUND < rate < _RATE_UPPER_BOUND):
            return None
        if abs(step) < _NEWTON_TOLERANCE:
            return rate
    return None


def _bisection(npv_at: Callable[[float], float], lower: float, upper: float) -> float | None:
    try:
        lower_value = npv_at(lower)
        upper_value = npv_at(upper)
    except (OverflowError, ZeroDivisionError):
        return None
    if lower_value == 0.0:
        return lower
    if upper_value == 0.0:
        return upper
    if (lower_value > 0.0) == (upper_value > 0.0):
        return None
    for _ in range(_BISECTION_MAX_ITERATIONS):
        middle = (lower + upper) / 2.0
        try:
            middle_value = npv_at(middle)
        except (OverflowError, ZeroDivisionError):
            return None
        if middle_value == 0.0 or (upper - lower) / 2.0 < _BISECTION_TOLERANCE:
            return middle
        if (middle_value > 0.0) == (lower_value > 0.0):
            lower, lower_value = middle, middle_value
        else:
            upper = middle
    return (lower + upper) / 2.0


def _validate_cashflows(cashflows: list[tuple[date, int]]) -> None:
    for day, amount in cashflows:
        if isinstance(day, datetime) or not isinstance(day, date):
            raise TypeError("cashflow dates must be datetime.date")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise TypeError("cashflow amounts must be int minor units")


def compute_portfolio_xirr(cashflows: list[tuple[date, int]], max_iterations: int = 100) -> float | None:
    """
    Computes the annualized Internal Rate of Return (XIRR) as a percent, rounded to 2 dp,
    over dated cashflows [(date, signed_amount_minor)]: investments are negative and the
    current portfolio valuation is positive.

    Returns None when there are fewer than 2 cashflows, when the amounts do not contain
    both a positive and a negative value, or when no root exists in the rate interval.
    The input list is not modified.
    """
    _validate_cashflows(cashflows)
    if len(cashflows) < 2:
        return None
    amounts_minor = [amount for _, amount in cashflows]
    if not (any(amount > 0 for amount in amounts_minor) and any(amount < 0 for amount in amounts_minor)):
        return None

    t0 = min(day for day, _ in cashflows)
    years = [(day - t0).days / _DAYS_PER_YEAR for day, _ in cashflows]
    amounts = [amount / _MINOR_PER_MAJOR for amount in amounts_minor]

    rate = _newton_raphson(amounts, years, max_iterations)
    if rate is None:
        rate = _bisection(
            lambda candidate: _npv(candidate, amounts, years),
            _RATE_LOWER_BOUND,
            _RATE_UPPER_BOUND,
        )
    if rate is None:
        return None
    return round(rate * 100.0, _PERCENT_PRECISION)
