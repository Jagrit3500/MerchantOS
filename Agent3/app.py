import hashlib
import html
import importlib
import json
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation

import streamlit as st

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(AGENT_DIR)
for path in (AGENT_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from escalation_agent import ESCALATION_TIERS, ISSUE_TYPES, EscalationAgent

import src.ui as _ui
from src import config
from src.activity_history import record_activity
from src.policy_evidence import search_local_policy

# Refresh shared presentation helpers when an existing Streamlit session reruns.
importlib.reload(_ui)
from src.ui import (
    activity_history,
    badge,
    footer,
    inject_theme,
    metric,
    nav,
    note,
    panel,
    require_auth,
    section_title,
    steps,
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


def fetch_policy_evidence(issue_key: str, use_live_retrieval: bool = True) -> dict:
    query = (
        "What policy evidence, merchant complaint steps, settlement duties, and escalation requirements "
        f"apply to this payment aggregator dispute: {ISSUE_TYPES[issue_key]}? "
        f"Use {config.PA_DIRECTIONS_REFERENCE} and the configured provider policy."
    )
    local = search_local_policy(query)
    evidence = local.get("answer", "").strip()
    source = local.get("source", "Local policy library")
    retrieval = "Local document search"
    if use_live_retrieval:
        try:
            from src.llm_agent import get_answer as rag_get_answer

            result = rag_get_answer(query)
            evidence = result.get("answer", "").strip() or evidence
            chunks = result.get("chunks", [])
            if chunks:
                source = chunks[0].get("source", source)
            retrieval = "Semantic policy search"
        except Exception:
            LOGGER.debug(
                "Semantic policy retrieval failed; using local evidence", exc_info=True
            )
    return {"answer": evidence, "source": source, "retrieval": retrieval}


def normalized_amount(raw_amount: str) -> tuple[str, str | None]:
    """Return a correspondence-ready amount or a validation message."""
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


def reset_correspondence_state(*, clear_evidence_review: bool = True) -> None:
    for key in ("a3_grievance_edit", "a3_ombudsman_edit", "a3_legal_edit"):
        st.session_state.pop(key, None)
    if clear_evidence_review:
        st.session_state.pop("a3_evidence_reviewed", None)


st.markdown(
    '<section class="a3-hero">'
    '<div class="a3-hero-copy"><div class="a3-kicker"><i></i> RECOVERY CORRESPONDENCE DESK</div>'
    "<h1>Make the record impossible to ignore.</h1>"
    "<p>Build a precise case file, match every claim to evidence, and prepare the next response with the right level of restraint.</p>"
    '<div class="a3-hero-tags"><span>Structured case file</span><span>Evidence-led drafts</span><span>Current escalation routes</span></div></div>'
    '<div class="a3-hero-visual" aria-hidden="true"><div class="a3-orbit orbit-one"></div><div class="a3-orbit orbit-two"></div>'
    '<div class="a3-seal"><span>CASE</span><strong>03</strong><small>READY DESK</small></div>'
    '<div class="a3-signal signal-one"></div><div class="a3-signal signal-two"></div></div>'
    "</section>",
    unsafe_allow_html=True,
)

workflow_step = int(st.session_state.get("a3_step", 0))
steps(["Build the record", "Match the evidence", "Prepare the response"], workflow_step)
if flash_message := st.session_state.pop("a3_flash", None):
    st.success(flash_message)

main, context = st.columns([1.9, 1], gap="large")
with main:
    details_tab, evidence_tab, drafts_tab = st.tabs(
        ["01  Case file", "02  Evidence room", "03  Correspondence"]
    )

with details_tab:  # noqa: SIM117 - keep Streamlit tab and bordered panel scopes explicit
    with panel(
        "Open a case", "Start with facts the provider can verify.", key="a3-case-form"
    ):
        st.markdown(
            '<div class="a3-form-section"><span>01</span><div><strong>Merchant identity</strong><small>Required sender and account details</small></div></div>',
            unsafe_allow_html=True,
        )
        row1 = st.columns(3)
        merchant_name = row1[0].text_input("Full name *", placeholder="Rahul Sharma")
        business_name = row1[1].text_input(
            "Business or legal entity *", placeholder="ShopEasy Retail Pvt Ltd"
        )
        merchant_id = row1[2].text_input(
            f"{config.AGGREGATOR_SHORT} Merchant ID *", placeholder="M_ABC123XYZ"
        )
        row2 = st.columns(3)
        email = row2[0].text_input(
            "Registered email *", placeholder="accounts@example.com"
        )
        phone = row2[1].text_input("Phone number *", placeholder="+91 98765 43210")
        state = row2[2].text_input("State or UT *", placeholder="Karnataka")
        address = st.text_area(
            "Registered address *",
            placeholder="Business address for the legal notice",
            height=78,
        )

        st.markdown(
            '<div class="a3-form-section"><span>02</span><div><strong>Dispute record</strong><small>What happened, when, and for how much</small></div></div>',
            unsafe_allow_html=True,
        )
        row3 = st.columns(3)
        issue_type = row3[0].selectbox(
            "Dispute category *", list(ISSUE_TYPES), format_func=ISSUE_TYPES.get
        )
        amount = row3[1].text_input(
            f"Disputed amount ({config.CURRENCY_SYMBOL})", placeholder="45000.00"
        )
        issue_date = row3[2].date_input(
            "Issue began *", value=CURRENT_DATE, max_value=CURRENT_DATE
        )
        row4 = st.columns(2)
        txn_ids = row4[0].text_input(
            "Transaction or order IDs", placeholder="pay_ABC123, pay_XYZ789"
        )
        grievance_ref = row4[1].text_input(
            "Previous ticket ID", placeholder="RZP_TICKET_98765"
        )
        description = st.text_area(
            "Chronological issue summary *",
            placeholder="Describe what happened, what you submitted, and the responses received.",
            height=110,
        )
        timeline_text = st.text_area(
            "Key milestones · one per line *",
            placeholder="YYYY-MM-DD: Settlements paused\nYYYY-MM-DD: Submitted supporting documents\nYYYY-MM-DD: Followed up with support",
            height=100,
        )

days_elapsed = max(agent.calculate_days(issue_date), 0)
recommended = agent.recommend_tier(days_elapsed)
timeline = [line.strip() for line in timeline_text.splitlines() if line.strip()]
amount_value, amount_error = normalized_amount(amount)

merchant = {
    "name": merchant_name.strip() or "[YOUR NAME]",
    "business_name": business_name.strip() or "[YOUR BUSINESS NAME]",
    "merchant_id": merchant_id.strip() or "[YOUR MERCHANT ID]",
    "email": email.strip() or "[YOUR REGISTERED EMAIL]",
    "phone": phone.strip() or "[YOUR REGISTERED PHONE]",
    "state": state.strip() or "[YOUR STATE]",
    "address": address.strip() or "[YOUR REGISTERED ADDRESS]",
}
issue = {
    "issue_type": issue_type,
    "first_reported_date": issue_date.strftime("%d %B %Y"),
    "days_elapsed": days_elapsed,
    "amount": amount_value,
    "txn_ids": txn_ids.strip() or "As per attached statement",
    "description": description.strip() or "[DESCRIBE YOUR ISSUE]",
    "timeline": timeline or ["[ADD YOUR TIMELINE OF EVENTS]"],
    "grievance_ref": grievance_ref.strip(),
}
signature_issue = {key: value for key, value in issue.items() if key != "days_elapsed"}
case_signature = json.dumps(
    {"merchant": merchant, "issue": signature_issue}, sort_keys=True
)
submitted_case = st.session_state.get("a3_submitted_case")
submitted_signature = submitted_case.get("signature") if submitted_case else None
submitted_key = (
    hashlib.sha256(submitted_signature.encode("utf-8")).hexdigest()[:16]
    if submitted_signature
    else "locked"
)

with details_tab:
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
    missing_fields = [label for label, value in required_fields.items() if not value]
    if amount_error:
        st.error(amount_error)
    if submitted_case and submitted_signature != case_signature:
        st.warning(
            "These details differ from the submitted case. Submit again to rebuild the evidence packet and correspondence."
        )

    blocked_reasons = [*missing_fields]
    if amount_error:
        blocked_reasons.append("a valid disputed amount")
    if st.button(
        "Update case and rebuild evidence"
        if submitted_case
        else "Submit case and build evidence",
        type="primary",
        width="stretch",
        disabled=bool(blocked_reasons),
        help=(f"Complete: {', '.join(blocked_reasons)}." if blocked_reasons else None),
        key="a3_submit_case",
    ):
        snapshot = {
            "merchant": dict(merchant),
            "issue": {**issue, "timeline": list(issue["timeline"])},
            "issue_type": issue_type,
            "since_label": issue_date.strftime("Since %d %b %Y"),
            "signature": case_signature,
        }
        with st.spinner("Building the evidence packet for this submitted case…"):
            st.session_state.a3_policy_evidence = fetch_policy_evidence(
                issue_type,
                use_live_retrieval=config.AUTO_FETCH_POLICY_EVIDENCE,
            )
        st.session_state.a3_submitted_case = snapshot
        st.session_state.a3_step = 1
        st.session_state.a3_evidence_issue = issue_type
        reset_correspondence_state()
        if st.session_state.get("a3_last_saved_signature") != case_signature:
            record_activity(
                st.session_state.merchantos_user.get("id", "local"),
                "agent3",
                "case_saved",
                ISSUE_TYPES[issue_type],
                f"{days_elapsed} days unresolved · {config.CURRENCY_SYMBOL}{amount_value} · {recommended['name']}",
                {
                    "issue_type": issue_type,
                    "days_elapsed": days_elapsed,
                    "recommended_tier": recommended["tier"],
                },
            )
            st.session_state.a3_last_saved_signature = case_signature
        st.session_state.a3_flash = (
            "Case submitted and saved. The evidence room is now unlocked."
        )
        st.rerun()

with evidence_tab:
    if not submitted_case:
        with panel(
            "Evidence room locked",
            "Submit a complete case file before policy evidence is selected.",
            key="a3-evidence-locked",
        ):
            st.info(
                "Return to 01 Case file, complete every required field, and select “Submit case and build evidence”."
            )
    else:
        submitted_issue_type = submitted_case["issue_type"]
        evidence = agent.get_evidence_checklist(submitted_issue_type)
        section_title("Evidence room", "Built from the submitted case snapshot")
        with st.container(border=True, key="a3-evidence-list"):
            st.markdown(
                '<div class="a3-evidence-intro"><span>CHECKLIST</span><strong>Collect the source record</strong><small>Tick an item only when the copy is clear, dated, and ready to attach.</small></div>',
                unsafe_allow_html=True,
            )
            for index, item in enumerate(evidence):
                st.checkbox(item, key=f"a3_ev_{submitted_key}_{index}")
        with panel(
            "Supporting policy evidence",
            "Matched to the submitted dispute category—not a legal conclusion.",
            key="a3-policy-source",
        ):
            policy = st.session_state.get("a3_policy_evidence", {})
            st.caption(
                f"{policy.get('source', 'Local policy library')} · {policy.get('retrieval', 'Local document search')}"
            )
            st.markdown(
                policy.get("answer", "No supporting policy evidence is available yet.")
            )
            if st.button("Refresh policy evidence", key="a3_refresh_evidence"):
                with st.spinner("Searching the policy library…"):
                    st.session_state.a3_policy_evidence = fetch_policy_evidence(
                        submitted_issue_type, use_live_retrieval=True
                    )
                st.rerun()
        st.checkbox(
            "I reviewed the evidence checklist and will verify every attachment before sending.",
            key="a3_evidence_reviewed",
        )
        if st.button(
            "Confirm evidence and prepare correspondence",
            type="primary",
            width="stretch",
            disabled=not st.session_state.get("a3_evidence_reviewed", False),
            help="Confirm the evidence review first.",
            key="a3_prepare_correspondence",
        ):
            st.session_state.a3_step = 2
            reset_correspondence_state(clear_evidence_review=False)
            st.session_state.a3_flash = "Evidence review confirmed. Correspondence is now generated from the submitted case."
            st.rerun()

with drafts_tab:
    if not submitted_case or workflow_step < 2:
        with panel(
            "Correspondence locked",
            "Submit the case and confirm the evidence review before drafts are generated.",
            key="a3-drafts-locked",
        ):
            st.info(
                "Complete 01 Case file and 02 Evidence room to unlock provider, Ombudsman, and counsel-review drafts."
            )
    else:
        submitted_merchant = submitted_case["merchant"]
        submitted_issue = submitted_case["issue"]
        submitted_days = int(submitted_issue["days_elapsed"])
        section_title(
            "Correspondence studio", "Generated from the submitted case snapshot"
        )
        grievance = agent.draft_grievance_letter(submitted_merchant, submitted_issue)
        ombudsman = agent.draft_rbi_ombudsman_complaint(
            submitted_merchant, submitted_issue
        )
        legal = agent.draft_legal_notice(submitted_merchant, submitted_issue)
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Grievance letter", "Ombudsman complaint", "Legal notice", "Filing guide"]
        )

        with tab1:
            st.markdown("### Provider grievance letter")
            st.caption(
                "Confirm every fact and attach the evidence listed in the submitted packet."
            )
            grievance_edited = st.text_area(
                "Grievance letter",
                grievance,
                height=380,
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
                "Days elapsed alone do not establish eligibility. Confirm that the complained-against entity is covered, a prior written complaint was made, and no Scheme exclusion applies."
            )
            if submitted_days < config.OMBUDSMAN_TRIGGER_DAYS:
                st.warning(
                    f"This issue has been open for {submitted_days} days. Standard Ombudsman escalation generally begins after {config.OMBUDSMAN_TRIGGER_DAYS} days without satisfactory resolution."
                )
            ombudsman_edited = st.text_area(
                "Ombudsman complaint",
                ombudsman,
                height=380,
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
            st.caption(
                "Have a qualified advocate review this draft before formal service."
            )
            legal_edited = st.text_area(
                "Legal notice",
                legal,
                height=380,
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
            st.markdown("### File on the RBI Complaint Management System")
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
                    "Upload your settlement statements, screenshots, KYC submissions, and prior correspondence.",
                ),
                (
                    "Save the reference",
                    "Submit the case and retain the Complaint Reference Number for follow-up.",
                ),
            ]
            for index, (title, body) in enumerate(filing_steps, 1):
                st.markdown(
                    f'<div class="case-line"><span class="case-number">{index:02}</span><div><strong>{title}</strong><p>{body}</p></div></div>',
                    unsafe_allow_html=True,
                )

with context:
    active_issue = submitted_case["issue"] if submitted_case else issue
    active_issue_type = submitted_case["issue_type"] if submitted_case else issue_type
    active_days = int(active_issue["days_elapsed"])
    active_recommended = agent.recommend_tier(active_days)
    active_amount = active_issue.get("amount", "N/A")
    active_since = (
        submitted_case["since_label"]
        if submitted_case
        else issue_date.strftime("Since %d %b %Y")
    )
    brief_title = "Submitted case brief" if submitted_case else "Case preview"
    brief_subtitle = (
        "Downstream output uses this confirmed snapshot."
        if submitted_case
        else "Complete and submit the form to unlock evidence."
    )
    badge_label = "Recommended route" if submitted_case else "Route preview"
    with panel(brief_title, brief_subtitle, key="a3-case-brief"):
        st.markdown(
            f'<div class="a3-brief-status">{badge(badge_label, "good")}<strong>{html.escape(active_recommended["name"])}</strong><small>{html.escape(active_recommended["contact"])}</small></div>',
            unsafe_allow_html=True,
        )
        metric("Days unresolved", str(active_days), active_since)
        if active_amount != "N/A":
            metric(
                "Amount in dispute",
                f"{config.CURRENCY_SYMBOL}{active_amount}",
                ISSUE_TYPES[active_issue_type],
            )
    with st.container(key="a3-route-map"):
        section_title(
            "Escalation map", "Advance only when the prior route is exhausted"
        )
        for tier in ESCALATION_TIERS:
            active = tier["tier"] == active_recommended["tier"]
            reached = active_days >= tier["trigger_days"]
            status = (
                "Recommended"
                if active
                else ("Available" if reached else f"From day {tier['trigger_days']}")
            )
            tone = "good" if active else "info"
            st.markdown(
                f'<div class="case-line {"current" if active else ""}"><span class="case-number">{tier["tier"]:02}</span><div><strong>{html.escape(tier["name"])}</strong><p>{html.escape(tier["description"])}</p>{badge(status, tone)}</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown("<br>", unsafe_allow_html=True)
    note(
        "Keep the record clear.",
        "Attach the original support request, the provider’s response, and the relevant transaction records to your correspondence.",
    )

activity_history("agent3")
footer()
