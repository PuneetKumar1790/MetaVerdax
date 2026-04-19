# MetaVerdax Agent

AI-powered data governance and observability agent for OpenMetadata.

## What it does

MetaVerdax turns natural-language requests into governance actions for datasets. It reads metadata from OpenMetadata, runs validation/drift/anomaly checks, assigns a risk level, and writes the result back as observations, tasks, and tags.

It also generates PDF reports with lineage and carbon-impact context for audit-ready demos.

MetaVerdax turns natural-language requests into executable governance workflows:
- reads metadata from OpenMetadata through MCP
- runs MetaVerdax validation/drift/anomaly checks on incoming datasets
- assigns risk (`SAFE`, `WARN`, `REVIEW`, `CRITICAL`)
- writes findings back to metadata systems (observations, tasks, tags)
- generates audit-ready PDF reports with lineage and carbon impact context

## Problem

Teams lose time and money when low-quality data reaches ML retraining:
- data scientists often spend 60-80% of effort on data cleanup
- bad retrains can waste $10k-$100k+ in compute
- data quality incidents can create large business and compliance risk

MetaVerdax provides an AI-agent layer over metadata + observability to prevent risky retrains before cost is incurred.

## Personas

- **ML Engineer / Data Scientist**: asks if a dataset is safe before retraining, wants exact risk reasons.
- **Compliance Officer / CTO**: tracks blocked retrains, exports evidence, and reviews governance posture without touching code.

## What Is Implemented

- FastAPI backend with streaming chat endpoint (SSE)
- React frontend (Vite + TypeScript) for chat, uploads, scans, and reporting views
- OpenMetadata client integration:
  - reads metadata context through MCP
  - writes governance artifacts to OpenMetadata REST APIs (feed/tasks/tags)
  - falls back to mock MCP write-back if OpenMetadata is unreachable
- LLM abstraction layer (Groq, Gemini, Anthropic)
- MetaVerdax runtime integration:
  - schema/range/null validation
  - drift detection
  - anomaly scoring
  - carbon savings estimation
  - PDF report generation
- Demo UI surfaces governance write-backs directly:
  - observation, task, and tag chips
  - live scan summary with lineage and carbon impact
  - `View in OpenMetadata` deep-link for scanned table/entity
  - PDF report download link
- Session history persistence (in-memory + SQLite)
- Scan result persistence and compliance queries (MongoDB)
- Demo tooling:
  - synthetic safe/poisoned datasets
  - mock MCP server

## Architecture

```text
User (Chat / Upload)
   |
   v
React UI (frontend/)
   |
   v
FastAPI API (app/main.py + app/routes/agent_routes.py)
   |
   +--> MetaVerdaxAgent (app/agent/verdax_agent.py)
          |
          +--> LLM Client (app/llm/client.py)
          |      - planning JSON + response synthesis
          |
          +--> OpenMetadata Client (app/mcp_client.py)
          |      - reads: MCP endpoints (table, lineage, profiles)
          |      - writes: OpenMetadata REST (observation/task/tag)
          |      - fallback: mock MCP write-back
          |
          +--> MetaVerdax Core Modules (external reference root)
                 - validator, drift detector, anomaly scorer
                 - carbon calculator, report generator

Persistence:
- SQLite: session message history
- MongoDB: scan results / blocked retrain analytics
```

## OpenMetadata APIs Called

MetaVerdax calls these OpenMetadata endpoints directly or through the MCP bridge:

- `POST /api/v1/users/login` — obtain a JWT for real OpenMetadata sessions
- `GET /api/v1/tables/{id}` and `GET /api/v1/tables/name/{fullyQualifiedName}` — resolve the target table
- `POST /api/v1/feed` — create observations and task-style governance items on the table activity feed
- `PATCH /api/v1/tables/{fullyQualifiedName}` — attach `VerdaxRisk.*` tags using the direct FQN patch flow
- `PATCH /api/v1/tables/{id}` — fallback patch flow for tags when the FQN patch is rejected
- OpenMetadata MCP bridge at `/mcp` — read table context, lineage, and profiling data when available

## Repository Layout

```text
app/
  main.py
  routes/agent_routes.py
  agent/verdax_agent.py
  agent/session_store.py
  mcp_client.py
  llm/client.py
  config/settings.py

tests/
  test_agent.py
  test_mcp_client.py
  demo_setup.py
  demo_assets/
```

## Prerequisites

- Python 3.11+
- MongoDB running locally or remotely
- OpenMetadata instance running (recommended: `http://localhost:8585`)
- Optional mock MCP server for offline/synthetic demo mode
- Access to MetaVerdax runtime source (configured via `VERDAX_REFERENCE_ROOT`)
- At least one LLM provider API key (Groq/Gemini/Anthropic)

## Configuration

MetaVerdax connects to a real OpenMetadata instance by default. A mock MCP server (`tests/demo_setup.py`) is included as a fallback for offline development and testing.

Create `.env` in repo root (example):

