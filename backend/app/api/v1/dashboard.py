from fastapi import APIRouter

from app.api.deps import ClockDep, Conn, DeviceId
from app.api.envelope import ok
from app.finance import queries

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(conn: Conn, clock: ClockDep, _: DeviceId) -> dict:
    return ok(queries.dashboard_summary(conn, clock().date()))
