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
import src.activity_history as _activity_history
import src.policy_evidence as _policy_evidence

# Refresh configuration only when an existing Streamlit process still has the
# older module shape. Avoid an unconditional reload because deployments and
# tests may intentionally override configuration values in memory.
if not hasattr(config, "AGGREGATOR_GRIEVANCE_URL"):
    importlib.reload(config)

# Refresh shared helpers when Streamlit reruns after a local code update.
importlib.reload(_activity_history)
importlib.reload(_policy_evidence)
from src.activity_history import read_activity, read_activity_history, record_activity, update_activity_metadata
from src.policy_evidence import get_policy_evidence, search_local_policy
from src.shared_state import write_reconciliation_state
import reconciliation_agent as _reconciliation_agent

importlib.reload(_reconciliation_agent)
from reconciliation_agent import FEE_DEFAULT, FEE_RATES, ReconciliationAgent
import src.ui as _ui

# Refresh shared presentation helpers when an existing Streamlit session reruns.
importlib.reload(_ui)
from src.ui import activity_history, app_urls, badge, esc, footer, inject_theme, metric, nav, note, panel, require_auth, same_tab_link, section_title, steps


st.set_page_config(page_title="MerchantOS · Settlement Reconciliation", page_icon="M", layout="wide", initial_sidebar_state="expanded")
inject_theme()
require_auth("agent2")
nav("agent2")
urls = app_urls()


def clear_analysis() -> None:
    for key in list(st.session_state):
        if key.startswith("a2_"):
            del st.session_state[key]


def render_reconciliation_header() -> None:
    """Render the dedicated intake/completion identity for Agent 2."""
    completed = bool(st.session_state.get("a2_done"))
    title = "Your settlement audit is ready." if completed else "See exactly where every rupee went."
    description = (
        "Review exceptions, reconcile the balance, and export a support-ready recovery package."
        if completed
        else "Bring a settlement report or check one transaction. MerchantOS traces held funds, timing, fees, tax, and residual variance."
    )
    mode = "Audit complete" if completed else "Reconciliation workspace"
    st.markdown(
        f'<header class="a2-hero {"completed" if completed else "active"}">'
        '<div class="a2-hero-copy">'
        f'<div class="eyebrow">{esc(config.AGGREGATOR_SHORT)} / SETTLEMENT INTELLIGENCE</div>'
        f'<h1>{esc(title)}</h1><p>{esc(description)}</p>'
        '<div class="a2-hero-chips">'
        '<span><i></i>Exception ledger</span><span><i></i>Fee and tax checks</span>'
        '<span><i></i>Exportable recovery brief</span></div></div>'
        '<div class="a2-flow-map" aria-hidden="true">'
        '<span class="a2-flow-line line-one"></span><span class="a2-flow-line line-two"></span>'
        '<div class="a2-flow-node node-gross"><small>01</small><b>Gross</b></div>'
        '<div class="a2-flow-node node-audit"><small>02</small><b>Audit</b></div>'
        '<div class="a2-flow-node node-bank"><small>03</small><b>Bank</b></div>'
        '<span class="a2-flow-pulse pulse-one"></span><span class="a2-flow-pulse pulse-two"></span>'
        f'<div class="a2-flow-label"><i></i>{esc(mode)}</div></div></header>',
        unsafe_allow_html=True,
    )


def policy_query(summary: dict) -> str:
    """Build one stable, case-aware query for initial retrieval and refreshes."""
    signals = []
    if summary.get("held_count"):
        signals.append("funds placed on hold")
    if summary.get("pending_count"):
        signals.append("pending merchant settlements")
    if summary.get("tat_count"):
        signals.append("settlement timing exceptions")
    if summary.get("total_overcharge", 0) > 0:
        signals.append("fee or tax differences")
    case_signals = ", ".join(signals) or "merchant settlement reconciliation"
    return (
        f"For {case_signals}, what do {config.PA_DIRECTIONS_REFERENCE}, "
        f"{config.PA_DISPUTE_REFERENCE}, and {config.PA_SETTLEMENT_REFERENCE} say about "
        "merchant grievance routes, reconciliation, settlement schedules, pricing, and remediation?"
    )


