from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    auth,
    budgets,
    categories,
    dashboard,
    goals,
    health,
    recurring,
    splits,
    statements,
    tax,
    transactions,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    health,
    auth,
    accounts,
    categories,
    transactions,
    splits,
    statements,
    dashboard,
    budgets,
    recurring,
    goals,
    tax,
):
    api_router.include_router(module.router)
