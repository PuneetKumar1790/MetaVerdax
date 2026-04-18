"""Streamlit interface for MetaVerdax Agent (Engineer + Compliance views)."""

from __future__ import annotations

import io
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def _safe_secret(key: str, default: str) -> str:
    """Read Streamlit secret if available, else fallback to env/default."""
    try:
        return str(st.secrets.get(key, os.getenv(key.upper(), default)))
    except Exception:
        return str(os.getenv(key.upper(), default))


API_BASE = _safe_secret("api_base_url", "http://localhost:8000")
MCP_BASE = _safe_secret("mcp_base_url", "http://localhost:8585/mcp")


def _find_logo_file() -> Path | None:
    """Find a logo image from the repository logo directory."""
    root = Path(__file__).resolve().parents[1]
    logo_dir = root / "logo"
    if not logo_dir.exists():
        return None

    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg"):
        files = sorted(logo_dir.glob(pattern))
        if files:
            return files[0]
    return None


def _find_logo_files() -> dict[str, Path | None]:
    """Return both brand assets if available."""
    root = Path(__file__).resolve().parents[1]
    logo_dir = root / "logo"
    return {
        "brand_name": logo_dir / "brand_name.png" if (logo_dir / "brand_name.png").exists() else None,
        "logo_mark": logo_dir / "metaverdax_logo_design_on_black.png"
        if (logo_dir / "metaverdax_logo_design_on_black.png").exists()
        else None,
    }


def _get_app_mode() -> str:
    """Read current view mode from query params/session state."""
    try:
        qp = st.query_params.get("view")
        if isinstance(qp, list):
            qp = qp[0] if qp else None
        if qp in {"landing", "prototype"}:
            return str(qp)
    except Exception:
        pass
    return str(st.session_state.get("app_mode", "landing"))


def _set_app_mode(mode: str) -> None:
    """Persist view mode in session and query params."""
    st.session_state["app_mode"] = mode
    try:
        st.query_params["view"] = mode
    except Exception:
        pass


def _inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');

:root {
    --bg: #0a0f16;
    --bg2: #0f1624;
    --panel: #111827;
    --panel2: #182235;
    --accent: #22c55e;
    --critical: #ef4444;
    --warn: #f59e0b;
    --safe: #38bdf8;
    --text: #e5eef7;
    --muted: #91a4b7;
}

html, body, [data-testid="stAppViewContainer"] {
  background:
        radial-gradient(circle at 20% 15%, rgba(34,197,94,0.11), transparent 32%),
        radial-gradient(circle at 80% 10%, rgba(56,189,248,0.10), transparent 28%),
        linear-gradient(170deg, var(--bg) 0%, var(--bg2) 100%);
  color: var(--text);
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 { color: var(--text) !important; letter-spacing: 0.2px; }

header[data-testid="stHeader"] {
    background: transparent;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0e1420 0%, #111827 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}

section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
    color: #dbe6f1 !important;
}

[data-testid="stSidebar"] {
    padding-top: 0.25rem;
}

.metric, .mono, code {
  font-family: 'JetBrains Mono', monospace !important;
}

div[data-testid="metric-container"] {
    background: linear-gradient(145deg, rgba(17,24,39,0.94), rgba(24,34,53,0.92));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 14px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.16);
}

div[data-testid="metric-container"] label {
    color: #9fb2c7 !important;
    font-weight: 600 !important;
}

div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f8fbff !important;
    font-weight: 800 !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 10px;
    border-bottom: 1px solid rgba(255,255,255,0.10);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 999px;
    padding: 8px 18px;
    font-weight: 700;
    color: #b4c4d6;
}

.stTabs [aria-selected="true"] {
    color: #ffffff !important;
    background: rgba(34,197,94,0.10);
}

button[kind="secondary"], .stButton > button {
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.10);
    background: linear-gradient(145deg, rgba(24,34,53,0.98), rgba(17,24,39,0.98));
    color: #f6fbff;
}

.hero {
    padding: 10px 0 6px;
}

.hero h1 {
    margin-bottom: 0.15rem;
}

.hero p {
    color: var(--muted);
    margin-top: 0;
}

