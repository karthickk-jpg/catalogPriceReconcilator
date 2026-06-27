from __future__ import annotations

from fastapi import FastAPI

from api.routes.reconcile import router as reconcile_router
from api.routes.history import router as history_router
from api.routes.settings import router as settings_router

app = FastAPI(title="CPRP API")


app.include_router(reconcile_router, prefix="")
app.include_router(history_router, prefix="")
app.include_router(settings_router, prefix="")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


