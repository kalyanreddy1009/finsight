"""SQL for budgets, financial goals, recurring bills and the tax summary, plus pure date helpers.

All SQL is parameterised. Dynamic column and table names are fixed literals or allow-listed
field names chosen in code, never user input.
"""

import calendar
import sqlite3
import uuid
from datetime import date, timedelta
from typing import Any

from app.database.session import transaction

Record = dict[str, Any]

MONTHS_PER_FREQUENCY = {"MONTHLY": 1, "QUARTERLY": 3, "YEARLY": 12}
FY_START_MONTH = 4

GOAL_COLUMNS = (
    "id, name, linked_account_id, target_amount_minor, current_locked_amount_minor, "
    "monthly_contribution_minor, target_date, priority, status, created_at"
)
GOAL_WRITABLE = frozenset(
    {
        "name",
        "linked_account_id",
        "target_amount_minor",
        "current_locked_amount_minor",
        "monthly_contribution_minor",
        "target_date",
        "priority",
        "status",
    }
)
RECURRING_SELECT = (
    "SELECT r.id, r.merchant_id, m.canonical_name AS merchant_name, r.category_id, "
    "c.name AS category_name, r.account_id, r.expected_amount_minor, r.frequency, "
    "r.next_expected_date, r.is_mandatory, r.is_active "
    "FROM recurring_rules r JOIN merchants m ON m.id = r.merchant_id "
    "JOIN categories c ON c.id = r.category_id"
)
RECURRING_WRITABLE = frozenset(
    {
        "merchant_id",
        "category_id",
        "account_id",
        "expected_amount_minor",
        "moving_avg_amount_minor",
        "frequency",
        "expected_day_of_month",
        "next_expected_date",
        "is_mandatory",
        "is_active",
    }
)

_BUDGET_SPENT_SQL = (
    "SELECT COALESCE(SUM(l.signed_amount_minor), 0) FROM journal_lines l "
    "JOIN journal_entries e ON e.id = l.journal_entry_id JOIN accounts a ON a.id = l.account_id "
    "WHERE e.status = 'POSTED' AND a.account_class = 'EXPENSE' AND e.entry_date >= ? AND e.entry_date < ?"
)
_BUDGET_CATEGORIES_SQL = (
    "SELECT c.id AS category_id, c.name AS category_name, bc.limit_minor, bc.alert_threshold_pct, "
    "COALESCE((SELECT SUM(l.signed_amount_minor) FROM journal_lines l "
    "JOIN journal_entries e ON e.id = l.journal_entry_id "
    "WHERE l.account_id = c.ledger_account_id AND e.status = 'POSTED' "
    "AND e.entry_date >= ? AND e.entry_date < ?), 0) AS spent_minor "
    "FROM budget_categories bc JOIN categories c ON c.id = bc.category_id "
    "WHERE bc.budget_id = ? ORDER BY c.name, c.id"
)
_TAX_TOTALS_SQL = (
    "SELECT t.tax_section, COALESCE(SUM(t.user_share_minor), 0) AS total_minor, "
    "COUNT(*) AS transaction_count FROM transactions t "
    "JOIN journal_entries e ON e.id = t.journal_entry_id "
    "WHERE t.tax_section != 'NONE' AND t.transaction_type IN ('EXPENSE', 'INVESTMENT') "
    "AND t.review_status != 'SUPERSEDED' AND e.status = 'POSTED' "
    "AND t.transaction_date BETWEEN ? AND ? GROUP BY t.tax_section ORDER BY t.tax_section"
)


# ------------------------------------------------------------- pure date maths


def next_occurrence(current: date, frequency: str, day_of_month: int | None) -> date:
    """Return the next due date one period after ``current``.

    WEEKLY adds seven days. MONTHLY, QUARTERLY and YEARLY move the month forward and use
    ``day_of_month`` (or the current day when None), clamped to the target month's last day.
    """
    if frequency == "WEEKLY":
        return current + timedelta(days=7)
    if frequency not in MONTHS_PER_FREQUENCY:
        raise ValueError(f"Unknown frequency: {frequency}")
    total = current.year * 12 + (current.month - 1) + MONTHS_PER_FREQUENCY[frequency]
    year, month_index = divmod(total, 12)
    month = month_index + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month or current.day, last_day))


def month_range(month: str) -> tuple[str, str]:
    """ISO strings for the first day of YYYY-MM and the first day of the following month."""
    year, number = (int(part) for part in month.split("-"))
    first = date(year, number, 1)
    next_first = first.replace(day=calendar.monthrange(year, number)[1]) + timedelta(days=1)
    return first.isoformat(), next_first.isoformat()


def financial_year(today: date) -> int:
    """FY 2026 runs 2026-04-01 to 2027-03-31; the year is the calendar year it starts in."""
    return today.year if today.month >= FY_START_MONTH else today.year - 1


