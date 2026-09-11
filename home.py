from __future__ import annotations

import socket
from datetime import datetime

import streamlit as st

from Agent1.kyc_agent import QUESTIONS
from Agent3.escalation_agent import ESCALATION_TIERS
from src import config
from src.shared_state import read_reconciliation_state
from src.ui import (
    activity_heatmap,
    app_urls,
    badge,
    esc,
    footer,
    hero,
    inject_theme,
    metric,
    nav,
    note,
    panel,
    require_auth,
    same_tab_link,
    section_title,
)


st.set_page_config(
    page_title="MerchantOS · Recovery Command Center",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_theme()
require_auth("home")
nav("home")
urls = app_urls()


def is_port_active(port: int) -> bool:
    for host in dict.fromkeys((config.FRONTEND_BIND_HOST, config.HOST)):
        try:
            with socket.create_connection((host, port), timeout=config.PORT_CHECK_TIMEOUT):
                return True
        except OSError:
            continue
    return False


def state_caption(state: dict | None) -> str:
    if not state:
        return "Waiting for your first reconciliation"
    source = state.get("source") or "Reconciliation workspace"
    try:
        updated = datetime.fromisoformat(state["updated_at"]).astimezone().strftime("%d %b %Y, %H:%M")
        return f"Latest successful reconciliation · {source} · {updated}"
    except (KeyError, TypeError, ValueError):
        return f"Latest successful reconciliation · {source}"


hero(
    "MERCHANT OPERATIONS / COMMAND CENTER",
    "Recover revenue with clear evidence.",
    "Diagnose account restrictions, reconcile every payout, and prepare the right escalation from one focused workspace.",
)


@st.fragment(run_every=config.DASHBOARD_REFRESH_INTERVAL_SECONDS)
def live_workspace() -> None:
    state = read_reconciliation_state()
    summary = state.get("summary", {}) if state else {}
    recovery = float(summary.get("recovery_amount") or 0)
    fee_difference = float(summary.get("total_overcharge") or 0)
    exception_count = int(summary.get("held_count") or 0) + int(summary.get("pending_count") or 0)
    service_states = {
        "agent1": is_port_active(config.PORT_AGENT1),
        "agent2": is_port_active(config.PORT_AGENT2),
        "agent3": is_port_active(config.PORT_AGENT3),
    }

    section_title("Recovery pulse", state_caption(state))
    with st.container(key="home_metrics"):
        metric_cols = st.columns(4)
        metric_data = [
            ("Capital to review", f"{config.CURRENCY_SYMBOL}{recovery:,.2f}", f"{exception_count} held or pending transactions"),
            ("Gross processed", f"{config.CURRENCY_SYMBOL}{float(summary.get('total_gross') or 0):,.2f}", f"{int(summary.get('total_transactions') or 0)} transactions"),
            ("Settled to bank", f"{config.CURRENCY_SYMBOL}{float(summary.get('total_settled') or 0):,.2f}", f"{int(summary.get('settled_count') or 0)} completed"),
            ("Fee difference", f"{config.CURRENCY_SYMBOL}{fee_difference:,.2f}", "Charged above configured expectation"),
        ]
        for column, values in zip(metric_cols, metric_data):
            with column:
                metric(*values)

    if state:
        st.caption("These values come from the latest successful reconciliation and update automatically.")
    else:
        st.caption("No report has been analyzed yet. Open Reconciliation and upload a settlement CSV to populate this dashboard.")

    section_title("Choose the next action", "Three connected recovery workflows")
    with st.container(key="home_actions"):
        cards = st.columns(3, gap="large")
        card_data = [
            (
                cards[0],
                "01 / Diagnose",
                "KYC & fund holds",
                f"Answer {len(QUESTIONS)} focused questions, identify the likely restriction, and prepare a document checklist.",
                "agent1",
                "Start diagnosis",
            ),
            (
                cards[1],
                "02 / Reconcile",
                "Settlement audit",
                "Upload a CSV, isolate held and pending payouts, compare configured fees, and export an audit record.",
                "agent2",
                "Audit settlements",
            ),
            (
                cards[2],
                "03 / Escalate",
                "Formal correspondence",
                f"Build a case file and prepare the appropriate response across {len(ESCALATION_TIERS)} escalation levels.",
                "agent3",
                "Prepare escalation",
            ),
        ]
        for column, eyebrow, title, body, key, action in card_data:
            with column:
                with panel(title, eyebrow):
                    tone = "good" if service_states[key] else "warn"
                    st.markdown(badge("Online" if service_states[key] else "Starting", tone), unsafe_allow_html=True)
                    st.write(body)
                    same_tab_link(f"{action} →", urls[key])

    section_title("Attention ledger", "Held and pending items from your latest reconciliation")
    flagged = list(summary.get("held_funds") or []) + list(summary.get("pending_funds") or [])
    if flagged:
        rows = []
        for transaction in flagged:
            tone = "danger" if transaction["status"] in ("hold", "on_hold") else "warn"
            rows.append(
                "<tr>"
                f"<td><span class='mono'>{esc(transaction['transaction_id'])}</span>"
                f"<br><small>{esc(transaction.get('order_id', ''))}</small></td>"
                f"<td>{badge(transaction['status'].replace('_', ' '), tone)}</td>"
                f"<td>{esc(transaction['payment_method'].title())}</td>"
                f"<td class='money'>{esc(config.CURRENCY_SYMBOL)}{float(transaction['amount']):,.2f}</td>"
                "</tr>"
            )
        st.markdown(
            "<div class='table-scroll'><table class='data-table'>"
            "<thead><tr><th>Transaction</th><th>Status</th><th>Method</th><th class='money'>Gross</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
    elif state:
        st.success("The latest reconciliation contains no held or pending transactions.")
    else:
        st.info("The ledger will appear after you complete your first reconciliation.")

    with st.container(key="home_support"):
        guide_col, status_col = st.columns(2, gap="large")
        with guide_col:
            note(
                "A simple recovery sequence.",
                "Start with the restriction, validate the money, then escalate using the same evidence. Each workspace keeps its task narrow and produces a downloadable record.",
            )

        with status_col:
            with panel("Workspace status", "Local service readiness"):
                for key, label in [
                    ("agent1", "KYC diagnosis"),
                    ("agent2", "Reconciliation"),
                    ("agent3", "Escalation"),
                ]:
                    tone = "good" if service_states[key] else "warn"
                    status = "Ready" if service_states[key] else "Starting"
                    st.markdown(
                        f"<div class='case-line'><span class='case-number'>{badge(status, tone)}</span>"
                        f"<div><strong>{label}</strong><p>{esc(urls[key])}</p></div></div>",
                        unsafe_allow_html=True,
                    )


live_workspace()
activity_heatmap()
footer()