```bash
# OpenMetadata / MCP
OPENMETADATA_URL=http://localhost:8585
OPENMETADATA_TOKEN=
OPENMETADATA_JWT_TOKEN=
MCP_ENDPOINT=/mcp

# LLM
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=

# Files and storage
MAX_UPLOAD_SIZE_MB=100
TEMP_UPLOAD_DIR=/tmp/verdax_uploads
REPORTS_DIR=reports/agent
SQLITE_PATH=meta_verdax_sessions.db
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=verdax
MONGODB_SCANS_COLLECTION=verdax_scans

```

Auth note:
- `OPENMETADATA_JWT_TOKEN` is preferred for real OpenMetadata UI/API sessions.
- `OPENMETADATA_TOKEN` (PAT) can still be used when available.
- If both are set, the app uses JWT first.

Optional environment variable for MetaVerdax module imports:

```bash
export VERDAX_REFERENCE_ROOT=/data/We_Make_Devs/MetaVerdax
```

## Local Run

Install deps:

```bash
pip install -r requirements.txt
```

Start API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start frontend (new terminal):

```bash
npm --prefix frontend install
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

## Quick Start (Fastest Demo Launch)

Use the preconfigured VS Code task for one-click startup:

1. Open Command Palette.
2. Run `Tasks: Run Build Task`.
3. Select `MetaVerdax: Run Full Stack`.

This starts:
- mock MCP dev tool (`tests/demo_setup.py --mock-mcp`)
- backend (`uvicorn app.main:app` on `127.0.0.1:8000`)
- frontend (`vite` on `127.0.0.1:5173`)

If you prefer terminal commands instead of VS Code tasks, run these in separate terminals:

```bash
# Terminal 1
.venv/bin/python tests/demo_setup.py --mock-mcp
```

```bash
# Terminal 2
OPENMETADATA_URL=http://localhost:8585 MCP_ENDPOINT=/mcp \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# Terminal 3
VITE_API_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

Open:
- App: `http://127.0.0.1:5173/app`
- OpenMetadata: `http://localhost:8585`

## Real OpenMetadata Demo Mode (Recommended)

> The demo video was recorded against a live OpenMetadata instance (localhost:8585). Mock fallback was not used during recording.

Set:
- `OPENMETADATA_URL=http://localhost:8585`
- `OPENMETADATA_JWT_TOKEN=<token from /api/v1/users/login>`
Then run backend + frontend with these exact commands:

```bash
OPENMETADATA_URL=http://localhost:8585 MCP_ENDPOINT=/mcp \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

Verify in the UI:
- `OpenMetadata connected` health indicator
- scan summary shows observation/task/tag chips
- `View in OpenMetadata` link opens the corresponding table/entity page

## Mock MCP Demo Mode (Fallback)

Generate demo assets with the dev/mock helper:

```bash
python tests/demo_setup.py --output-dir tests/demo_assets
```

Run mock MCP server on `:8586`:

```bash
python tests/demo_setup.py --mock-mcp
```

Then point app config to:
- `OPENMETADATA_URL=http://localhost:8586`
- `MCP_ENDPOINT=/mcp`

## How to Run It Locally

Exact commands for a local run:

```bash
pip install -r requirements.txt
```

```bash
npm --prefix frontend install
```

```bash
OPENMETADATA_URL=http://localhost:8585 MCP_ENDPOINT=/mcp \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

Open:
- App: `http://127.0.0.1:5173/app`
- OpenMetadata: `http://localhost:8585`

## API Endpoints

- `GET /health`
- `POST /agent/chat` (streaming SSE)
- `POST /agent/upload-and-scan`
- `GET /agent/sessions/{session_id}/history`
- `GET /agent/scan-results`
- `GET /agent/blocked-retrains`

## Example Requests

Chat:

```bash
curl -N -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Is my latest customer churn training dataset safe to retrain?",
    "dataset_path":"tests/demo_assets/poisoned_customer_churn.csv",
    "session_id":"sess-demo-01"
  }'
```

Upload and scan:

```bash
curl -X POST http://localhost:8000/agent/upload-and-scan \
  -F "file=@tests/demo_assets/poisoned_customer_churn.csv" \
  -F "table_fqn=ecommerce.customer_churn_v3" \
  -F "session_id=sess-demo-02"
```

## Typical Agent Flow

1. Parse user intent from natural language.
2. Build action plan (JSON) with entities and required actions.
3. Pull metadata/context through MCP.
4. Run MetaVerdax checks on uploaded or referenced dataset.
5. Compute risk level and recommendations.
6. If risky, create governance task and add risk tag.
7. Push observation back to metadata.
8. Generate report and return stream response + saved scan record.

## Tests

Run all tests:

```bash
pytest -q
```

Current coverage focuses on:
- agent orchestration and risk outputs
- MCP client behavior and error handling

## Project Positioning

Primary track: **MCP Ecosystem & AI Agents**

Why this project is strong:
- uses MCP for both read and write operations
- combines metadata context + runtime data quality checks
- produces operational and compliance outcomes (tasks, tags, reports)
- demonstrates practical AI governance value with clear ROI narrative

## Known Gaps / Next Iterations

- add explicit retrain-gate endpoint for CI/CD or orchestrator hooks
- wire risk thresholds fully from config (avoid hardcoded values)
- strengthen explainability UI section with check-by-check rationale
- add demo video and architecture diagram image for submission package

## License

Add your preferred license here before public release.
