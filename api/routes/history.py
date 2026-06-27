from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/history")
def history_placeholder() -> dict:
    return {"ok": False, "message": "Not implemented yet"}


