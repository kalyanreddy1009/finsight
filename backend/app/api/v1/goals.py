"""Goals endpoints."""

import sqlite3

from fastapi import APIRouter

from app.api.deps import Conn, DeviceId
from app.api.envelope import ok
from app.api.errors import ApiError, not_found
from app.api.v1.schemas import GoalIn, GoalPatchIn
from app.finance import plan_queries as plan

router = APIRouter(prefix="/goals", tags=["goals"])

_NULLABLE_GOAL_FIELDS = frozenset({"target_date", "linked_account_id"})


def _validate_goal(conn: sqlite3.Connection, goal: plan.Record) -> None:
    """Check the resulting goal row: locked amount within target, linked account must exist."""
    if goal["current_locked_amount_minor"] > goal["target_amount_minor"]:
        raise ApiError(
            422, "VALIDATION_ERROR", "current_locked_amount_minor cannot exceed target_amount_minor."
        )
    account_id = goal["linked_account_id"]
    if account_id is not None and not plan.account_exists(conn, account_id):
        raise ApiError(422, "VALIDATION_ERROR", "linked_account_id must be an existing account.")


def _require_goal(conn: sqlite3.Connection, goal_id: str) -> plan.Record:
    goal = plan.get_goal(conn, goal_id)
    if goal is None:
        raise not_found("Goal")
    return goal


@router.get("")
async def list_goals(conn: Conn, _: DeviceId) -> dict:
    return ok(plan.list_goals(conn))


@router.post("", status_code=201)
async def create_goal(body: GoalIn, conn: Conn, _: DeviceId) -> dict:
    fields = body.model_dump()
    _validate_goal(conn, {**fields, "status": "ACTIVE"})
    goal_id = plan.create_goal(conn, fields)
    return ok(plan.get_goal(conn, goal_id))


@router.patch("/{goal_id}")
async def patch_goal(goal_id: str, body: GoalPatchIn, conn: Conn, _: DeviceId) -> dict:
    current = _require_goal(conn, goal_id)
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    if not changes:
        raise ApiError(422, "VALIDATION_ERROR", "Provide at least one goal field to change.")
    if any(value is None and name not in _NULLABLE_GOAL_FIELDS for name, value in changes.items()):
        raise ApiError(422, "VALIDATION_ERROR", "Only target_date and linked_account_id can be null.")
    _validate_goal(conn, {**current, **changes})
    plan.update_goal(conn, goal_id, changes)
    return ok(plan.get_goal(conn, goal_id))


@router.delete("/{goal_id}")
async def delete_goal(goal_id: str, conn: Conn, _: DeviceId) -> dict:
    if not plan.delete_goal(conn, goal_id):
        raise not_found("Goal")
    return ok({"deleted": True})