def fetch_policy_evidence(summary: dict, reconnect_index: bool = False) -> dict:
    """Return stable extractive evidence plus semantic relevance metadata."""
    result = get_policy_evidence(
        policy_query(summary),
        semantic=True,
        reconnect_index=reconnect_index,
    )
    # A semantic result describes relevance, while the visible source cards must
    # always come from the current local policy files.
    if not result.get("extractive_chunks"):
        local = search_local_policy(policy_query(summary))
        result["extractive_chunks"] = list(local.get("chunks") or [])
        result["answer"] = local.get("answer", result.get("answer", ""))
        result["source"] = local.get("source", result.get("source", "Local policy library"))
    settlement_terms = (
        "settlement", "reconciliation", "pricing", "grievance", "dispute",
        "refund", "held fund", "funds on hold", "merchant agreement",
    )
    relevant_chunks = [
        chunk for chunk in result.get("extractive_chunks", [])
        if any(
            term in f'{chunk.get("section", "")} {chunk.get("text", "")}'.lower()
            for term in settlement_terms
        )
    ]
    if relevant_chunks:
        result["extractive_chunks"] = relevant_chunks
        result["source"] = ", ".join(
            dict.fromkeys(str(chunk.get("source", "Local policy library")) for chunk in relevant_chunks)
        )
    return result


def run_analysis(
    content: str,
    source: str,
    publish_to_dashboard: bool = True,
    record_history: bool = True,
) -> bool:
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
    evidence = fetch_policy_evidence(summary)
    transaction_label = "transaction" if summary["total_transactions"] == 1 else "transactions"

    st.session_state.a2_agent = agent
    st.session_state.a2_summary = summary
    st.session_state.a2_evidence = evidence.get("answer", "")
    st.session_state.a2_policy_meta = evidence
    st.session_state.a2_source = source
    st.session_state.a2_input_csv = content
    st.session_state.a2_done = True
    if record_history:
        record_activity(
            st.session_state.merchantos_user.get("id", "local"),
            "agent2",
            "reconciliation_completed",
            f"Reconciled {source}",
            (
                f'{summary["total_transactions"]} {transaction_label} · '
                f'{summary["held_count"] + summary["pending_count"]} held or pending · '
                f'{config.CURRENCY_SYMBOL}{summary.get("amount_to_review", summary["recovery_amount"]):,.2f} to review'
            ),
            {
                "source": source,
                "total_transactions": summary["total_transactions"],
                "recovery_amount": summary.get("amount_to_review", summary["recovery_amount"]),
                "input_csv": content,
            },
        )
    if publish_to_dashboard:
        try:
            write_reconciliation_state(summary, source)
        except OSError as exc:
            st.warning(f"Reconciliation completed, but the command center could not be updated: {exc}")
    return True


def restore_activity_route() -> str | None:
    """Rebuild an owned reconciliation selected from Agent 2 history."""
    raw_activity_id = st.query_params.get("activity")
    loaded_activity_id = st.session_state.get("a2_loaded_activity_id")

    def reject_route(message: str) -> str:
        st.query_params.pop("activity", None)
        clear_analysis()
        return message

    if not raw_activity_id:
        if loaded_activity_id is not None:
            clear_analysis()
        return None
    try:
        activity_id = int(raw_activity_id)
        if activity_id < 1:
            raise ValueError
    except (TypeError, ValueError):
        return reject_route("This saved-reconciliation link is invalid.")
    if loaded_activity_id == activity_id:
        return None

    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    entry = read_activity(user_id, activity_id, section="agent2")
    metadata = entry.get("metadata", {}) if entry else {}
    content = metadata.get("input_csv")
    source = metadata.get("source")
    if not isinstance(content, str) or not content.strip() or not isinstance(source, str):
        return reject_route("This older reconciliation does not contain the report data required to reopen it.")

    clear_analysis()
    if not run_analysis(content, source, publish_to_dashboard=False, record_history=False):
        return reject_route("This saved reconciliation cannot be reopened with the current audit rules.")
    st.session_state.a2_loaded_activity_id = activity_id
    return None


