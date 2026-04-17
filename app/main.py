"""MetaVerdax FastAPI entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.routes.agent_routes import router as agent_router

app = FastAPI(title="MetaVerdax Agent API", version="0.1.0")
app.include_router(agent_router)

reports_root = Path(settings.reports_dir).resolve().parent
reports_root.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(reports_root)), name="reports")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
