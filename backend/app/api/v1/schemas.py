"""Request models. Money is a strict int of paise (floats and numeric strings are rejected)."""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, StrictStr

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