def rescheduled_day(stored_day: int | None, new_date: date) -> int:
    """Day of month to store when a PATCH moves next_expected_date.

    A new date on the last day of a shorter month keeps a larger stored day, so a day-31 rule
    does not drift to 28 after a clamped date. Otherwise the new date's day is used.
    """
    last_day = calendar.monthrange(new_date.year, new_date.month)[1]
    if stored_day is not None and new_date.day == last_day and stored_day > new_date.day:
        return stored_day
    return new_date.day


def financial_year_bounds(year: int) -> tuple[date, date]:
    return date(year, FY_START_MONTH, 1), date(year + 1, FY_START_MONTH, 1) - timedelta(days=1)


# ------------------------------------------------------------------- helpers


def _db_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _insert(conn: sqlite3.Connection, table: str, values: Record, allowed: frozenset[str]) -> None:
    assert set(values) <= allowed, f"unexpected columns for {table}"
    names = ", ".join(values)
    marks = ", ".join("?" * len(values))
    conn.execute(
        f"INSERT INTO {table} ({names}) VALUES ({marks})",  # noqa: S608
        [_db_value(v) for v in values.values()],
    )


def _update(
    conn: sqlite3.Connection, table: str, row_id: str, changes: Record, allowed: frozenset[str]
) -> bool:
    assert set(changes) <= allowed, f"unexpected columns for {table}"
    assignments = ", ".join(f"{name} = ?" for name in changes)
    values = [_db_value(v) for v in changes.values()]
    with transaction(conn):
        cursor = conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",  # noqa: S608
            (*values, row_id),
        )
    return cursor.rowcount == 1


def _delete(conn: sqlite3.Connection, table: str, row_id: str) -> bool:
    with transaction(conn):
        cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))  # noqa: S608
    return cursor.rowcount == 1


def account_exists(conn: sqlite3.Connection, account_id: str) -> bool:
    return conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone() is not None


def expense_category_ids(conn: sqlite3.Connection, category_ids: list[str]) -> set[str]:
    """The subset of ``category_ids`` that exist and are EXPENSE categories."""
    if not category_ids:
        return set()
    marks = ",".join("?" * len(category_ids))
    rows = conn.execute(
        f"SELECT id FROM categories WHERE category_type = 'EXPENSE' AND id IN ({marks})",  # noqa: S608
        category_ids,
    ).fetchall()
    return {row["id"] for row in rows}


# ------------------------------------------------------------------ budgets


def get_budget(conn: sqlite3.Connection, month: str) -> Record | None:
    row = conn.execute(
        "SELECT id, name, period_month, total_limit_minor FROM budgets WHERE period_month = ?", (month,)
    ).fetchone()
    if row is None:
        return None
    first, next_first = month_range(month)
    categories = conn.execute(_BUDGET_CATEGORIES_SQL, (first, next_first, row["id"])).fetchall()
    spent = conn.execute(_BUDGET_SPENT_SQL, (first, next_first)).fetchone()[0]
    return {**dict(row), "spent_minor": int(spent), "categories": [dict(c) for c in categories]}


def replace_budget(
    conn: sqlite3.Connection, month: str, name: str, total_limit_minor: int, categories: list[Record]
) -> None:
    """Create or replace the month's budget and its category rows in one transaction."""
    with transaction(conn):
        existing = conn.execute("SELECT id FROM budgets WHERE period_month = ?", (month,)).fetchone()
        if existing is None:
            budget_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO budgets (id, name, period_month, total_limit_minor) VALUES (?, ?, ?, ?)",
                (budget_id, name, month, total_limit_minor),
            )
        else:
            budget_id = existing["id"]
            conn.execute(
                "UPDATE budgets SET name = ?, total_limit_minor = ? WHERE id = ?",
                (name, total_limit_minor, budget_id),
            )
            conn.execute("DELETE FROM budget_categories WHERE budget_id = ?", (budget_id,))
        conn.executemany(
            "INSERT INTO budget_categories (id, budget_id, category_id, limit_minor, alert_threshold_pct) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (str(uuid.uuid4()), budget_id, c["category_id"], c["limit_minor"], c["alert_threshold_pct"])
                for c in categories
            ],
        )


def delete_budget(conn: sqlite3.Connection, month: str) -> bool:
    with transaction(conn):
        row = conn.execute("SELECT id FROM budgets WHERE period_month = ?", (month,)).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM budget_categories WHERE budget_id = ?", (row["id"],))
        conn.execute("DELETE FROM budgets WHERE id = ?", (row["id"],))
    return True


# -------------------------------------------------------------------- goals


def list_goals(conn: sqlite3.Connection) -> list[Record]:
    rows = conn.execute(f"SELECT {GOAL_COLUMNS} FROM financial_goals ORDER BY priority, created_at, id")  # noqa: S608
    return [dict(r) for r in rows.fetchall()]


