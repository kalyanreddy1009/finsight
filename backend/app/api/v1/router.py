from fastapi import APIRouter

from app.api.v1 import accounts, auth, categories, dashboard, health, splits, transactions

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, accounts, categories, transactions, splits, dashboard):
    api_router.include_router(module.router)
