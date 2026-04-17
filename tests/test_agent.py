from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd

from app.agent.verdax_agent import MetaVerdaxAgent


class FakeMCP:
    async def get_table_metadata(self, fqn: str) -> dict:
        return {
            "fullyQualifiedName": fqn,
            "columns": [
                {"name": "feature_a", "dataType": "DOUBLE"},
                {"name": "feature_b", "dataType": "DOUBLE"},
                {"name": "target", "dataType": "INT"},
            ],
        }

    async def get_column_profile(self, fqn: str) -> dict:
        return {"fullyQualifiedName": fqn}

    async def get_lineage(self, fqn: str, entity_type: str = "table") -> dict:
        return {"affected_dashboards": 2, "affected_models": 1}

    async def list_tables_with_drift(self, days: int = 7) -> list[dict]:
        return [{"fullyQualifiedName": "ecommerce.customer_churn_v3", "lastDriftScore": 0.84}]

    async def push_observation(self, fqn: str, observation: dict) -> dict:
        return {"status": "ok", "id": "obs_1"}

    async def create_task(self, fqn: str, title: str, description: str, assignee: str | None = None) -> dict:
        return {"id": "task_123", "title": title}

    async def tag_entity(self, fqn: str, tags: list[str]) -> dict:
        return {"status": "tagged", "tags": tags}


class FakeLLM:
    async def complete(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str:
        return """{
          "intent": "validate_dataset",
          "entities": {"table_fqn": "ecommerce.customer_churn_v3", "dataset_path": null, "days": 7, "assignee": null},
          "actions": ["get_table_metadata", "run_validation", "calculate_risk", "calculate_carbon"]
        }"""

    async def stream(self, messages: list[dict], system: str | None = None):
        text = "Scan complete. Risk assessed."
        for token in text.split(" "):
            yield token + " "


def test_agent_run_produces_scan_result(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "feature_a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "feature_b": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            "target": [0, 0, 1, 0, 1, 1],
        }
    )
    dataset_path = tmp_path / "sample.csv"
    df.to_csv(dataset_path, index=False)

    agent = MetaVerdaxAgent(mcp_client=FakeMCP(), llm_client=FakeLLM(), model="mock")

    async def _run() -> list[str]:
        streamed: list[str] = []
        async for chunk in agent.run("Is this dataset safe to retrain?", dataset_path=str(dataset_path)):
            streamed.append(chunk)
        return streamed

    streamed = asyncio.run(_run())

    assert "Scan" in "".join(streamed)
    assert agent.last_execution_context.get("scan_result")
    risk = agent.last_execution_context["scan_result"]["risk_level"]
    assert risk in {"SAFE", "WARN", "REVIEW", "CRITICAL"}


def test_calculate_risk_thresholds() -> None:
    agent = MetaVerdaxAgent(mcp_client=FakeMCP(), llm_client=FakeLLM(), model="mock")

    risk = agent._calculate_risk(
        validation_result={"critical_failures": 1, "warnings": 0},
        drift_result={"drift_score": 0.1},
        anomaly_result={"anomaly_rate": 0.05},
    )
    assert risk == "CRITICAL"

    risk = agent._calculate_risk(
        validation_result={"critical_failures": 0, "warnings": 2},
        drift_result={"drift_score": 0.3},
        anomaly_result={"anomaly_rate": 0.05},
    )
    assert risk == "WARN"
