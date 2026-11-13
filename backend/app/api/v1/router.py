from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    ai,
    auth,
    budgets,
    categories,
    dashboard,
    goals,
    health,
    insights,
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
    insights,
    ai,
):
    api_router.include_router(module.router)
