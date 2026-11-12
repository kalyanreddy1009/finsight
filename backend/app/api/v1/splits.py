from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, Conn, DeviceId, IdempotencyKey
from app.api.envelope import ok
from app.api.errors import not_found
from app.api.v1.schemas import SettleIn, SplitStatus
from app.finance import queries
from app.finance.ledger_service import LedgerService

router = APIRouter(prefix="/splits", tags=["splits"])


@router.get("")
async def list_splits(conn: Conn, _: DeviceId, status: Annotated[SplitStatus | None, Query()] = None) -> dict:
    return ok(queries.list_splits(conn, status))


@router.post("/{split_id}/settle", status_code=201)
async def settle_split(
    split_id: str, body: SettleIn, conn: Conn, clock: ClockDep, key: IdempotencyKey, _: DeviceId
) -> dict:
    if queries.get_split(conn, split_id) is None:
        raise not_found("Split")
    tx_id = LedgerService(conn).settle_split(
        split_id=split_id,
        bank_account_id=body.bank_account_id,
        amount_minor=body.amount_minor,
        tx_date=body.transaction_date or clock().date(),
        idempotency_key=key,
        description=body.description,
    )
    return ok(
        {"transaction": queries.get_transaction(conn, tx_id), "split": queries.get_split(conn, split_id)}
    )
