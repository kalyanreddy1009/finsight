"""Chart of accounts: user accounts and spending/income categories."""

import sqlite3
import uuid

from app.database.session import transaction

_CATEGORY_LEDGER_CLASS = {"EXPENSE": "EXPENSE", "INCOME": "INCOME"}


def create_account(
    conn: sqlite3.Connection,
    *,
    name: str,
    account_class: str,
    account_subtype: str,
    institution: str | None = None,
    is_liquid: bool = True,
    credit_limit_minor: int | None = None,
    billing_day: int | None = None,
    due_day: int | None = None,
) -> str:
    """Insert an account and return its id."""
    if not name.strip():
        raise ValueError("Account name must not be empty.")
    if credit_limit_minor is not None and (
        isinstance(credit_limit_minor, bool) or not isinstance(credit_limit_minor, int)
    ):
        raise TypeError("credit_limit_minor must be an int.")
    account_id = str(uuid.uuid4())
    with transaction(conn):
        _insert_account(
            conn,
            account_id=account_id,
            name=name,
            account_class=account_class,
            account_subtype=account_subtype,
            institution=institution,
            is_liquid=is_liquid,
            credit_limit_minor=credit_limit_minor,
            billing_day=billing_day,
            due_day=due_day,
        )
    return account_id


def _insert_account(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    name: str,
    account_class: str,
    account_subtype: str,
    institution: str | None = None,
    is_liquid: bool = True,
    credit_limit_minor: int | None = None,
    billing_day: int | None = None,
    due_day: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO accounts (id, name, account_class, account_subtype, institution, is_liquid, "
        "credit_limit_minor, billing_day, due_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            account_id,
            name,
            account_class,
            account_subtype,
            institution,
            int(is_liquid),
            credit_limit_minor,
            billing_day,
            due_day,
        ),
    )


def create_category(
    conn: sqlite3.Connection,
    *,
    name: str,
    category_type: str,
    default_tax_section: str = "NONE",
    is_discretionary: bool = True,
    is_sensitive_private: bool = False,
) -> tuple[str, str]:
    """Insert a category plus its backing ledger account; return (category_id, ledger_account_id)."""
    ledger_class = _CATEGORY_LEDGER_CLASS.get(category_type)
    if ledger_class is None:
        raise ValueError("Only EXPENSE and INCOME categories are backed by a ledger account.")
    if not name.strip():
        raise ValueError("Category name must not be empty.")
    category_id = str(uuid.uuid4())
    ledger_account_id = str(uuid.uuid4())
    with transaction(conn):
        _insert_account(
            conn,
            account_id=ledger_account_id,
            name=name,
            account_class=ledger_class,
            account_subtype="SYSTEM_CATEGORY",
            is_liquid=False,
        )
        conn.execute(
            "INSERT INTO categories (id, ledger_account_id, name, category_type, default_tax_section, "
            "is_discretionary, is_sensitive_private) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                category_id,
                ledger_account_id,
                name,
                category_type,
                default_tax_section,
                int(is_discretionary),
                int(is_sensitive_private),
            ),
        )
    return category_id, ledger_account_id
