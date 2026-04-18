"""FastAPI routes for MetaVerdax Agent chat, scans, and compliance APIs."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.agent.session_store import SessionStore
from app.agent.verdax_agent import VerdaxAgent
from app.config.settings import settings
from app.llm.client import LLMClient
from app.mcp_client import OpenMetadataMCPClient

router = APIRouter(prefix="/agent", tags=["agent"])
api_router = APIRouter(prefix="/api", tags=["frontend"])
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
    governance_actions: dict
    pdf_path: str | None
    openmetadata_task_id: str | None
    lineage_impact: dict


class FrontendChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    dataset_path: str | None = None


class FrontendValidateRequest(BaseModel):
    message: str
    session_id: str | None = None
    dataset_path: str | None = None
    table_fqn: str | None = None


def _pdf_to_public_url(pdf_path: str | None) -> str | None:
    if not pdf_path:
        return None

    reports_root = Path(settings.reports_dir).resolve().parent
    candidate = Path(pdf_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()

    try:
        relative = candidate.relative_to(reports_root)
    except ValueError:
        return None

    return f"/reports/{relative.as_posix()}"


def _map_risk_for_frontend(risk_level: str | None) -> Literal["CRITICAL", "HIGH", "LOW", "APPROVED"]:
    if not risk_level:
        return "LOW"

    risk = risk_level.upper()
    if risk == "CRITICAL":
        return "CRITICAL"
    if risk in {"REVIEW", "WARN"}:
        return "HIGH"
    if risk == "SAFE":
        return "APPROVED"
    return "LOW"


def _build_llm_client() -> LLMClient:
    key_map = {
        "groq": settings.groq_api_key,
        "gemini": settings.gemini_api_key,
        "anthropic": settings.anthropic_api_key,
    }
    provider = settings.llm_provider.lower()
    api_key = key_map.get(provider, "")
    return LLMClient(provider=provider, api_key=api_key, model=settings.llm_model)


def _scan_result_summary(scan_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not scan_result:
        return None

    governance_actions = scan_result.get("governance_actions", {}) if isinstance(scan_result, dict) else {}

    return {
        "scan_id": scan_result.get("scan_id"),
        "table_fqn": scan_result.get("table_fqn"),
        "risk_level": scan_result.get("risk_level"),
        "carbon_saved_kg": scan_result.get("carbon_saved_kg", 0.0),
        "lineage_impact": scan_result.get("lineage_impact", {}),
        "validation_summary": scan_result.get("validation_summary", {}),
        "drift_summary": scan_result.get("drift_summary", {}),
        "anomaly_summary": scan_result.get("anomaly_summary", {}),
        "governance_actions": governance_actions,
        "pdf_path": scan_result.get("pdf_path"),
        "pdf_url": _pdf_to_public_url(scan_result.get("pdf_path")),
        "openmetadata_task_id": scan_result.get("openmetadata_task_id"),
    }


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


@api_router.get("/health")
async def frontend_health() -> dict[str, Any]:
    mcp_client = OpenMetadataMCPClient(
        base_url=f"{settings.openmetadata_url.rstrip('/')}{settings.mcp_endpoint}",
        token=settings.openmetadata_token,
    )

    openmetadata_connected = True
    try:
        await mcp_client.list_tools()
    except Exception:
        openmetadata_connected = False

    return {"status": "ok", "openmetadata_connected": openmetadata_connected}


def _frontend_response_map(agent: VerdaxAgent, full_text: str) -> dict[str, Any]:
    scan_result = agent.last_execution_context.get("scan_result") or {}
    result_map = agent.last_execution_context.get("results") or {}
    if scan_result:
        try:
            session_store.save_scan_result(scan_result)
        except Exception:
            pass

    pdf_path = scan_result.get("pdf_path") if isinstance(scan_result, dict) else None
    report_id = Path(str(pdf_path)).name if pdf_path else None

    return {
        "response": full_text.strip(),
        "risk_score": _map_risk_for_frontend(result_map.get("calculate_risk") if isinstance(result_map, dict) else None),
        "report_id": report_id,
        "scan_result": _scan_result_summary(scan_result if isinstance(scan_result, dict) else None),
    }


async def _run_frontend_chat(body: FrontendChatRequest) -> dict[str, Any]:
    session_id = body.session_id or "frontend-default"
    agent = _get_agent(session_id)
    session_store.add_message(session_id, "user", body.message)

    full_text = ""
    try:
        async for token in agent.run(body.message, dataset_path=body.dataset_path):
            full_text += token
    except Exception as exc:
        safe_error = f"Unable to complete this request right now: {exc}"
        session_store.add_message(session_id, "assistant", safe_error)
        return {
            "response": safe_error,
            "risk_score": "LOW",
            "report_id": None,
            "scan_result": None,
        }

    session_store.add_message(session_id, "assistant", full_text)
    return _frontend_response_map(agent, full_text)


@api_router.post("/chat")
async def frontend_chat(body: FrontendChatRequest) -> dict[str, Any]:
    return await _run_frontend_chat(body)


@api_router.post("/validate")
async def frontend_validate(body: FrontendValidateRequest) -> dict[str, Any]:
    chat_body = FrontendChatRequest(message=body.message, session_id=body.session_id, dataset_path=body.dataset_path)
    result = await _run_frontend_chat(chat_body)
    if body.table_fqn:
        scan_result = result.get("scan_result") or {}
        scan_result["table_fqn"] = body.table_fqn
        result["scan_result"] = scan_result
    return result


@api_router.get("/history")
async def frontend_history() -> list[dict[str, Any]]:
    try:
        rows = session_store.get_recent_scan_results(limit=50)
    except Exception:
        return []

    history: list[dict[str, Any]] = []
    for row in rows:
        risk_level = str(row.get("risk_level", "SAFE"))
        history.append(
            {
                "id": str(row.get("scan_id") or row.get("timestamp") or os.urandom(4).hex()),
                "dataset": Path(str(row.get("dataset_path") or "unknown")).name,
                "risk_score": risk_level,
                "timestamp": str(row.get("timestamp") or ""),
                "action": "Blocked retrain" if risk_level in {"CRITICAL", "REVIEW"} else "Approved retrain",
                "report_url": _pdf_to_public_url(row.get("pdf_path")),
            }
        )

    return history


@api_router.get("/reports")
async def frontend_reports() -> list[dict[str, Any]]:
    try:
        rows = session_store.get_recent_scan_results(limit=100)
    except Exception:
        return []

    reports: list[dict[str, Any]] = []
    for row in rows:
        pdf_path = row.get("pdf_path")
        public_url = _pdf_to_public_url(pdf_path)
        if not public_url:
            continue

        filename = Path(str(pdf_path)).name
        reports.append(
            {
                "id": str(row.get("scan_id") or filename),
                "filename": filename,
                "dataset": Path(str(row.get("dataset_path") or "unknown")).name,
                "created_at": str(row.get("timestamp") or ""),
                "download_url": public_url,
            }
        )

    return reports


@api_router.get("/report/latest")
async def frontend_latest_report() -> FileResponse:
    reports_dir = Path(settings.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    candidates = sorted(reports_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail="No reports available")
    latest = candidates[0]
    return FileResponse(path=str(latest), filename=latest.name, media_type="application/pdf")