def get_goal(conn: sqlite3.Connection, goal_id: str) -> Record | None:
    row = conn.execute(f"SELECT {GOAL_COLUMNS} FROM financial_goals WHERE id = ?", (goal_id,)).fetchone()  # noqa: S608
    return dict(row) if row else None


def create_goal(conn: sqlite3.Connection, fields: Record) -> str:
    goal_id = str(uuid.uuid4())
    with transaction(conn):
        values = {"id": goal_id, **fields, "status": "ACTIVE"}
        _insert(conn, "financial_goals", values, GOAL_WRITABLE | {"id"})
    return goal_id


def update_goal(conn: sqlite3.Connection, goal_id: str, changes: Record) -> bool:
    return _update(conn, "financial_goals", goal_id, changes, GOAL_WRITABLE)


def delete_goal(conn: sqlite3.Connection, goal_id: str) -> bool:
    return _delete(conn, "financial_goals", goal_id)


# ---------------------------------------------------------------- recurring


def _merchant_id(conn: sqlite3.Connection, name: str) -> str:
    """Get-or-create a merchant by canonical name, matching case-insensitively."""
    row = conn.execute("SELECT id FROM merchants WHERE canonical_name = ? COLLATE NOCASE", (name,)).fetchone()
    if row is not None:
        return row["id"]
    merchant_id = str(uuid.uuid4())
    values = {"id": merchant_id, "canonical_name": name}
    _insert(conn, "merchants", values, frozenset({"id", "canonical_name"}))
    return merchant_id


def _recurring_record(row: sqlite3.Row) -> Record:
    return {**dict(row), "is_mandatory": bool(row["is_mandatory"]), "is_active": bool(row["is_active"])}


def list_recurring(conn: sqlite3.Connection) -> list[Record]:
    rows = conn.execute(f"{RECURRING_SELECT} ORDER BY r.next_expected_date, r.id").fetchall()  # noqa: S608
    return [_recurring_record(r) for r in rows]


def get_recurring(conn: sqlite3.Connection, rule_id: str) -> Record | None:
    row = conn.execute(f"{RECURRING_SELECT} WHERE r.id = ?", (rule_id,)).fetchone()  # noqa: S608
    return _recurring_record(row) if row else None


def create_recurring(conn: sqlite3.Connection, merchant_name: str, fields: Record) -> str:
    """Store a rule; the moving average starts at the expected amount and the day at the due date's day."""
    rule_id = str(uuid.uuid4())
    due = fields["next_expected_date"]
    with transaction(conn):
        _insert(
            conn,
            "recurring_rules",
            {
                "id": rule_id,
                "merchant_id": _merchant_id(conn, merchant_name),
                "category_id": fields["category_id"],
                "account_id": fields["account_id"],
                "expected_amount_minor": fields["expected_amount_minor"],
                "moving_avg_amount_minor": fields["expected_amount_minor"],
                "frequency": fields["frequency"],
                "expected_day_of_month": due.day,
                "next_expected_date": due,
                "is_mandatory": fields["is_mandatory"],
                "is_active": True,
            },
            RECURRING_WRITABLE | {"id"},
        )
    return rule_id


def update_recurring(conn: sqlite3.Connection, rule_id: str, changes: Record) -> bool:
    return _update(conn, "recurring_rules", rule_id, changes, RECURRING_WRITABLE)


def stored_day_of_month(conn: sqlite3.Connection, rule_id: str) -> int | None:
    row = conn.execute(
        "SELECT expected_day_of_month FROM recurring_rules WHERE id = ?", (rule_id,)
    ).fetchone()
    return row["expected_day_of_month"] if row else None


def advance_recurring(conn: sqlite3.Connection, rule_id: str) -> Record | None:
    """Move the due date forward one period using the stored day of month; None if the rule is missing.

    The read and the write share one transaction, so two concurrent advances cannot step from the same date.
    """
    with transaction(conn):
        row = conn.execute(
            "SELECT frequency, next_expected_date, expected_day_of_month FROM recurring_rules WHERE id = ?",
            (rule_id,),
        ).fetchone()
        if row is None:
            return None
        following = next_occurrence(
            date.fromisoformat(row["next_expected_date"]), row["frequency"], row["expected_day_of_month"]
        )
        _update(conn, "recurring_rules", rule_id, {"next_expected_date": following}, RECURRING_WRITABLE)
    return get_recurring(conn, rule_id)


def delete_recurring(conn: sqlite3.Connection, rule_id: str) -> bool:
    return _delete(conn, "recurring_rules", rule_id)


# ---------------------------------------------------------------------- tax


def tax_section_totals(conn: sqlite3.Connection, start: date, end: date) -> list[Record]:
    """Per tax section: summed user share and count, for POSTED, non-superseded (not reversed) rows."""
    rows = conn.execute(_TAX_TOTALS_SQL, (start.isoformat(), end.isoformat())).fetchall()
    return [dict(r) for r in rows]
