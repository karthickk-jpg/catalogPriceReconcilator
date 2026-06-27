from __future__ import annotations

from fastapi import FastAPI

from api.routes.reconcile import router as reconcile_router

app = FastAPI(title="CPRP API")

app.include_router(reconcile_router, prefix="")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