def render_transaction_table(transactions: list[dict]) -> None:
    """Render the ledger as a readable responsive table instead of a raw dataframe."""
    rows = []
    for txn in transactions:
        status = str(txn.get("status", "unknown")).replace("_", " ").title()
        tone = "danger" if txn.get("status") in {"on_hold", "hold"} else "warn" if txn.get("status") in {"pending", "processing"} else "good"
        dates = f'{esc(str(txn.get("transaction_date", "-")))}<span>→</span>{esc(str(txn.get("settlement_date", "-")))}'
        rows.append(
            '<tr>'
            f'<td><span class="mono">{esc(str(txn.get("transaction_id", "-")))}</span>'
            f'<small>Order {esc(str(txn.get("order_id", "-")))}</small></td>'
            f'<td>{badge(status, tone)}</td>'
            f'<td><strong>{config.CURRENCY_SYMBOL}{float(txn.get("amount", 0)):,.2f}</strong>'
            f'<small>{esc(str(txn.get("payment_method", "-"))).title()}</small></td>'
            f'<td><strong>{config.CURRENCY_SYMBOL}{float(txn.get("settlement_amount", 0)):,.2f}</strong>'
            f'<small>Fee + tax {config.CURRENCY_SYMBOL}{float(txn.get("fee", 0)) + float(txn.get("tax", 0)):,.2f}</small></td>'
            f'<td class="a2-date-pair">{dates}</td></tr>'
        )
    st.markdown(
        '<div class="a2-ledger-shell"><div class="a2-table-scroll"><table class="a2-ledger-table">'
        '<thead><tr><th>Transaction</th><th>Status</th><th>Gross</th><th>Settlement</th><th>Transaction → settlement</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></div>',
        unsafe_allow_html=True,
    )


def render_sample_table(frame: pd.DataFrame, total_rows: int) -> None:
    """Present a compact preview with the same visual language as the result ledger."""
    records = frame.to_dict("records")
    rows = []
    for row in records:
        status_raw = str(row.get("status", "unknown")).lower().replace(" ", "_")
        tone = "danger" if status_raw in {"on_hold", "hold"} else "warn" if status_raw in {"pending", "processing"} else "good"
        rows.append(
            '<tr>'
            f'<td><span class="mono">{esc(str(row.get("transaction_id", "-")))}</span></td>'
            f'<td>{badge(status_raw.replace("_", " ").title(), tone)}</td>'
            f'<td class="money">{config.CURRENCY_SYMBOL}{float(row.get("amount", 0)):,.2f}</td>'
            f'<td class="money">{config.CURRENCY_SYMBOL}{float(row.get("settlement_amount", 0)):,.2f}</td>'
            f'<td>{esc(str(row.get("payment_method", "-"))).title()}</td></tr>'
        )
    st.markdown(
        '<div class="a2-sample-preview"><div class="a2-sample-heading"><span>LIVE PREVIEW</span>'
        f'<strong>{len(records)} of {total_rows} rows</strong></div><div class="a2-table-scroll">'
        '<table class="a2-ledger-table"><thead><tr><th>Transaction</th><th>Status</th><th class="money">Gross</th>'
        f'<th class="money">Settlement</th><th>Method</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>',
        unsafe_allow_html=True,
    )


