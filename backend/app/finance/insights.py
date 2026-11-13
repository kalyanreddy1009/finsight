"""Deterministic spending insights: month totals, category shares, trend and rule-based highlights.

Integer paise only. "Spending" is the sum of POSTED journal lines on EXPENSE accounts, the same
definition the dashboard and budgets use. All SQL is parameterised.
"""

import calendar
import re
import sqlite3
from datetime import date, timedelta
from typing import Any

from app.finance import plan_queries as plan

Record = dict[str, Any]

DEFAULT_MONTHS = 6
MAX_MONTHS = 12
MAX_HIGHLIGHTS = 6
BILL_DUE_DAYS = 7
CHANGE_PERCENT = 25
CHANGE_MIN_MINOR = 500_00
BUDGET_NEAR_PERCENT = 90
BASIS_POINTS = 10_000
NAME_MAX_CHARS = 60
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")

_FLOW_SQL = (
    "SELECT substr(e.entry_date, 1, 7) AS year_month, a.account_class, "
    "COALESCE(SUM(l.signed_amount_minor), 0) AS total_minor "
    "FROM journal_lines l JOIN journal_entries e ON e.id = l.journal_entry_id "
    "JOIN accounts a ON a.id = l.account_id "
    "WHERE e.status = 'POSTED' AND a.account_class IN ('EXPENSE', 'INCOME') "
    "AND e.entry_date >= ? AND e.entry_date < ? GROUP BY year_month, a.account_class"
)
_CATEGORY_SQL = (
    "SELECT c.id AS category_id, c.name, "
    "COALESCE(SUM(CASE WHEN e.entry_date >= ? THEN l.signed_amount_minor ELSE 0 END), 0) AS spent_minor, "
    "COALESCE(SUM(CASE WHEN e.entry_date < ? THEN l.signed_amount_minor ELSE 0 END), 0) AS previous_minor, "
    "COALESCE(SUM(CASE WHEN e.entry_date < ? THEN l.signed_amount_minor ELSE 0 END), 0) "
    "AS previous_to_date_minor "
    "FROM journal_lines l JOIN journal_entries e ON e.id = l.journal_entry_id "
    "JOIN accounts a ON a.id = l.account_id JOIN categories c ON c.ledger_account_id = l.account_id "
    "WHERE e.status = 'POSTED' AND a.account_class = 'EXPENSE' AND e.entry_date >= ? AND e.entry_date < ? "
    "GROUP BY c.id, c.name"
)
_BILLS_SQL = (
    "SELECT m.canonical_name AS merchant_name, r.expected_amount_minor, r.next_expected_date "
    "FROM recurring_rules r JOIN merchants m ON m.id = r.merchant_id "
    "WHERE r.is_active = 1 AND r.next_expected_date BETWEEN ? AND ? "
    "ORDER BY r.next_expected_date, r.id"
)


# ------------------------------------------------------------------ helpers