.chat-user {
  margin-left: 18%;
    background: linear-gradient(135deg, #202a3a, #2b3548);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 10px 14px;
  color: #F8FBFF;
  animation: fadeInUp 260ms ease;
}

.chat-agent {
  margin-right: 18%;
    background: linear-gradient(135deg, #0f1724, #0f221d);
    border: 1px solid rgba(34,197,94,0.22);
  border-radius: 14px;
  padding: 10px 14px;
  color: #D8FFE8;
  animation: fadeInUp 260ms ease;
}

.risk-card {
    border: 1px solid rgba(255,255,255,0.10);
  border-radius: 16px;
    background: linear-gradient(140deg, rgba(15,23,32,0.96), rgba(10,18,26,0.96));
  padding: 16px;
  margin-top: 14px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.16);
}

.brand-title {
    font-weight: 800;
    letter-spacing: 0.4px;
    color: #f7fbff;
    margin-top: 0.5rem;
}

.brand-tagline {
    color: #8ea1b5;
    font-size: 0.92rem;
    margin-top: -0.15rem;
}

.sidebar-divider {
    border-top: 1px solid rgba(255,255,255,0.08);
    margin: 0.8rem 0 1rem;
}

.sidebar-chip {
    display: inline-block;
    margin: 0.1rem 0.35rem 0.1rem 0;
    padding: 0.3rem 0.6rem;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(255,255,255,0.03);
    color: #cfe0f0;
    font-size: 0.76rem;
}

.dot { font-size: 10px; vertical-align: middle; margin-right: 6px; }

.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #f7fbff;
    margin-bottom: 0.2rem;
}

.section-subtitle {
    color: var(--muted);
    margin-top: 0;
}

.landing-wrap {
    margin: 0.2rem 0 1.2rem;
}

.hero-panel {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 24px;
    background:
        radial-gradient(circle at 20% 20%, rgba(34,197,94,0.16), transparent 34%),
        radial-gradient(circle at 75% 15%, rgba(56,189,248,0.14), transparent 30%),
        linear-gradient(145deg, rgba(10,15,22,0.98), rgba(17,24,39,0.98));
    box-shadow: 0 18px 44px rgba(0,0,0,0.24);
    padding: 28px;
}

.hero-kicker {
    display: inline-block;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid rgba(34,197,94,0.25);
    background: rgba(34,197,94,0.08);
    color: #bff5cd;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.8rem;
}

.hero-title {
    font-size: clamp(2.2rem, 5vw, 4.3rem);
    line-height: 1.02;
    font-weight: 900;
    color: #f8fbff;
    margin: 0.2rem 0 0.6rem;
}

.hero-copy {
    color: #b1c2d4;
    font-size: 1.02rem;
    line-height: 1.7;
    max-width: 72ch;
}

.hero-chip-row { margin-top: 0.9rem; }

.hero-chip {
    display: inline-block;
    margin: 0.2rem 0.4rem 0.2rem 0;
    padding: 0.38rem 0.72rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    color: #dce8f4;
    font-size: 0.8rem;
}

.info-card {
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(150deg, rgba(17,24,39,0.94), rgba(11,17,26,0.96));
    padding: 18px;
    box-shadow: 0 14px 28px rgba(0,0,0,0.16);
    height: 100%;
}

.info-card h3 {
    margin: 0 0 0.5rem;
    font-size: 1.05rem;
}

.info-card p, .info-card li {
    color: #bac8d8;
    line-height: 1.6;
}

.value-stat {
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.10);
    background: linear-gradient(145deg, rgba(17,24,39,0.92), rgba(24,34,53,0.92));
    padding: 16px;
    text-align: left;
    height: 100%;
}

.value-stat .big {
    font-size: 1.55rem;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 0.2rem;
}

.value-stat .small {
    color: #a7bbcd;
    font-size: 0.9rem;
    line-height: 1.5;
}

.workflow-step {
    padding: 0.9rem 1rem;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.03);
    min-height: 100%;
}

.workflow-step .step-no {
    display: inline-block;
    width: 30px;
    height: 30px;
    line-height: 30px;
    border-radius: 50%;
    text-align: center;
    margin-bottom: 0.5rem;
    font-weight: 800;
    color: #0b1220;
    background: linear-gradient(145deg, #86efac, #38bdf8);
}

.resource-pill {
    display: inline-block;
    margin: 0.2rem 0.35rem 0.2rem 0;
    padding: 0.36rem 0.68rem;
    border-radius: 999px;
    background: rgba(34,197,94,0.10);
    border: 1px solid rgba(34,197,94,0.18);
    color: #d9ffe3;
    font-size: 0.8rem;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0px); }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _api_get(path: str) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def _status_dot(ok: bool) -> str:
    return "<span class='dot' style='color:#00FF88'>●</span>" if ok else "<span class='dot' style='color:#FF3B3B'>●</span>"


