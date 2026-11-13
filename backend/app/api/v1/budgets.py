"""Budgets endpoints: one budget per calendar month (YYYY-MM)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import Conn, DeviceId
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import BudgetIn
from app.finance import plan_queries as plan

router = APIRouter(prefix="/budgets", tags=["budgets"])

Month = Annotated[str, Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


def _validate_budget(conn: sqlite3.Connection, body: BudgetIn) -> None:
    category_ids = [c.category_id for c in body.categories]
    if len(set(category_ids)) != len(category_ids):
        raise ApiError(422, "VALIDATION_ERROR", "A category may appear only once in a budget.")
    if set(category_ids) - plan.expense_category_ids(conn, category_ids):
        raise ApiError(422, "VALIDATION_ERROR", "Budget categories must be existing EXPENSE categories.")
    if sum(c.limit_minor for c in body.categories) > body.total_limit_minor:
        raise ApiError(422, "VALIDATION_ERROR", "The category limits exceed the total budget limit.")


@router.get("/{month}")
async def get_budget(month: Month, conn: Conn, _: DeviceId) -> dict:
    return ok({"month": month, "budget": plan.get_budget(conn, month)})


@router.put("/{month}")
async def put_budget(month: Month, body: BudgetIn, conn: Conn, _: DeviceId) -> dict:
    _validate_budget(conn, body)
    categories = [c.model_dump() for c in body.categories]
    plan.replace_budget(conn, month, body.name, body.total_limit_minor, categories)
    return ok({"month": month, "budget": plan.get_budget(conn, month)})


@router.delete("/{month}")
async def delete_budget(month: Month, conn: Conn, _: DeviceId) -> dict:
    if not plan.delete_budget(conn, month):
        raise not_found("Budget")
    return ok({"deleted": True})
