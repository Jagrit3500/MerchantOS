import html
import importlib
import os
import sys
from datetime import date

import streamlit as st

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(AGENT_DIR)
for path in (AGENT_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from src import config
from src.activity_history import record_activity
from src.policy_evidence import search_local_policy
from escalation_agent import ESCALATION_TIERS, ISSUE_TYPES, EscalationAgent
import src.ui as _ui

# Refresh shared presentation helpers when an existing Streamlit session reruns.
importlib.reload(_ui)
from src.ui import activity_history, badge, footer, hero, inject_theme, metric, nav, note, panel, require_auth, section_title, steps


st.set_page_config(page_title="MerchantOS · Formal Escalation", page_icon="M", layout="wide", initial_sidebar_state="expanded")
inject_theme()
require_auth("agent3")
nav("agent3")
agent = EscalationAgent()


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
            pass
    return {"answer": evidence, "source": source, "retrieval": retrieval}

hero(
    "RECOVERY / CORRESPONDENCE",
    "A considered next step.",
    "Bring your case details, evidence, and formal correspondence together in one place.",
)
main, context = st.columns([1.9, 1], gap="large")
with main:
    details_tab, evidence_tab, drafts_tab = st.tabs(["01  Case details", "02  Evidence", "03  Correspondence"])

with details_tab:
    with panel("Case details", "Enter the merchant profile and the dispute timeline."):
        st.markdown("### Merchant profile")
        row1 = st.columns(3)
        merchant_name = row1[0].text_input("Full name *", placeholder="Rahul Sharma")
        business_name = row1[1].text_input("Business or legal entity *", placeholder="ShopEasy Retail Pvt Ltd")
        merchant_id = row1[2].text_input(f"{config.AGGREGATOR_SHORT} Merchant ID *", placeholder="M_ABC123XYZ")
        row2 = st.columns(3)
        email = row2[0].text_input("Registered email *", placeholder="accounts@example.com")
        phone = row2[1].text_input("Phone number *", placeholder="+91 98765 43210")
        state = row2[2].text_input("State or UT", placeholder="Karnataka")
        address = st.text_area("Registered address", placeholder="Business address for the legal notice", height=78)

        st.markdown("### Dispute record")
        row3 = st.columns(3)
        issue_type = row3[0].selectbox("Dispute category *", list(ISSUE_TYPES), format_func=ISSUE_TYPES.get)
        amount = row3[1].text_input(f"Disputed amount ({config.CURRENCY_SYMBOL})", placeholder="45000.00")
        issue_date = row3[2].date_input("Issue began *", value=date.today(), max_value=date.today())
        row4 = st.columns(2)
        txn_ids = row4[0].text_input("Transaction or order IDs", placeholder="pay_ABC123, pay_XYZ789")
        grievance_ref = row4[1].text_input("Previous ticket ID", placeholder="RZP_TICKET_98765")
        description = st.text_area("Chronological issue summary *", placeholder="Describe what happened, what you submitted, and the responses received.", height=110)
        timeline_text = st.text_area("Key milestones · one per line", placeholder="YYYY-MM-DD: Settlements paused\nYYYY-MM-DD: Submitted supporting documents\nYYYY-MM-DD: Followed up with support", height=100)


days_elapsed = max(agent.calculate_days(issue_date), 0)
recommended = agent.recommend_tier(days_elapsed)
evidence = agent.get_evidence_checklist(issue_type)
timeline = [line.strip() for line in timeline_text.splitlines() if line.strip()]

merchant = {
    "name": merchant_name or "[YOUR NAME]",
    "business_name": business_name or "[YOUR BUSINESS NAME]",
    "merchant_id": merchant_id or "[YOUR MERCHANT ID]",
    "email": email or "[YOUR REGISTERED EMAIL]",
    "phone": phone or "[YOUR REGISTERED PHONE]",
    "state": state or "[YOUR STATE]",
    "address": address or "[YOUR REGISTERED ADDRESS]",
}
issue = {
    "issue_type": issue_type,
    "first_reported_date": issue_date.strftime("%d %B %Y"),
    "days_elapsed": days_elapsed,
    "amount": amount or "N/A",
    "txn_ids": txn_ids or "As per attached statement",
    "description": description or "[DESCRIBE YOUR ISSUE]",
    "timeline": timeline or ["[ADD YOUR TIMELINE OF EVENTS]"],
    "grievance_ref": grievance_ref,
}

if st.session_state.get("a3_evidence_issue") != issue_type:
    with st.spinner("Preparing policy evidence for this dispute…"):
        st.session_state.a3_policy_evidence = fetch_policy_evidence(
            issue_type,
            use_live_retrieval=config.AUTO_FETCH_POLICY_EVIDENCE,
        )
        st.session_state.a3_evidence_issue = issue_type

with details_tab:
    required_case_fields = merchant_name and business_name and merchant_id and email and description
    if st.button(
        "Save case to history",
        type="primary",
        width="stretch",
        disabled=not required_case_fields,
        help="Complete the required merchant and issue fields first." if not required_case_fields else None,
    ):
        record_activity(
            st.session_state.merchantos_user.get("id", "local"),
            "agent3",
            "case_saved",
            ISSUE_TYPES[issue_type],
            f'{days_elapsed} days unresolved · {config.CURRENCY_SYMBOL}{amount or "Amount not entered"} · {recommended["name"]}',
            {"issue_type": issue_type, "days_elapsed": days_elapsed, "recommended_tier": recommended["tier"]},
        )
        st.success("Case saved to your activity history.")


with evidence_tab:
    section_title("Documents to collect", "Tick each item as you prepare it")
    with st.container(border=True):
        for index, item in enumerate(evidence):
            st.checkbox(item, key=f"a3_ev_{issue_type}_{index}")
    with panel("Supporting policy evidence", "Fetched automatically for the selected dispute category."):
        policy = st.session_state.get("a3_policy_evidence", {})
        st.caption(f'{policy.get("source", "Local policy library")} · {policy.get("retrieval", "Local document search")}')
        st.markdown(policy.get("answer", "No supporting policy evidence is available yet."))
        if st.button("Refresh policy evidence", key="a3_refresh_evidence"):
            with st.spinner("Searching the policy library…"):
                st.session_state.a3_policy_evidence = fetch_policy_evidence(issue_type, use_live_retrieval=True)
            st.rerun()


with drafts_tab:
    section_title("Your correspondence", "Generated from the case details")
    grievance = agent.draft_grievance_letter(merchant, issue)
    ombudsman = agent.draft_rbi_ombudsman_complaint(merchant, issue)
    legal = agent.draft_legal_notice(merchant, issue)
    tab1, tab2, tab3, tab4 = st.tabs(["Grievance letter", "Ombudsman complaint", "Legal notice", "Filing guide"])

    with tab1:
        st.markdown("### Tier 2 · Grievance Officer")
        st.caption("Review placeholders, confirm the facts, and attach the evidence listed above.")
        grievance_edited = st.text_area("Grievance letter", grievance, height=380, label_visibility="collapsed", key="a3_grievance_edit")
        st.download_button("Download grievance letter", grievance_edited, f"{config.AGGREGATOR_SHORT.lower()}_grievance_letter.txt", "text/plain", width="stretch")

    with tab2:
        st.markdown("### Tier 3 · RBI Integrated Ombudsman")
        st.warning("Days elapsed alone do not establish eligibility. Confirm that the complained-against entity is covered, a prior written complaint was made, and no Scheme exclusion applies.")
        if days_elapsed < config.OMBUDSMAN_TRIGGER_DAYS:
            st.warning(f"This issue has been open for {days_elapsed} days. Standard Ombudsman escalation generally begins after {config.OMBUDSMAN_TRIGGER_DAYS} days without satisfactory resolution.")
        ombudsman_edited = st.text_area("Ombudsman complaint", ombudsman, height=380, label_visibility="collapsed", key="a3_ombudsman_edit")
        st.download_button("Download Ombudsman complaint", ombudsman_edited, "rbi_ombudsman_complaint.txt", "text/plain", width="stretch")

    with tab3:
        st.markdown("### Tier 4 · Formal legal notice")
        st.caption("Have a qualified advocate review this draft before formal service.")
        legal_edited = st.text_area("Legal notice", legal, height=380, label_visibility="collapsed", key="a3_legal_edit")
        st.download_button("Download legal notice", legal_edited, f"legal_notice_{config.AGGREGATOR_SHORT.lower()}.txt", "text/plain", width="stretch")

    with tab4:
        st.markdown("### File on the RBI Complaint Management System")
        steps = [
            ("Open the portal", f"Visit {config.OMBUDSMAN_URL} and choose File a Complaint."),
            ("Verify your identity", "Enter your email or mobile number and complete OTP verification."),
            ("Select the entity", f"Choose the applicable payment-services category and {config.AGGREGATOR_NAME}."),
            ("Enter the complaint", "Paste the reviewed Ombudsman complaint and confirm every factual detail."),
            ("Attach evidence", "Upload your settlement statements, screenshots, KYC submissions, and prior correspondence."),
            ("Save the reference", "Submit the case and retain the Complaint Reference Number for follow-up."),
        ]

        for index, (title, body) in enumerate(steps, 1):
            st.markdown(f'<div class="case-line"><span class="case-number">{index:02}</span><div><strong>{title}</strong><p>{body}</p></div></div>', unsafe_allow_html=True)



with context:
    with panel("Your case at a glance"):
        metric("Days unresolved", str(days_elapsed), issue_date.strftime("Since %d %b %Y"))
        st.caption("RECOMMENDED NEXT STEP")
        st.markdown(f"**{recommended['name']}**")
        st.caption(recommended["contact"])
        if amount:
            metric("Amount in dispute", f"{config.CURRENCY_SYMBOL}{amount}", ISSUE_TYPES[issue_type])
    section_title("Escalation path")
    for tier in ESCALATION_TIERS:
        active = tier["tier"] == recommended["tier"]
        reached = days_elapsed >= tier["trigger_days"]
        status = "Recommended" if active else ("Available" if reached else f"From day {tier['trigger_days']}")
        tone = "good" if active else "info"
        st.markdown(
            f'<div class="case-line {"current" if active else ""}"><span class="case-number">{tier["tier"]:02}</span><div><strong>{html.escape(tier["name"])}</strong><p>{html.escape(tier["description"])}</p>{badge(status, tone)}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("<br>", unsafe_allow_html=True)
    note("Keep the record clear.", "Attach the original support request, the provider’s response, and the relevant transaction records to your correspondence.")

activity_history("agent3")
footer()
