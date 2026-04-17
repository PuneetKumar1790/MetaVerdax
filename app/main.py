"""MetaVerdax FastAPI entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.routes.agent_routes import router as agent_router

app = FastAPI(title="MetaVerdax Agent API", version="0.1.0")
app.include_router(agent_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
