import html
import importlib
import os
import sys

import streamlit as st

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(AGENT_DIR)
for path in (AGENT_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from kyc_agent import KYCDiagnosisAgent
from ticket_drafter import draft_ticket, get_escalation_path
import src.ui as _ui

# Refresh shared presentation helpers when an existing Streamlit session reruns.
importlib.reload(_ui)
from src.ui import app_urls, badge, esc, footer, hero, inject_theme, nav, note, panel, section_title, steps


st.set_page_config(page_title="MerchantOS · KYC & Hold Diagnosis", page_icon="M", layout="wide", initial_sidebar_state="expanded")
inject_theme()
nav("agent1")
urls = app_urls()

CURATED_EVIDENCE = {
    "KYC_WRONG_DOCS": "RBI PA Directions 2025, Para 4.3(ii): GST registration is not mandatory for an unregistered sole proprietor. PAN, Aadhaar, and an accepted form of business proof may complete due diligence.",
    "KYC_MISSING_DOCS": "RBI PA Directions 2025, Paras 4.3–4.6 and 5.4: the payment aggregator must identify acceptable documents and review a complete KYC submission within the applicable turnaround time.",
    "RISK_TXN_SPIKE": "RBI PA Directions 2025, Section 5.2: a risk-based hold should be communicated in writing with the triggering reason, required action, and an estimated resolution timeline.",
    "RISK_CHARGEBACK": "Card-network monitoring and RBI risk governance allow merchants to submit proof of delivery, fulfillment logs, and customer communication to substantiate legitimate transactions.",
    "REGULATORY_LEA": "A freeze arising from a competent authority order is governed by that order. Request the reference, issuing authority, scope, and affected transactions in writing.",
}


def reset_diagnosis() -> None:
    for key in list(st.session_state):
        if key.startswith("a1_"):
            del st.session_state[key]


def initialize() -> None:
    if "a1_agent" not in st.session_state:
        st.session_state.a1_agent = KYCDiagnosisAgent()
        st.session_state.a1_question = st.session_state.a1_agent.reset()
        st.session_state.a1_done = False
        st.session_state.a1_diagnosis = None
        st.session_state.a1_evidence = None
        st.session_state.a1_meta = None
        st.session_state.a1_history = []


def fetch_evidence(diagnosis: dict) -> None:
    evidence = ""
    meta = {"source": "MerchantOS policy library", "similarity": None, "llm_used": False}
    try:
        from src.llm_agent import get_answer as rag_get_answer

        result = rag_get_answer(diagnosis["rag_query"])
        evidence = result.get("answer", "").strip()
        chunks = result.get("chunks", [])
        top = chunks[0] if chunks else {}
        meta = {
            "source": top.get("source", "MerchantOS policy library"),
            "similarity": top.get("similarity"),
            "llm_used": result.get("llm_used", False),
        }
    except Exception:
        pass
    st.session_state.a1_evidence = evidence or CURATED_EVIDENCE.get(diagnosis["hold_reason"], "")
    st.session_state.a1_meta = meta


hero(
    "RECOVERY / COMPLIANCE",
    "Let's get to the source of the hold.",
    "Six short questions. A document checklist and a support request tailored to your situation.",
)
initialize()

if not st.session_state.a1_done:
    q = st.session_state.a1_question
    stage = 0 if q["step"] <= 2 else 1 if q["step"] <= 4 else 2
    steps(["Account status", "Business & activity", "Review & response"], stage)
    form_col, context_col = st.columns([1.65, 1], gap="large")
    with form_col:
        with panel(key="question"):
            st.caption(f'QUESTION {q["step"]:02} OF {q["total"]:02}')
            st.subheader(q["question"])
            st.progress((q["step"] - 1) / q["total"])
            chosen = st.radio("Select the closest answer", q["options"], index=None, key=f'a1_choice_{q["step"]}')
            custom = ""
            custom_selected = chosen and ("something else" in chosen.lower() or "not listed" in chosen.lower())
            if custom_selected:
                custom = st.text_input("Dashboard message", placeholder="Describe the restriction shown on your account", key="a1_custom_description")
            st.divider()
            previous, proceed = st.columns(2)
            with previous:
                if st.button("← Back", disabled=not st.session_state.a1_history, width="stretch"):
                    history = st.session_state.a1_history[:-1]
                    st.session_state.a1_agent = KYCDiagnosisAgent()
                    st.session_state.a1_question = st.session_state.a1_agent.reset()
                    for answer in history:
                        st.session_state.a1_question = st.session_state.a1_agent.step(answer)["next"]
                    st.session_state.a1_history = history
                    st.rerun()
            with proceed:
                if st.button("Prepare my response →" if q["step"] == q["total"] else "Continue →", type="primary", width="stretch", disabled=not chosen or (custom_selected and not custom.strip())):
                    answer = f"Custom Issue: {custom.strip()}" if custom_selected else chosen
                    st.session_state.a1_history.append(answer)
                    result = st.session_state.a1_agent.step(answer)
                    if result["done"]:
                        st.session_state.a1_done = True
                        st.session_state.a1_diagnosis = result["diagnosis"]
                    else:
                        st.session_state.a1_question = result["next"]
                    st.rerun()
    with context_col:
        hints = {
            "dashboard_status": ("Start with what you can see.", "Your dashboard status helps distinguish an account restriction from an individual settlement delay. Keep the exact message handy."),
            "kyc_email": ("The request is part of the evidence.", "Check the latest email from your payment provider. The requested document or verification step helps explain the restriction."),
            "merchant_type": ("The right documents depend on you.", "Choose the legal structure under which you registered your merchant account."),
            "txn_spike": ("Give the activity some context.", "A seasonal sale or a new campaign can change your transaction pattern. Think about the last 30 days."),
            "chargeback": ("Check your dispute notifications.", "Look for chargeback notices or customer dispute messages in your account and email."),
            "days_on_hold": ("Build an accurate timeline.", "Use the date you first noticed the restriction. Keep any support acknowledgements alongside this date."),
        }
        note(*hints.get(q["key"], ("Keep your records nearby.", "Dashboard messages and provider emails will help you choose an answer.")))
        if st.session_state.a1_history:
            with st.expander("Your answers so far", expanded=True):
                for i, answer in enumerate(st.session_state.a1_history, 1):
                    st.caption(f"{i:02} / {answer}")
else:
    diagnosis = st.session_state.a1_diagnosis
    info = diagnosis["hold_info"]
    docs = diagnosis["required_docs"]
    if st.session_state.a1_evidence is None:
        with st.spinner("Preparing your supporting evidence…"):
            fetch_evidence(diagnosis)

    steps(["Account status", "Business & activity", "Review & response"], 3)
    tone = "danger" if info.get("urgency") in ("CRITICAL", "HIGH") else "warn"
    st.markdown(f'<div class="case-line current"><span class="case-number">RESULT</span><div><strong>{esc(info["label"])}</strong><p>{esc(info["description"])}</p>{badge(info.get("urgency", "MEDIUM").title() + " priority", tone)}</div></div>', unsafe_allow_html=True)
    checklist, letter_tab, evidence_tab = st.tabs(["Your action plan", "Support request", "Supporting evidence"])
    with checklist:
        left, right = st.columns([1.5, 1], gap="large")
        with left:
            with panel("Documents to prepare", diagnosis["merchant_type"]):
                st.caption(docs.get("rbi_ref", ""))
                for item in docs.get("mandatory", []):
                    st.checkbox(item, key=f"a1_m_{item}")
                st.markdown("**Provide any one**")
                for item in docs.get("one_of", []):
                    st.checkbox(item, key=f"a1_o_{item}")
                for item in docs.get("not_required", []):
                    st.caption(item)
        with right:
            note("A complete response moves the case forward.", "Collect the relevant documents, review the support request, and replace its placeholders before sending.")
            with st.expander("Escalation roadmap"):
                for item in get_escalation_path():
                    st.markdown(f'**{item["tier"]}. {item["action"]}**')
                    st.caption(item["timeline"])
    with letter_tab:
        with panel("Review your support request", "Edits below are included in your download.", key="doc-preview"):
            ticket = draft_ticket(diagnosis, st.session_state.a1_evidence)
            edited = st.text_area("Support request", value=ticket, height=420, key="a1_ticket_edit", label_visibility="collapsed")
            a, b = st.columns(2)
            a.download_button("Download support request", edited, f"{os.getenv('PAYMENT_AGGREGATOR_SHORT', 'aggregator').lower()}_dispute_ticket.txt", "text/plain", type="primary", width="stretch")
            b.link_button("Open escalation →", urls["agent3"], width="stretch")
    with evidence_tab:
        with panel("Policy evidence"):
            meta = st.session_state.a1_meta or {}
            st.caption(meta.get("source", "MerchantOS policy library"))
            if meta.get("similarity") is not None:
                st.caption(f'Retrieval similarity: {meta["similarity"]:.0%}')
            else:
                st.caption("Local reference summary · live retrieval unavailable")
            st.markdown(st.session_state.a1_evidence)
            if st.button("Refresh evidence"):
                st.session_state.a1_evidence = None
                st.rerun()
            with st.expander("Verification guardrail example"):
                st.caption("Demonstration: requests to waive mandatory identity verification should be redirected to completing the required checks.")
    if st.button("Start another diagnosis"):
        reset_diagnosis()
        st.rerun()

footer()
