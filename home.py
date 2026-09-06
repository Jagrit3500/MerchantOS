import streamlit as st
import os, socket

st.set_page_config(
    page_title="MerchantOS — Autonomous Compliance & Recovery Command Center",
    page_icon="🏛️",
    layout="wide",
)

HOST = os.getenv("MERCHANTOS_HOST", "localhost")
PORT_A1 = os.getenv("PORT_AGENT1", "8502")
PORT_A2 = os.getenv("PORT_AGENT2", "8503")
PORT_A3 = os.getenv("PORT_AGENT3", "8504")

URL_A1 = f"http://{HOST}:{PORT_A1}"
URL_A2 = f"http://{HOST}:{PORT_A2}"
URL_A3 = f"http://{HOST}:{PORT_A3}"

def is_port_active(host: str, port_str: str) -> bool:
    try:
        port = int(port_str)
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except Exception:
        return False

a1_active = is_port_active(HOST, PORT_A1)
a2_active = is_port_active(HOST, PORT_A2)
a3_active = is_port_active(HOST, PORT_A3)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,.stApp { font-family: 'Inter', sans-serif; }
.stApp { background: #060912; color: #e2e8f0; }

.hero {
    text-align: center; padding: 48px 20px 24px;
}
.hero-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(0, 212, 170, 0.1); color: #00d4aa;
    border: 1px solid rgba(0, 212, 170, 0.3); border-radius: 24px;
    padding: 6px 16px; font-size: 12px; font-weight: 700;
    letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 16px;
}
.hero-title {
    font-size: 60px; font-weight: 900; letter-spacing: -2.5px;
    background: linear-gradient(135deg, #00d4aa 0%, #6366f1 50%, #ef4444 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1.1; margin-bottom: 14px;
}
.hero-sub {
    font-size: 17px; color: #94a3b8; max-width: 720px;
    margin: 0 auto 32px; line-height: 1.6;
}

/* Stat Cards */
.stat-row {
    display: flex; gap: 18px; justify-content: center;
    flex-wrap: wrap; margin-bottom: 40px;
}
.stat-pill {
    background: #0e1424; border: 1px solid #1e293b; border-radius: 20px;
    padding: 12px 26px; text-align: center; min-width: 140px;
}
.stat-num { font-size: 24px; font-weight: 800; }
.stat-lbl { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.6px; margin-top: 2px; }

/* Agent Cards */
.agent-card {
    background: #0d1322; border-radius: 18px; padding: 28px 24px;
    border: 1px solid #1e293b; position: relative; overflow: hidden;
    transition: all 0.3s ease; min-height: 340px;
}
.agent-card:hover {
    border-color: #334155; transform: translateY(-3px);
}
.agent-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 4px; border-radius: 18px 18px 0 0;
}
.agent-1::before { background: linear-gradient(90deg, #6366f1, #00d4aa); }
.agent-2::before { background: linear-gradient(90deg, #00d4aa, #10b981); }
.agent-3::before { background: linear-gradient(90deg, #ef4444, #f59e0b); }

.agent-icon {
    font-size: 42px; margin-bottom: 14px;
}
.agent-title {
    font-size: 20px; font-weight: 800; color: #f8fafc;
    margin-bottom: 6px;
}
.agent-subtitle {
    font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px;
    color: #64748b; margin-bottom: 12px; font-weight: 700;
}
.agent-desc {
    font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 18px;
}
.feature-chip {
    display: inline-block; background: #131c31; border: 1px solid #23314d;
    border-radius: 20px; padding: 3px 10px; font-size: 11px; color: #94a3b8;
    margin: 3px 2px;
}
.port-tag {
    position: absolute; top: 18px; right: 18px;
    background: #070a13; border: 1px solid #1e293b; border-radius: 8px;
    padding: 4px 10px; font-size: 11px; font-family: monospace; font-weight: 700;
}
.tag-online { color: #10b981; border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.08); }
.tag-offline { color: #f59e0b; border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.08); }

/* Link Buttons */
div[data-testid="stLinkButton"] > a {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    text-decoration: none !important;
    padding: 13px 20px !important;
    transition: all 0.25s ease !important;
    border: none !important;
}
div[data-testid="stLinkButton"] > a:hover {
    transform: translateY(-2px) !important;
}

.btn-a1 div[data-testid="stLinkButton"] > a {
    background: linear-gradient(135deg, #3730a3, #6366f1) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35) !important;
}
.btn-a1 div[data-testid="stLinkButton"] > a:hover {
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.6) !important;
}

.btn-a2 div[data-testid="stLinkButton"] > a {
    background: linear-gradient(135deg, #065f46, #00d4aa) !important;
    color: #04120e !important;
    box-shadow: 0 4px 16px rgba(0, 212, 170, 0.35) !important;
}
.btn-a2 div[data-testid="stLinkButton"] > a:hover {
    box-shadow: 0 8px 24px rgba(0, 212, 170, 0.6) !important;
}

.btn-a3 div[data-testid="stLinkButton"] > a {
    background: linear-gradient(135deg, #7f1d1d, #ef4444) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35) !important;
}
.btn-a3 div[data-testid="stLinkButton"] > a:hover {
    box-shadow: 0 8px 24px rgba(239, 68, 68, 0.6) !important;
}

.direct-link {
    display: block; text-align: center; font-size: 11px;
    margin-top: 8px; text-decoration: underline; opacity: 0.85;
}
.direct-link:hover { opacity: 1.0; }
</style>
""", unsafe_allow_html=True)

# Hero
st.markdown("""
<div class='hero'>
  <div class='hero-badge'>⚡ Autonomous Compliance & Settlement Resolution Copilot</div>
  <div class='hero-title'>MerchantOS</div>
  <div class='hero-sub'>
    Unified compliance and settlement resolution copilot for Indian merchants and payment aggregators.
    Diagnose KYC holds, reconcile settlement deficits, audit fees against published rates, and assemble
    statutory documentation to unblock cash flow and eliminate support backlogs.
  </div>
</div>
""", unsafe_allow_html=True)

# Headline Callout: Total Trapped Capital
st.markdown("""
<div style='background: linear-gradient(135deg, rgba(239,68,68,0.12) 0%, rgba(99,102,241,0.1) 100%);
     border: 1px solid rgba(239,68,68,0.3); border-radius: 18px; padding: 22px 28px; margin: 0 auto 32px;
     max-width: 900px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px'>
  <div>
    <div style='font-size: 11px; color: #ef4444; text-transform: uppercase; font-weight: 800; letter-spacing: 1px'>
      🚨 Aggregate Trapped Capital Requiring Action Today
    </div>
    <div style='font-size: 38px; font-weight: 900; color: #f8fafc; line-height: 1.1; margin-top: 4px'>
      ₹94,688<span style='font-size: 18px; color: #94a3b8; font-weight: 500'>.00</span>
    </div>
    <div style='font-size: 12px; color: #94a3b8; margin-top: 4px'>
      Spans: <strong>₹34,200</strong> KYC Holds (Agent 1) + <strong>₹57,500</strong> Settlement Delays & <strong>₹2,988</strong> Fee Variances (Agent 2)
    </div>
  </div>
  <div style='display: flex; gap: 10px;'>
    <div style='background: rgba(15,23,42,0.8); border: 1px solid #334155; border-radius: 12px; padding: 10px 18px; text-align: center'>
      <div style='font-size: 18px; font-weight: 800; color: #ef4444'>4</div>
      <div style='font-size: 10px; color: #64748b; text-transform: uppercase'>Held Txns</div>
    </div>
    <div style='background: rgba(15,23,42,0.8); border: 1px solid #334155; border-radius: 12px; padding: 10px 18px; text-align: center'>
      <div style='font-size: 18px; font-weight: 800; color: #f59e0b'>T+5</div>
      <div style='font-size: 10px; color: #64748b; text-transform: uppercase'>TAT Breach</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Stats
st.markdown("""
<div class='stat-row'>
  <div class='stat-pill'><div class='stat-num' style='color:#6366f1'>3</div><div class='stat-lbl'>Autonomous AI Agents</div></div>
  <div class='stat-pill'><div class='stat-num' style='color:#00d4aa'>25+</div><div class='stat-lbl'>RBI Statutory Directions</div></div>
  <div class='stat-pill'><div class='stat-num' style='color:#ef4444'>4</div><div class='stat-lbl'>Statutory Escalation Tiers</div></div>
  <div class='stat-pill'><div class='stat-num' style='color:#f59e0b'>100%</div><div class='stat-lbl'>Policy-Driven & Auditable</div></div>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    tag_cls = "tag-online" if a1_active else "tag-offline"
    status_text = f"● Online (:{PORT_A1})" if a1_active else f"○ Starting (:{PORT_A1})"
    st.markdown(f"""
    <div class='agent-card agent-1'>
      <div class='port-tag {tag_cls}'>{status_text}</div>
      <div class='agent-icon'>🛡️</div>
      <div class='agent-subtitle'>Agent 1 &nbsp;|&nbsp; Port {PORT_A1}</div>
      <div class='agent-title'>KYC & Fund Hold Diagnosis</div>
      <div class='agent-desc'>
        Diagnose why your Razorpay account or settlement is paused in 5 interactive steps.
        Retrieves authoritative RBI clauses and compiles a legally-grounded support ticket.
      </div>
      <div>
        <span class='feature-chip'>RAG Vector Search</span>
        <span class='feature-chip'>RBI Statutory Citations</span>
        <span class='feature-chip'>Prohibited Demand Detector</span>
        <span class='feature-chip'>Ticket Drafter</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='btn-a1'>", unsafe_allow_html=True)
    st.link_button("🛡️ Launch Agent 1 ↗", url=URL_A1, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<a class='direct-link' href='{URL_A1}' target='_blank' style='color:#6366f1'>Direct Link: {URL_A1}</a>", unsafe_allow_html=True)

with col2:
    tag_cls = "tag-online" if a2_active else "tag-offline"
    status_text = f"● Online (:{PORT_A2})" if a2_active else f"○ Starting (:{PORT_A2})"
    st.markdown(f"""
    <div class='agent-card agent-2'>
      <div class='port-tag {tag_cls}'>{status_text}</div>
      <div class='agent-icon'>💳</div>
      <div class='agent-subtitle'>Agent 2 &nbsp;|&nbsp; Port {PORT_A2}</div>
      <div class='agent-title'>Settlement Reconciliation</div>
      <div class='agent-desc'>
        Upload your Razorpay settlement CSV to detect held funds, missing credits,
        T+2 TAT delays, and fee overcharges exceeding published platform rates.
      </div>
      <div>
        <span class='feature-chip'>CSV Parser</span>
        <span class='feature-chip'>TAT Delay Detector</span>
        <span class='feature-chip'>Fee Rate Audit</span>
        <span class='feature-chip'>Exportable Audit Report</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='btn-a2'>", unsafe_allow_html=True)
    st.link_button("💳 Launch Agent 2 ↗", url=URL_A2, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<a class='direct-link' href='{URL_A2}' target='_blank' style='color:#00d4aa'>Direct Link: {URL_A2}</a>", unsafe_allow_html=True)

with col3:
    tag_cls = "tag-online" if a3_active else "tag-offline"
    status_text = f"● Online (:{PORT_A3})" if a3_active else f"○ Starting (:{PORT_A3})"
    st.markdown(f"""
    <div class='agent-card agent-3'>
      <div class='port-tag {tag_cls}'>{status_text}</div>
      <div class='agent-icon'>⚖️</div>
      <div class='agent-subtitle'>Agent 3 &nbsp;|&nbsp; Port {PORT_A3}</div>
      <div class='agent-title'>Formal Escalation & Ombudsman</div>
      <div class='agent-desc'>
        Escalate beyond customer support. Tracks elapsed dispute days, identifies statutory eligibility,
        and auto-generates formal Grievance letters, RBI Ombudsman complaints, and Legal notices.
      </div>
      <div>
        <span class='feature-chip'>Grievance Letters</span>
        <span class='feature-chip'>RBI Ombudsman Filing</span>
        <span class='feature-chip'>Legal Notice Generator</span>
        <span class='feature-chip'>Evidence Dossier Checklist</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='btn-a3'>", unsafe_allow_html=True)
    st.link_button("⚖️ Launch Agent 3 ↗", url=URL_A3, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<a class='direct-link' href='{URL_A3}' target='_blank' style='color:#ef4444'>Direct Link: {URL_A3}</a>", unsafe_allow_html=True)

st.markdown("---")

st.markdown("### 🗺️ Full Remediation Workflow")
flow_cols = st.columns(7)
steps_flow = [
    ("🛡️ Agent 1", "Diagnose hold cause & check KYC"),
    ("→", ""),
    ("💳 Agent 2", "Reconcile CSV & calculate deficit"),
    ("→", ""),
    ("⚖️ Agent 3", "Generate formal legal dossier"),
    ("→", ""),
    ("🏛️ RBI Ombudsman", "File complaint on cms.rbi.org.in"),
]
for col, (icon, label) in zip(flow_cols, steps_flow):
    with col:
        if label:
            st.markdown(f"""
            <div style='text-align:center;background:#0d1322;border-radius:12px;padding:16px 8px;border:1px solid #1e293b'>
              <div style='font-size:22px'>{icon}</div>
              <div style='font-size:12px;color:#94a3b8;margin-top:6px;font-weight:600'>{label}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align:center;padding:26px 0;font-size:22px;color:#475569'>{icon}</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;font-size:12px;color:#475569'>"
    "MerchantOS — Autonomous Defense for Indian Merchants | Adheres to RBI Master Directions on Payment Aggregators 2025 | "
    "Not legal advice — consult a registered advocate for formal representation"
    "</div>",
    unsafe_allow_html=True,
)
