"""Recurring bills endpoints (recurring_rules, with merchants get-or-created by name)."""

import sqlite3

from fastapi import APIRouter

from app.api.deps import Conn, DeviceId
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import RecurringIn, RecurringPatchIn
from app.finance import plan_queries as plan

router = APIRouter(prefix="/recurring", tags=["recurring"])


def _check_category(conn: sqlite3.Connection, category_id: str) -> None:
    if category_id not in plan.expense_category_ids(conn, [category_id]):
        raise ApiError(422, "VALIDATION_ERROR", "category_id must be an existing EXPENSE category.")


def _require_rule(conn: sqlite3.Connection, rule_id: str) -> plan.Record:
    rule = plan.get_recurring(conn, rule_id)
    if rule is None:
        raise not_found("Recurring bill")
    return rule


@router.get("")
async def list_recurring(conn: Conn, _: DeviceId) -> dict:
    return ok(plan.list_recurring(conn))


@router.post("", status_code=201)
async def create_recurring(body: RecurringIn, conn: Conn, _: DeviceId) -> dict:
    merchant_name = body.merchant_name.strip()
    if not merchant_name:
        raise ApiError(422, "VALIDATION_ERROR", "merchant_name cannot be blank.")
    _check_category(conn, body.category_id)
    if body.account_id is not None and not plan.account_exists(conn, body.account_id):
        raise ApiError(422, "VALIDATION_ERROR", "account_id must be an existing account.")
    fields = body.model_dump(exclude={"merchant_name"})
    rule_id = plan.create_recurring(conn, merchant_name, fields)
    return ok(plan.get_recurring(conn, rule_id))


@router.patch("/{rule_id}")
async def patch_recurring(rule_id: str, body: RecurringPatchIn, conn: Conn, _: DeviceId) -> dict:
    _require_rule(conn, rule_id)
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    if not changes:
        raise ApiError(422, "VALIDATION_ERROR", "Provide at least one recurring bill field to change.")
    if any(value is None for value in changes.values()):
        raise ApiError(422, "VALIDATION_ERROR", "Recurring bill fields cannot be null.")
    if "category_id" in changes:
        _check_category(conn, changes["category_id"])
    if "next_expected_date" in changes:
        stored_day = plan.stored_day_of_month(conn, rule_id)
        changes["expected_day_of_month"] = plan.rescheduled_day(stored_day, changes["next_expected_date"])
    plan.update_recurring(conn, rule_id, changes)
    return ok(plan.get_recurring(conn, rule_id))


@router.post("/{rule_id}/advance")
async def advance_recurring(rule_id: str, conn: Conn, _: DeviceId) -> dict:
    rule = plan.advance_recurring(conn, rule_id)
    if rule is None:
        raise not_found("Recurring bill")
    return ok(rule)


@router.delete("/{rule_id}")
async def delete_recurring(rule_id: str, conn: Conn, _: DeviceId) -> dict:
    if not plan.delete_recurring(conn, rule_id):
        raise not_found("Recurring bill")
    return ok({"deleted": True})
