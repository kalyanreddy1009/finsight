import re
from typing import Annotated

from fastapi import APIRouter, Header, Query

from app.api.deps import ClockDep, Conn, DeviceId, IdempotencyKey
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import (
    ExpenseIn,
    IncomeIn,
    IsoDate,
    RefundIn,
    ReverseIn,
    ReviewStatus,
    SplitShareIn,
    TaxSection,
    TransactionIn,
    TransactionPatchIn,
    TransferIn,
)
from app.finance import queries
from app.finance.ledger_service import LedgerService, SplitShareSpec

router = APIRouter(prefix="/transactions", tags=["transactions"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
_VERSION_RE = re.compile(r'^(?:W/)?"?(\d{1,9})"?$')


def _split_specs(splits: list[SplitShareIn]) -> list[SplitShareSpec]:
    return [SplitShareSpec(s.counterparty_name, s.counterparty_vpa, s.owed_amount_minor) for s in splits]


def _post(ledger: LedgerService, body: ExpenseIn | IncomeIn | TransferIn | RefundIn, key: str) -> str:
    common = {
        "amount_minor": body.amount_minor,
        "tx_date": body.transaction_date,
        "idempotency_key": key,
        "description": body.description,
    }
    if isinstance(body, ExpenseIn):
        return ledger.record_expense(
            source_account_id=body.account_id,
            category_id=body.category_id,
            splits=_split_specs(body.splits),
            is_provisional=body.is_provisional,
            **common,
        )
    if isinstance(body, IncomeIn):
        return ledger.record_income(dest_account_id=body.account_id, category_id=body.category_id, **common)
    if isinstance(body, TransferIn):
        return ledger.record_transfer(
            from_account_id=body.from_account_id, to_account_id=body.to_account_id, **common
        )
    return ledger.record_refund(
        dest_account_id=body.account_id, original_transaction_id=body.original_transaction_id, **common
    )


def _parse_version(if_match: str | None) -> int:
    if if_match is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", "The If-Match header (transaction version) is required.")
    match = _VERSION_RE.match(if_match.strip())
    if match is None:
        raise ApiError(400, "INVALID_IF_MATCH", "If-Match must be the transaction version number.")
    return int(match.group(1))


@router.get("")
async def list_transactions(
    conn: Conn,
    _: DeviceId,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
    date_from: IsoDate | None = None,
    date_to: IsoDate | None = None,
    account_id: Annotated[str | None, Query(max_length=64)] = None,
    category_id: Annotated[str | None, Query(max_length=64)] = None,
    tax_section: TaxSection | None = None,
    review_status: ReviewStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> dict:
    filters = queries.TransactionFilters(
        date_from, date_to, account_id, category_id, tax_section, review_status, q
    )
    rows, next_cursor = queries.list_transactions(conn, filters, limit, cursor)
    return ok(rows, {"next_cursor": next_cursor})


@router.post("", status_code=201)
async def create_transaction(body: TransactionIn, conn: Conn, key: IdempotencyKey, _: DeviceId) -> dict:
    tx_id = _post(LedgerService(conn), body, key)
    return ok(queries.get_transaction(conn, tx_id))


@router.get("/{transaction_id}")
async def get_transaction(transaction_id: str, conn: Conn, _: DeviceId) -> dict:
    record = queries.get_transaction(conn, transaction_id)
    if record is None:
        raise not_found("Transaction")
    return ok(record)


@router.patch("/{transaction_id}")
async def patch_transaction(
    transaction_id: str,
    body: TransactionPatchIn,
    conn: Conn,
    clock: ClockDep,
    _: DeviceId,
    if_match: Annotated[str | None, Header()] = None,
) -> dict:
    version = _parse_version(if_match)
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    if not changes:
        raise ApiError(422, "VALIDATION_ERROR", "Provide at least one of notes, tax_section, category_id.")
    if changes.get("tax_section", "") is None or changes.get("category_id", "") is None:
        raise ApiError(422, "VALIDATION_ERROR", "tax_section and category_id cannot be null.")
    if queries.get_transaction(conn, transaction_id) is None:
        raise not_found("Transaction")
    try:
        record = queries.apply_transaction_patch(conn, transaction_id, version, changes, clock().date())
    except queries.VersionConflictError as conflict:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            "The transaction was changed by someone else.",
            meta={"current": conflict.current},
        ) from None
    return ok(record)


@router.post("/{transaction_id}/reverse", status_code=201)
async def reverse_transaction(
    transaction_id: str,
    conn: Conn,
    clock: ClockDep,
    key: IdempotencyKey,
    _: DeviceId,
    body: ReverseIn | None = None,
) -> dict:
    entry_id = queries.journal_entry_id_of(conn, transaction_id)
    if entry_id is None:
        raise not_found("Transaction")
    when = (body.transaction_date if body else None) or clock().date()
    reversal_id = LedgerService(conn).reverse_entry(
        journal_entry_id=entry_id, entry_date=when, idempotency_key=key
    )
    return ok(queries.get_transaction(conn, reversal_id))