def format_inr(amount_minor: int) -> str:
    """Rupees with Indian digit grouping from integer paise, e.g. 12345600 -> '₹1,23,456.00'."""
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise TypeError("amount_minor must be int")
    rupees, paise = divmod(abs(amount_minor), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    sign = "-" if amount_minor < 0 else ""
    return f"{sign}₹{digits}.{paise:02d}"


def shift_month(first: date, delta: int) -> date:
    index = first.year * 12 + (first.month - 1) + delta
    year, month_index = divmod(index, 12)
    return date(year, month_index + 1, 1)


def _is_up(current: int, previous: int) -> bool:
    """At least 25% and at least Rs 500 above a non-zero previous value."""
    diff = current - previous
    return previous > 0 and diff >= CHANGE_MIN_MINOR and diff * 100 >= previous * CHANGE_PERCENT


def _is_down(current: int, previous: int) -> bool:
    diff = previous - current
    return previous > 0 and diff >= CHANGE_MIN_MINOR and diff * 100 >= previous * CHANGE_PERCENT


def clean_name(text: str | None, limit: int = NAME_MAX_CHARS) -> str:
    """User-supplied names go into sentences and model prompts: no control characters, bounded length."""
    return _CONTROL_CHARS.sub(" ", text or "").strip()[:limit]


def previous_cutoff(today: date) -> date:
    """Exclusive end of the previous month's same-day-of-month window (clamped to its last day)."""
    previous_first = shift_month(today.replace(day=1), -1)
    last_day = calendar.monthrange(previous_first.year, previous_first.month)[1]
    return previous_first + timedelta(days=min(today.day, last_day))


def _highlight(kind: str, severity: str, title: str, detail: str) -> Record:
    return {"kind": kind, "severity": severity, "title": title, "detail": detail}


# ---------------------------------------------------------------- queries


def _flows(conn: sqlite3.Connection, start: date, end: date) -> dict[str, tuple[int, int]]:
    """year_month -> (income_minor, expense_minor) for POSTED entries in [start, end)."""
    rows = conn.execute(_FLOW_SQL, (start.isoformat(), end.isoformat())).fetchall()
    result: dict[str, list[int]] = {}
    for row in rows:
        pair = result.setdefault(row["year_month"], [0, 0])
        if row["account_class"] == "INCOME":
            pair[0] = -int(row["total_minor"])
        else:
            pair[1] = int(row["total_minor"])
    return {month: (pair[0], pair[1]) for month, pair in result.items()}


def _categories(
    conn: sqlite3.Connection,
    first: date,
    next_first: date,
    previous_first: date,
    cutoff: date,
    expense_minor: int,
) -> list[Record]:
    """Current-month categories. ``previous_to_date_minor`` is internal (highlight comparisons only)."""
    rows = conn.execute(
        _CATEGORY_SQL,
        (
            first.isoformat(),
            first.isoformat(),
            cutoff.isoformat(),
            previous_first.isoformat(),
            next_first.isoformat(),
        ),
    ).fetchall()
    items = [
        {
            "category_id": r["category_id"],
            "name": clean_name(r["name"]),
            "spent_minor": int(r["spent_minor"]),
            "previous_minor": int(r["previous_minor"]),
            "previous_to_date_minor": int(r["previous_to_date_minor"]),
            "share_bp": 0,
        }
        for r in rows
        if int(r["spent_minor"]) > 0
    ]
    items.sort(key=lambda c: (-c["spent_minor"], c["name"], c["category_id"]))
    if expense_minor > 0:
        for item in items:
            item["share_bp"] = item["spent_minor"] * BASIS_POINTS // expense_minor
    return items


def _has_posted_activity(conn: sqlite3.Connection, first: date, next_first: date) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions t JOIN journal_entries e ON e.id = t.journal_entry_id "
        "WHERE e.status = 'POSTED' AND t.review_status != 'SUPERSEDED' "
        "AND t.transaction_date >= ? AND t.transaction_date < ? LIMIT 1",
        (first.isoformat(), next_first.isoformat()),
    ).fetchone()
    return row is not None


# -------------------------------------------------------------- highlights


def _spending_highlights(expense: int, previous: int, categories: list[Record]) -> list[Record]:
    """``previous`` is the previous month up to the same day of the month, not its full total."""
    found: list[Record] = []
    if categories:
        top = categories[0]
        found.append(
            _highlight(
                "TOP_CATEGORY",
                "info",
                f"{top['name']} is your biggest spend",
                f"{top['name']} took {format_inr(top['spent_minor'])} this month, "
                f"{top['share_bp'] // 100}% of your spending.",
            )
        )
    if _is_up(expense, previous):
        found.append(
            _highlight(
                "SPENDING_UP",
                "warning",
                "Spending is higher than last month",
                f"You have spent {format_inr(expense)} so far, {format_inr(expense - previous)} more "
                f"than the same days last month ({format_inr(previous)}).",
            )
        )
    elif _is_down(expense, previous):
        found.append(
            _highlight(
                "SPENDING_DOWN",
                "info",
                "Spending is lower than last month",
                f"You have spent {format_inr(expense)} so far, {format_inr(previous - expense)} less "
                f"than the same days last month ({format_inr(previous)}).",
            )
        )
    for cat in categories:
        if _is_up(cat["spent_minor"], cat["previous_to_date_minor"]):
            found.append(
                _highlight(
                    "CATEGORY_UP",
                    "warning",
                    f"{cat['name']} is up from last month",
                    f"{cat['name']} is {format_inr(cat['spent_minor'])} this month against "
                    f"{format_inr(cat['previous_to_date_minor'])} over the same days last month.",
                )
            )
    return found


