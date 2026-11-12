from fastapi import APIRouter

from app.api.deps import Conn, DeviceId
from app.api.envelope import ok
from app.api.v1.schemas import CategoryIn
from app.finance import chart, queries

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories(conn: Conn, _: DeviceId) -> dict:
    return ok(queries.list_categories(conn))


@router.post("", status_code=201)
async def create_category(body: CategoryIn, conn: Conn, _: DeviceId) -> dict:
    category_id, _ledger_account_id = chart.create_category(
        conn,
        name=body.name,
        category_type=body.category_type,
        default_tax_section=body.default_tax_section,
        is_discretionary=body.is_discretionary,
        is_sensitive_private=body.is_sensitive_private,
    )
    return ok(queries.get_category(conn, category_id))
