"""Seed data required by the ledger."""

import sqlite3

PENDING_REIMBURSEMENTS_ACCOUNT_ID = "sys-pending-reimbursements"
OPENING_EQUITY_ACCOUNT_ID = "sys-opening-equity"

UNCATEGORIZED_EXPENSE_CATEGORY_ID = "sys-cat-uncategorized-expense"
UNCATEGORIZED_INCOME_CATEGORY_ID = "sys-cat-uncategorized-income"
UNCATEGORIZED_EXPENSE_ACCOUNT_ID = "acct-sys-uncategorized-expense"
UNCATEGORIZED_INCOME_ACCOUNT_ID = "acct-sys-uncategorized-income"

# (category id, backing ledger account id, ledger account class / category type)
_UNCATEGORIZED = (
    (UNCATEGORIZED_EXPENSE_CATEGORY_ID, UNCATEGORIZED_EXPENSE_ACCOUNT_ID, "EXPENSE"),
    (UNCATEGORIZED_INCOME_CATEGORY_ID, UNCATEGORIZED_INCOME_ACCOUNT_ID, "INCOME"),
)


def seed_system_accounts(conn: sqlite3.Connection) -> None:
    """Insert system accounts and categories if missing (idempotent)."""
    conn.execute(
        "INSERT OR IGNORE INTO accounts (id, name, account_class, account_subtype, is_liquid) "
        "VALUES (?, ?, 'ASSET', 'REIMBURSEMENT_CLEARING', 0)",
        (PENDING_REIMBURSEMENTS_ACCOUNT_ID, "Pending Reimbursements"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO accounts (id, name, account_class, account_subtype, is_liquid) "
        "VALUES (?, ?, 'EQUITY', 'OPENING_EQUITY', 0)",
        (OPENING_EQUITY_ACCOUNT_ID, "Opening Equity"),
    )
    for category_id, account_id, kind in _UNCATEGORIZED:
        conn.execute(
            "INSERT OR IGNORE INTO accounts (id, name, account_class, account_subtype, is_liquid) "
            "VALUES (?, 'Uncategorized', ?, 'SYSTEM_CATEGORY', 0)",
            (account_id, kind),
        )
        conn.execute(
            "INSERT OR IGNORE INTO categories (id, ledger_account_id, name, category_type, "
            "is_discretionary, is_system_category) VALUES (?, ?, 'Uncategorized', ?, 0, 1)",
            (category_id, account_id, kind),
        )