def _budget_item(label: str, spent: int, limit: int) -> Record | None:
    if limit <= 0:
        return None
    if spent > limit:
        return _highlight(
            "BUDGET_OVER",
            "warning",
            f"{label} is over budget",
            f"You have spent {format_inr(spent)} against a limit of {format_inr(limit)}.",
        )
    if spent * 100 >= limit * BUDGET_NEAR_PERCENT:
        return _highlight(
            "BUDGET_NEAR",
            "warning",
            f"{label} is close to its limit",
            f"You have spent {format_inr(spent)} of {format_inr(limit)}, "
            f"{spent * 100 // limit}% of the limit.",
        )
    return None


def _budget_highlights(conn: sqlite3.Connection, month: str) -> list[Record]:
    budget = plan.get_budget(conn, month)
    if budget is None:
        return []
    candidates = [_budget_item("Your monthly budget", budget["spent_minor"], budget["total_limit_minor"])]
    candidates += [
        _budget_item(f"The {clean_name(c['category_name'])} budget", c["spent_minor"], c["limit_minor"])
        for c in budget["categories"]
    ]
    return [c for c in candidates if c is not None]


def _bill_highlights(conn: sqlite3.Connection, today: date) -> list[Record]:
    rows = conn.execute(_BILLS_SQL, (today.isoformat(), (today + timedelta(days=BILL_DUE_DAYS)).isoformat()))
    found = []
    for row in rows.fetchall():
        merchant = clean_name(row["merchant_name"]) or "A bill"
        days = (date.fromisoformat(row["next_expected_date"]) - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
        found.append(
            _highlight(
                "BILL_DUE",
                "info",
                f"{merchant} is due {when}",
                f"{merchant} of {format_inr(row['expected_amount_minor'])} is due on "
                f"{row['next_expected_date']}.",
            )
        )
    return found


def _rank(items: list[Record]) -> list[Record]:
    """Warnings first (stable), capped at MAX_HIGHLIGHTS."""
    ordered = sorted(items, key=lambda h: 0 if h["severity"] == "warning" else 1)
    return ordered[:MAX_HIGHLIGHTS]


# ----------------------------------------------------------------- summary


def spending_summary(conn: sqlite3.Connection, today: date, months: int = DEFAULT_MONTHS) -> Record:
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= MAX_MONTHS:
        raise ValueError(f"months must be between 1 and {MAX_MONTHS}")
    first = today.replace(day=1)
    next_first = shift_month(first, 1)
    previous_first = shift_month(first, -1)
    flows = _flows(conn, shift_month(first, -max(months - 1, 1)), next_first)

    trend = []
    for offset in range(months - 1, -1, -1):
        key = shift_month(first, -offset).strftime("%Y-%m")
        income, expense = flows.get(key, (0, 0))
        trend.append({"year_month": key, "income_minor": income, "expense_minor": expense})
    income, expense = flows.get(first.strftime("%Y-%m"), (0, 0))
    previous_expense = flows.get(previous_first.strftime("%Y-%m"), (0, 0))[1]
    cutoff = previous_cutoff(today)
    previous_to_date = _flows(conn, previous_first, cutoff).get(previous_first.strftime("%Y-%m"), (0, 0))[1]
    categories = _categories(conn, first, next_first, previous_first, cutoff, expense)

    if _has_posted_activity(conn, first, next_first):
        found = _spending_highlights(expense, previous_to_date, categories)
        found += _budget_highlights(conn, first.strftime("%Y-%m"))
        found += _bill_highlights(conn, today)
        highlights = _rank(found)
    else:
        highlights = [
            _highlight(
                "NO_DATA",
                "info",
                "No transactions yet this month",
                "Add or import transactions to see spending insights.",
            )
        ]
    return {
        "as_of": today.isoformat(),
        "month": first.strftime("%Y-%m"),
        "income_minor": income,
        "expense_minor": expense,
        "net_minor": income - expense,
        "previous_expense_minor": previous_expense,
        "categories": [{k: v for k, v in c.items() if k != "previous_to_date_minor"} for c in categories],
        "trend": trend,
        "highlights": highlights,
    }


def month_bounds(today: date) -> tuple[date, date]:
    """First and last day of ``today``'s month."""
    return today.replace(day=1), today.replace(day=calendar.monthrange(today.year, today.month)[1])
