from fastapi import APIRouter

from app.api.envelope import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return ok({"status": "ok"})
