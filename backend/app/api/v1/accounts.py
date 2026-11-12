from fastapi import APIRouter

from app.api.deps import Conn, DeviceId
from app.api.envelope import ok
from app.api.errors import ApiError
from app.api.v1.schemas import LIABILITY_SUBTYPES, LIQUID_DEFAULT_SUBTYPES, AccountIn
from app.finance import queries

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(conn: Conn, _: DeviceId) -> dict:
    return ok(queries.list_accounts(conn))


@router.post("", status_code=201)
async def create_account(body: AccountIn, conn: Conn, _: DeviceId) -> dict:
    account_class = "LIABILITY" if body.account_subtype in LIABILITY_SUBTYPES else "ASSET"
    if body.account_class is not None and body.account_class != account_class:
        raise ApiError(422, "VALIDATION_ERROR", f"{body.account_subtype} accounts must be {account_class}.")
    if (body.opening_balance_minor is None) != (body.opening_date is None):
        raise ApiError(422, "VALIDATION_ERROR", "opening_balance_minor and opening_date go together.")
    opening = None
    if body.opening_balance_minor is not None and body.opening_date is not None:
        opening = queries.OpeningBalance(body.opening_balance_minor, body.opening_date)
    is_liquid = (
        body.is_liquid if body.is_liquid is not None else body.account_subtype in LIQUID_DEFAULT_SUBTYPES
    )
    account = queries.create_account_with_opening(
        conn,
        opening,
        name=body.name,
        account_class=account_class,
        account_subtype=body.account_subtype,
        institution=body.institution,
        is_liquid=is_liquid,
        credit_limit_minor=body.credit_limit_minor,
        billing_day=body.billing_day,
        due_day=body.due_day,
    )
    return ok(account)
