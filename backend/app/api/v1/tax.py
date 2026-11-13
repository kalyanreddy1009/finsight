"""Tax endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, Conn, DeviceId
from app.api.envelope import ok
from app.finance import plan_queries as plan

router = APIRouter(prefix="/tax", tags=["tax"])

# Old-regime deduction limits in paise, informational only; sections without a limit are null.
SECTION_LIMITS_MINOR = {"80C": 15_000_000, "80D": 2_500_000, "80CCD": 5_000_000, "24B": 20_000_000}


@router.get("/summary")
async def tax_summary(
    conn: Conn,
    clock: ClockDep,
    _: DeviceId,
    fy: Annotated[int, Query(ge=2000, le=2100)] | None = None,
) -> dict:
    year = fy if fy is not None else plan.financial_year(clock().date())
    start, end = plan.financial_year_bounds(year)
    sections = [
        {
            "tax_section": row["tax_section"],
            "total_minor": row["total_minor"],
            "transaction_count": row["transaction_count"],
            "limit_minor": SECTION_LIMITS_MINOR.get(row["tax_section"]),
        }
        for row in plan.tax_section_totals(conn, start, end)
    ]
    return ok(
        {
            "fy": year,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "sections": sections,
            "total_minor": sum(section["total_minor"] for section in sections),
        }
    )