def _check_health(url: str) -> bool:
    try:
        r = requests.get(url, timeout=3)
        return r.status_code < 500
    except Exception:
        return False


def _ensure_state() -> None:
    st.session_state.setdefault("session_id", f"sess-{uuid.uuid4().hex[:8]}")
    st.session_state.setdefault("sessions", [])
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_scan", None)
    st.session_state.setdefault("app_mode", "landing")


def _new_session() -> None:
    old = st.session_state.get("session_id")
    if old and old not in st.session_state["sessions"]:
        st.session_state["sessions"].append(old)
    st.session_state["session_id"] = f"sess-{uuid.uuid4().hex[:8]}"
    st.session_state["messages"] = []
    st.session_state["last_scan"] = None


def _stream_chat(message: str, dataset_path: str | None = None) -> tuple[str, dict | None]:
    payload = {
        "message": message,
        "dataset_path": dataset_path,
        "session_id": st.session_state["session_id"],
    }

    full_text = ""
    scan_result = None
    placeholder = st.empty()

    with requests.post(f"{API_BASE}/agent/chat", json=payload, stream=True, timeout=180) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "):
                continue
            content = raw_line[len("data: "):]
            if content == "[DONE]":
                break
            try:
                event = json.loads(content)
            except json.JSONDecodeError:
                continue

            if "token" in event:
                full_text += event["token"]
                placeholder.markdown(full_text)
            if "scan_result" in event:
                scan_result = event["scan_result"]

    placeholder.markdown(full_text)
    return full_text, scan_result


def _risk_color(level: str) -> str:
    if level == "CRITICAL":
        return "#FF3B3B"
    if level in {"WARN", "REVIEW"}:
        return "#FFB800"
    return "#00C9FF"


