import csv
import importlib
import io
import os
import sys

import pandas as pd
import streamlit as st

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(AGENT_DIR)
for path in (AGENT_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from src import config
from src.activity_history import record_activity
from src.policy_evidence import search_local_policy
from src.shared_state import write_reconciliation_state
from reconciliation_agent import FEE_DEFAULT, FEE_RATES, ReconciliationAgent
import src.ui as _ui

# Refresh shared presentation helpers when an existing Streamlit session reruns.
importlib.reload(_ui)
from src.ui import activity_history, app_urls, badge, esc, footer, hero, inject_theme, metric, nav, note, panel, require_auth, same_tab_link, section_title, steps


st.set_page_config(page_title="MerchantOS · Settlement Reconciliation", page_icon="M", layout="wide", initial_sidebar_state="expanded")
inject_theme()
require_auth("agent2")
nav("agent2")
urls = app_urls()


def clear_analysis() -> None:
    for key in list(st.session_state):
        if key.startswith("a2_"):
            del st.session_state[key]


def fetch_policy_evidence(use_live_retrieval: bool = False) -> str:
    query = f"What do {config.PA_DIRECTIONS_REFERENCE} {config.PA_DISPUTE_REFERENCE} and {config.PA_SETTLEMENT_REFERENCE} require for merchant disputes and transparent settlement timelines?"
    evidence = search_local_policy(query).get("answer", "")
    if use_live_retrieval:
        try:
            from src.llm_agent import get_answer as rag_get_answer

            result = rag_get_answer(query)
            evidence = result.get("answer", "").strip() or evidence
        except Exception:
            pass
    return evidence


def run_analysis(content: str, source: str, publish_to_dashboard: bool = True) -> bool:
    agent = ReconciliationAgent()
    parsed = agent.parse_csv(content)
    if parsed["errors"]:
        st.error("\n".join(parsed["errors"]))
        return False
    for warning in parsed["warnings"]:
        st.warning(warning)
    if not parsed["parsed"]:
        st.warning("No valid transactions were found in this file.")
        return False

    summary = agent.analyze()
    evidence = fetch_policy_evidence(use_live_retrieval=config.AUTO_FETCH_POLICY_EVIDENCE)

    st.session_state.a2_agent = agent
    st.session_state.a2_summary = summary
    st.session_state.a2_evidence = evidence
    st.session_state.a2_done = True
    record_activity(
        st.session_state.merchantos_user.get("id", "local"),
        "agent2",
        "reconciliation_completed",
        f"Reconciled {source}",
        (
            f'{summary["total_transactions"]} transactions · '
            f'{summary["held_count"] + summary["pending_count"]} held or pending · '
            f'{config.CURRENCY_SYMBOL}{summary["recovery_amount"]:,.2f} to review'
        ),
        {
            "source": source,
            "total_transactions": summary["total_transactions"],
            "recovery_amount": summary["recovery_amount"],
        },
    )
    if publish_to_dashboard:
        try:
            write_reconciliation_state(summary, source)
        except OSError as exc:
            st.warning(f"Reconciliation completed, but the command center could not be updated: {exc}")
    return True


hero("RECOVERY / SETTLEMENTS", "Every payout, accounted for.", "Inspect a settlement report, review exceptions, and prepare a recovery request.")

if not st.session_state.get("a2_done"):
    steps(["Add your data", "Review exceptions", "Export your report"], 0)
    main, supporting = st.columns([1.8, 1], gap="large")
    with main:
        with panel("Start a reconciliation", "Choose how you want to add your transactions."):
            upload_tab, manual_tab, sample_tab = st.tabs(["Upload report", "Single transaction", "Try a sample"])
            with upload_tab:
                st.caption(f"{config.AGGREGATOR_SHORT} settlement export · CSV")
                uploaded = st.file_uploader("Choose a settlement report", type=["csv"])
                if uploaded:
                    raw = uploaded.getvalue()
                    try:
                        content = raw.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        content = raw.decode("latin-1")
                    st.caption(f"{uploaded.name} · {max(len(content.splitlines()) - 1, 0)} rows")
                    with st.spinner("Analyzing your report…"):
                        if run_analysis(content, uploaded.name):
                            st.rerun()
                with st.expander("Required columns"):
                    st.code("transaction_id, amount, fee, tax, settlement_amount, status, payment_method", language=None)
                    st.caption("Add transaction_date and settlement_date to check turnaround times.")
            with manual_tab:
                with st.form("a2_manual"):
                    one, two = st.columns(2)
                    txn_id = one.text_input("Transaction ID", placeholder="pay_ABC123")
                    amount = two.number_input(f"Gross amount ({config.CURRENCY_SYMBOL})", min_value=0.0, value=None, step=config.MANUAL_AMOUNT_STEP)
                    method = one.selectbox("Payment method", ["UPI", "Card", "NetBanking", "Wallet", "EMI", "PayLater"])
                    status = two.selectbox("Status", ["on_hold", "pending", "settled"])
                    txn_date = one.text_input("Transaction date", placeholder="YYYY-MM-DD")
                    settle_date = two.text_input("Settlement date", placeholder="YYYY-MM-DD")
                    st.caption("This quick check uses the configured fee schedule. Upload a CSV to audit actual charged fees.")
                    submitted = st.form_submit_button("Check transaction →", type="primary", width="stretch")
                if submitted and amount is not None:
                    rate, gst = FEE_RATES.get(method.lower(), FEE_DEFAULT)
                    fee = round(amount * rate / 100, 2)
                    tax = round(fee * gst / 100, 2)
                    settled = round(amount - fee - tax, 2) if status == "settled" else 0
                    buffer = io.StringIO()
                    writer = csv.writer(buffer)
                    writer.writerow(["settlement_date", "transaction_id", "amount", "fee", "tax", "settlement_amount", "status", "payment_method", "transaction_date"])
                    writer.writerow([settle_date, txn_id or "TXN_MANUAL", amount, fee, tax, settled, status, method.lower(), txn_date])
                    with st.spinner("Checking transaction…"):
                        if run_analysis(buffer.getvalue(), "Manual transaction"):
                            st.rerun()
            with sample_tab:
                sample_path = config.SAMPLE_SETTLEMENT_PATH
                if os.path.exists(sample_path):
                    with open(sample_path, encoding="utf-8") as f:
                        sample_content = f.read()
                    st.markdown(f"**{len(pd.read_csv(io.StringIO(sample_content)))} transactions. A useful place to start.**")
                    st.caption("Includes settled, pending, and held transactions. This sample has no transaction dates, so turnaround checks are unavailable.")
                    st.dataframe(pd.read_csv(io.StringIO(sample_content)).head(config.SAMPLE_PREVIEW_ROWS), width="stretch", hide_index=True)
                    if st.button("Reconcile sample →", type="primary", width="stretch"):
                        with st.spinner("Analyzing sample…"):
                            if run_analysis(sample_content, "Bundled sample", publish_to_dashboard=False):
                                st.rerun()
                    st.download_button("Download sample CSV", sample_content, "sample_settlement.csv", "text/csv")
                else:
                    st.info("The sample report is unavailable. Upload your own CSV to continue.")
    with supporting:
        note("Follow the money, row by row.", "Your audit separates held and pending amounts, compares charged fees with configured rates, and checks settlement dates when available.")
        section_title("What you'll receive")
        for number, title, body in [
            ("01", "An exception ledger", "Related issues grouped under one transaction."),
            ("02", "A financial summary", "Gross, settled, held, fees, and any remaining variance."),
            ("03", "A recovery request", "A downloadable audit and a support letter you can edit."),
        ]:
            st.markdown(f'<div class="case-line"><span class="case-number">{number}</span><div><strong>{title}</strong><p>{body}</p></div></div>', unsafe_allow_html=True)
else:
    agent = st.session_state.a2_agent
    summary = st.session_state.a2_summary
    steps(["Add your data", "Review exceptions", "Export your report"], 1)
    columns = st.columns(4)
    for column, label, value, sub in [
        (columns[0], "Gross processed", f'{config.CURRENCY_SYMBOL}{summary["total_gross"]:,.2f}', f'{summary["total_transactions"]} transactions'),
        (columns[1], "Settled to bank", f'{config.CURRENCY_SYMBOL}{summary["total_settled"]:,.2f}', f'{summary["settled_count"]} settled'),
        (columns[2], "Held & pending", f'{config.CURRENCY_SYMBOL}{summary["recovery_amount"]:,.2f}', f'{summary["held_count"] + summary["pending_count"]} to follow up'),
        (columns[3], "Fee difference", f'{config.CURRENCY_SYMBOL}{summary["total_overcharge"]:,.2f}', "Charged minus expected"),
    ]:
        with column:
            metric(label, value, sub)

    issues = {}
    for transactions, label, detail in [
        (summary["held_funds"], "On hold", lambda t: f'{config.CURRENCY_SYMBOL}{t["amount"]:,.2f} withheld'),
        (summary["pending_funds"], "Pending", lambda t: f'{config.CURRENCY_SYMBOL}{t["amount"]:,.2f} pending'),
        (summary["tat_violations"], "Delay", lambda t: f'{t["days_delayed"]} {config.SETTLEMENT_DAY_MODE} days to settlement'),
        (summary["overcharged_fees"], "Fee difference", lambda t: f'{config.CURRENCY_SYMBOL}{t["overcharge"]:,.2f} above expected fee/tax'),
    ]:
        for txn in transactions:
            entry = issues.setdefault(txn["transaction_id"], {"txn": txn, "labels": [], "details": []})
            entry["labels"].append(label)
            entry["details"].append(detail(txn))

    exceptions, ledger, report, context = st.tabs(["Exceptions", "All transactions", "Report & request", "Policy context"])
    with exceptions:
        section_title(f"{len(issues)} transactions to review", "Select a category to narrow the list")
        category = st.selectbox("Exception category", ["All exceptions", "On hold", "Pending", "Delay", "Fee difference"], label_visibility="collapsed")
        rows = []
        for tid, item in issues.items():
            if category != "All exceptions" and category not in item["labels"]:
                continue
            tags = " ".join(badge(label, "danger" if label == "On hold" else "warn") for label in item["labels"])
            rows.append(f'<tr><td><span class="mono">{esc(tid)}</span><br><small>{esc(item["txn"]["payment_method"])}</small></td><td>{tags}</td><td class="money">{config.CURRENCY_SYMBOL}{item["txn"]["amount"]:,.2f}</td><td>{esc(" · ".join(item["details"]))}</td></tr>')
        if rows:
            st.markdown('<div class="table-scroll"><table class="data-table"><thead><tr><th>Transaction</th><th>Exception</th><th class="money">Gross</th><th>Review notes</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>', unsafe_allow_html=True)
        else:
            st.success("No exceptions in this category.")
        if not any(t.get("_txn_date") and t.get("_set_date") for t in agent.transactions):
            st.caption("Turnaround checks unavailable: both transaction and settlement dates are needed.")
    with ledger:
        search = st.text_input("Search ledger", placeholder="Transaction or order ID")
        transactions = [t for t in agent.transactions if search.lower() in (t["transaction_id"] + " " + t["order_id"]).lower()]
        st.dataframe(pd.DataFrame([{k: v for k, v in t.items() if not k.startswith("_")} for t in transactions]), width="stretch", hide_index=True)
    with report:
        gross = summary["total_gross"]
        settled = summary["total_settled"]
        held = summary["recovery_amount_net"]
        costs = round(summary["total_fee_charged"] + summary["total_tax_charged"], 2)
        variance = round(gross - settled - held - costs, 2)
        parts = [("Gross", gross), ("Settled", settled), ("Held / pending net", held), ("Fees / tax", costs), ("Residual variance", variance)]
        equation = "".join(f'<div>{label}<strong>{config.CURRENCY_SYMBOL}{value:,.2f}</strong></div>' for label, value in parts)
        st.markdown(f'<div class="audit-equation">{equation}</div>', unsafe_allow_html=True)
        st.caption("Residual variance is gross less settlements, held/pending net amounts, and all charged fees/tax. Review non-zero balances against the source report.")
        with panel("Recovery request", "Review the figures and replace the placeholders. Your edits are included in the download.", key="doc-preview"):
            edited = st.text_area("Dispute letter", value=agent.draft_recovery_ticket(), height=380, key="a2_ticket_edit", label_visibility="collapsed")
            a, b = st.columns(2)
            a.download_button("Download request", edited, "reconciliation_dispute.txt", "text/plain", type="primary", width="stretch")
            b.download_button("Export audit CSV", agent.export_report_csv(), "reconciliation_report.csv", "text/csv", width="stretch")
    with context:
        with panel("Supporting policy context"):
            st.markdown(st.session_state.a2_evidence)
            if st.button("Refresh policy evidence"):
                with st.spinner("Searching the policy library…"):
                    st.session_state.a2_evidence = fetch_policy_evidence(use_live_retrieval=True)
                st.rerun()
            same_tab_link("Prepare a formal escalation →", urls["agent3"])
    if st.button("Start another reconciliation"):
        clear_analysis()
        st.rerun()

activity_history("agent2")
footer()
