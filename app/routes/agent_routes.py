"""FastAPI routes for MetaVerdax Agent chat, scans, and compliance APIs."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.session_store import SessionStore
from app.agent.verdax_agent import VerdaxAgent
from app.config.settings import settings
from app.llm.client import LLMClient
from app.mcp_client import OpenMetadataMCPClient

router = APIRouter(prefix="/agent", tags=["agent"])
session_store = SessionStore()
agents: dict[str, VerdaxAgent] = {}


class ChatRequest(BaseModel):
    message: str
    dataset_path: str | None = None
    session_id: str


class ScanResult(BaseModel):
    scan_id: str
    timestamp: datetime
    table_fqn: str
    dataset_path: str
    risk_level: Literal["SAFE", "WARN", "REVIEW", "CRITICAL"]
    validation_summary: dict
    drift_summary: dict
    anomaly_summary: dict
    carbon_saved_kg: float
    pdf_path: str | None
    openmetadata_task_id: str | None
    lineage_impact: dict


def _build_llm_client() -> LLMClient:
    key_map = {
        "groq": settings.groq_api_key,
        "gemini": settings.gemini_api_key,
        "anthropic": settings.anthropic_api_key,
    }
    provider = settings.llm_provider.lower()
    api_key = key_map.get(provider, "")
    return LLMClient(provider=provider, api_key=api_key, model=settings.llm_model)


def _get_agent(session_id: str) -> VerdaxAgent:
    if session_id in agents:
        return agents[session_id]

    mcp_client = OpenMetadataMCPClient(
        base_url=f"{settings.openmetadata_url.rstrip('/')}{settings.mcp_endpoint}",
        token=settings.openmetadata_token,
    )
    agent = VerdaxAgent(mcp_client=mcp_client, llm_client=_build_llm_client(), model=settings.llm_model)

    existing_history = session_store.get_history(session_id)
    if existing_history:
        agent.session_history = [{"role": m["role"], "content": m["content"]} for m in existing_history]
    agents[session_id] = agent
    return agent


@router.post("/chat")
async def chat_with_agent(body: ChatRequest) -> StreamingResponse:
    agent = _get_agent(body.session_id)
    session_store.add_message(body.session_id, "user", body.message)

    async def event_stream():
        full_text = ""
        try:
            async for token in agent.run(body.message, dataset_path=body.dataset_path):
                full_text += token
                yield f"data: {json.dumps({'token': token})}\n\n"

            session_store.add_message(body.session_id, "assistant", full_text)

            scan_result = agent.last_execution_context.get("scan_result")
            if scan_result:
                inserted_id = session_store.save_scan_result(scan_result)
                yield f"data: {json.dumps({'scan_saved': inserted_id, 'scan_result': scan_result}, default=str)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/upload-and-scan", response_model=ScanResult)
async def upload_and_scan(
    file: UploadFile = File(...),
    table_fqn: str = Form(...),
    session_id: str = Form(...),
) -> ScanResult:
    Path(settings.temp_upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.reports_dir).mkdir(parents=True, exist_ok=True)

    filename = file.filename or "uploaded_dataset.csv"
    ext = Path(filename).suffix.lower()
    if ext not in {".csv", ".parquet"}:
        raise HTTPException(status_code=400, detail="Only CSV and Parquet uploads are supported")

    target_path = Path(settings.temp_upload_dir) / f"{session_id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{filename}"
    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds max_upload_size_mb")

    await asyncio.to_thread(target_path.write_bytes, content)

    agent = _get_agent(session_id)
    plan = {
        "intent": "validate_dataset",
        "entities": {
            "table_fqn": table_fqn,
            "dataset_path": str(target_path),
            "days": 7,
            "assignee": None,
        },
        "actions": [
            "get_table_metadata",
            "get_column_profile",
            "get_lineage",
            "run_validation",
            "calculate_risk",
            "calculate_carbon",
            "push_observation",
            "create_task",
            "tag_entity",
            "generate_pdf",
        ],
    }
    context = await agent._execute_actions(plan=plan, dataset_path=str(target_path))
    agent.last_execution_context = context

    scan_result = dict(context.get("scan_result") or {})
    if not scan_result:
        raise HTTPException(status_code=500, detail="Agent did not produce a scan result")

    scan_result["table_fqn"] = table_fqn
    try:
        session_store.save_scan_result(scan_result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist scan result to MongoDB: {exc}") from exc

    return ScanResult.model_validate(scan_result)


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> dict[str, Any]:
    return {"session_id": session_id, "history": session_store.get_history(session_id)}


@router.get("/scan-results")
async def get_scan_results() -> dict[str, Any]:
    try:
        rows = session_store.get_recent_scan_results(limit=50)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read scan results: {exc}") from exc
    return {"count": len(rows), "results": rows}


@router.get("/blocked-retrains")
async def get_blocked_retrains() -> dict[str, Any]:
    try:
        rows = session_store.get_blocked_retrains_last_30_days()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read blocked retrains: {exc}") from exc
    return {"count": len(rows), "results": rows}