def _render_risk_card(scan: dict) -> None:
    level = scan.get("risk_level", "SAFE")
    color = _risk_color(level)
    drift = scan.get("drift_summary", {}).get("drift_score", 0)
    anomaly_rate = scan.get("anomaly_summary", {}).get("anomaly_rate", 0)
    table = scan.get("table_fqn", "dataset")
    carbon = scan.get("carbon_saved_kg", 0)
    pdf = scan.get("pdf_path")
    pdf_url = None
    if pdf:
        if str(pdf).startswith(("http://", "https://")):
            pdf_url = str(pdf)
        else:
            pdf_url = f"{API_BASE.rstrip('/')}/{str(pdf).lstrip('./')}"
    om_base = MCP_BASE.rsplit("/mcp", 1)[0] if "/mcp" in MCP_BASE else MCP_BASE
    is_mock_mcp = ":8586" in om_base
    metadata_url = f"{om_base}/mcp/state" if is_mock_mcp else om_base
    metadata_label = "Open MCP State (Mock)" if is_mock_mcp else "Open in OpenMetadata"

    st.markdown(
        f"""
<div class='risk-card'>
  <div style='font-family: JetBrains Mono, monospace; font-weight:700; color:{color};'>
    {level} - {table}
  </div>
  <div style='margin-top:6px;'>Drift: {drift} | Anomalies: {float(anomaly_rate) * 100:.1f}%</div>
  <div style='margin-top:4px;'>CO2 saved by blocking: {carbon:.1f}kg</div>
  <div style='margin-top:10px;'>
        <a href='{pdf_url or '#'}' target='_blank'>View PDF</a> | <a href='{metadata_url}' target='_blank'>{metadata_label}</a>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _build_summary_pdf(scan_results: list[dict]) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, y, "MetaVerdax Compliance Audit Summary")
    y -= 24
    p.setFont("Helvetica", 10)
    p.drawString(40, y, f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    y -= 24

    headers = ["Timestamp", "Table", "Risk", "CO2 kg"]
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, headers[0])
    p.drawString(180, y, headers[1])
    p.drawString(360, y, headers[2])
    p.drawString(430, y, headers[3])
    y -= 16

    p.setFont("Helvetica", 9)
    for row in scan_results[:40]:
        if y < 60:
            p.showPage()
            y = height - 40
            p.setFont("Helvetica", 9)
        p.drawString(40, y, str(row.get("timestamp", ""))[:19])
        p.drawString(180, y, str(row.get("table_fqn", ""))[:30])
        p.drawString(360, y, str(row.get("risk_level", "")))
        p.drawString(430, y, f"{float(row.get('carbon_saved_kg', 0.0)):.1f}")
        y -= 14

    p.save()
    buffer.seek(0)
    return buffer.read()


def _render_landing_page() -> None:
    logos = _find_logo_files()
    st.markdown(
        """
<div class='landing-wrap'>
  <div class='hero-panel'>
    <div class='hero-kicker'>MCP Ecosystem · AI Agents · Data Governance</div>
    <div class='hero-title'>MetaVerdax: turn metadata into a guardrail for every retrain.</div>
    <div class='hero-copy'>
      MetaVerdax converts natural-language intent into an AI governance workflow that reads OpenMetadata through MCP,
      validates datasets against live metadata, detects drift and anomalies, blocks risky retrains, and writes audit-ready
      evidence back to your data catalog.
    </div>
    <div class='hero-chip-row'>
      <span class='hero-chip'>FastAPI backend</span>
      <span class='hero-chip'>Streamlit premium UI</span>
      <span class='hero-chip'>Groq / Gemini / Claude</span>
      <span class='hero-chip'>OpenMetadata MCP</span>
      <span class='hero-chip'>Verdax validation engine</span>
      <span class='hero-chip'>Audit-ready PDFs</span>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1])
    with left:
        if logos["logo_mark"] is not None:
            st.image(str(logos["logo_mark"]), width=220)
    with right:
        if logos["brand_name"] is not None:
            st.image(str(logos["brand_name"]), width=260)

    launch_cols = st.columns([1, 1, 2])
    with launch_cols[0]:
        if st.button("Launch Prototype", type="primary", use_container_width=True):
            _set_app_mode("prototype")
            st.rerun()
    with launch_cols[1]:
        if st.button("See the Product", use_container_width=True):
            _set_app_mode("prototype")
            st.rerun()

    st.markdown("### Why this matters")
    st.markdown(
        """
MetaVerdax solves a costly loop: ML teams spend most of their time cleaning data, retrains waste GPU budget, and
compliance teams struggle to prove governance. The product gives you a single decision point before a retrain happens.
        """
    )

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(
            """
<div class='value-stat'>
  <div class='big'>60-80%</div>
  <div class='small'>of a data scientist's time can be spent cleaning and validating data instead of building models.</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            """
<div class='value-stat'>
  <div class='big'>$10k-$100k+</div>
  <div class='small'>can be wasted on one bad retrain when bad data reaches a large model.</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            """
<div class='value-stat'>
  <div class='big'>$110M</div>
  <div class='small'>was lost by Unity Technologies in 2022 due to corrupted ML training data.</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with s4:
        st.markdown(
            """
<div class='value-stat'>
  <div class='big'>€35M</div>
  <div class='small'>is the EU AI Act fine ceiling that makes governance and auditability non-negotiable.</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Who it is for")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown(
            """
<div class='info-card'>
  <h3>ML Engineer / Data Scientist</h3>
  <p>Triggers scans through chat, API, or CLI before retraining. Wants a fast risk score, exact failure reasons, and an automatic block when the data is unsafe.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            """
<div class='info-card'>
  <h3>Compliance Officer / CTO</h3>
  <p>Never touches code. Opens a dashboard to review blocked retrains, downloadable PDF evidence, drift stats, lineage impact, and carbon savings for auditors and clients.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### What the agent actually does")
    w1, w2, w3, w4 = st.columns(4)
    steps = [
        ("01", "Understands natural language like 'Is my dataset safe to retrain?'"),
        ("02", "Reads schema, profiles, lineage, tests, owners, and glossary from OpenMetadata via MCP."),
        ("03", "Runs Verdax checks: nulls, duplicates, ranges, chi-squared drift, Isolation Forest, and risk scoring."),
        ("04", "Writes back tasks, tags, observations, and a PDF audit trail with CO2 impact."),
    ]
    for col, (no, text) in zip((w1, w2, w3, w4), steps):
        with col:
            st.markdown(
                f"""
<div class='workflow-step'>
  <div class='step-no'>{no}</div>
  <div>{text}</div>
</div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### Value delivered")
    v1, v2, v3 = st.columns(3)
    with v1:
        st.markdown(
            """
<div class='info-card'>
  <h3>Risk prevention</h3>
  <p>Blocks or flags dangerous retrains before compute is burned and broken models are shipped.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
    with v2:
        st.markdown(
            """
<div class='info-card'>
  <h3>Audit readiness</h3>
  <p>Produces compliance evidence: timestamps, drift stats, lineage impact, ownership context, and PDF reports.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
    with v3:
        st.markdown(
            """
<div class='info-card'>
  <h3>Carbon and ESG</h3>
  <p>Shows CO2 saved by blocking bad retrains, making sustainability part of the governance story.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Resources and stack")
    st.markdown(
        """
<div>
  <span class='resource-pill'>OpenMetadata</span>
  <span class='resource-pill'>MCP</span>
  <span class='resource-pill'>FastAPI</span>
  <span class='resource-pill'>Streamlit</span>
  <span class='resource-pill'>Groq / Gemini / Claude</span>
  <span class='resource-pill'>Pandas</span>
  <span class='resource-pill'>Scikit-learn</span>
  <span class='resource-pill'>MongoDB</span>
  <span class='resource-pill'>SQLite</span>
  <span class='resource-pill'>ReportLab</span>
  <span class='resource-pill'>Verdax validator, drift detector, anomaly scorer, carbon calculator, report generator</span>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Demo story")
    st.markdown(
        """
1. Upload a poisoned customer churn CSV.
2. Ask in plain English if the dataset is safe to retrain.
3. Watch MetaVerdax read metadata, run Verdax checks, and label the risk.
4. See the task created in OpenMetadata, the PDF report generated, and the blocked retrain evidence captured.
        """
    )


def engineer_tab() -> None:
    st.markdown(
        """
<div class='hero'>
  <div class='section-title'>Engineer Chat Interface</div>
  <div class='section-subtitle'>Ask about dataset safety, drift, and compliance actions from one place.</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    for msg in st.session_state["messages"]:
        if msg["role"] == "user":
            st.markdown(f"<div class='chat-user'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            # Parse markdown so **bold** and bullet formatting render correctly.
            st.markdown(msg["content"])

    suggestions = [
        "Is my dataset safe?",
        "Show drift last 7 days",
        "Generate compliance report",
    ]
    cols = st.columns(3)
    for i, s in enumerate(suggestions):
        if cols[i].button(s, key=f"sugg-{i}"):
            st.session_state["pending_message"] = s

    message = st.chat_input("Ask MetaVerdax Agent")
    if st.session_state.get("pending_message") and not message:
        message = st.session_state.pop("pending_message")

    if message:
        st.session_state["messages"].append({"role": "user", "content": message})
        st.markdown(f"<div class='chat-user'>{message}</div>", unsafe_allow_html=True)

        answer, scan_result = _stream_chat(message)
        st.session_state["messages"].append({"role": "assistant", "content": answer})

        if scan_result:
            st.session_state["last_scan"] = scan_result
            _render_risk_card(scan_result)

    if st.session_state.get("last_scan"):
        _render_risk_card(st.session_state["last_scan"])


def compliance_tab() -> None:
    st.markdown(
        """
<div class='hero'>
  <div class='section-title'>Compliance &amp; Governance Overview</div>
  <div class='section-subtitle'>Review scan history, blocked retrains, and audit output.</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    try:
        scan_payload = _api_get("/agent/scan-results")
        blocked_payload = _api_get("/agent/blocked-retrains")
    except Exception as exc:
        st.error(f"Failed to load compliance data: {exc}")
        return

    results = scan_payload.get("results", [])
    blocked = blocked_payload.get("results", [])

    total_scans = len(results)
    blocked_count = len(blocked)
    co2_total = sum(float(r.get("carbon_saved_kg", 0.0)) for r in results)
    open_tasks = sum(1 for r in results if r.get("openmetadata_task_id"))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Scans", f"{total_scans}")
    k2.metric("Blocked Retrains", f"{blocked_count}")
    k3.metric("CO2 Saved (kg)", f"{co2_total:.1f}")
    k4.metric("Open Tasks", f"{open_tasks}")

    st.markdown("### Recent Scan Results")
    if results:
        df = pd.DataFrame(results)
        risk_filter = st.multiselect("Filter by risk", ["SAFE", "WARN", "REVIEW", "CRITICAL"], default=[])
        if risk_filter:
            df = df[df["risk_level"].isin(risk_filter)]
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "Download scan results CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="meta_verdax_scan_results.csv",
            mime="text/csv",
        )
    else:
        st.info("No scan results available yet.")

    st.markdown("### Blocked Retrains (Last 30 Days)")
    if blocked:
        cols = st.columns(2)
        for idx, row in enumerate(blocked[:12]):
            level = row.get("risk_level", "REVIEW")
            color = _risk_color(level)
            with cols[idx % 2]:
                st.markdown(
                    f"""
<div class='risk-card'>
  <div style='font-weight:700; color:{color};'>{level}</div>
  <div class='mono'>{row.get('table_fqn', 'unknown')}</div>
  <div style='font-size:13px;color:#B8C4CE;'>{row.get('timestamp','')}</div>
</div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No blocked retrains in the last 30 days.")

    if st.button("Download Full Audit Report (PDF)"):
        pdf_bytes = _build_summary_pdf(results)
        st.download_button(
            "Save Audit PDF",
            data=pdf_bytes,
            file_name="meta_verdax_audit_report.pdf",
            mime="application/pdf",
        )


def sidebar() -> None:
    logo_path = _find_logo_file()
    if logo_path is not None:
        st.sidebar.image(str(logo_path), width=92)

    st.sidebar.markdown("<div class='brand-title'>MetaVerdax</div>", unsafe_allow_html=True)
    st.sidebar.markdown("<div class='brand-tagline'>AI-driven dataset safety and compliance control</div>", unsafe_allow_html=True)
    st.sidebar.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)

    st.sidebar.markdown("<span class='sidebar-chip'>Engineer</span><span class='sidebar-chip'>Compliance</span><span class='sidebar-chip'>Audit</span>", unsafe_allow_html=True)

    if _get_app_mode() != "prototype":
        st.sidebar.markdown("### Landing page")
        st.sidebar.caption("Open the full working prototype to chat, scan, and generate reports.")
        if st.sidebar.button("Launch Prototype", use_container_width=True):
            _set_app_mode("prototype")
            st.rerun()
        st.sidebar.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
        st.sidebar.caption("Prototype controls appear after launch.")
        return

    api_ok = _check_health(f"{API_BASE}/health")
    mcp_ok = _check_health(MCP_BASE)
    st.sidebar.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(f"API Status: {_status_dot(api_ok)}", unsafe_allow_html=True)
    st.sidebar.markdown(f"MCP Status: {_status_dot(mcp_ok)}", unsafe_allow_html=True)

    st.sidebar.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)

    if _get_app_mode() == "prototype":
        if st.sidebar.button("← Back to Landing"):
            _set_app_mode("landing")
            st.rerun()

    st.sidebar.markdown("### Sessions")
    st.sidebar.code(st.session_state["session_id"], language=None)
    if st.sidebar.button("New Session"):
        _new_session()
        st.rerun()

    if st.session_state["sessions"]:
        selected = st.sidebar.selectbox("Previous Sessions", ["-"] + st.session_state["sessions"])
        if selected != "-" and st.sidebar.button("Load Session"):
            st.session_state["session_id"] = selected
            try:
                history = _api_get(f"/agent/sessions/{selected}/history").get("history", [])
                st.session_state["messages"] = [{"role": h["role"], "content": h["content"]} for h in history]
            except Exception:
                pass
            st.rerun()

    st.sidebar.markdown("### File Uploader")
    upload = st.sidebar.file_uploader("Upload CSV/Parquet", type=["csv", "parquet"])
    table_fqn = st.sidebar.text_input("Table FQN", value="ecommerce.customer_churn_v3")
    if upload and st.sidebar.button("Upload and Scan"):
        files = {"file": (upload.name, upload.getvalue(), upload.type or "application/octet-stream")}
        data = {"table_fqn": table_fqn, "session_id": st.session_state["session_id"]}
        try:
            response = requests.post(f"{API_BASE}/agent/upload-and-scan", files=files, data=data, timeout=180)
            response.raise_for_status()
            st.session_state["last_scan"] = response.json()
            st.sidebar.success("Scan completed")
        except Exception as exc:
            st.sidebar.error(f"Upload scan failed: {exc}")

    st.sidebar.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
    st.sidebar.caption("MetaVerdax UI aligned to the Verdax visual language.")


def main() -> None:
    st.set_page_config(page_title="MetaVerdax Agent", page_icon="V", layout="wide")
    _inject_css()
    _ensure_state()
    sidebar()

    if _get_app_mode() != "prototype":
        _render_landing_page()
        return

    st.markdown(
        """
<div class='hero'>
  <div class='section-title'>Main Prototype</div>
  <div class='section-subtitle'>Chat with the agent, scan data, and review compliance evidence.</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["Engineer", "Compliance"])
    with tab1:
        engineer_tab()
    with tab2:
        compliance_tab()


if __name__ == "__main__":
    main()
