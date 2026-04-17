"""MetaVerdax agent orchestration: LLM planning + MCP + MetaVerdax runtime."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.config.settings import settings
from app.mcp_client import OpenMetadataMCPClient

VERDAX_REFERENCE_ROOT = os.getenv("VERDAX_REFERENCE_ROOT", "/data/We_Make_Devs/Verdax")
if VERDAX_REFERENCE_ROOT not in sys.path:
    sys.path.insert(0, VERDAX_REFERENCE_ROOT)

# Import existing MetaVerdax components as-is.
from core.anomaly_scorer import AnomalyScorer  # type: ignore
from core.carbon_calculator import CarbonCalculator  # type: ignore
from core.drift_detector import DriftDetector  # type: ignore
from core.validator import DataValidator  # type: ignore


@dataclass
class PlanEntities:
    table_fqn: str | None = None
    dataset_path: str | None = None
    days: int = 7
    assignee: str | None = None


class MetaVerdaxAgent:
    """Agent that plans actions with LLM and executes MCP + MetaVerdax workflows."""

    def __init__(self, mcp_client: OpenMetadataMCPClient, llm_client: Any, model: str):
        self.mcp = mcp_client
        self.llm = llm_client
        self.model = model
        self.session_history: list[dict[str, str]] = []
        self.last_execution_context: dict[str, Any] = {}

    async def run(self, user_message: str, dataset_path: str | None = None) -> AsyncGenerator[str, None]:
        """Run the full agent loop and stream final response tokens."""
        self.session_history.append({"role": "user", "content": user_message})

        plan = await self._plan(user_message)
        if dataset_path:
            plan.setdefault("entities", {})["dataset_path"] = dataset_path

        execution_context = await self._execute_actions(plan, dataset_path=dataset_path)
        self.last_execution_context = execution_context

        final_text = ""
        try:
            prompt = self._build_synthesis_prompt(user_message, plan, execution_context)
            stream_messages = self._history_for_llm() + [{"role": "user", "content": prompt}]
            async for token in self.llm.stream(stream_messages, system="You are MetaVerdax Agent. Be concise and operational."):
                final_text += token
                yield token
        except Exception:
            final_text = self._local_summary(user_message, plan, execution_context)
            for token in final_text.split(" "):
                yield token + " "

        self.session_history.append({"role": "assistant", "content": final_text})

    async def _plan(self, user_message: str) -> dict:
        """Create a structured JSON action plan from user request and session context."""
        system_prompt = (
            "You are a data governance AI agent. Given a user request, output ONLY valid JSON with this schema:"
            " {"
            '"intent":"validate_dataset | show_drift | generate_report | search_metadata | general",'
            '"entities":{"table_fqn":"...","dataset_path":"...","days":7,"assignee":"..."},'
            '"actions":["get_table_metadata","run_validation","push_observation"]'
            " }. Only include required actions."
        )
        llm_messages = self._history_for_llm() + [{"role": "user", "content": user_message}]

        try:
            raw = await self.llm.complete(llm_messages, system=system_prompt, json_mode=True)
            plan = json.loads(raw)
            return self._normalize_plan(plan)
        except Exception:
            return self._heuristic_plan(user_message)

    async def _execute_actions(self, plan: dict, dataset_path: str | None = None) -> dict:
        """Execute actions in sequence and collect context outputs."""
        context: dict[str, Any] = {
            "plan": plan,
            "results": {},
            "scan_result": None,
        }
        entities = plan.get("entities", {})
        table_fqn = entities.get("table_fqn")
        resolved_dataset_path = dataset_path or entities.get("dataset_path")

        for action in plan.get("actions", []):
            if action == "get_table_metadata" and table_fqn:
                context["results"][action] = await self.mcp.get_table_metadata(table_fqn)
            elif action == "get_column_profile" and table_fqn:
                context["results"][action] = await self.mcp.get_column_profile(table_fqn)
            elif action == "get_lineage" and table_fqn:
                context["results"][action] = await self.mcp.get_lineage(table_fqn)
            elif action == "list_drift_tables":
                context["results"][action] = await self.mcp.list_tables_with_drift(days=int(entities.get("days", 7)))
            elif action == "run_validation":
                context["results"][action] = await self._run_validation(
                    table_fqn=table_fqn,
                    dataset_path=resolved_dataset_path,
                    table_metadata=context["results"].get("get_table_metadata"),
                )
            elif action == "calculate_risk":
                validation = context["results"].get("run_validation", {}).get("validation", {})
                drift = context["results"].get("run_validation", {}).get("drift", {})
                anomaly = context["results"].get("run_validation", {}).get("anomaly", {})
                context["results"][action] = self._calculate_risk(validation, drift, anomaly)
            elif action == "calculate_carbon":
                risk_level = context["results"].get("calculate_risk", "SAFE")
                context["results"][action] = await self._calculate_carbon(risk_level)
            elif action == "generate_pdf":
                context["results"][action] = await self._generate_pdf(
                    context=context,
                    table_fqn=table_fqn,
                    dataset_path=resolved_dataset_path,
                )
            elif action == "push_observation" and table_fqn:
                observation = self._build_observation_payload(context)
                context["results"][action] = await self.mcp.push_observation(table_fqn, observation)
            elif action == "create_task" and table_fqn:
                risk_level = context["results"].get("calculate_risk", "SAFE")
                if risk_level in {"REVIEW", "CRITICAL"}:
                    context["results"][action] = await self.mcp.create_task(
                        fqn=table_fqn,
                        title=f"MetaVerdax {risk_level} risk detected",
                        description=self._task_description(context),
                        assignee=entities.get("assignee"),
                    )
                else:
                    context["results"][action] = {"status": "skipped", "reason": "risk below REVIEW"}
            elif action == "tag_entity" and table_fqn:
                risk_level = context["results"].get("calculate_risk", "SAFE")
                context["results"][action] = await self.mcp.tag_entity(table_fqn, [f"MetaVerdaxRisk.{risk_level}"])

        context["scan_result"] = self._build_scan_result(context, table_fqn=table_fqn, dataset_path=resolved_dataset_path)
        return context

    def _calculate_risk(self, validation_result: dict, drift_result: dict, anomaly_result: dict) -> str:
        """Compute SAFE/WARN/REVIEW/CRITICAL based on validation, drift, anomaly."""
        critical_failures = int(validation_result.get("critical_failures", 0))
        warnings = int(validation_result.get("warnings", 0))
        drift_score = float(drift_result.get("drift_score", 0.0))
        anomaly_rate = float(anomaly_result.get("anomaly_rate", 0.0))

        if critical_failures > 0 or drift_score > 0.8 or anomaly_rate > 0.15:
            return "CRITICAL"
        if warnings > 3 or drift_score > 0.5:
            return "REVIEW"
        if warnings > 0 or drift_score > 0.2:
            return "WARN"
        return "SAFE"

    async def _run_validation(
        self,
        table_fqn: str | None,
        dataset_path: str | None,
        table_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not dataset_path:
            return {
                "validation": {"critical_failures": 0, "warnings": 0, "passed": True},
                "drift": {"drift_score": 0.0, "drift_detected": False},
                "anomaly": {"anomaly_rate": 0.0, "score": 0.0},
                "notes": "No dataset path provided; runtime checks skipped.",
            }

        path = Path(dataset_path)
        if not path.exists():
            return {
                "validation": {"critical_failures": 1, "warnings": 0, "passed": False},
                "drift": {"drift_score": 0.0, "drift_detected": False},
                "anomaly": {"anomaly_rate": 1.0, "score": 1.0},
                "notes": f"Dataset file not found: {dataset_path}",
            }

        if path.suffix.lower() == ".parquet":
            df = await asyncio.to_thread(pd.read_parquet, path)
        else:
            df = await asyncio.to_thread(pd.read_csv, path)

        expected_schema = None
        if table_metadata and isinstance(table_metadata, dict):
            cols = table_metadata.get("columns", [])
            if isinstance(cols, list) and cols:
                expected_schema = {
                    str(c.get("name")): self._map_openmetadata_type(str(c.get("dataType", "")))
                    for c in cols
                    if isinstance(c, dict) and c.get("name")
                }

        expected_ranges = DataValidator.infer_ranges(df)
        validator = DataValidator(expected_schema=expected_schema, expected_ranges=expected_ranges)
        validation_result = await asyncio.to_thread(validator.validate, df)

        dataset_name = table_fqn or path.stem
        drift_detector = DriftDetector()
        drift_result = await asyncio.to_thread(drift_detector.detect, df, dataset_name)

        anomaly_scorer = AnomalyScorer()
        anomaly_score = await asyncio.to_thread(anomaly_scorer.score, validation_result, drift_result)

        failed_checks = [name for name, check in validation_result.checks.items() if not check.passed]
        warning_checks = [name for name in failed_checks if name not in {"schema", "null_check"}]
        drift_score = min(len(drift_result.drifted_features) / max(len(drift_result.feature_details), 1), 1.0)

        return {
            "validation": {
                "passed": bool(validation_result.passed),
                "critical_failures": sum(1 for c in failed_checks if c in {"schema", "null_check"}),
                "warnings": len(warning_checks),
                "failed_checks": failed_checks,
                "recommendation": validation_result.recommendation,
                "anomaly_score": validation_result.anomaly_score,
                "checks": {k: v.model_dump() for k, v in validation_result.checks.items()},
            },
            "drift": {
                "drift_detected": drift_result.drift_detected,
                "drift_score": round(drift_score, 4),
                "drifted_features": drift_result.drifted_features,
                "severity": drift_result.drift_severity,
                "isolation_forest_ratio": drift_result.isolation_forest_anomaly_ratio,
                "isolation_forest_delta": drift_result.isolation_forest_delta,
            },
            "anomaly": {
                "score": anomaly_score.score,
                "action": anomaly_score.action,
                "recommendation": anomaly_score.recommendation,
                "anomaly_rate": drift_result.isolation_forest_anomaly_ratio,
                "breakdown": anomaly_score.breakdown,
            },
            "dataset": {
                "rows": int(len(df)),
                "columns": int(len(df.columns)),
                "path": str(path),
            },
        }

    async def _calculate_carbon(self, risk_level: str) -> dict[str, Any]:
        calculator = CarbonCalculator()
        prevented = risk_level in {"REVIEW", "CRITICAL"}
        result = await asyncio.to_thread(
            calculator.calculate,
            model_size="medium",
            cloud_provider="aws",
            region="us-east-1",
            prevented=prevented,
        )
        return result.model_dump()

    async def _generate_pdf(
        self,
        context: dict[str, Any],
        table_fqn: str | None,
        dataset_path: str | None,
    ) -> dict[str, Any]:
        Path(settings.reports_dir).mkdir(parents=True, exist_ok=True)
        file_name = f"meta_verdax_audit_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = str(Path(settings.reports_dir) / file_name)

        validation = context["results"].get("run_validation", {}).get("validation", {})
        drift = context["results"].get("run_validation", {}).get("drift", {})
        anomaly = context["results"].get("run_validation", {}).get("anomaly", {})
        carbon = context["results"].get("calculate_carbon", {})
        risk = context["results"].get("calculate_risk", "SAFE")
        lineage = context["results"].get("get_lineage", {})

        def _build_pdf() -> str:
            p = canvas.Canvas(output_path, pagesize=A4)
            width, height = A4
            y = height - 48

            # Brand header (text-only) avoids leaking legacy Verdax artwork in generated reports.
            p.setFont("Helvetica-Bold", 22)
            p.drawString(40, y, "MetaVerdax")
            y -= 22
            p.setFont("Helvetica", 12)
            p.drawString(40, y, "Governance and Sustainability Impact Report")
            y -= 26

            p.setFont("Helvetica", 10)
            p.drawString(40, y, f"Generated (UTC): {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")
            y -= 14
            p.drawString(40, y, f"Table: {table_fqn or 'unknown'}")
            y -= 14
            p.drawString(40, y, f"Dataset: {dataset_path or 'N/A'}")
            y -= 24

            p.setFont("Helvetica-Bold", 12)
            p.drawString(40, y, "Risk Summary")
            y -= 16
            p.setFont("Helvetica", 10)
            p.drawString(40, y, f"Risk Level: {risk}")
            y -= 14
            p.drawString(40, y, f"Critical Failures: {validation.get('critical_failures', 0)}")
            y -= 14
            p.drawString(40, y, f"Warnings: {validation.get('warnings', 0)}")
            y -= 14
            p.drawString(40, y, f"Drift Score: {drift.get('drift_score', 0.0)}")
            y -= 14
            p.drawString(40, y, f"Anomaly Rate: {anomaly.get('anomaly_rate', 0.0)}")
            y -= 22

            p.setFont("Helvetica-Bold", 12)
            p.drawString(40, y, "Lineage Impact")
            y -= 16
            p.setFont("Helvetica", 10)
            p.drawString(40, y, f"Affected Dashboards: {int(lineage.get('affected_dashboards', 0))}")
            y -= 14
            p.drawString(40, y, f"Affected Models: {int(lineage.get('affected_models', 0))}")
            y -= 22

            p.setFont("Helvetica-Bold", 12)
            p.drawString(40, y, "Sustainability")
            y -= 16
            p.setFont("Helvetica", 10)
            p.drawString(40, y, f"CO2 Saved (kg): {float(carbon.get('co2_saved_kg', 0.0)):.2f}")

            p.save()
            return output_path

        generated_path = await asyncio.to_thread(_build_pdf)
        return {"pdf_path": generated_path}

    def _build_scan_result(self, context: dict[str, Any], table_fqn: str | None, dataset_path: str | None) -> dict[str, Any]:
        run_validation = context["results"].get("run_validation", {})
        risk_level = context["results"].get("calculate_risk", "SAFE")
        carbon = context["results"].get("calculate_carbon", {})
        lineage = context["results"].get("get_lineage", {})
        task = context["results"].get("create_task", {})
        pdf = context["results"].get("generate_pdf", {})

        lineage_impact = {
            "affected_dashboards": int(lineage.get("affected_dashboards", 0)),
            "affected_models": int(lineage.get("affected_models", 0)),
        }

        return {
            "scan_id": f"scan_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(UTC).isoformat(),
            "table_fqn": table_fqn or "unknown",
            "dataset_path": dataset_path or "",
            "risk_level": risk_level,
            "validation_summary": run_validation.get("validation", {}),
            "drift_summary": run_validation.get("drift", {}),
            "anomaly_summary": run_validation.get("anomaly", {}),
            "carbon_saved_kg": float(carbon.get("co2_saved_kg", 0.0)),
            "pdf_path": pdf.get("pdf_path"),
            "openmetadata_task_id": task.get("id") if isinstance(task, dict) else None,
            "lineage_impact": lineage_impact,
        }

    def _task_description(self, context: dict[str, Any]) -> str:
        risk = context["results"].get("calculate_risk", "UNKNOWN")
        drift = context["results"].get("run_validation", {}).get("drift", {})
        validation = context["results"].get("run_validation", {}).get("validation", {})
        return (
            f"MetaVerdax flagged dataset as {risk}. "
            f"Drift score={drift.get('drift_score', 0.0)}, "
            f"critical_failures={validation.get('critical_failures', 0)}."
        )

    def _build_observation_payload(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "risk_level": context["results"].get("calculate_risk", "SAFE"),
            "validation": context["results"].get("run_validation", {}).get("validation", {}),
            "drift": context["results"].get("run_validation", {}).get("drift", {}),
            "anomaly": context["results"].get("run_validation", {}).get("anomaly", {}),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _history_for_llm(self) -> list[dict[str, str]]:
        return [{"role": msg["role"], "content": msg["content"]} for msg in self.session_history[-20:]]

    def _build_synthesis_prompt(self, user_message: str, plan: dict, execution_context: dict[str, Any]) -> str:
        return (
            "User asked: "
            f"{user_message}\n"
            "Action plan:\n"
            f"{json.dumps(plan, indent=2)}\n"
            "Execution context:\n"
            f"{json.dumps(execution_context.get('results', {}), default=str)[:5000]}\n"
            "Respond with: 1) direct answer, 2) key risk signals, 3) next recommended action."
        )

    def _local_summary(self, user_message: str, plan: dict, execution_context: dict[str, Any]) -> str:
        scan = execution_context.get("scan_result") or {}
        risk = scan.get("risk_level", "SAFE")
        drift = scan.get("drift_summary", {}).get("drift_score", 0.0)
        anomaly_rate = scan.get("anomaly_summary", {}).get("anomaly_rate", 0.0)
        pdf = scan.get("pdf_path")

        return (
            f"Request processed for: {user_message}. "
            f"Risk level is {risk}. Drift score is {drift}. Anomaly rate is {anomaly_rate}. "
            f"Plan intent was {plan.get('intent', 'general')}. "
            f"PDF report: {pdf if pdf else 'not generated'}."
        )

    def _normalize_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "intent": str(plan.get("intent", "general")),
            "entities": {
                "table_fqn": None,
                "dataset_path": None,
                "days": 7,
                "assignee": None,
            },
            "actions": [],
        }
        entities = plan.get("entities") or {}
        normalized["entities"].update(
            {
                "table_fqn": entities.get("table_fqn"),
                "dataset_path": entities.get("dataset_path"),
                "days": int(entities.get("days", 7) or 7),
                "assignee": entities.get("assignee"),
            }
        )

        actions = [str(a) for a in plan.get("actions", []) if isinstance(a, str)]
        if not actions:
            actions = self._heuristic_plan(str(plan)).get("actions", [])

        # For validation scans, enforce the complete orchestration chain so
        # risk and governance side-effects are always executed.
        if normalized["intent"] == "validate_dataset":
            required_chain = [
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
            ]
            action_set = set(actions)
            for item in required_chain:
                if item not in action_set:
                    actions.append(item)
                    action_set.add(item)
        normalized["actions"] = actions
        return normalized

    def _heuristic_plan(self, user_message: str) -> dict[str, Any]:
        text = user_message.lower()
        intent = "general"
        actions: list[str] = []

        if any(k in text for k in ["validate", "safe", "scan", "retrain"]):
            intent = "validate_dataset"
            actions.extend(
                [
                    "get_table_metadata",
                    "get_column_profile",
                    "run_validation",
                    "calculate_risk",
                    "calculate_carbon",
                    "push_observation",
                    "create_task",
                    "tag_entity",
                    "generate_pdf",
                ]
            )
        elif "drift" in text:
            intent = "show_drift"
            actions.extend(["list_drift_tables"])
        elif "report" in text or "pdf" in text:
            intent = "generate_report"
            actions.extend(["run_validation", "calculate_risk", "calculate_carbon", "generate_pdf"])
        elif "metadata" in text or "lineage" in text:
            intent = "search_metadata"
            actions.extend(["get_table_metadata", "get_lineage"])
        else:
            actions.extend(["get_table_metadata"])

        entities = {
            "table_fqn": self._extract_table_fqn(user_message),
            "dataset_path": self._extract_dataset_path(user_message),
            "days": 7,
            "assignee": None,
        }
        return {"intent": intent, "entities": entities, "actions": actions}

    @staticmethod
    def _extract_table_fqn(text: str) -> str | None:
        parts = text.replace("\n", " ").split(" ")
        for part in parts:
            if part.count(".") >= 2 and all(chunk.strip() for chunk in part.split(".")):
                return part.strip(" ,.;")
        return None

    @staticmethod
    def _extract_dataset_path(text: str) -> str | None:
        for token in text.replace("\n", " ").split(" "):
            if token.endswith(".csv") or token.endswith(".parquet"):
                return token.strip(" ,.;")
        return None

    @staticmethod
    def _map_openmetadata_type(data_type: str) -> str:
        t = data_type.lower()
        if t in {"int", "integer", "bigint", "smallint"}:
            return "int64"
        if t in {"float", "double", "decimal", "real", "numeric"}:
            return "float64"
        if t in {"boolean", "bool"}:
            return "bool"
        return "object"
