"""Safe-to-Spend liquidity calculator. All amounts are paise (minor units); integer arithmetic only."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SafeToSpendResult:
    liquid_cash_minor: int
    card_liability_minor: int
    upcoming_obligations_minor: int
    goal_locks_minor: int
    safe_to_spend_minor: int
    daily_safe_burn_minor: int
    is_liquidity_deficit: bool
    deficit_minor: int


def _require_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")


def _require_non_negative(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def calculate_safe_to_spend_minor(
    liquid_bank_balances_minor: int,
    unpaid_credit_card_balances_minor: int,
    upcoming_30d_mandatory_obligations_minor: int,
    active_goal_locks_minor: int,
    days_remaining_in_month: int,
) -> SafeToSpendResult:
    """
    Computes true disposable cash in paise after subtracting all unpaid credit card debt,
    upcoming 30-day EMIs/bills, and locked savings goals. The card balance may be passed
    as a positive or negative number; its absolute value is the liability.
    """
    _require_int("liquid_bank_balances_minor", liquid_bank_balances_minor)
    _require_int("unpaid_credit_card_balances_minor", unpaid_credit_card_balances_minor)
    _require_int("upcoming_30d_mandatory_obligations_minor", upcoming_30d_mandatory_obligations_minor)
    _require_int("active_goal_locks_minor", active_goal_locks_minor)
    _require_int("days_remaining_in_month", days_remaining_in_month)
    _require_non_negative(
        "upcoming_30d_mandatory_obligations_minor", upcoming_30d_mandatory_obligations_minor
    )
    _require_non_negative("active_goal_locks_minor", active_goal_locks_minor)

    card_liability_minor = abs(unpaid_credit_card_balances_minor)
    net_disposable_minor = (
        liquid_bank_balances_minor
        - card_liability_minor
        - upcoming_30d_mandatory_obligations_minor
        - active_goal_locks_minor
    )
    safe_to_spend_minor = max(0, net_disposable_minor)
    days = max(1, days_remaining_in_month)
    return SafeToSpendResult(
        liquid_cash_minor=liquid_bank_balances_minor,
        card_liability_minor=card_liability_minor,
        upcoming_obligations_minor=upcoming_30d_mandatory_obligations_minor,
        goal_locks_minor=active_goal_locks_minor,
        safe_to_spend_minor=safe_to_spend_minor,
        daily_safe_burn_minor=safe_to_spend_minor // days,
        is_liquidity_deficit=net_disposable_minor < 0,
        deficit_minor=abs(min(0, net_disposable_minor)),
    )
