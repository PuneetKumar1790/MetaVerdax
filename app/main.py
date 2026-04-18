"""MetaVerdax FastAPI entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.routes.agent_routes import api_router, router as agent_router

app = FastAPI(title="MetaVerdax Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(agent_router)
app.include_router(api_router)

reports_root = Path(settings.reports_dir).resolve().parent
reports_root.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(reports_root)), name="reports")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
