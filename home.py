import streamlit as st
import pandas as pd
import os, socket
from datetime import date
from pathlib import Path
from Agent2.reconciliation_agent import ReconciliationAgent

st.set_page_config(
    page_title="MerchantOS — Autonomous Compliance & Recovery Command Center",
    page_icon="🏛️",
    layout="wide",
)

# ─── Dynamic Config & Variables (Zero Hardcoding) ─────────────────────────────
HOST = os.getenv("MERCHANTOS_HOST", "localhost")
PORT_A1 = os.getenv("PORT_AGENT1", "8502")
PORT_A2 = os.getenv("PORT_AGENT2", "8503")
PORT_A3 = os.getenv("PORT_AGENT3", "8504")

URL_A1 = os.getenv("MERCHANTOS_AGENT1_URL", f"http://{HOST}:{PORT_A1}")
URL_A2 = os.getenv("MERCHANTOS_AGENT2_URL", f"http://{HOST}:{PORT_A2}")
URL_A3 = os.getenv("MERCHANTOS_AGENT3_URL", f"http://{HOST}:{PORT_A3}")

CURRENCY_SYM = os.getenv("MERCHANT_CURRENCY_SYMBOL", "₹")
CURRENCY_CODE = os.getenv("MERCHANT_CURRENCY", "INR")
AGG_NAME = os.getenv("PAYMENT_AGGREGATOR_NAME", "Razorpay Software Private Limited")
AGG_SHORT = os.getenv("PAYMENT_AGGREGATOR_SHORT", "Razorpay")
WORKSPACE_NAME = os.getenv("MERCHANT_WORKSPACE_NAME", "Merchant workspace")
REGION = os.getenv("MERCHANT_REGION", "India")

def is_port_active(host: str, port_str: str) -> bool:
    try:
        port = int(port_str)
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except Exception:
        return False

a1_active = is_port_active(HOST, PORT_A1)
a2_active = is_port_active(HOST, PORT_A2)
a3_active = is_port_active(HOST, PORT_A3)

# ─── Dynamic Trapped Capital Calculation ──────────────────────────────────────
sample_csv = Path(__file__).parent / "Agent2" / "sample_data" / "sample_settlement.csv"
agent = ReconciliationAgent()
if sample_csv.exists():
    agent.parse_csv(sample_csv.read_text(encoding="utf-8"))
else:
    agent.parse_csv("transaction_id,amount,fee,tax,settlement_amount,status,payment_method\n")
summary = agent.analyze()

kyc_hold_amount = float(os.getenv("SAMPLE_KYC_HOLD_AMOUNT", "34200.00"))
held_amount = sum(t["amount"] for t in summary.get("held_funds", []))
pending_amount = sum(t["amount"] for t in summary.get("pending_funds", []))
fee_overcharge = summary.get("total_overcharge", 0.0)
recovery_agent2 = summary.get("recovery_amount", 0.0)
gross_processed = summary.get("total_gross", 0.0)
settled_to_bank = summary.get("total_settled", 0.0)
total_trapped = kyc_hold_amount + recovery_agent2
held_txns_count = summary.get("held_count", 0) + summary.get("pending_count", 0)

# ─── CSS Styles (Dark Fintech Command Center) ─────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,.stApp {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: #060912; color: #e2e8f0; }}

