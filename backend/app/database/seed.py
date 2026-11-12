"""Seed data required by the ledger."""

import sqlite3

PENDING_REIMBURSEMENTS_ACCOUNT_ID = "sys-pending-reimbursements"
OPENING_EQUITY_ACCOUNT_ID = "sys-opening-equity"


def seed_system_accounts(conn: sqlite3.Connection) -> None:
    """Insert system accounts if missing (idempotent)."""
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
