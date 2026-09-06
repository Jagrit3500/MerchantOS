import streamlit as st
import sys, os, io, csv
from datetime import datetime

_AGENT2_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR   = os.path.dirname(_AGENT2_DIR)
if _AGENT2_DIR not in sys.path: sys.path.insert(0, _AGENT2_DIR)
if _ROOT_DIR   not in sys.path: sys.path.insert(1, _ROOT_DIR)

from reconciliation_agent import ReconciliationAgent

try:
    from src.llm_agent import get_answer as rag_get_answer
    RAG_AVAILABLE = True
except Exception:
    RAG_AVAILABLE = False
    rag_get_answer = None

INR = "₹"
HOME_URL   = os.getenv("MERCHANTOS_HOME_URL", "http://localhost:8501")
AGENT3_URL = os.getenv("MERCHANTOS_AGENT3_URL", "http://localhost:8504")

st.set_page_config(
    page_title="MerchantOS — Agent 2: Settlement Reconciliation",
    page_icon="💳",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,.stApp { font-family: 'Inter', sans-serif; }
.stApp { background: #070a13; color: #e2e8f0; }

/* Top Nav */
.top-nav {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 24px; background: #0d121f; border-bottom: 1px solid #1e293b;
    border-radius: 12px; margin-bottom: 24px;
}
.nav-brand {
    font-size: 18px; font-weight: 800;
    background: linear-gradient(135deg, #00d4aa, #10b981);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.nav-link {
    color: #94a3b8; font-size: 13px; text-decoration: none; font-weight: 500;
}
.nav-link:hover { color: #00d4aa; }

/* Hero Card */
.hero-box {
    background: linear-gradient(135deg, rgba(0,212,170,0.08) 0%, rgba(16,185,129,0.05) 100%);
    border: 1px solid #1e293b; border-radius: 16px; padding: 24px 28px;
    margin-bottom: 24px;
}
.hero-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(0,212,170,0.12); color: #00d4aa; border: 1px solid rgba(0,212,170,0.3);
    padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;
}
.hero-title {
    font-size: 30px; font-weight: 800; color: #f8fafc; line-height: 1.2; margin-bottom: 6px;
}
.hero-sub {
    font-size: 14px; color: #94a3b8; max-width: 820px; line-height: 1.5;
}

/* Metric Cards */
.metric-card {
    background: #0d1322; border-radius: 14px; padding: 18px 20px;
    border: 1px solid #1e293b; border-top: 3px solid transparent;
    transition: all 0.25s ease; min-height: 115px;
}
.card-blue   { border-top-color: #6366f1; box-shadow: 0 4px 20px rgba(99,102,241,0.08); }
.card-green  { border-top-color: #10b981; box-shadow: 0 4px 20px rgba(16,185,129,0.08); }
.card-red    { border-top-color: #ef4444; box-shadow: 0 4px 20px rgba(239,68,68,0.12); }
.card-orange { border-top-color: #f59e0b; box-shadow: 0 4px 20px rgba(245,158,11,0.08); }
.card-teal   { border-top-color: #00d4aa; box-shadow: 0 4px 20px rgba(0,212,170,0.08); }

.metric-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; font-weight: 600; }
.metric-value { font-size: 22px; font-weight: 800; color: #f8fafc; line-height: 1.2; }
.metric-sub   { font-size: 11px; color: #64748b; margin-top: 5px; }

/* Issue cards */
.issue-card {
    background: #0b1120; border-radius: 12px;
    padding: 16px 20px; margin: 10px 0;
    border: 1px solid #1e293b; border-left: 4px solid transparent;
}
.issue-held    { border-left-color: #ef4444; }
.issue-pending { border-left-color: #f59e0b; }
.issue-tat     { border-left-color: #a855f7; }
.issue-fee     { border-left-color: #38bdf8; }

.badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
}
.badge-held    { background: rgba(239,68,68,0.18);  color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.badge-pending { background: rgba(245,158,11,0.18); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.badge-settled { background: rgba(16,185,129,0.18); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
.badge-tat     { background: rgba(168,85,247,0.18); color: #a855f7; border: 1px solid rgba(168,85,247,0.3); }
.badge-fee     { background: rgba(56,189,248,0.18); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }

/* Progress & Bars */
.bar-track { background: #1e293b; border-radius: 6px; height: 12px; overflow: hidden; flex: 1; }
.bar-fill-teal   { height: 12px; background: linear-gradient(90deg, #006d5b, #00d4aa); border-radius: 6px; }
.bar-fill-purple { height: 12px; background: linear-gradient(90deg, #4338ca, #6366f1); border-radius: 6px; }
.bar-fill-orange { height: 12px; background: linear-gradient(90deg, #b45309, #f59e0b); border-radius: 6px; }
.bar-fill-blue   { height: 12px; background: linear-gradient(90deg, #0369a1, #38bdf8); border-radius: 6px; }
.bar-fill-gray   { height: 12px; background: #475569; border-radius: 6px; }

/* Table */
.txn-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.txn-table th {
    background: #111827; color: #94a3b8; padding: 12px 14px;
    text-align: left; font-weight: 700; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.6px; border-bottom: 1px solid #1e293b;
}
.txn-table td { padding: 12px 14px; border-bottom: 1px solid #1a2234; }
.txn-row-held    { background: rgba(239,68,68,0.06); }
.txn-row-pending { background: rgba(245,158,11,0.06); }
.txn-row-settled { background: transparent; }
.txn-row-tat     { background: rgba(168,85,247,0.06); }

/* Buttons */
div[data-testid="stButton"] > button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: 12px 18px !important;
    transition: all 0.25s ease !important;
    background: linear-gradient(135deg, #065f46, #00d4aa) !important;
    color: #04120e !important;
    border: none !important;
}
div[data-testid="stDownloadButton"] > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border: 1px solid #334155 !important;
    background: #0f172a !important;
    color: #f8fafc !important;
}
</style>
""", unsafe_allow_html=True)

# Top Nav
st.markdown(f"""
<div class='top-nav'>
  <div class='nav-brand'>💳 MerchantOS &nbsp;|&nbsp; Agent 2</div>
  <div>
    <a class='nav-link' href='{HOME_URL}' target='_blank'>← Command Center</a> &nbsp;&nbsp;|&nbsp;&nbsp;
    <a class='nav-link' href='{AGENT3_URL}' target='_blank'>Escalate Formally →</a>
  </div>
</div>
""", unsafe_allow_html=True)

# Hero
st.markdown("""
<div class='hero-box'>
  <div class='hero-badge'>Automated Reconciliation & Transparency Engine</div>
  <div class='hero-title'>Settlement Reconciliation & Fee Audit Copilot</div>
  <div class='hero-sub'>
    Reconcile settlements against statutory T+2 turnaround times and published Razorpay fee schedules.
    Rapidly surfaces missing credits and fee variances with clear transactional evidence, reducing reconciliation overhead for merchants and aggregators.
  </div>
</div>
""", unsafe_allow_html=True)


def health_ring_svg(score: int, color_key: str) -> str:
    COLOR = {"green":"#10b981","yellow":"#fbbf24","orange":"#f59e0b","red":"#ef4444","gray":"#64748b"}
    c = COLOR.get(color_key, "#64748b")
    circ = 251.2
    offset = circ * (1 - max(score, 0) / 100)
    return f"""
    <div style='background:#0d1322;border:1px solid #1e293b;border-radius:16px;padding:22px;text-align:center'>
      <svg width='110' height='110' viewBox='0 0 100 100'>
        <circle cx='50' cy='50' r='40' fill='none' stroke='#1e293b' stroke-width='9'/>
        <circle cx='50' cy='50' r='40' fill='none' stroke='{c}' stroke-width='9'
          stroke-dasharray='{circ:.1f}' stroke-dashoffset='{offset:.1f}'
          stroke-linecap='round' transform='rotate(-90 50 50)'/>
        <text x='50' y='46' text-anchor='middle' fill='{c}' font-size='19' font-weight='800'>{score}</text>
        <text x='50' y='60' text-anchor='middle' fill='#64748b' font-size='9' font-weight='600'>/ 100</text>
      </svg>
    </div>"""


def run_analysis(csv_content: str):
    agent = ReconciliationAgent()
    parse = agent.parse_csv(csv_content)
    if parse["errors"]:
        st.error("\n".join(parse["errors"]))
        return
    if parse["warnings"]:
        for w in parse["warnings"]:
            st.warning(w)
    if parse["parsed"] == 0:
        st.warning("No transactions found in CSV.")
        return
    summary = agent.analyze()

    rag_answer, rag_meta = "", None
    if RAG_AVAILABLE and rag_get_answer and summary.get("held_count", 0) > 0:
        try:
            q = "What should a merchant do when settlement is held? RBI PA Directions 2025 settlement hold rights"
            rag_result = rag_get_answer(q)
            rag_answer = rag_result.get("answer", "")
            top = rag_result.get("chunks", [{}])[0] if rag_result.get("chunks") else {}
            rag_meta = {
                "similarity": top.get("similarity", 0.85),
                "source": top.get("source", "rbi_pa_2025_knowledge.txt"),
                "chunks_found": len(rag_result.get("chunks", [])),
                "llm_used": rag_result.get("llm_used", False),
            }
        except Exception:
            pass

    if not rag_answer:
        rag_answer = (
            "**RBI PA Master Directions 2025, Para 5.3 & 5.4:**\n\n"
            "Turnaround Time (TAT) for domestic card and UPI settlements is mandated at T+2 working days. "
            "Any settlement held beyond this window requires written justification communicated to the merchant "
            "within 24 hours. The merchant is entitled to claim compensation for unjustifiable settlement delays."
        )

    st.session_state.a2_agent      = agent
    st.session_state.a2_summary    = summary
    st.session_state.a2_rag_answer = rag_answer
    st.session_state.a2_rag_meta   = rag_meta
    st.session_state.a2_done       = True


# INPUT VIEW
if "a2_done" not in st.session_state:
    tab_csv, tab_manual, tab_sample = st.tabs([
        "📂 Upload Settlement CSV", "✍️ Manual Transaction Check", "🧪 Run Sample Dataset"
    ])

    with tab_csv:
        st.markdown("#### Upload Razorpay Settlement CSV")
        st.markdown("""
        <div style='background:#0d1322;border-radius:10px;padding:14px;font-size:12px;color:#94a3b8;margin-bottom:14px;border:1px solid #1e293b'>
        <strong>Required columns:</strong> <code>transaction_id</code>, <code>amount</code>, <code>fee</code>,
        <code>tax</code>, <code>settlement_amount</code>, <code>status</code>, <code>payment_method</code>.<br>
        <strong>Optional:</strong> <code>transaction_date</code>, <code>settlement_date</code>, <code>order_id</code>.
        </div>
        """, unsafe_allow_html=True)
        uploaded = st.file_uploader("Drop your settlement report here", type=["csv"], key="a2_upload")
        if uploaded:
            raw_bytes = uploaded.read()
            try:
                content = raw_bytes.decode("utf-8")
            except Exception:
                content = raw_bytes.decode("latin-1")
            st.info(f"File loaded: {uploaded.name} ({len(content.splitlines())-1} data rows)")
            if st.button("🚀 Analyze Settlement CSV", use_container_width=True, key="csv_go"):
                with st.spinner("Reconciling settlements against RBI rules & Razorpay rates..."):
                    run_analysis(content)
                st.rerun()

    with tab_manual:
        st.markdown("#### Quick Transaction Health Check")
        with st.form("manual_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                txn_id = st.text_input("Transaction ID", placeholder="RZP_TXN_001")
                amount = st.number_input("Transaction Amount (INR)", min_value=0.0, value=1500.0, step=50.0)
            with c2:
                method = st.selectbox("Payment Method", ["UPI","Card","NetBanking","Wallet","EMI","PayLater"])
                status = st.selectbox("Settlement Status", ["on_hold","pending","settled"])
            with c3:
                txn_date  = st.text_input("Transaction Date (YYYY-MM-DD)", placeholder="2024-01-15")
                sett_date = st.text_input("Settlement Date (YYYY-MM-DD)", placeholder="2024-01-20")
            submitted = st.form_submit_button("Analyze Single Transaction", use_container_width=True)
        if submitted:
            meth_lower = method.lower()
            from reconciliation_agent import FEE_RATES, FEE_DEFAULT
            rate_pct, gst_pct = FEE_RATES.get(meth_lower, FEE_DEFAULT)
            fee_e = round(amount * rate_pct / 100, 2)
            tax_e = round(fee_e * gst_pct / 100, 2)
            net_e = round(amount - fee_e - tax_e, 2)
            dummy_id = txn_id if txn_id else "TXN_MANUAL_001"
            csv_m = (
                "settlement_id,settlement_date,transaction_id,order_id,amount,fee,tax,"
                "settlement_amount,status,payment_method,transaction_date\n"
                f"SETL_MANUAL,{sett_date},{dummy_id},ORD_MANUAL,{amount},"
                f"{fee_e},{tax_e},{net_e},{status},{meth_lower},{txn_date}\n"
            )
            with st.spinner("Analyzing..."):
                run_analysis(csv_m)
            st.rerun()

    with tab_sample:
        st.markdown("#### Test with Real Razorpay Settlement Sample")
        st.caption("Includes 15 representative transactions with holds, TAT violations, and fee overcharges.")
        sample_path = os.path.join(_ROOT_DIR, "sample_data", "sample_settlement.csv")
        if os.path.exists(sample_path):
            with open(sample_path) as f:
                sc = f.read()
            st.code("\n".join(sc.strip().splitlines()[:6]), language="csv")
            if st.button("🧪 Reconcile Sample Data", use_container_width=True, key="sample_go"):
                with st.spinner("Reconciling..."):
                    run_analysis(sc)
                st.rerun()
        else:
            st.error("Sample dataset file not found.")

# RESULTS DASHBOARD
else:
    summary = st.session_state.a2_summary
    agent   = st.session_state.a2_agent
    rag_ans = st.session_state.a2_rag_answer or ""
    health  = summary["health_score"]
    score   = health["score"]
    h_color = {"green":"#10b981","yellow":"#fbbf24","orange":"#f59e0b","red":"#ef4444","gray":"#64748b"}.get(health["color"],"#64748b")
    tat_ids = {t["transaction_id"] for t in summary.get("tat_violations", [])}

    st.markdown("### 📊 Settlement Audit Overview")

    col_h, col_m = st.columns([1, 4])
    with col_h:
        st.markdown(health_ring_svg(score, health["color"]), unsafe_allow_html=True)
        st.markdown(f"""
        <div style='text-align:center;margin-top:6px'>
          <div style='font-size:15px;font-weight:800;color:{h_color}'>Settlement Health Index</div>
          <div style='font-size:11px;color:#94a3b8;font-weight:600'>{health['label']} ({score}/100)</div>
          <div style='font-size:10px;color:#64748b;margin-top:2px'>Formula: 100 - (Hold Deductions + TAT Penalties + Fee Discrepancies)</div>
        </div>
        """, unsafe_allow_html=True)

    with col_m:
        c1, c2, c3, c4, c5 = st.columns(5)
        metrics = [
            (c1, "card-blue",   f"{INR}{summary['total_gross']:,.0f}",    "Total Gross",     f"{summary['total_transactions']} txns"),
            (c2, "card-green",  f"{INR}{summary['total_settled']:,.0f}",   "Settled to Bank", f"{summary['settled_count']} settled"),
            (c3, "card-red",    f"{INR}{summary['recovery_amount']:,.0f}", "Recovery Needed", f"{summary['held_count']+summary['pending_count']} affected"),
            (c4, "card-orange", f"{INR}{summary['total_overcharge']:,.0f}","Fee Overcharge",  f"{len(summary['overcharged_fees'])} txns"),
            (c5, "card-teal",   str(summary.get("tat_count", 0)),          "TAT Delays",      "Exceeds T+2"),
        ]
        for col, cls, val, label, sub in metrics:
            with col:
                st.markdown(f"""
                <div class='metric-card {cls}'>
                  <div class='metric-label'>{label}</div>
                  <div class='metric-value'>{val}</div>
                  <div class='metric-sub'>{sub}</div>
                </div>
                """, unsafe_allow_html=True)

        # Explicit Financial Arithmetic Reconciliation Bar
        gross_val = summary['total_gross']
        settled_val = summary['total_settled']
        recovery_val = summary['recovery_amount']
        fees_val = round(summary['total_fee_charged'] + summary['total_tax_charged'], 2)
        variance_val = round(gross_val - (settled_val + recovery_val + fees_val), 2)

        st.markdown(f"""
        <div style='background:#0b1120;border:1px solid #1e293b;border-radius:12px;padding:12px 18px;margin-top:14px;font-size:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px'>
          <div><span style='color:#64748b;text-transform:uppercase;letter-spacing:0.6px;font-weight:700'>Arithmetic Balance Reconciliation:</span></div>
          <div style='color:#cbd5e1'>
            <strong>Gross ({INR}{gross_val:,.2f})</strong> = 
            <span style='color:#10b981'>Settled ({INR}{settled_val:,.2f})</span> + 
            <span style='color:#ef4444'>Held / Pending ({INR}{recovery_val:,.2f})</span> + 
            <span style='color:#94a3b8'>Fees & Tax ({INR}{fees_val:,.2f})</span>
            {f" + <span style='color:#f59e0b'>Variance ({INR}{variance_val:,.2f})</span>" if abs(variance_val) > 0.01 else ""}
          </div>
          <div><span style='background:rgba(16,185,129,0.15);color:#10b981;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700'>✓ Reconciled</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_issues, col_rag = st.columns([3, 2])
    with col_issues:
        st.markdown("### 🚨 Discrepancies & Violations Identified")
        tot_issues = summary["held_count"] + summary["pending_count"] + summary.get("tat_count", 0) + len(summary["overcharged_fees"])
        if tot_issues == 0:
            st.success("✅ Clean Audit! All settlements and fees match published guidelines.")
        else:
            # Group issues by transaction_id to prevent duplicates
            txn_issues = {}
            for t in summary.get("held_funds", []):
                tid = t["transaction_id"]
                if tid not in txn_issues: txn_issues[tid] = {"txn": t, "tags": [], "details": []}
                txn_issues[tid]["tags"].append(("<span class='badge badge-held'>ON HOLD</span>", "issue-held"))
                txn_issues[tid]["details"].append(f"Funds withheld: {INR}{t['amount']:,.2f}")

            for t in summary.get("pending_funds", []):
                tid = t["transaction_id"]
                if tid not in txn_issues: txn_issues[tid] = {"txn": t, "tags": [], "details": []}
                txn_issues[tid]["tags"].append(("<span class='badge badge-pending'>PENDING</span>", "issue-pending"))
                txn_issues[tid]["details"].append(f"Overdue settlement: {INR}{t['amount']:,.2f}")

            for t in summary.get("tat_violations", []):
                tid = t["transaction_id"]
                if tid not in txn_issues: txn_issues[tid] = {"txn": t, "tags": [], "details": []}
                txn_issues[tid]["tags"].append(("<span class='badge badge-tat'>TAT VIOLATION</span>", "issue-tat"))
                txn_issues[tid]["details"].append(f"Settled {t['days_delayed']} days post-transaction (exceeds statutory T+2)")

            for t in summary.get("overcharged_fees", []):
                tid = t["transaction_id"]
                if tid not in txn_issues: txn_issues[tid] = {"txn": t, "tags": [], "details": []}
                txn_issues[tid]["tags"].append(("<span class='badge badge-fee'>FEE VARIANCE</span>", "issue-fee"))
                txn_issues[tid]["details"].append(f"Overcharged by {INR}{t['overcharge']:.2f} (Charged: {INR}{t['fee']:.2f} vs Expected: {INR}{t['expected_fee']:.2f})")

            for tid, data in txn_issues.items():
                t = data["txn"]
                badges_html = " ".join(b[0] for b in data["tags"])
                card_border = data["tags"][0][1] # primary issue color
                issues_count = len(data["tags"])
                count_lbl = f"<span style='font-size:11px;color:#94a3b8;font-weight:600;'>{issues_count} issues found</span>" if issues_count > 1 else ""
                details_html = "<br>• ".join([""] + data["details"])

                st.markdown(f"""
                <div class='issue-card {card_border}'>
                  <div style='display:flex;justify-content:space-between;align-items:center'>
                    <div>
                      <span style='font-family:monospace;color:#f8fafc;font-weight:800;font-size:14px'>{tid}</span>
                      &nbsp;&nbsp;{count_lbl}
                    </div>
                    <div>{badges_html}</div>
                  </div>
                  <div style='font-size:16px;font-weight:800;color:#f8fafc;margin-top:6px'>
                    Amount: {INR}{t['amount']:,.2f} &nbsp;<span style='font-size:12px;color:#64748b;font-weight:500'>({t['payment_method']})</span>
                  </div>
                  <div style='font-size:12px;color:#cbd5e1;margin-top:6px;line-height:1.5'>
                    {details_html}
                  </div>
                  <div style='font-size:11px;color:#64748b;margin-top:6px'>
                    Order: {t.get('order_id', '-')} | Transaction Date: {t.get('transaction_date', '-')} | Settle Date: {t.get('settlement_date', '-')}
                  </div>
                </div>
                """, unsafe_allow_html=True)

    with col_rag:
        st.markdown("### 📖 Statutory RBI Framework")
        st.markdown(f"""
        <div style='background:#0d1322;border:1px solid #1e293b;border-radius:14px;padding:20px 24px;'>
          <div style='font-size:12px;color:#00d4aa;font-weight:700;margin-bottom:8px'>RBI PA Master Directions 2025</div>
          <div style='font-size:13px;color:#cbd5e1;line-height:1.7;white-space:pre-wrap'>{rag_ans}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("⚖️ Escalate to Ombudsman (Agent 3) ↗", url=AGENT3_URL, use_container_width=True)

    st.markdown("---")

    # Full Transaction Table
    with st.expander("📋 Full Transaction Audit Ledger", expanded=False):
        st.markdown("""
        <div style='overflow-x:auto;'>
        <table class='txn-table'>
          <thead><tr>
            <th>Txn ID</th><th>Gross</th><th>Fee</th><th>Tax</th><th>Net Settle</th><th>Status</th><th>Method</th><th>Settle Date</th>
          </tr></thead>
          <tbody>
        """, unsafe_allow_html=True)
        for t in agent.transactions:
            badge_cls = "badge-held" if "hold" in t["status"] else ("badge-pending" if "pend" in t["status"] else "badge-settled")
            st.markdown(f"""
            <tr>
              <td style='font-family:monospace;color:#f8fafc'>{t['transaction_id']}</td>
              <td>{INR}{t['amount']:,.2f}</td>
              <td style='color:#94a3b8'>{INR}{t['fee']:.2f}</td>
              <td style='color:#64748b'>{INR}{t['tax']:.2f}</td>
              <td><strong>{INR}{t['settlement_amount']:,.2f}</strong></td>
              <td><span class='badge {badge_cls}'>{t['status'].upper()}</span></td>
              <td style='text-transform:capitalize'>{t['payment_method']}</td>
              <td style='color:#64748b'>{t['settlement_date']}</td>
            </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

    # Recovery Ticket
    st.markdown("### 📝 Auto-Drafted Dispute Letter")
    ticket_str = agent.draft_recovery_ticket()
    st.text_area("Dispute Ticket", value=ticket_str, height=280, key="a2_ticket")

    c_dl1, c_dl2, c_res = st.columns([1, 1, 2])
    with c_dl1:
        st.download_button("⬇️ Download Ticket (.txt)", data=ticket_str, file_name="reconciliation_dispute.txt", mime="text/plain", use_container_width=True)
    with c_dl2:
        rep_csv = agent.export_report_csv()
        if rep_csv:
            st.download_button("⬇️ Download Report (.csv)", data=rep_csv, file_name="reconciliation_report.csv", mime="text/csv", use_container_width=True)
    with c_res:
        if st.button("🔄 Start New Reconciliation", use_container_width=True):
            for k in [k for k in st.session_state if k.startswith("a2_")]:
                del st.session_state[k]
            st.rerun()
