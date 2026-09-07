"""Overview: a working sample ledger and clear entry points into recovery tasks."""
import importlib
import os
from pathlib import Path

import streamlit as st

from Agent2.reconciliation_agent import ReconciliationAgent
import src.ui as _ui

# Streamlit retains imported modules when file watching is disabled.
importlib.reload(_ui)
from src.ui import app_urls, badge, esc, footer, hero, icon, inject_theme, metric, nav, panel, section_title

CURRENCY_SYM = os.getenv("MERCHANT_CURRENCY_SYMBOL", "₹")

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
    st.markdown(f'<div class="overview-total"><div class="label">Awaiting settlement</div><div class="balance-art" aria-hidden="true"><i></i><i></i><i></i><i></i></div><div class="amount">{CURRENCY_SYM}{summary["recovery_amount"]:,.0f}<span>.00</span></div><p>{summary["held_count"] + summary["pending_count"]} transactions to follow up · sample report</p><div class="balance-meta"><div><strong>{CURRENCY_SYM}{held:,.0f}</strong><small>On hold</small></div><div><strong>{CURRENCY_SYM}{pending:,.0f}</strong><small>Pending</small></div><div><strong>{summary["settled_count"]} / {summary["total_transactions"]}</strong><small>Transactions settled</small></div></div></div>', unsafe_allow_html=True)
with right:
    with panel("Where the money stands", f"Gross transaction value · {CURRENCY_SYM}{gross:,.2f}"):
        parts = [("Settled", received, "#315c3b"), ("On hold", held, "#a0b487"), ("Pending", pending, "#dfe89b"), ("Deductions on paid rows", deducted_from_paid, "#e8ece1")]
        bars = "".join(f'<div style="width:{value / gross * 100:.4f}%;background:{color}" title="{esc(label)}: {CURRENCY_SYM}{value:,.2f}"></div>' for label, value, color in parts)
        legend = "".join(f'<div><i style="--swatch:{color}"></i><span>{label}<strong>{CURRENCY_SYM}{value:,.2f}</strong></span></div>' for label, value, color in parts)
        st.markdown(f'<div class="composition"><div class="composition-bar" role="img" aria-label="Breakdown of gross transaction value">{bars}</div><div class="composition-legend">{legend}</div></div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3, gap="large")
with c1:
    metric("Gross processed", f"{CURRENCY_SYM}{gross:,.2f}", f'{summary["total_transactions"]} transactions in this report')
with c2:
    metric("Settled to bank", f"{CURRENCY_SYM}{received:,.2f}", f'{summary["settled_count"]} marked as settled')
with c3:
    metric("Fee difference", f'{CURRENCY_SYM}{summary["total_overcharge"]:,.2f}', "Charged fees minus configured expected fees")

section_title("Attention ledger", "Transactions flagged by the sample reconciliation")

tbl, aside = st.columns([1.5, 1], gap="large")
with tbl:
    rows = []
    for t in (summary["held_funds"] + summary["pending_funds"])[:8]:
        tone = "caution" if t["status"] == "pending" else "critical"
        rows.append(f'<tr><td><span class="mono">{esc(t["transaction_id"])}</span></td><td>{badge(t["status"].replace("_", " ").title(), tone)}</td><td class="money">{CURRENCY_SYM}{t["amount"]:,.2f}</td><td>{esc(t["payment_method"])}</td></tr>')
    table_body = "".join(rows) or '<tr><td colspan="4">No pending settlement rows found.</td></tr>'
    st.markdown(
        f'<div class="table-wrap"><table class="data-table"><thead><tr><th>Transaction</th><th>Status</th><th class="money">Amount</th><th>Method</th></tr></thead><tbody>{table_body}</tbody></table></div>',
        unsafe_allow_html=True,
    )

with aside:
    with panel("Methods in this file", "Volume breakdown across recorded methods"):
        for method, stats in summary.get("by_method", {}).items():
            st.markdown(f'<div class="method-row"><span>{esc(method.title())}</span><div class="method-track"><i style="width:{stats["gross"] / gross * 100:.2f}%"></i></div><strong>{CURRENCY_SYM}{stats["gross"]:,.0f}</strong></div>', unsafe_allow_html=True)

section_title("Recovery playbooks", "Choose where you need to take action first")

cards = [
    ("kyc", "KYC & fund holds", "Step through the decision tree to determine why funds are restricted and assemble supporting documentation.", urls["agent1"], "Start diagnosis →"),
    ("recon", "Settlement reconciliation", "Upload a CSV export to check fees against published schedules and uncover delayed settlements.", urls["agent2"], "Reconcile a file →"),
    ("legal", "Formal escalation", "Build formal correspondence for grievances, legal notices, or an ombudsman filing from your case details.", urls["agent3"], "Assemble letters →"),
]

cc1, cc2, cc3 = st.columns(3, gap="large")
for col, (kind, title, body, target_url, action_label) in zip((cc1, cc2, cc3), cards):
    with col:
        with panel(title, ""):
            st.markdown(f'<div class="card-lead">{icon(kind)}</div>', unsafe_allow_html=True)
            st.markdown(f'<p class="card-copy">{esc(body)}</p>', unsafe_allow_html=True)
            st.link_button(action_label, target_url, width="stretch")

footer()
