"""Request models. Money is a strict int of paise (floats and numeric strings are rejected)."""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TaxSection = Literal["NONE", "80C", "80D", "80CCD", "HRA", "24B", "LTCG", "STCG"]
ReviewStatus = Literal["PROVISIONAL", "PENDING_REVIEW", "AUTO_APPROVED", "USER_APPROVED", "SUPERSEDED"]
SplitStatus = Literal["OPEN", "PARTIAL", "SETTLED", "WRITTEN_OFF"]
UserAccountSubtype = Literal[
    "BANK_SAVINGS", "BANK_CURRENT", "CREDIT_CARD", "CASH", "WALLET", "INVESTMENT_DEMAT", "INVESTMENT_MF",
    "FIXED_DEPOSIT", "PF_EPF_PPF", "PHYSICAL_ASSET", "LOAN_HOME", "LOAN_VEHICLE", "LOAN_PERSONAL",
]  # fmt: skip
LIABILITY_SUBTYPES = frozenset({"CREDIT_CARD", "LOAN_HOME", "LOAN_VEHICLE", "LOAN_PERSONAL"})
LIQUID_DEFAULT_SUBTYPES = frozenset({"BANK_SAVINGS", "BANK_CURRENT", "CASH", "WALLET"})


def _iso_date_only(value: object) -> object:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        raise ValueError("must be an ISO date (YYYY-MM-DD)")
    return value


IsoDate = Annotated[date, BeforeValidator(_iso_date_only)]
Minor = Annotated[StrictInt, Field(gt=0, le=10**13)]
Text = Annotated[StrictStr, Field(min_length=1, max_length=200)]
Id = Annotated[StrictStr, Field(min_length=1, max_length=64)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------- auth


class SetupIn(Body):
    password: Annotated[StrictStr, Field(min_length=12, max_length=256)]
    device_name: Annotated[StrictStr, Field(min_length=1, max_length=100)]


class LoginIn(Body):
    password: Annotated[StrictStr, Field(min_length=1, max_length=256)]
    device_name: Annotated[StrictStr, Field(min_length=1, max_length=100)]


class DeviceRevokeIn(Body):
    device_id: Id


# ----------------------------------------------------------------- ledger


class AccountIn(Body):
    name: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    account_subtype: UserAccountSubtype
    account_class: Literal["ASSET", "LIABILITY"] | None = None
    institution: Annotated[StrictStr, Field(max_length=100)] | None = None
    is_liquid: StrictBool | None = None
    credit_limit_minor: Annotated[StrictInt, Field(ge=0, le=10**13)] | None = None
    billing_day: Annotated[StrictInt, Field(ge=1, le=31)] | None = None
    due_day: Annotated[StrictInt, Field(ge=1, le=31)] | None = None
    opening_balance_minor: Minor | None = None
    opening_date: IsoDate | None = None


class CategoryIn(Body):
    name: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    category_type: Literal["EXPENSE", "INCOME"]
    default_tax_section: TaxSection = "NONE"
    is_discretionary: StrictBool = True
    is_sensitive_private: StrictBool = False


class SplitShareIn(Body):
    counterparty_name: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    counterparty_vpa: Annotated[StrictStr, Field(max_length=100)] | None = None
    owed_amount_minor: Minor


class _TransactionBase(Body):
    amount_minor: Minor
    transaction_date: IsoDate
    description: Text | None = None


class ExpenseIn(_TransactionBase):
    kind: Literal["expense"]
    account_id: Id
    category_id: Id
    splits: Annotated[list[SplitShareIn], Field(max_length=20)] = []
    is_provisional: StrictBool = False


class IncomeIn(_TransactionBase):
    kind: Literal["income"]
    account_id: Id
    category_id: Id


class TransferIn(_TransactionBase):
    kind: Literal["transfer"]
    from_account_id: Id
    to_account_id: Id


class RefundIn(_TransactionBase):
    kind: Literal["refund"]
    account_id: Id
    original_transaction_id: Id


TransactionIn = Annotated[ExpenseIn | IncomeIn | TransferIn | RefundIn, Field(discriminator="kind")]


class TransactionPatchIn(Body):
    notes: Annotated[StrictStr, Field(max_length=2000)] | None = None
    tax_section: TaxSection | None = None
    category_id: Id | None = None


class ReverseIn(Body):
    transaction_date: IsoDate | None = None


class SettleIn(Body):
    bank_account_id: Id
    amount_minor: Minor
    transaction_date: IsoDate | None = None
    description: Text | None = None


# ------------------------------------------------------- plan: budgets, goals, recurring

Name = Annotated[StrictStr, Field(min_length=1, max_length=100)]
Frequency = Literal["WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"]
GoalStatus = Literal["ACTIVE", "PAUSED", "COMPLETED"]
Priority = Annotated[StrictInt, Field(ge=1, le=99)]
AlertPct = Annotated[StrictInt, Field(ge=1, le=100)]
Amount0 = Annotated[StrictInt, Field(ge=0, le=10**13)]


class BudgetCategoryIn(Body):
    category_id: Id
    limit_minor: Minor
    alert_threshold_pct: AlertPct = 80


class BudgetIn(Body):
    name: Name = "Monthly Budget"
    total_limit_minor: Minor
    categories: Annotated[list[BudgetCategoryIn], Field(max_length=50)] = []


class GoalIn(Body):
    name: Name
    target_amount_minor: Minor
    current_locked_amount_minor: Amount0 = 0
    monthly_contribution_minor: Amount0 = 0
    target_date: IsoDate | None = None
    priority: Priority = 1
    linked_account_id: Id | None = None


class GoalPatchIn(Body):
    """Only fields present in the body change. The router rejects nulls on non-nullable fields."""

    name: Name | None = None
    target_amount_minor: Minor | None = None
    current_locked_amount_minor: Amount0 | None = None
    monthly_contribution_minor: Amount0 | None = None
    target_date: IsoDate | None = None
    priority: Priority | None = None
    linked_account_id: Id | None = None
    status: GoalStatus | None = None


class RecurringIn(Body):
    merchant_name: Name
    category_id: Id
    account_id: Id | None = None
    expected_amount_minor: Minor
    frequency: Frequency
    next_expected_date: IsoDate
    is_mandatory: StrictBool = True


class RecurringPatchIn(Body):
    """Only fields present in the body are changed; the router rejects explicit nulls."""

    expected_amount_minor: Minor | None = None
    frequency: Frequency | None = None
    next_expected_date: IsoDate | None = None
    is_mandatory: StrictBool | None = None
    is_active: StrictBool | None = None
    category_id: Id | None = None


# ------------------------------------------------------------------------ ai

ChatText = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
HistoryText = Annotated[StrictStr, StringConstraints(min_length=1, max_length=2000)]


class ChatMessageIn(Body):
    role: Literal["user", "assistant"]
    content: HistoryText


class ChatIn(Body):
    question: ChatText
    history: list[ChatMessageIn] = Field(default_factory=list, max_length=6)
