"""Overview: a working sample ledger and clear entry points into recovery tasks."""
import importlib
from pathlib import Path

import streamlit as st

from Agent2.reconciliation_agent import ReconciliationAgent
import src.ui as _ui

# Streamlit retains imported modules when file watching is disabled.
importlib.reload(_ui)
from src.ui import app_urls, badge, esc, footer, hero, icon, inject_theme, metric, nav, panel, section_title

st.set_page_config(page_title="Overview · MerchantOS", page_icon="M", layout="wide", initial_sidebar_state="expanded")
inject_theme()
nav("home")
urls = app_urls()
hero("THE MERCHANT'S DESK", "Your money. A clearer picture.", "Track settlement exceptions and take the next step toward resolving them.")

toolbar, action = st.columns([3, 1])
with toolbar:
    st.caption("SAMPLE WORKSPACE  /  Figures calculated from the included settlement report")
with action:
    st.link_button("Reconcile a report →", urls["agent2"], type="primary", width="stretch")

agent = ReconciliationAgent()
sample = Path(__file__).parent / "Agent2" / "sample_data" / "sample_settlement.csv"
if sample.exists():
    agent.parse_csv(sample.read_text(encoding="utf-8"))
else:
    agent.parse_csv("transaction_id,amount,fee,tax,settlement_amount,status,payment_method\n")
summary = agent.analyze()
held = sum(t["amount"] for t in summary["held_funds"])
pending = sum(t["amount"] for t in summary["pending_funds"])
received = summary["total_settled"]
gross = summary["total_gross"]
# The remainder completes the gross ledger without double-counting fees on unpaid rows.
deducted_from_paid = gross - received - held - pending

left, right = st.columns([1.05, 1], gap="large")
with left:
    st.markdown(f'<div class="overview-total"><div class="label">Awaiting settlement</div><div class="balance-art" aria-hidden="true"><i></i><i></i><i></i><i></i></div><div class="amount">{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{summary["recovery_amount"]:,.0f}<span>.00</span></div><p>{summary["held_count"] + summary["pending_count"]} transactions to follow up · sample report</p><div class="balance-meta"><div><strong>{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{held:,.0f}</strong><small>On hold</small></div><div><strong>{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{pending:,.0f}</strong><small>Pending</small></div><div><strong>{summary["settled_count"]} / {summary["total_transactions"]}</strong><small>Transactions settled</small></div></div></div>', unsafe_allow_html=True)
with right:
    with panel("Where the money stands", f"Gross transaction value · {os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{gross:,.2f}"):
        parts = [("Settled", received, "#315c3b"), ("On hold", held, "#a0b487"), ("Pending", pending, "#dfe89b"), ("Deductions on paid rows", deducted_from_paid, "#e8ece1")]
        bars = "".join(f'<div style="width:{value / gross * 100:.4f}%;background:{color}" title="{esc(label)}: {os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{value:,.2f}"></div>' for label, value, color in parts)
        legend = "".join(f'<div><i style="--swatch:{color}"></i><span>{label}<strong>{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{value:,.2f}</strong></span></div>' for label, value, color in parts)
        st.markdown(f'<div class="composition"><div class="composition-bar" role="img" aria-label="Breakdown of gross transaction value">{bars}</div><div class="composition-legend">{legend}</div></div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3, gap="large")
with c1:
    metric("Gross processed", f"{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{gross:,.2f}", f'{summary["total_transactions"]} transactions in this report')
with c2:
    metric("Settled to bank", f"{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{received:,.2f}", f'{summary["settled_count"]} marked as settled')
with c3:
    metric("Fee difference", f'{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{summary["total_overcharge"]:,.2f}', "Charged fees minus configured expected fees")

main, aside = st.columns([1.8, 1], gap="large")
with main:
    section_title("Settlement activity")
    filter_col, search_col = st.columns([1, 1.5])
    selected_status = filter_col.selectbox("Show status", ["All transactions", "Needs attention", "Settled"], label_visibility="collapsed")
    search = search_col.text_input("Find transaction", placeholder="Search transaction or order ID", label_visibility="collapsed")
    txns = agent.transactions
    if selected_status == "Needs attention":
        txns = [t for t in txns if t["status"] != "settled"]
    elif selected_status == "Settled":
        txns = [t for t in txns if t["status"] == "settled"]
    if search:
        txns = [t for t in txns if search.lower() in (t["transaction_id"] + " " + t["order_id"]).lower()]
    rows = []
    for t in txns[:8]:
        tone = {"settled": "good", "on_hold": "danger", "pending": "warn"}.get(t["status"], "info")
        rows.append(f'<tr><td><span class="mono">{esc(t["transaction_id"])}</span></td><td>{badge(t["status"].replace("_", " ").title(), tone)}</td><td class="money">{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{t["amount"]:,.2f}</td><td>{esc(t["payment_method"])}</td></tr>')
    if rows:
        st.markdown('<div class="table-scroll"><table class="data-table"><thead><tr><th>Transaction</th><th>Status</th><th class="money">Gross amount</th><th>Method</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>', unsafe_allow_html=True)
        st.caption(f"Showing {min(8, len(txns))} of {len(txns)} matching transactions")
    else:
        st.info("No transactions match this search.")
    st.download_button("Export sample audit", agent.export_report_csv(), "sample_audit.csv", "text/csv")
with aside:
    section_title("Take the next step")
    links = [
        ("agent1", "Understand a fund hold", "A guided check of your account restriction."),
        ("agent2", "Review your settlements", "Upload a report and inspect the exceptions."),
        ("agent3", "Prepare an escalation", "Assemble your evidence and correspondence."),
    ]
    for key, title, desc in links:
        st.markdown(f'<a class="action-link" href="{esc(urls[key])}" target="_self"><span>{icon(key)}</span><div><strong>{title}</strong><small>{desc}</small></div>{icon("arrow")}</a>', unsafe_allow_html=True)
    section_title("Volume by payment method")
    for method, stats in summary["method_stats"].items():
        st.markdown(f'<div class="method-row"><span>{esc(method.title())}</span><div class="method-track"><i style="width:{stats["gross"] / gross * 100:.2f}%"></i></div><strong>{os.getenv('MERCHANT_CURRENCY_SYMBOL', '₹')}{stats["gross"]:,.0f}</strong></div>', unsafe_allow_html=True)

st.markdown(f'<div class="cta-band"><div><h3>Give every exception a next step.</h3><p>Start with your own report to create a settlement audit and a dispute letter.</p></div><a href="{esc(urls["agent2"])}" target="_self">Start a reconciliation {icon("arrow")}</a></div>', unsafe_allow_html=True)
footer()
