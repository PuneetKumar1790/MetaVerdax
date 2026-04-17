"""Streamlit interface for MetaVerdax Agent (Engineer + Compliance views)."""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime

import pandas as pd
import requests
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

API_BASE = st.secrets.get("api_base_url", "http://localhost:8000")
MCP_BASE = st.secrets.get("mcp_base_url", "http://localhost:8585/mcp")


def _inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap');

:root {
  --bg: #0A0A0F;
  --panel: #12121A;
  --panel2: #181824;
  --accent: #00FF88;
  --critical: #FF3B3B;
  --warn: #FFB800;
  --safe: #00C9FF;
  --text: #EAF2F5;
  --muted: #95A3AD;
}

html, body, [data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 20% 20%, rgba(0,255,136,0.08), transparent 36%),
    radial-gradient(circle at 80% 10%, rgba(0,201,255,0.08), transparent 30%),
    linear-gradient(170deg, #0A0A0F 0%, #11111B 100%);
  color: var(--text);
  font-family: 'Space Grotesk', sans-serif;
}

h1, h2, h3 { color: var(--text) !important; letter-spacing: 0.3px; }

[data-testid="stSidebar"] {
  background: linear-gradient(170deg, #0E0E16 0%, #121220 100%);
  border-right: 1px solid rgba(255,255,255,0.05);
}

.metric, .mono, code {
  font-family: 'JetBrains Mono', monospace !important;
}

.chat-user {
  margin-left: 18%;
  background: linear-gradient(135deg, #20202C, #2A2A39);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 10px 14px;
  color: #F8FBFF;
  animation: fadeInUp 260ms ease;
}

.chat-agent {
  margin-right: 18%;
  background: linear-gradient(135deg, #10161A, #0E1E1A);
  border: 1px solid rgba(0,255,136,0.25);
  border-radius: 14px;
  padding: 10px 14px;
  color: #D8FFE8;
  animation: fadeInUp 260ms ease;
}

.risk-card {
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 16px;
  background: linear-gradient(140deg, #13131D, #0F1720);
  padding: 16px;
  margin-top: 14px;
}

.dot { font-size: 16px; vertical-align: middle; }

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
                placeholder.markdown(f"<div class='chat-agent'>{full_text}</div>", unsafe_allow_html=True)
            if "scan_result" in event:
                scan_result = event["scan_result"]

    placeholder.markdown(f"<div class='chat-agent'>{full_text}</div>", unsafe_allow_html=True)
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
    om_url = MCP_BASE.replace("/mcp", "")

    st.markdown(
        f"""
<div class='risk-card'>
  <div style='font-family: JetBrains Mono, monospace; font-weight:700; color:{color};'>
    {level} - {table}
  </div>
  <div style='margin-top:6px;'>Drift: {drift} | Anomalies: {float(anomaly_rate) * 100:.1f}%</div>
  <div style='margin-top:4px;'>CO2 saved by blocking: {carbon:.1f}kg</div>
  <div style='margin-top:10px;'>
    <a href='{pdf or '#'}' target='_blank'>View PDF</a> | <a href='{om_url}' target='_blank'>Open in OpenMetadata</a>
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


def engineer_tab() -> None:
    st.subheader("Engineer Chat Interface")

    for msg in st.session_state["messages"]:
        style = "chat-user" if msg["role"] == "user" else "chat-agent"
        st.markdown(f"<div class='{style}'>{msg['content']}</div>", unsafe_allow_html=True)

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
    st.markdown("## Compliance & Governance Overview")

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
    st.sidebar.markdown("## MetaVerdax Agent")

    api_ok = _check_health(f"{API_BASE}/health")
    mcp_ok = _check_health(MCP_BASE)
    st.sidebar.markdown(f"API Status: {_status_dot(api_ok)}", unsafe_allow_html=True)
    st.sidebar.markdown(f"MCP Status: {_status_dot(mcp_ok)}", unsafe_allow_html=True)

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


def main() -> None:
    st.set_page_config(page_title="MetaVerdax Agent", page_icon="V", layout="wide")
    _inject_css()
    _ensure_state()
    sidebar()

    tab1, tab2 = st.tabs(["Engineer", "Compliance"])
    with tab1:
        engineer_tab()
    with tab2:
        compliance_tab()


if __name__ == "__main__":
    main()
