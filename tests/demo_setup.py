"""Demo data generator and mock OpenMetadata MCP server for MetaVerdax."""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

RNG_SEED = 42
TABLE_FQN = "ecommerce.customer_churn_v3"


def _base_dataframe(rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    tenure = rng.integers(1, 72, size=rows)
    monthly_charges = rng.normal(loc=72.0, scale=18.0, size=rows).clip(5, 250)
    total_charges = (monthly_charges * tenure + rng.normal(0, 120, size=rows)).clip(0, 15000)
    support_tickets = rng.poisson(2.0, size=rows)
    contract = rng.choice(["month-to-month", "one-year", "two-year"], size=rows, p=[0.6, 0.25, 0.15])
    payment_method = rng.choice(["credit_card", "bank_transfer", "paypal"], size=rows, p=[0.45, 0.35, 0.20])
    churn_prob = 1 / (1 + np.exp(-(0.03 * (monthly_charges - 70) + 0.35 * support_tickets - 1.2 * (tenure / 72))))
    churn = (rng.random(size=rows) < churn_prob).astype(int)

    return pd.DataFrame(
        {
            "customer_id": [f"CUST-{i:06d}" for i in range(rows)],
            "tenure_months": tenure,
            "monthly_charges": np.round(monthly_charges, 2),
            "total_charges": np.round(total_charges, 2),
            "support_tickets": support_tickets,
            "contract_type": contract,
            "payment_method": payment_method,
            "target": churn,
        }
    )


def generate_demo_data(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_df = _base_dataframe(1000)

    poisoned_df = safe_df.copy()
    rng = random.Random(RNG_SEED)

    # 40% null injections in selected columns
    for col in ["monthly_charges", "total_charges", "contract_type", "payment_method"]:
        indices = rng.sample(range(len(poisoned_df)), k=int(0.4 * len(poisoned_df)))
        poisoned_df.loc[indices, col] = np.nan

    # Range violations and outliers
    poisoned_df.loc[poisoned_df.sample(frac=0.2, random_state=RNG_SEED).index, "monthly_charges"] = 9999
    poisoned_df.loc[poisoned_df.sample(frac=0.15, random_state=RNG_SEED + 1).index, "tenure_months"] = -8

    # High drift in categories and target balance
    poisoned_df["contract_type"] = np.where(
        np.random.default_rng(RNG_SEED + 3).random(len(poisoned_df)) > 0.2,
        "month-to-month",
        "two-year",
    )
    poisoned_df["target"] = np.where(
        np.random.default_rng(RNG_SEED + 4).random(len(poisoned_df)) > 0.65,
        1,
        0,
    )

    safe_path = output_dir / "safe_customer_churn.csv"
    poisoned_path = output_dir / "poisoned_customer_churn.csv"
    baseline_path = output_dir / "baseline_customer_churn.csv"

    safe_df.to_csv(safe_path, index=False)
    safe_df.sample(frac=1.0, random_state=RNG_SEED + 9).to_csv(baseline_path, index=False)
    poisoned_df.to_csv(poisoned_path, index=False)

    return {"safe": safe_path, "poisoned": poisoned_path, "baseline": baseline_path}


def build_mock_mcp_app() -> FastAPI:
    app = FastAPI(title="MetaVerdax Mock OpenMetadata MCP", version="0.1.0")

    tools = [
        {"name": "get_table", "description": "Fetch table metadata"},
        {"name": "get_column_profile", "description": "Fetch column profile"},
        {"name": "get_lineage", "description": "Fetch lineage graph"},
        {"name": "search_metadata", "description": "Search metadata"},
        {"name": "create_test_result", "description": "Create quality result"},
        {"name": "add_observation", "description": "Add data quality observation"},
        {"name": "create_task", "description": "Create governance task"},
        {"name": "add_tags", "description": "Tag entity"},
    ]

    state: dict[str, Any] = {
        "observations": [],
        "tasks": [],
        "tags": [],
        "table": {
            "fullyQualifiedName": TABLE_FQN,
            "name": "customer_churn_v3",
            "owner": "ml-platform",
            "service": "ecommerce_warehouse",
            "columns": [
                {"name": "customer_id", "dataType": "VARCHAR"},
                {"name": "tenure_months", "dataType": "INT"},
                {"name": "monthly_charges", "dataType": "DOUBLE"},
                {"name": "total_charges", "dataType": "DOUBLE"},
                {"name": "support_tickets", "dataType": "INT"},
                {"name": "contract_type", "dataType": "VARCHAR"},
                {"name": "payment_method", "dataType": "VARCHAR"},
                {"name": "target", "dataType": "INT"},
            ],
        },
        "column_profile": {
            "fullyQualifiedName": f"{TABLE_FQN}.monthly_charges",
            "profile": {
                "nullCount": 12,
                "min": 9.8,
                "max": 248.2,
                "mean": 72.3,
                "stddev": 18.1,
            },
        },
        "lineage": {
            "entity": TABLE_FQN,
            "affected_dashboards": 4,
            "affected_models": 3,
            "upstream": ["raw.billing", "raw.crm"],
            "downstream": ["ml.customer_retention_model", "bi.executive_churn_dashboard"],
        },
    }

    @app.get("/mcp")
    async def list_tools() -> dict[str, Any]:
        return {"tools": tools}

    @app.get("/mcp/state")
    async def read_state() -> dict[str, Any]:
        return state

    @app.post("/mcp")
    async def call_tool(request: Request) -> JSONResponse:
        payload = await request.json()
        method = payload.get("method", "")
        params = payload.get("params", {})
        rpc_id = payload.get("id", 1)

        def rpc_result(result: Any) -> JSONResponse:
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})

        def rpc_error(code: int, message: str) -> JSONResponse:
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})

        if method in {"tools/list", "list_tools"}:
            return rpc_result({"tools": tools})

        if method not in {"tools/call", "call_tool"}:
            return rpc_error(-32601, f"Method not found: {method}")

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
        else:
            tool_name = params.get("tool")
            arguments = params.get("arguments", {})

        if tool_name == "get_table":
            fqn = arguments.get("fullyQualifiedName")
            if fqn != TABLE_FQN:
                return rpc_error(404, "Table not found")
            return rpc_result(state["table"])

        if tool_name == "get_column_profile":
            return rpc_result(state["column_profile"])

        if tool_name == "get_lineage":
            return rpc_result(state["lineage"])

        if tool_name == "search_metadata":
            return rpc_result(
                {
                    "results": [
                        {
                            "fullyQualifiedName": TABLE_FQN,
                            "entityType": "table",
                            "lastDriftScore": 0.82,
                            "days": arguments.get("filters", {}).get("days", 7),
                        }
                    ]
                }
            )

        if tool_name in {"create_test_result", "add_observation"}:
            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "fullyQualifiedName": arguments.get("fullyQualifiedName"),
                "observation": arguments.get("observation"),
            }
            state["observations"].append(entry)
            return rpc_result({"status": "ok", "observation_id": f"obs_{len(state['observations'])}"})

        if tool_name == "create_task":
            task = {
                "id": f"task_{len(state['tasks']) + 1}",
                "title": arguments.get("title", "Verdax Risk Alert"),
                "description": arguments.get("description", ""),
                "assignee": arguments.get("assignee"),
                "fullyQualifiedName": arguments.get("fullyQualifiedName"),
                "status": "Open",
                "created_at": datetime.now(UTC).isoformat(),
            }
            state["tasks"].append(task)
            return rpc_result(task)

        if tool_name == "add_tags":
            entry = {
                "fullyQualifiedName": arguments.get("fullyQualifiedName"),
                "tags": arguments.get("tags", []),
            }
            state["tags"].append(entry)
            return rpc_result({"status": "tagged", **entry})

        return rpc_error(-32601, f"Tool not found: {tool_name}")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="MetaVerdax demo setup helper")
    parser.add_argument("--output-dir", default="tests/demo_assets", help="Where to write generated CSV files")
    parser.add_argument("--mock-mcp", action="store_true", help="Start the mock MCP server on port 8586")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    paths = generate_demo_data(output_dir)

    print("Generated demo datasets:")
    print(json.dumps({k: str(v.resolve()) for k, v in paths.items()}, indent=2))

    if args.mock_mcp:
        app = build_mock_mcp_app()
        print("Starting mock MCP server on http://0.0.0.0:8586/mcp")
        uvicorn.run(app, host="0.0.0.0", port=8586, log_level="info")


if __name__ == "__main__":
    main()