/* Top Bar */
.top-bar {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 18px; background: rgba(13, 19, 34, 0.75);
    border: 1px solid rgba(30, 41, 59, 0.8); border-radius: 12px;
    margin-bottom: 24px; backdrop-filter: blur(12px);
}}
.top-bar-left {{
    display: flex; align-items: center; gap: 10px; font-size: 13px; color: #94a3b8;
}}
.top-bar-left strong {{ color: #f8fafc; }}
.top-bar-badge {{
    background: rgba(0, 212, 170, 0.12); color: #00d4aa;
    border: 1px solid rgba(0, 212, 170, 0.3); border-radius: 6px;
    padding: 2px 8px; font-size: 11px; font-weight: 700;
}}
.top-bar-right {{
    font-size: 12px; color: #64748b; font-family: monospace;
}}

/* Hero Section */
.hero {{
    text-align: center; padding: 32px 20px 20px; position: relative;
}}
.hero-badge {{
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(0, 212, 170, 0.1); color: #00d4aa;
    border: 1px solid rgba(0, 212, 170, 0.35); border-radius: 24px;
    padding: 6px 18px; font-size: 12px; font-weight: 700;
    letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 16px;
    box-shadow: 0 0 20px rgba(0, 212, 170, 0.15);
}}
.hero-title {{
    font-size: 64px; font-weight: 900; letter-spacing: -2.5px;
    background: linear-gradient(135deg, #00d4aa 0%, #6366f1 50%, #ef4444 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1.1; margin-bottom: 14px;
    filter: drop-shadow(0 0 35px rgba(99, 102, 241, 0.25));
}}
.hero-sub {{
    font-size: 16px; color: #94a3b8; max-width: 780px;
    margin: 0 auto 32px; line-height: 1.6;
}}

/* Headline Callout: Total Trapped Capital */
.trapped-box {{
    background: linear-gradient(135deg, rgba(239,68,68,0.14) 0%, rgba(99,102,241,0.12) 100%);
    border: 1px solid rgba(239,68,68,0.35); border-radius: 20px; padding: 24px 30px; margin: 0 auto 34px;
    max-width: 960px; display: flex; justify-content: space-between; align-items: center;
    flex-wrap: wrap; gap: 18px; backdrop-filter: blur(16px);
    box-shadow: 0 8px 32px rgba(239, 68, 68, 0.12);
}}
.trapped-title {{
    font-size: 12px; color: #ef4444; text-transform: uppercase; font-weight: 800; letter-spacing: 1px;
}}
.trapped-amount {{
    font-size: 42px; font-weight: 900; color: #f8fafc; line-height: 1.1; margin-top: 4px;
}}
.trapped-sub {{
    font-size: 13px; color: #94a3b8; margin-top: 6px;
}}
.trapped-badges {{
    display: flex; gap: 12px;
}}
.trapped-pill {{
    background: rgba(15,23,42,0.85); border: 1px solid #334155; border-radius: 12px;
    padding: 12px 20px; text-align: center; min-width: 90px;
}}

/* Stat Pills */
.stat-row {{
    display: flex; gap: 18px; justify-content: center;
    flex-wrap: wrap; margin-bottom: 40px;
}}
.stat-pill {{
    background: #0d1322; border: 1px solid #1e293b; border-radius: 16px;
    padding: 14px 26px; text-align: center; min-width: 150px;
    transition: transform 0.2s ease, border-color 0.2s ease;
}}
.stat-pill:hover {{
    transform: translateY(-2px); border-color: #334155;
}}
.stat-num {{ font-size: 26px; font-weight: 800; }}
.stat-lbl {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.6px; margin-top: 3px; }}

/* Agent Cards */
.agent-card {{
    background: #0d1322; border-radius: 20px; padding: 30px 26px;
    border: 1px solid #1e293b; position: relative; overflow: hidden;
    transition: all 0.3s ease; min-height: 340px; margin-bottom: 12px; display: flex; flex-direction: column;
}}
.agent-card:hover {{
    border-color: #334155; transform: translateY(-4px);
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
}}
.agent-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 4px; border-radius: 20px 20px 0 0;
}}
.agent-1::before {{ background: linear-gradient(90deg, #6366f1, #00d4aa); }}
.agent-2::before {{ background: linear-gradient(90deg, #00d4aa, #10b981); }}
.agent-3::before {{ background: linear-gradient(90deg, #ef4444, #f59e0b); }}

.agent-icon {{ font-size: 44px; margin-bottom: 16px; }}
.agent-title {{ font-size: 21px; font-weight: 800; color: #f8fafc; margin-bottom: 6px; }}
.agent-subtitle {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; color: #64748b; margin-bottom: 12px; font-weight: 700; }}
.agent-desc {{ font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 20px; flex-grow: 1; }}

.feature-chip {{
    display: inline-block; background: #131c31; border: 1px solid #23314d;
    border-radius: 20px; padding: 3px 10px; font-size: 11px; color: #94a3b8;
    margin: 3px 2px;
}}
.port-tag {{
    position: absolute; top: 20px; right: 20px;
    background: #070a13; border: 1px solid #1e293b; border-radius: 8px;
    padding: 5px 12px; font-size: 11px; font-family: monospace; font-weight: 700;
}}
.tag-online {{ color: #10b981; border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.1); }}
.tag-offline {{ color: #f59e0b; border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.1); }}

/* Link Buttons */
div[data-testid="stLinkButton"] > a {{
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    text-decoration: none !important;
    padding: 13px 20px !important;
    transition: all 0.25s ease !important;
    border: none !important;
}}
div[data-testid="stLinkButton"] > a:hover {{
    transform: translateY(-2px) !important;
}}

.btn-a1 div[data-testid="stLinkButton"] > a {{
    background: linear-gradient(135deg, #3730a3, #6366f1) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35) !important;
}}
.btn-a1 div[data-testid="stLinkButton"] > a:hover {{
    box-shadow: 0 8px 26px rgba(99, 102, 241, 0.6) !important;
}}

.btn-a2 div[data-testid="stLinkButton"] > a {{
    background: linear-gradient(135deg, #065f46, #00d4aa) !important;
    color: #04120e !important;
    box-shadow: 0 4px 16px rgba(0, 212, 170, 0.35) !important;
}}
.btn-a2 div[data-testid="stLinkButton"] > a:hover {{
    box-shadow: 0 8px 26px rgba(0, 212, 170, 0.6) !important;
}}

.btn-a3 div[data-testid="stLinkButton"] > a {{
    background: linear-gradient(135deg, #7f1d1d, #ef4444) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35) !important;
}}
.btn-a3 div[data-testid="stLinkButton"] > a:hover {{
    box-shadow: 0 8px 26px rgba(239, 68, 68, 0.6) !important;
}}

.direct-link {{
    display: block; text-align: center; font-size: 11px;
    margin-top: 10px; text-decoration: underline; opacity: 0.85;
}}
.direct-link:hover {{ opacity: 1.0; }}

/* Dashboard & Ledger Table */
.dashboard-card {{
    background: #0d1322; border: 1px solid #1e293b; border-radius: 18px;
    padding: 24px; margin-top: 20px;
}}
.data-table {{
    width: 100%; border-collapse: collapse; font-size: 13px;
}}
.data-table th {{
    text-align: left; padding: 10px 12px; color: #64748b; font-size: 11px;
    text-transform: uppercase; border-bottom: 1px solid #1e293b;
}}
.data-table td {{
    padding: 12px; border-bottom: 1px solid #131c31; color: #cbd5e1;
}}
.badge-status {{
    display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;
}}
.badge-caution {{ background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }}
.badge-critical {{ background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }}
.money-cell {{ text-align: right; font-family: monospace; font-weight: 700; color: #f8fafc; }}
</style>
""", unsafe_allow_html=True)

# ─── Top Bar ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class='top-bar'>
  <div class='top-bar-left'>
    <span class='top-bar-badge'>WORKSPACE</span>
    <strong>{WORKSPACE_NAME}</strong> · {REGION} · {CURRENCY_CODE}
  </div>
  <div class='top-bar-right'>
    {date.today():%d %b %Y} · Multi-Agent Architecture
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Hero Section ─────────────────────────────────────────────────────────────
st.markdown(f"""
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

# ─── Headline Callout: Total Trapped Capital (Dynamically Derived) ─────────────
st.markdown(f"""
<div class='trapped-box'>
  <div>
    <div class='trapped-title'>
      🚨 Aggregate Trapped Capital Requiring Action Today
    </div>
    <div class='trapped-amount'>
      {CURRENCY_SYM}{total_trapped:,.0f}<span style='font-size: 20px; color: #94a3b8; font-weight: 500'>.00</span>
    </div>
    <div class='trapped-sub'>
      Spans: <strong>{CURRENCY_SYM}{kyc_hold_amount:,.0f}</strong> KYC Holds (Agent 1) + <strong>{CURRENCY_SYM}{recovery_agent2:,.0f}</strong> Settlement Deficits & <strong>{CURRENCY_SYM}{fee_overcharge:,.0f}</strong> Fee Variances (Agent 2)
    </div>
  </div>
  <div class='trapped-badges'>
    <div class='trapped-pill'>
      <div style='font-size: 20px; font-weight: 800; color: #ef4444'>{held_txns_count}</div>
      <div style='font-size: 10px; color: #64748b; text-transform: uppercase'>Held Txns</div>
    </div>
    <div class='trapped-pill'>
      <div style='font-size: 20px; font-weight: 800; color: #f59e0b'>T+5</div>
      <div style='font-size: 10px; color: #64748b; text-transform: uppercase'>TAT Breach</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Key Stats Row ────────────────────────────────────────────────────────────
st.markdown("""
<div class='stat-row'>
  <div class='stat-pill'><div class='stat-num' style='color:#6366f1'>3</div><div class='stat-lbl'>Autonomous AI Agents</div></div>
  <div class='stat-pill'><div class='stat-num' style='color:#00d4aa'>25+</div><div class='stat-lbl'>RBI Statutory Directions</div></div>
  <div class='stat-pill'><div class='stat-num' style='color:#ef4444'>4</div><div class='stat-lbl'>Statutory Escalation Tiers</div></div>
  <div class='stat-pill'><div class='stat-num' style='color:#f59e0b'>100%</div><div class='stat-lbl'>Policy-Driven & Auditable</div></div>
</div>
""", unsafe_allow_html=True)

# ─── Agent Launch Cards ───────────────────────────────────────────────────────
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
        Diagnose why your {AGG_SHORT} account or settlement is paused in 5 interactive steps.
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
        Upload your {AGG_SHORT} settlement CSV to detect held funds, missing credits,
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

st.markdown("<br><hr style='border-color:#1e293b'>", unsafe_allow_html=True)

# ─── Remediation Workflow Diagram ─────────────────────────────────────────────
st.markdown("<h3 style='color:#f8fafc;font-size:20px;margin-bottom:16px;'>🗺️ Full Remediation Workflow</h3>", unsafe_allow_html=True)
flow_cols = st.columns(7)
steps_flow = [
    ("🛡️", "Agent 1", "Diagnose hold cause & check KYC"),
    ("→", "", ""),
    ("💳", "Agent 2", "Reconcile CSV & calculate deficit"),
    ("→", "", ""),
    ("⚖️", "Agent 3", "Generate formal legal dossier"),
    ("→", "", ""),
    ("🏛️", "Ombudsman", "File complaint on cms.rbi.org.in"),
]
for col, (emoji, title, desc) in zip(flow_cols, steps_flow):
    with col:
        if title:
            st.markdown(f"""
            <div style='text-align:center;background:#0d1322;border-radius:14px;padding:14px 6px;border:1px solid #1e293b;min-height:96px;display:flex;flex-direction:column;align-items:center;justify-content:center'>
              <div style='font-size:24px;line-height:1.2'>{emoji}</div>
              <div style='font-size:12px;color:#f8fafc;font-weight:700;margin-top:4px;white-space:nowrap'>{title}</div>
              <div style='font-size:11px;color:#94a3b8;margin-top:4px;line-height:1.3'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align:center;padding:32px 0;font-size:22px;color:#475569'>{emoji}</div>", unsafe_allow_html=True)

# ─── Live Ledger & Settlement Payout Health (Integrated) ───────────────────────
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("📊 Live Sample Payout Health & Attention Ledger (Inspect Sample Report)", expanded=False):
    st.caption(f"Calculated dynamically from included sample report · {AGG_SHORT} Settlement Reconciliation")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross Processed", f"{CURRENCY_SYM}{gross_processed:,.2f}")
    m2.metric("Settled to Bank", f"{CURRENCY_SYM}{settled_to_bank:,.2f}")
    m3.metric("Held & Pending Deficit", f"{CURRENCY_SYM}{recovery_agent2:,.2f}")
    m4.metric("Fee Discrepancy", f"{CURRENCY_SYM}{fee_overcharge:,.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### ⚠️ Flagged Transactions Requiring Remediation")
    flagged_data = []
    for t in (summary.get("held_funds", []) + summary.get("pending_funds", [])):
        flagged_data.append({
            "Transaction ID": t.get("transaction_id", ""),
            "Status": t.get("status", "").replace("_", " ").title(),
            f"Amount ({CURRENCY_CODE})": f"{CURRENCY_SYM}{t.get('amount', 0):,.2f}",
            "Payment Method": t.get("payment_method", "").title(),
        })
    if flagged_data:
        df_flagged = pd.DataFrame(flagged_data)
        st.dataframe(df_flagged, use_container_width=True, hide_index=True)
    else:
        st.info("No flagged or pending transactions in this report.")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<br><hr style='border-color:#1e293b'>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center;font-size:12px;color:#64748b;padding-bottom:20px;line-height:1.6'>"
    f"<strong>MerchantOS</strong> — Autonomous Compliance & Settlement Resolution Copilot for Indian Merchants | "
    f"Adheres to RBI Master Directions on Payment Aggregators 2025 & Card Network Risk Frameworks | "
    f"Not legal advice — consult a registered advocate for formal representation"
    f"</div>",
    unsafe_allow_html=True,
)
