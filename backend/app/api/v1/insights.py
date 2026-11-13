"""Deterministic spending insights (no AI involved)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, Conn, DeviceId
from app.api.envelope import ok
from app.finance import insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary")
async def summary(
    conn: Conn,
    clock: ClockDep,
    _: DeviceId,
    months: Annotated[int, Query(ge=1, le=insights.MAX_MONTHS)] = insights.DEFAULT_MONTHS,
) -> dict:
    return ok(insights.spending_summary(conn, clock().date(), months))
