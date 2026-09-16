import hashlib
import html
import importlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import streamlit as st

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(AGENT_DIR)
for path in (AGENT_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import escalation_agent as _escalation

import src.ui as _ui
from src import config
from src.activity_history import (
    read_activity,
    record_activity,
    update_activity_metadata,
)
from src.policy_evidence import get_policy_evidence

importlib.reload(_ui)
importlib.reload(_escalation)
ESCALATION_TIERS = _escalation.ESCALATION_TIERS
ISSUE_TYPES = _escalation.ISSUE_TYPES
EscalationAgent = _escalation.EscalationAgent
from src.ui import (
    activity_history,
    badge,
    esc,
    footer,
    inject_theme,
    nav,
    panel,
    require_auth,
    section_title,
)

st.set_page_config(
    page_title="MerchantOS · Formal Escalation",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()
require_auth("agent3")
nav("agent3")

agent = EscalationAgent()
LOGGER = logging.getLogger(__name__)
CURRENT_DATE = datetime.now().astimezone().date()


ISSUE_POLICY_QUERIES = {
    "kyc_hold": "merchant KYC due diligence account hold paragraph 13 remediation",
    "settlement_hold": "merchant settlement held funds escrow paragraph 16 grievance paragraph 8",
    "settlement_missing": "missing merchant settlement escrow credit timeline paragraph 16",
    "fee_overcharge": "merchant pricing fees MDR agreement disclosure paragraph 10",
    "tat_violation": "merchant settlement timeline schedule agreement paragraph 16 Table 1",
    "account_suspended": "merchant account suspension restriction reason grievance paragraph 8",
    "chargeback_dispute": "merchant chargeback dispute refund responsibilities grievance redressal",
    "other": "merchant complaint grievance officer escalation matrix paragraph 8",
}


def fetch_policy_evidence(issue_key: str, use_live_retrieval: bool = True) -> dict:
    query = (
        f"{ISSUE_POLICY_QUERIES[issue_key]}. {ISSUE_TYPES[issue_key]}. "
        f"Use {config.PA_DIRECTIONS_REFERENCE} and the provider's published policy."
    )
    try:
        return get_policy_evidence(query, semantic=use_live_retrieval)
    except Exception:
        LOGGER.debug("Policy retrieval failed", exc_info=True)
        return get_policy_evidence(query, semantic=False)


def normalized_amount(raw_amount: str) -> tuple[str, str | None]:
    value = raw_amount.strip().replace(",", "")
    if not value:
        return "N/A", None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return value, "Disputed amount must be a valid number."
    if not amount.is_finite() or amount <= 0:
        return value, "Disputed amount must be greater than zero."
    return f"{amount:,.2f}", None


def contact_validation_errors(email: str, phone: str) -> list[str]:
    errors = []
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        errors.append("Enter a valid registered email address.")
    clean_phone = phone.strip()
    digits = re.sub(r"\D", "", clean_phone)
    if not re.fullmatch(r"\+?[0-9\s().-]+", clean_phone) or not 7 <= len(digits) <= 15:
        errors.append("Enter a valid phone number containing 7 to 15 digits.")
    return errors


def clear_document_state() -> None:
    for key in ("a3_grievance_edit", "a3_ombudsman_edit", "a3_legal_edit"):
        st.session_state.pop(key, None)


def clear_workspace() -> None:
    for key in (
        "a3_submitted_case",
        "a3_policy_evidence",
        "a3_loaded_activity_id",
        "a3_workspace_flash",
        "a3_workspace_persisted",
    ):
        st.session_state.pop(key, None)
    clear_document_state()
    st.query_params.pop("activity", None)


def case_key(snapshot: dict) -> str:
    return hashlib.sha256(snapshot["signature"].encode("utf-8")).hexdigest()[:16]


def timing_values(issue: dict) -> tuple[int, int]:
    calendar_days = max(int(issue.get("days_elapsed", 0)), 0)
    if issue.get("business_days_elapsed") is not None:
        return calendar_days, max(int(issue["business_days_elapsed"]), 0)
    try:
        start = datetime.strptime(  # noqa: DTZ007 - parsing a date-only stored value
            issue["first_reported_date"], "%d %B %Y"
        ).date()
        end = start + timedelta(days=calendar_days)
        business_days = agent.calculate_business_days(start, end)
    except (KeyError, TypeError, ValueError):
        business_days = calendar_days
    issue["business_days_elapsed"] = business_days
    return calendar_days, business_days


def persist_workspace_value(name: str, value: dict) -> None:
    activity_id = st.session_state.get("a3_loaded_activity_id")
    if not isinstance(activity_id, int):
        return
    persisted = st.session_state.setdefault("a3_workspace_persisted", {})
    if persisted.get(name) == value:
        return
    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    if update_activity_metadata(user_id, activity_id, {name: value}):
        persisted[name] = value


def valid_case_snapshot(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    merchant = value.get("merchant")
    issue = value.get("issue")
    issue_type = value.get("issue_type")
    return (
        isinstance(merchant, dict)
        and isinstance(issue, dict)
        and issue_type in ISSUE_TYPES
        and all(
            merchant.get(key)
            for key in (
                "name",
                "business_name",
                "merchant_id",
                "email",
                "phone",
                "state",
                "address",
            )
        )
        and all(
            issue.get(key) is not None
            for key in (
                "first_reported_date",
                "days_elapsed",
                "amount",
                "description",
                "timeline",
            )
        )
    )


def restore_activity_route() -> str | None:
    raw_activity_id = st.query_params.get("activity")
    if not raw_activity_id:
        if st.session_state.get("a3_loaded_activity_id") is not None:
            clear_workspace()
        return None
    try:
        activity_id = int(raw_activity_id)
        if activity_id < 1:
            raise ValueError
    except (TypeError, ValueError):
        clear_workspace()
        return "This saved-case link is invalid."
    if st.session_state.get(
        "a3_loaded_activity_id"
    ) == activity_id and valid_case_snapshot(st.session_state.get("a3_submitted_case")):
        return None

    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    entry = read_activity(user_id, activity_id, section="agent3")
    metadata = entry.get("metadata", {}) if entry else {}
    snapshot = metadata.get("case_snapshot")
    if not valid_case_snapshot(snapshot):
        clear_workspace()
        return "This older saved case does not contain the complete record required to reopen it."
    st.session_state.a3_submitted_case = snapshot
    policy = metadata.get("policy_evidence")
    if not isinstance(policy, dict) or not policy.get("answer"):
        policy = fetch_policy_evidence(
            snapshot["issue_type"], use_live_retrieval=config.AUTO_FETCH_POLICY_EVIDENCE
        )
    st.session_state.a3_policy_evidence = policy
    st.session_state.a3_loaded_activity_id = activity_id
    clear_document_state()
    workspace_state = {
        "evidence_state": metadata.get("evidence_state", {}),
        "document_edits": metadata.get("document_edits", {}),
    }
    st.session_state.a3_workspace_persisted = workspace_state
    evidence_state = workspace_state["evidence_state"]
    if isinstance(evidence_state, dict):
        current_case_key = case_key(snapshot)
        for index, checked in evidence_state.items():
            if str(index).isdigit():
                st.session_state[f"a3_ev_{current_case_key}_{index}"] = bool(checked)
    document_edits = workspace_state["document_edits"]
    if isinstance(document_edits, dict):
        for name, widget_key in {
            "grievance": "a3_grievance_edit",
            "ombudsman": "a3_ombudsman_edit",
            "legal": "a3_legal_edit",
        }.items():
            if isinstance(document_edits.get(name), str):
                st.session_state[widget_key] = document_edits[name]
    return None


def route_status(
    tier: dict, recommended: dict, calendar_days: int, business_days: int
) -> tuple[str, str]:
    if tier["tier"] == recommended["tier"]:
        return "Recommended now", "good"
    elapsed = business_days if tier["day_basis"] == "business" else calendar_days
    if elapsed >= tier["trigger_days"]:
        return "Available", "info"
    basis = "business" if tier["day_basis"] == "business" else "calendar"
    return f"From {tier['trigger_days']} {basis} days", "info"


def render_route_ladder(
    recommended: dict, calendar_days: int, business_days: int
) -> None:
    cards = []
    for tier in ESCALATION_TIERS:
        status, tone = route_status(
            tier, recommended, calendar_days, business_days
        )
        cards.append(
            f'<article class="a3-route-card {"active" if tier["tier"] == recommended["tier"] else ""}">'
            f'<div class="a3-route-head"><span>{tier["tier"]:02}</span>{badge(status, tone)}</div>'
            f"<strong>{esc(tier['name'])}</strong><p>{esc(tier['description'])}</p></article>"
        )
    st.markdown(
        '<div class="a3-route-ladder">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def render_intake_hero() -> None:
    st.markdown(
        '<section class="a3-intake-hero">'
        '<div class="a3-intake-copy"><div class="a3-kicker"><i></i> ESCALATION CASE DESK</div>'
        "<h1>Turn a difficult issue into a clear record.</h1>"
        "<p>Enter the facts once. MerchantOS will open a private case workspace with the evidence checklist, escalation route, and correspondence tailored to that record.</p>"
        '<div class="a3-intake-chips"><span>One verified case file</span><span>Evidence before claims</span><span>Editable correspondence</span></div></div>'
        '<div class="a3-intake-art" aria-hidden="true"><span class="a3-art-label">CASE ARCHITECTURE</span>'
        '<div class="a3-art-stack"><div><small>01</small><b>Facts</b></div><div><small>02</small><b>Evidence</b></div><div><small>03</small><b>Response</b></div></div>'
        '<div class="a3-art-line"></div><em>Ready when the record is complete</em></div></section>',
        unsafe_allow_html=True,
    )


def render_intake() -> None:
    render_intake_hero()
    if message := st.session_state.pop("a3_route_error", None):
        st.error(message)
    form_column, guide_column = st.columns([1.75, 0.8], gap="large")
    with form_column:
        with st.form("a3_case_intake", border=False):  # noqa: SIM117 - explicit form/panel scopes
            with panel(
                "Build the case file",
                "Required fields ensure every generated document has a complete sender and dispute record.",
                key="a3-intake-form",
            ):
                st.markdown(
                    '<div class="a3-form-section"><span>01</span><div><strong>Merchant identity</strong><small>The account and sender the provider can verify</small></div></div>',
                    unsafe_allow_html=True,
                )
                row1 = st.columns(3)
                merchant_name = row1[0].text_input(
                    "Full name *", placeholder="Rahul Sharma", key="a3_full_name"
                )
                business_name = row1[1].text_input(
                    "Business or legal entity *",
                    placeholder="ShopEasy Retail Pvt Ltd",
                    key="a3_business_name",
                )
                merchant_id = row1[2].text_input(
                    f"{config.AGGREGATOR_SHORT} Merchant ID *",
                    placeholder="M_ABC123XYZ",
                    key="a3_merchant_id",
                )
                row2 = st.columns(3)
                email = row2[0].text_input(
                    "Registered email *",
                    placeholder="accounts@example.com",
                    key="a3_email",
                )
                phone = row2[1].text_input(
                    "Phone number *", placeholder="+91 98765 43210", key="a3_phone"
                )
                state = row2[2].text_input(
                    "State or UT *", placeholder="Karnataka", key="a3_state"
                )
                address = st.text_area(
                    "Registered address *",
                    placeholder="Business address used in formal correspondence",
                    height=86,
                    key="a3_address",
                )
                st.markdown(
                    '<div class="a3-form-section"><span>02</span><div><strong>Dispute record</strong><small>What happened, when it began, and what value is affected</small></div></div>',
                    unsafe_allow_html=True,
                )
                row3 = st.columns(3)
                issue_type = row3[0].selectbox(
                    "Dispute category *",
                    list(ISSUE_TYPES),
                    format_func=ISSUE_TYPES.get,
                    key="a3_issue_type",
                )
                amount = row3[1].text_input(
                    f"Disputed amount ({config.CURRENCY_SYMBOL})",
                    placeholder="45000.00",
                    key="a3_amount",
                )
                issue_date = row3[2].date_input(
                    "Issue began *",
                    value=CURRENT_DATE,
                    max_value=CURRENT_DATE,
                    key="a3_issue_date",
                )
                row4 = st.columns(2)
                txn_ids = row4[0].text_input(
                    "Transaction or order IDs",
                    placeholder="pay_ABC123, pay_XYZ789",
                    key="a3_txn_ids",
                )
                grievance_ref = row4[1].text_input(
                    "Previous ticket ID",
                    placeholder="RZP_TICKET_98765",
                    key="a3_grievance_ref",
                )
                description = st.text_area(
                    "Chronological issue summary *",
                    placeholder="Describe what happened, what you submitted, and the responses received.",
                    height=120,
                    key="a3_description",
                )
                timeline_text = st.text_area(
                    "Key milestones · one per line *",
                    placeholder="YYYY-MM-DD: First contacted support\nYYYY-MM-DD: Submitted requested records\nYYYY-MM-DD: Followed up",
                    height=112,
                    key="a3_timeline",
                )
                st.markdown(
                    '<div class="a3-submit-note"><span>What happens next</span><p>Your case is saved, then opened in a separate workspace. You can return to it from history at any time.</p></div>',
                    unsafe_allow_html=True,
                )
                submitted = st.form_submit_button(
                    "Create case workspace →",
                    type="primary",
                    width="stretch",
                    key="a3_create_workspace",
                )

        if submitted:
            timeline = [
                line.strip() for line in timeline_text.splitlines() if line.strip()
            ]
            amount_value, amount_error = normalized_amount(amount)
            required_fields = {
                "full name": merchant_name.strip(),
                "business or legal entity": business_name.strip(),
                "merchant ID": merchant_id.strip(),
                "registered email": email.strip(),
                "phone number": phone.strip(),
                "state or UT": state.strip(),
                "registered address": address.strip(),
                "issue summary": description.strip(),
                "at least one milestone": timeline_text.strip(),
            }
            missing = [label for label, value in required_fields.items() if not value]
            contact_errors = contact_validation_errors(email, phone)
            if missing:
                st.error("Complete the required fields: " + ", ".join(missing) + ".")
            elif contact_errors:
                st.error(" ".join(contact_errors))
            elif amount_error:
                st.error(amount_error)
            else:
                days_elapsed = max(agent.calculate_days(issue_date), 0)
                business_days_elapsed = max(
                    agent.calculate_business_days(issue_date), 0
                )
                recommended = agent.recommend_tier(
                    days_elapsed, business_days_elapsed
                )
                merchant = {
                    "name": merchant_name.strip(),
                    "business_name": business_name.strip(),
                    "merchant_id": merchant_id.strip(),
                    "email": email.strip(),
                    "phone": phone.strip(),
                    "state": state.strip(),
                    "address": address.strip(),
                }
                issue = {
                    "issue_type": issue_type,
                    "first_reported_date": issue_date.strftime("%d %B %Y"),
                    "days_elapsed": days_elapsed,
                    "business_days_elapsed": business_days_elapsed,
                    "amount": amount_value,
                    "txn_ids": txn_ids.strip() or "As per attached statement",
                    "description": description.strip(),
                    "timeline": timeline,
                    "grievance_ref": grievance_ref.strip(),
                }
                signature_payload = {
                    "merchant": merchant,
                    "issue": {
                        key: value
                        for key, value in issue.items()
                        if key not in {"days_elapsed", "business_days_elapsed"}
                    },
                }
                signature = json.dumps(signature_payload, sort_keys=True)
                snapshot = {
                    "merchant": merchant,
                    "issue": issue,
                    "issue_type": issue_type,
                    "since_label": issue_date.strftime("Since %d %b %Y"),
                    "signature": signature,
                }
                with st.spinner(
                    "Opening the case workspace and matching policy evidence…"
                ):
                    policy = fetch_policy_evidence(
                        issue_type, use_live_retrieval=config.AUTO_FETCH_POLICY_EVIDENCE
                    )
                user_id = st.session_state.merchantos_user.get("id", "local")
                activity_id = record_activity(
                    user_id,
                    "agent3",
                    "case_saved",
                    ISSUE_TYPES[issue_type],
                    f"{days_elapsed} calendar / {business_days_elapsed} business days · {config.CURRENCY_SYMBOL}{amount_value} · {recommended['name']}",
                    {
                        "issue_type": issue_type,
                        "days_elapsed": days_elapsed,
                        "business_days_elapsed": business_days_elapsed,
                        "recommended_tier": recommended["tier"],
                        "case_snapshot": snapshot,
                        "policy_evidence": policy,
                        "evidence_state": {},
                        "document_edits": {},
                    },
                )
                st.session_state.a3_submitted_case = snapshot
                st.session_state.a3_policy_evidence = policy
                st.session_state.a3_loaded_activity_id = activity_id
                st.session_state.a3_workspace_persisted = {
                    "evidence_state": {},
                    "document_edits": {},
                }
                st.session_state.a3_workspace_flash = (
                    "Case workspace created from your submitted record."
                )
                clear_document_state()
                st.query_params["activity"] = str(activity_id)
                st.rerun()

    with guide_column:
        st.markdown(
            '<aside class="a3-intake-guide"><div class="a3-guide-kicker">A BETTER HAND-OFF</div><h2>One record.<br>Every next step.</h2>'
            "<p>The workspace separates facts, supporting material, and formal language so the merchant can review each layer independently.</p>"
            "<ol><li><span>01</span><div><b>Enter verifiable facts</b><small>No evidence or drafts appear before submission.</small></div></li>"
            "<li><span>02</span><div><b>Inspect the evidence packet</b><small>Checklist and policy context match the submitted category.</small></div></li>"
            "<li><span>03</span><div><b>Choose the right response</b><small>Provider, Ombudsman, and counsel-review drafts stay editable.</small></div></li></ol>"
            '<div class="a3-guide-foot">MerchantOS prepares the record. You remain in control of what is sent.</div></aside>',
            unsafe_allow_html=True,
        )
    activity_history("agent3")


def render_case_overview(snapshot: dict, recommended: dict) -> None:
    merchant, issue = snapshot["merchant"], snapshot["issue"]
    calendar_days, business_days = timing_values(issue)
    facts = [
        ("Merchant", merchant["business_name"]),
        ("Merchant ID", merchant["merchant_id"]),
        ("Contact", merchant["email"]),
        ("Issue began", issue["first_reported_date"]),
        ("Previous ticket", issue.get("grievance_ref") or "Not supplied"),
        ("Transactions", issue.get("txn_ids") or "Not supplied"),
    ]
    st.markdown(
        '<div class="a3-overview-grid">'
        + "".join(
            f"<div><span>{esc(label)}</span><strong>{esc(value)}</strong></div>"
            for label, value in facts
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.15, 0.85], gap="large")
    with left:  # noqa: SIM117 - preserve explicit Streamlit layout scopes
        with panel(
            "Case narrative",
            "The submitted statement of events",
            key="a3-narrative-panel",
        ):
            st.write(issue["description"])
            st.markdown(
                '<div class="a3-timeline-title">Recorded milestones</div>',
                unsafe_allow_html=True,
            )
            timeline_html = "".join(
                f"<li><i></i><span>{esc(item)}</span></li>"
                for item in issue["timeline"]
            )
            st.markdown(
                f'<ol class="a3-timeline">{timeline_html}</ol>', unsafe_allow_html=True
            )
    with right:  # noqa: SIM117 - preserve explicit Streamlit layout scopes
        with panel(
            "Recommended next action",
            "Provider levels use weekdays; external review uses calendar days",
            key="a3-next-action",
        ):
            st.markdown(
                f'<div class="a3-next-route">{badge("Recommended now", "good")}<strong>{esc(recommended["name"])}</strong><p>{esc(recommended["description"])}</p><a href="{html.escape(recommended["contact"], quote=True)}" target="_blank" rel="noopener">Open route ↗</a></div>',
                unsafe_allow_html=True,
            )
    section_title(
        "Escalation route",
        "Progress only after the prior channel has been used or exhausted",
    )
    render_route_ladder(recommended, calendar_days, business_days)


def render_evidence_room(snapshot: dict) -> None:
    issue_type = snapshot["issue_type"]
    current_case_key = case_key(snapshot)
    checklist = agent.get_evidence_checklist(issue_type)
    section_title("Evidence room", "A case-specific packet—not a legal conclusion")
    progress = sum(
        bool(st.session_state.get(f"a3_ev_{current_case_key}_{index}"))
        for index in range(len(checklist))
    )
    readiness = round(progress / len(checklist) * 100) if checklist else 0
    st.markdown(
        f'<div class="a3-evidence-banner"><div><span>PACKET READINESS</span><strong>{progress} of {len(checklist)} items checked</strong><p>Tick an item only when the copy is clear, dated, and ready to attach.</p></div><b>{readiness}%</b></div>',
        unsafe_allow_html=True,
    )
    evidence_column, policy_column = st.columns([0.8, 1.2], gap="large")
    with evidence_column, st.container(border=True, key="a3-evidence-list"):
        evidence_state = {}
        for index, item in enumerate(checklist):
            evidence_state[str(index)] = st.checkbox(
                item, key=f"a3_ev_{current_case_key}_{index}"
            )
        persist_workspace_value("evidence_state", evidence_state)
    with policy_column:  # noqa: SIM117 - preserve explicit Streamlit layout scopes
        with panel(
            "Supporting policy context",
            "Matched to the submitted dispute category",
            key="a3-policy-source",
        ):
            policy = st.session_state.get("a3_policy_evidence", {})
            st.caption(
                f"{policy.get('source', 'Local policy library')} · {policy.get('retrieval', 'Local document search')}"
            )
            st.markdown(
                policy.get("answer", "No supporting policy evidence is available yet.")
            )
            if st.button(
                "Refresh policy match", key="a3_refresh_evidence", width="stretch"
            ):
                with st.spinner("Searching the policy library…"):
                    st.session_state.a3_policy_evidence = fetch_policy_evidence(
                        issue_type, use_live_retrieval=True
                    )
                st.rerun()


def render_correspondence(snapshot: dict) -> None:
    merchant, issue = snapshot["merchant"], snapshot["issue"]
    grievance = agent.draft_grievance_letter(merchant, issue)
    ombudsman = agent.draft_rbi_ombudsman_complaint(merchant, issue)
    legal = agent.draft_legal_notice(merchant, issue)
    section_title("Correspondence studio", "Review every fact before sending or filing")
    st.markdown(
        '<div class="a3-correspondence-note"><span>Three response levels</span><p>Start with the provider grievance. Use external routes only after checking eligibility, prerequisites, and the status of the prior complaint.</p></div>',
        unsafe_allow_html=True,
    )
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Provider grievance", "Ombudsman draft", "Counsel review", "Filing guide"]
    )
    with tab1:
        st.markdown("### Provider grievance letter")
        st.caption(
            "Confirm every fact and attach the evidence listed in the case packet."
        )
        st.session_state.setdefault("a3_grievance_edit", grievance)
        grievance_edited = st.text_area(
            "Grievance letter",
            height=430,
            label_visibility="collapsed",
            key="a3_grievance_edit",
        )
        st.download_button(
            "Download grievance letter",
            grievance_edited,
            f"{config.AGGREGATOR_SHORT.lower()}_grievance_letter.txt",
            "text/plain",
            width="stretch",
        )
    with tab2:
        st.markdown("### RBI Ombudsman complaint draft")
        st.warning(
            "Elapsed days alone do not establish eligibility. Confirm entity coverage, the prior written complaint, the provider response, and every Scheme exclusion before filing."
        )
        st.session_state.setdefault("a3_ombudsman_edit", ombudsman)
        ombudsman_edited = st.text_area(
            "Ombudsman complaint",
            height=430,
            label_visibility="collapsed",
            key="a3_ombudsman_edit",
        )
        st.download_button(
            "Download Ombudsman complaint",
            ombudsman_edited,
            "rbi_ombudsman_complaint.txt",
            "text/plain",
            width="stretch",
        )
    with tab3:
        st.markdown("### Counsel-review legal notice")
        st.warning("This route requires review by a qualified advocate before service.")
        st.session_state.setdefault("a3_legal_edit", legal)
        legal_edited = st.text_area(
            "Legal notice",
            height=430,
            label_visibility="collapsed",
            key="a3_legal_edit",
        )
        st.download_button(
            "Download legal notice",
            legal_edited,
            f"legal_notice_{config.AGGREGATOR_SHORT.lower()}.txt",
            "text/plain",
            width="stretch",
        )
    with tab4:
        st.markdown("### RBI Complaint Management System filing guide")
        filing_steps = [
            (
                "Open the portal",
                f"Visit {config.OMBUDSMAN_URL} and choose File a Complaint.",
            ),
            (
                "Verify your identity",
                "Enter your email or mobile number and complete OTP verification.",
            ),
            (
                "Select the entity",
                f"Choose the applicable payment-services category and {config.AGGREGATOR_NAME}.",
            ),
            (
                "Enter the complaint",
                "Paste the reviewed Ombudsman complaint and confirm every factual detail.",
            ),
            (
                "Attach evidence",
                "Upload settlement statements, screenshots, submissions, and prior correspondence.",
            ),
            (
                "Save the reference",
                "Retain the Complaint Reference Number for follow-up.",
            ),
        ]
        guide_html = "".join(
            f"<li><span>{index:02}</span><div><strong>{esc(title)}</strong><p>{esc(body)}</p></div></li>"
            for index, (title, body) in enumerate(filing_steps, 1)
        )
        st.markdown(
            f'<ol class="a3-filing-guide">{guide_html}</ol>', unsafe_allow_html=True
        )
    persist_workspace_value(
        "document_edits",
        {
            "grievance": grievance_edited,
            "ombudsman": ombudsman_edited,
            "legal": legal_edited,
        },
    )


def render_workspace(snapshot: dict) -> None:
    merchant, issue, issue_type = (
        snapshot["merchant"],
        snapshot["issue"],
        snapshot["issue_type"],
    )
    days_elapsed, business_days_elapsed = timing_values(issue)
    recommended = agent.recommend_tier(days_elapsed, business_days_elapsed)
    activity_id = st.session_state.get("a3_loaded_activity_id")
    case_label = (
        f"CASE {activity_id:04}" if isinstance(activity_id, int) else "ACTIVE CASE"
    )
    amount_display = (
        f"{config.CURRENCY_SYMBOL}{issue['amount']}"
        if issue["amount"] != "N/A"
        else "Not entered"
    )
    toolbar_left, toolbar_right = st.columns([4, 1], vertical_alignment="center")
    with toolbar_left:
        st.markdown(
            f'<div class="a3-workspace-breadcrumb"><span>ESCALATION DESK</span><i></i><b>{esc(case_label)}</b></div>',
            unsafe_allow_html=True,
        )
    with toolbar_right:
        if st.button("← Case desk", key="a3_back_to_desk", width="stretch"):
            clear_workspace()
            st.rerun()
    st.markdown(
        '<section class="a3-workspace-hero">'
        f'<div class="a3-workspace-copy"><div class="a3-kicker"><i></i> {esc(ISSUE_TYPES[issue_type]).upper()}</div>'
        f"<h1>{esc(merchant['business_name'])}</h1><p>{esc(issue['description'])}</p>"
        f'<div class="a3-case-identity"><span>{esc(merchant["merchant_id"])}</span><span>{esc(merchant["name"])}</span><span>{esc(issue["first_reported_date"])}</span></div></div>'
        '<div class="a3-workspace-metrics">'
        f"<div><span>TIME OPEN</span><strong>{days_elapsed}</strong><small>calendar days · {business_days_elapsed} weekdays</small></div>"
        f"<div><span>VALUE AFFECTED</span><strong>{esc(amount_display)}</strong><small>{esc(ISSUE_TYPES[issue_type])}</small></div>"
        f'<div class="route"><span>NEXT ROUTE</span><strong>{esc(recommended["name"])}</strong><small>Review before advancing</small></div>'
        "</div></section>",
        unsafe_allow_html=True,
    )
    if message := st.session_state.pop("a3_workspace_flash", None):
        st.success(message)
    overview_tab, evidence_tab, correspondence_tab = st.tabs(
        ["01  Case overview", "02  Evidence room", "03  Correspondence"]
    )
    with overview_tab:
        render_case_overview(snapshot, recommended)
    with evidence_tab:
        render_evidence_room(snapshot)
    with correspondence_tab:
        render_correspondence(snapshot)


route_error = restore_activity_route()
if route_error:
    st.session_state.a3_route_error = route_error
submitted_case = st.session_state.get("a3_submitted_case")
if valid_case_snapshot(submitted_case) and st.query_params.get("activity"):
    render_workspace(submitted_case)
else:
    render_intake()
footer()
