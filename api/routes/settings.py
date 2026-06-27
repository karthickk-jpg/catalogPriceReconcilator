from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/settings")
def settings_placeholder() -> dict:
    return {"ok": False, "message": "Not implemented yet"}