def serialize_transactions(transactions: list[dict]) -> str:
    """Create a parseable snapshot for reopening a reconciliation from history."""
    columns = [
        "settlement_date", "transaction_id", "order_id", "settlement_id", "amount",
        "fee", "tax", "settlement_amount", "status", "payment_method", "transaction_date",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for transaction in transactions:
        writer.writerow({key: transaction.get(key, "") for key in columns})
    return output.getvalue()


def preserve_current_result_for_history(agent: ReconciliationAgent, summary: dict) -> None:
    """Backfill the active pre-upgrade result so its existing history card can reopen it."""
    if st.session_state.get("a2_input_csv"):
        return
    source = str(st.session_state.get("a2_source", "Current report"))
    content = serialize_transactions(agent.transactions)
    st.session_state.a2_input_csv = content
    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    for entry in read_activity_history(user_id, section="agent2"):
        metadata = entry.get("metadata", {})
        if (
            entry.get("action") == "reconciliation_completed"
            and metadata.get("source") == source
            and metadata.get("total_transactions") == summary.get("total_transactions")
            and not metadata.get("input_csv")
        ):
            update_activity_metadata(user_id, entry["id"], {"input_csv": content})
            break


def render_policy_cards(meta: dict) -> None:
    """Render current extractive passages as distinct, source-labelled cards."""
    chunks = meta.get("extractive_chunks") or []
    if not chunks:
        st.info("No settlement-specific passage matched this reconciliation. Refresh after updating the policy library.")
        return
    cards = []
    for index, chunk in enumerate(chunks, 1):
        text = " ".join(str(chunk.get("text", "")).split())
        if len(text) > config.POLICY_EVIDENCE_EXCERPT_CHARS:
            text = text[: config.POLICY_EVIDENCE_EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"
        cards.append(
            '<article class="a2-policy-card">'
            f'<div class="a2-policy-card-index">{index:02}</div><div>'
            f'<h4>{esc(str(chunk.get("section", "Policy passage")))}</h4>'
            f'<p>{esc(text)}</p><span>Source · {esc(str(chunk.get("source", "Local policy library")))}</span>'
            '</div></article>'
        )
    st.markdown(f'<div class="a2-policy-cards">{"".join(cards)}</div>', unsafe_allow_html=True)


activity_route_error = restore_activity_route()
if activity_route_error:
    st.warning(activity_route_error)
if st.session_state.get("a2_refresh_notice"):
    st.toast(st.session_state.a2_refresh_notice)
    st.session_state.a2_refresh_notice = None
render_reconciliation_header()

if not st.session_state.get("a2_done"):
    steps(["Add your data", "Review exceptions", "Export your report"], 0)
    main, supporting = st.columns([1.8, 1], gap="large")
    with main:
        with panel("Start a reconciliation", "Choose how you want to add your transactions.", key="a2-intake"):
            st.markdown(
                '<div class="a2-intake-strip"><span>DATA IN</span>'
                '<p>Use the route that matches the evidence you have available.</p>'
                '<b>CSV · MANUAL · SAMPLE</b></div>',
                unsafe_allow_html=True,
            )
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
                    sample_frame = pd.read_csv(io.StringIO(sample_content))
                    render_sample_table(sample_frame.head(config.SAMPLE_PREVIEW_ROWS), len(sample_frame))
                    if st.button("Reconcile sample →", type="primary", width="stretch"):
                        with st.spinner("Analyzing sample…"):
                            if run_analysis(sample_content, "Bundled sample", publish_to_dashboard=False):
                                st.rerun()
                    st.download_button("Download sample CSV", sample_content, "sample_settlement.csv", "text/csv")
                else:
                    st.info("The sample report is unavailable. Upload your own CSV to continue.")
    with supporting:
        with st.container(key="a2-guidance"):
            note("Follow the money, row by row.", "Your audit separates held and pending amounts, compares charged fees with configured rates, and checks settlement dates when available.")
            deliverables = "".join(
                f'<div class="a2-deliverable"><span>{number}</span><div><strong>{title}</strong><p>{body}</p></div></div>'
                for number, title, body in [
                    ("01", "An exception ledger", "Related issues grouped under one transaction."),
                    ("02", "A financial summary", "Gross, settled, held, fees, and any remaining variance."),
                    ("03", "A recovery request", "A downloadable audit and a support letter you can edit."),
                ]
            )
            st.markdown(
                '<section class="a2-deliverables"><div class="a2-section-kicker">YOUR OUTPUT</div>'
                '<h3>One report. Three useful views.</h3>' + deliverables + '</section>',
                unsafe_allow_html=True,
            )
else:
    agent = st.session_state.a2_agent
    summary = st.session_state.a2_summary
    preserve_current_result_for_history(agent, summary)
    stored_policy = st.session_state.get("a2_policy_meta")
    if not isinstance(stored_policy, dict) or not stored_policy.get("extractive_chunks"):
        current_evidence = fetch_policy_evidence(summary)
        st.session_state.a2_policy_meta = current_evidence
        st.session_state.a2_evidence = current_evidence.get("answer", "")
    steps(["Add your data", "Review exceptions", "Export your report"], 2)
    health = summary["health_score"]
    health_score = max(0, min(int(health.get("score", 0)), 100))
    health_degrees = round(health_score * 3.6)
    unsettled_count = summary["held_count"] + summary["pending_count"]
    unsettled_label = "item" if unsettled_count == 1 else "items"
    transaction_label = "transaction" if summary["total_transactions"] == 1 else "transactions"
    exception_count = summary.get("exception_transaction_count", unsettled_count + summary["tat_count"])
    exception_label = "transaction" if exception_count == 1 else "transactions"
    exception_summary = (
        f"No exceptions were identified across {summary['total_transactions']} {transaction_label}."
        if exception_count == 0
        else (
            f"{exception_count} {exception_label} require review across {summary['total_transactions']} {transaction_label}. "
            f"This includes {unsettled_count} unsettled {unsettled_label}."
        )
    )
    timing_status = summary.get("timing_assessment_status", "complete")
    if timing_status == "unavailable":
        timing_summary = "Settlement timing was not assessed because transaction and settlement dates were not supplied."
    elif timing_status == "partial":
        timing_summary = (
            f"Settlement timing was assessed for {summary.get('timing_evaluable_count', 0)} of "
            f"{summary['total_transactions']} {transaction_label}; {summary['tat_count']} timing exceptions were found in those rows."
        )
    else:
        timing_summary = f"The complete date review found {summary['tat_count']} timing exceptions."
    health_summary = f"{exception_summary} {timing_summary}"
    st.markdown(
        '<section class="a2-audit-overview">'
        f'<div class="a2-health-ring {esc(str(health.get("color", "gray")))}" style="--health-score:{health_degrees}deg">'
        f'<div><strong>{health_score}</strong><small>/ 100</small></div></div>'
        '<div class="a2-audit-copy"><span>RECONCILIATION HEALTH</span>'
        f'<h2>{esc(str(health.get("label", "Review needed")))}</h2>'
        f'<p>{esc(health_summary)}</p></div>'
        '<div class="a2-audit-focus">'
        '<small>AMOUNT TO REVIEW</small>'
        f'<strong>{config.CURRENCY_SYMBOL}{summary.get("amount_to_review", summary["recovery_amount"]):,.2f}</strong>'
        f'<span>{esc(str(st.session_state.get("a2_source", "Current report")))}</span></div></section>',
        unsafe_allow_html=True,
    )
    with st.container(key="a2-metrics"):
        columns = st.columns(4)
        for column, label, value, sub in [
            (columns[0], "Gross processed", f'{config.CURRENCY_SYMBOL}{summary["total_gross"]:,.2f}', f'{summary["total_transactions"]} {transaction_label}'),
            (columns[1], "Settled to bank", f'{config.CURRENCY_SYMBOL}{summary["total_settled"]:,.2f}', f'{summary["settled_count"]} settled'),
            (columns[2], "Held & pending", f'{config.CURRENCY_SYMBOL}{summary["recovery_amount"]:,.2f}', f'{summary["held_count"] + summary["pending_count"]} to follow up'),
            (columns[3], "Fee difference", f'{config.CURRENCY_SYMBOL}{summary["total_overcharge"]:,.2f}', "Charged minus configured benchmark"),
        ]:
            with column:
                metric(label, value, sub)

    issues = {}
    for transactions, label, detail in [
        (summary["held_funds"], "On hold", lambda t: f'{config.CURRENCY_SYMBOL}{t["amount"]:,.2f} withheld'),
        (summary["pending_funds"], "Pending", lambda t: f'{config.CURRENCY_SYMBOL}{t["amount"]:,.2f} pending'),
        (summary["tat_violations"], "Delay", lambda t: f'{t["days_delayed"]} {config.SETTLEMENT_DAY_MODE} days to settlement'),
        (
            summary.get("settlement_differences", []),
            "Settlement difference",
            lambda t: (
                f'{config.CURRENCY_SYMBOL}{t["shortfall"]:,.2f} settlement shortfall'
                if t["difference_type"] == "shortfall"
                else f'{config.CURRENCY_SYMBOL}{t["excess"]:,.2f} above calculated net settlement'
            ),
        ),
        (summary["overcharged_fees"], "Fee difference", lambda t: f'{config.CURRENCY_SYMBOL}{t["overcharge"]:,.2f} above configured fee/tax'),
    ]:
        for txn in transactions:
            entry = issues.setdefault(txn["transaction_id"], {"txn": txn, "labels": [], "details": []})
            entry["labels"].append(label)
            entry["details"].append(detail(txn))

    with st.container(key="a2-results"):
        exceptions, ledger, report, context = st.tabs(["Exceptions", "All transactions", "Report & request", "Policy context"])
    with exceptions:
        with st.container(key="a2-exceptions"):
            section_title(f"{len(issues)} transactions to review", "Select a category to narrow the list")
            category = st.selectbox(
                "Exception category",
                ["All exceptions", "On hold", "Pending", "Delay", "Settlement difference", "Fee difference"],
                label_visibility="collapsed",
            )
            rows = []
            for tid, item in issues.items():
                if category != "All exceptions" and category not in item["labels"]:
                    continue
                tags = " ".join(
                    badge(label, "danger" if label in {"On hold", "Settlement difference"} else "warn")
                    for label in item["labels"]
                )
                rows.append(f'<tr><td><span class="mono">{esc(tid)}</span><br><small>{esc(item["txn"]["payment_method"])}</small></td><td>{tags}</td><td class="money">{config.CURRENCY_SYMBOL}{item["txn"]["amount"]:,.2f}</td><td>{esc(" · ".join(item["details"]))}</td></tr>')
            if rows:
                st.markdown('<div class="table-scroll a2-exception-shell"><table class="data-table a2-exception-table"><thead><tr><th>Transaction</th><th>Exception</th><th class="money">Gross</th><th>Review notes</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>', unsafe_allow_html=True)
            else:
                st.success("No exceptions in this category.")
            if not any(t.get("_txn_date") and t.get("_set_date") for t in agent.transactions):
                with st.container(key="a2-tat-notice"):
                    st.info("Turnaround checks are unavailable because both transaction and settlement dates are required.")
    with ledger:
        with st.container(key="a2-ledger"):
            st.markdown('<div class="a2-tab-intro"><span>TRANSACTION LEDGER</span><h3>Trace every row from gross to bank.</h3><p>Search by transaction or order ID, then compare status, deductions, and settlement timing.</p></div>', unsafe_allow_html=True)
            search = st.text_input("Search ledger", placeholder="Transaction or order ID")
            transactions = [t for t in agent.transactions if search.lower() in (t["transaction_id"] + " " + t["order_id"]).lower()]
            if transactions:
                render_transaction_table(transactions)
            else:
                st.info("No transactions match this search.")
    with report:
        with st.container(key="a2-report"):
            gross = summary["total_gross"]
            settled = summary["total_settled"]
            held = summary["recovery_amount_net"]
            costs = round(summary["total_fee_charged"] + summary["total_tax_charged"], 2)
            variance = summary.get("residual_variance", round(gross - settled - held - costs, 2))
            parts = [("Gross", gross), ("Settled", settled), ("Held / pending net", held), ("Fees / tax", costs), ("Residual variance", variance)]
            equation = "".join(f'<div><span>{index:02}</span><small>{label}</small><strong>{config.CURRENCY_SYMBOL}{value:,.2f}</strong></div>' for index, (label, value) in enumerate(parts, 1))
            st.markdown('<div class="a2-tab-intro"><span>RECONCILIATION STATEMENT</span><h3>One balance, explained line by line.</h3><p>Every figure below is calculated from the current report.</p></div>' f'<div class="audit-equation">{equation}</div><div class="a2-equation-note"><i></i><p>Residual variance equals gross less settlements, held or pending net amounts, and charged fees or tax. Review any non-zero balance against the source report.</p></div>', unsafe_allow_html=True)
            with panel("Recovery request", "Review the figures and replace the placeholders. Your edits are included in the download.", key="doc-preview"):
                current_draft = ReconciliationAgent.draft_recovery_ticket(agent)
                edited = st.text_area("Dispute letter", value=current_draft, height=380, key="a2_ticket_edit_v4", label_visibility="collapsed")
                a, b = st.columns(2)
                a.download_button("Download request", edited, "reconciliation_dispute.txt", "text/plain", type="primary", width="stretch")
                b.download_button("Export audit CSV", agent.export_report_csv(), "reconciliation_report.csv", "text/csv", width="stretch")
    with context:
      with st.container(key="a2-policy"):
        with panel(
            "Supporting policy context",
            "Current source excerpts matched to this reconciliation.",
            key="a2-policy-panel",
        ):
            meta = st.session_state.get("a2_policy_meta") or {}
            confidence = meta.get("confidence") or {"score": 0.0, "label": "none"}
            score = float(confidence.get("score") or 0)
            label = str(confidence.get("label") or "none").title()
            tone = "good" if label == "High" else "warn" if label == "Medium" else "danger"
            score_degrees = max(0, min(round(score * 360), 360))
            st.markdown(
                '<div class="a2-policy-overview">'
                f'<div class="evidence-ring {tone}" style="--evidence-score:{score_degrees}deg"><div>'
                f'<strong>{score:.0%}</strong><small>{esc(label)}</small></div></div>'
                '<div><span>POLICY MATCH</span><h3>Evidence selected for this settlement case.</h3>'
                '<p>The score measures query-to-source relevance. It is not legal certainty or a prediction of the provider’s decision.</p></div></div>',
                unsafe_allow_html=True,
            )
            st.caption(
                f'{meta.get("retrieval", "Local document search")} · '
                f'{meta.get("confidence_method", "Retrieval relevance")} · '
                f'Checked {meta.get("checked_at", "now")}'
            )
            st.caption(f'Sources: {meta.get("source", "Local policy library")}')
            if meta.get("status"):
                st.info(meta["status"])
            render_policy_cards(meta)
            if st.button("Refresh policy evidence"):
                with st.spinner("Searching the policy library…"):
                    refreshed = fetch_policy_evidence(summary, reconnect_index=True)
                    st.session_state.a2_evidence = refreshed.get("answer", "")
                    st.session_state.a2_policy_meta = refreshed
                    st.session_state.a2_refresh_notice = "Policy evidence rechecked against the current indexed sources."
                st.rerun()
            same_tab_link("Prepare a formal escalation →", urls["agent3"])
    with st.container(key="a2-reset"):
        if st.button("Start another reconciliation"):
            st.query_params.clear()
            clear_analysis()
            st.rerun()

if not st.session_state.get("a2_done"):
    activity_history("agent2")
footer()
