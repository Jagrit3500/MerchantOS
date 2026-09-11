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

from src import config
import src.activity_history as _activity_history
importlib.reload(_activity_history)
from src.activity_history import read_activity, record_activity
import src.embedder as _embedder
if not hasattr(_embedder, "reconnect_chroma_client"):
    importlib.reload(_embedder)
import src.retriever as _retriever
import src.policy_evidence as _policy_evidence
import kyc_agent as _kyc_agent
import ticket_drafter as _ticket_drafter
import src.ui as _ui

# Refresh local workflow and presentation modules when an existing Streamlit
# process notices source changes. Streamlit otherwise keeps these imports cached.
importlib.reload(_kyc_agent)
importlib.reload(_ticket_drafter)
importlib.reload(_retriever)
importlib.reload(_policy_evidence)
importlib.reload(_ui)
from kyc_agent import KYCDiagnosisAgent, QUESTIONS
from ticket_drafter import draft_ticket, get_escalation_path
get_policy_evidence = _policy_evidence.get_policy_evidence
from src.ui import activity_history, app_urls, badge, esc, footer, inject_theme, nav, note, panel, require_auth, same_tab_link, section_title, steps


st.set_page_config(page_title="MerchantOS · KYC & Hold Diagnosis", page_icon="M", layout="wide", initial_sidebar_state="expanded")
inject_theme()
require_auth("agent1")
nav("agent1")
urls = app_urls()
aggregator_kyc_url = getattr(
    config,
    "AGGREGATOR_KYC_URL",
    "",
)
FLOW_VERSION = "2026-09-12.4"

def reset_diagnosis() -> None:
    for key in list(st.session_state):
        if key.startswith("a1_"):
            del st.session_state[key]


def initialize() -> None:
    if st.session_state.get("a1_flow_version") != FLOW_VERSION:
        reset_diagnosis()
        st.session_state.a1_flow_version = FLOW_VERSION
    if "a1_agent" not in st.session_state:
        st.session_state.a1_agent = KYCDiagnosisAgent()
        st.session_state.a1_question = st.session_state.a1_agent.reset()
        st.session_state.a1_done = False
        st.session_state.a1_diagnosis = None
        st.session_state.a1_evidence = None
        st.session_state.a1_meta = None
        st.session_state.a1_history = []
        st.session_state.a1_evidence_refreshes = 0
        st.session_state.a1_refresh_notice = None
        st.session_state.a1_loaded_activity_id = None
    if "a1_refresh_notice" not in st.session_state:
        st.session_state.a1_refresh_notice = None


def restore_activity_route() -> str | None:
    """Restore an owned saved diagnosis selected from this workspace's history."""
    raw_activity_id = st.query_params.get("activity")
    loaded_activity_id = st.session_state.get("a1_loaded_activity_id")

    def reject_route(message: str) -> str:
        st.query_params.pop("activity", None)
        reset_diagnosis()
        initialize()
        return message

    if not raw_activity_id:
        if loaded_activity_id is not None:
            reset_diagnosis()
            initialize()
        return None
    try:
        activity_id = int(raw_activity_id)
        if activity_id < 1:
            raise ValueError
    except (TypeError, ValueError):
        return reject_route("This saved-diagnosis link is invalid.")
    if loaded_activity_id == activity_id:
        return None

    user_id = st.session_state.get("merchantos_user", {}).get("id", "local")
    entry = read_activity(user_id, activity_id, section="agent1")
    answers = entry.get("metadata", {}).get("answers") if entry else None
    if not isinstance(answers, list) or len(answers) != len(QUESTIONS):
        return reject_route("This saved diagnosis is unavailable or does not contain a complete answer record.")

    agent = KYCDiagnosisAgent()
    result = None
    try:
        for answer in answers:
            result = agent.step(str(answer))
    except (RuntimeError, ValueError):
        return reject_route("This saved diagnosis cannot be reopened with the current questionnaire.")
    if not result or not result.get("done"):
        return reject_route("This saved diagnosis is incomplete.")

    reset_diagnosis()
    initialize()
    st.session_state.a1_agent = agent
    st.session_state.a1_history = list(answers)
    st.session_state.a1_done = True
    st.session_state.a1_diagnosis = result["diagnosis"]
    st.session_state.a1_evidence = None
    st.session_state.a1_meta = None
    st.session_state.a1_evidence_refreshes = 0
    st.session_state.a1_refresh_notice = None
    st.session_state.a1_loaded_activity_id = activity_id
    return None


def action_plan_copy(hold_reason: str) -> dict:
    if hold_reason in {"KYC_ACTION_REQUIRED", "KYC_DOCUMENT_CLARIFICATION"}:
        return {
            "title": "Documents to prepare",
            "guidance": "Preparation aid only - the current dashboard and provider checklist control the documents for this account.",
            "core": "Core records to prepare",
            "optional": "Case-dependent records - provide only if applicable or requested",
            "show_kyc_link": True,
        }
    if hold_reason == "REGULATORY_LEA":
        return {
            "title": "Evidence to preserve",
            "guidance": "Keep original notices, screenshots, identifiers, and communications. An authority order may limit what the provider can disclose.",
            "core": "Core evidence to preserve",
            "optional": "Additional records - include only if available or relevant",
            "show_kyc_link": False,
        }
    if hold_reason == "SETTLEMENT_DELAY":
        return {
            "title": "Records to reconcile",
            "guidance": "Compare the provider report, bank statement, dashboard timeline, and merchant agreement before assigning a cause.",
            "core": "Core settlement records",
            "optional": "Additional records - include where applicable",
            "show_kyc_link": False,
        }
    if hold_reason == "RESTRICTION_UNCONFIRMED":
        return {
            "title": "Evidence to collect",
            "guidance": "Preserve the exact dashboard status and provider communications. Ask for the reason before choosing a remediation path.",
            "core": "Core records to collect",
            "optional": "Additional records - include where relevant",
            "show_kyc_link": False,
        }
    return {
        "title": "Evidence to prepare",
        "guidance": "Keep records tied to the affected transactions and ask the provider to confirm the reason and remediation criteria.",
        "core": "Core case evidence",
        "optional": "Additional records - include where applicable",
        "show_kyc_link": False,
    }


def evidence_signature(result: dict | None) -> tuple:
    """Identify substantive retrieval output while ignoring the check timestamp."""
    result = result or {}
    confidence = result.get("confidence") or {}
    chunks = result.get("chunks") or []
    return (
        result.get("answer", ""),
        result.get("source", ""),
        confidence.get("score"),
        result.get("confidence_method", ""),
        tuple(
            (
                chunk.get("source", ""),
                chunk.get("page", ""),
                chunk.get("similarity", chunk.get("relevance", "")),
                chunk.get("text", ""),
            )
            for chunk in chunks
        ),
    )


def fetch_evidence(
    diagnosis: dict,
    use_semantic_retrieval: bool = False,
    reconnect_index: bool = False,
) -> dict:
    result = get_policy_evidence(
        diagnosis["rag_query"],
        semantic=use_semantic_retrieval,
        reconnect_index=reconnect_index,
    )
    st.session_state.a1_evidence = result.get("answer", "").strip()
    st.session_state.a1_meta = result
    return result


def question_progress(step: int, total: int) -> str:
    """Render a compact, accessible step rail for the active questionnaire."""
    segments = "".join(
        f'<span class="{"done" if number < step else "current" if number == step else "upcoming"}">'
        f'<b>{number:02}</b><i></i></span>'
        for number in range(1, total + 1)
    )
    return (
        f'<div class="question-progress" style="--question-total:{total}" role="progressbar" aria-valuemin="1" '
        f'aria-valuemax="{total}" aria-valuenow="{step}" aria-label="Question {step} of {total}">'
        f'{segments}</div>'
    )


def render_checklist_group(title: str, items: list[str], key_prefix: str, group_number: int) -> None:
    """Present dynamic checklist items as balanced, responsive document cards."""
    if not items:
        return
    st.markdown(
        '<div class="checklist-group-heading">'
        f'<span>{group_number:02}</span><div><small>RECORD GROUP</small><h4>{esc(title)}</h4></div>'
        f'<b>{len(items)} item{"s" if len(items) != 1 else ""}</b></div>',
        unsafe_allow_html=True,
    )
    with st.container(key=f"a1_checklist_{key_prefix}"):
        for offset in range(0, len(items), 2):
            columns = st.columns(2, gap="small")
            for column, item in zip(columns, items[offset : offset + 2]):
                with column:
                    st.checkbox(item, key=f"a1_{key_prefix}_{item}")


def render_workspace_header() -> None:
    completed = st.session_state.a1_done
    reopened = st.session_state.get("a1_loaded_activity_id") is not None
    title = "Your recovery brief is ready." if completed else "Turn the hold into a clear next step."
    description = (
        "Review the decision, prepare the right records, and use source-linked evidence before contacting support."
        if completed
        else f"Answer {len(QUESTIONS)} focused questions to build a document checklist, evidence trail, and editable support request."
    )
    mode = "Saved diagnosis reopened" if reopened else "Assessment complete" if completed else "Guided recovery workspace"
    st.markdown(
        f'<header class="agent1-hero {"completed" if completed else "active"}">'
        '<div class="agent1-hero-copy">'
        f'<div class="eyebrow">{esc(config.AGGREGATOR_SHORT)} / RECOVERY INTELLIGENCE</div>'
        f'<h1>{esc(title)}</h1><p>{esc(description)}</p>'
        '<div class="agent1-hero-chips">'
        f'<span><i></i>{len(QUESTIONS)} guided checks</span>'
        '<span><i></i>Source-linked evidence</span>'
        '<span><i></i>Editable response brief</span>'
        '</div></div>'
        '<div class="agent1-orbit" aria-hidden="true">'
        '<span class="orbit orbit-one"></span><span class="orbit orbit-two"></span>'
        '<span class="orbit-dot dot-one"></span><span class="orbit-dot dot-two"></span><span class="orbit-dot dot-three"></span>'
        '<div class="orbit-core"><small>CASE</small><strong>01</strong></div>'
        f'<div class="orbit-label"><i></i>{esc(mode)}</div>'
        '</div></header>',
        unsafe_allow_html=True,
    )


initialize()
activity_route_error = restore_activity_route()
if activity_route_error:
    st.warning(activity_route_error)
render_workspace_header()

if not st.session_state.a1_done:
    q = st.session_state.a1_question
    stage = 0 if q["step"] <= 2 else 1 if q["step"] <= 4 else 2
    steps(["Account status", "Business & activity", "Review & response"], stage)
    form_col, context_col = st.columns([1.65, 1], gap="large")
    with form_col:
        with panel(key="question"):
            progress_percent = round(q["step"] / q["total"] * 100)
            st.markdown(
                '<div class="question-meta">'
                f'<span><i></i>Question {q["step"]:02} of {q["total"]:02}</span>'
                f'<b>{progress_percent}% complete</b></div>',
                unsafe_allow_html=True,
            )
            st.subheader(q["question"])
            st.markdown(question_progress(q["step"], q["total"]), unsafe_allow_html=True)
            chosen = st.radio("Select the closest answer", q["options"], index=None, key=f'a1_choice_{q["step"]}')
            custom = ""
            custom_selected = chosen and ("something else" in chosen.lower() or "not listed" in chosen.lower())
            if custom_selected:
                custom = st.text_input(
                    "Dashboard message",
                    placeholder="Describe the restriction shown on your account",
                    max_chars=_kyc_agent.CUSTOM_ISSUE_MAX_LENGTH,
                    key="a1_custom_description",
                )
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
                        diagnosis = result["diagnosis"]
                        info = diagnosis["hold_info"]
                        record_activity(
                            st.session_state.merchantos_user.get("id", "local"),
                            "agent1",
                            "diagnosis_completed",
                            info["label"],
                            f'{info.get("urgency", "MEDIUM").title()} priority · {diagnosis["merchant_type"]}',
                            {"answers": list(st.session_state.a1_history)},
                        )
                    else:
                        st.session_state.a1_question = result["next"]
                    st.rerun()
    with context_col:
        hints = {
            "dashboard_status": ("Start with what you can see.", "Your dashboard status helps distinguish an account restriction from an individual settlement delay. Keep the exact message handy."),
            "kyc_email": ("The request is part of the evidence.", "Check the latest email from your payment provider. The requested document or verification step helps explain the restriction."),
            "merchant_type": ("The right documents depend on you.", "Choose the legal structure under which you registered your merchant account."),
            "txn_spike": ("Give the activity some context.", f"A seasonal sale or a new campaign can change your transaction pattern. Think about the last {config.TRANSACTION_LOOKBACK_DAYS} days."),
            "chargeback": ("Check your dispute notifications.", "Look for chargeback notices or customer dispute messages in your account and email."),
            "days_on_hold": ("Build an accurate timeline.", "Use the date you first noticed the restriction. Keep any support acknowledgements alongside this date."),
        }
        note(*hints.get(q["key"], ("Keep your records nearby.", "Dashboard messages and provider emails will help you choose an answer.")))
        roadmap_items = []
        for item_index, item_label in enumerate(("Identify the signal", "Add business context", "Prepare the response")):
            item_state = "complete" if item_index < stage else "current" if item_index == stage else "upcoming"
            item_mark = "✓" if item_index < stage else str(item_index + 1).zfill(2)
            roadmap_items.append(
                f'<div class="mini-roadmap-item {item_state}"><span>{item_mark}</span><div><strong>{esc(item_label)}</strong>'
                f'<small>{"Ready" if item_index < stage else "In progress" if item_index == stage else "Up next"}</small></div></div>'
            )
        st.markdown(
            '<div class="mini-roadmap"><div class="mini-roadmap-heading"><span>YOUR ROUTE</span>'
            '<b>From signal to response</b></div>' + "".join(roadmap_items) + '</div>',
            unsafe_allow_html=True,
        )
        if st.session_state.a1_history:
            answer_count = len(st.session_state.a1_history)
            with st.container(key="answer-recap"):
                with st.expander(
                    f'Your answers so far · {answer_count} recorded',
                    expanded=False,
                ):
                    for i, answer in enumerate(st.session_state.a1_history, 1):
                        st.caption(f"{i:02} / {answer}")
else:
    diagnosis = st.session_state.a1_diagnosis
    info = diagnosis["hold_info"]
    docs = diagnosis["required_docs"]
    plan_copy = action_plan_copy(diagnosis["hold_reason"])
    if st.session_state.a1_evidence is None:
        with st.spinner("Preparing your supporting evidence…"):
            fetch_evidence(diagnosis, use_semantic_retrieval=config.AUTO_FETCH_POLICY_EVIDENCE)
    if st.session_state.a1_refresh_notice:
        st.toast(st.session_state.a1_refresh_notice)
        st.session_state.a1_refresh_notice = None

    steps(["Account status", "Business & activity", "Review & response"], 3)
    tone = "danger" if info.get("urgency") in ("CRITICAL", "HIGH") else "warn"
    result_mode = "Saved case" if st.session_state.get("a1_loaded_activity_id") else "Current case"
    st.markdown(
        f'<section class="diagnosis-hero {tone}"><div class="diagnosis-signal"><span></span><i></i><b></b></div>'
        '<div class="diagnosis-copy"><div class="diagnosis-kicker">ASSESSMENT RESULT</div>'
        f'<h2>{esc(info["label"])}</h2><p>{esc(info["description"])}</p></div>'
        '<div class="diagnosis-meta">'
        f'<div><small>Priority</small><strong>{esc(info.get("urgency", "MEDIUM").title())}</strong></div>'
        f'<div><small>Entity</small><strong>{esc(diagnosis["merchant_type"])}</strong></div>'
        f'<div><small>Workspace</small><strong>{esc(result_mode)}</strong></div>'
        '</div></section>',
        unsafe_allow_html=True,
    )
    checklist, letter_tab, evidence_tab = st.tabs(["Your action plan", "Support request", "Supporting evidence"])
    with checklist:
        left, right = st.columns([1.5, 1], gap="large")
        with left:
            with panel(plan_copy["title"], diagnosis["merchant_type"], key="action-plan"):
                st.markdown(
                    '<div class="plan-brief">'
                    '<div><span>POLICY BASELINE</span>'
                    f'<p>{esc(docs.get("rbi_ref", ""))}</p></div>'
                    '<div><span>PREPARATION NOTE</span>'
                    f'<p>{esc(plan_copy["guidance"])}</p></div></div>',
                    unsafe_allow_html=True,
                )
                if plan_copy["show_kyc_link"] and aggregator_kyc_url:
                    st.markdown(f"[Check current {config.AGGREGATOR_SHORT} KYC requirements]({aggregator_kyc_url})")
                render_checklist_group(plan_copy["core"], docs.get("mandatory", []), "m", 1)
                render_checklist_group(plan_copy["optional"], docs.get("one_of", []), "o", 2)
                if docs.get("not_required"):
                    st.markdown(
                        '<div class="qualification-heading"><span>!</span><strong>Important qualification</strong></div>',
                        unsafe_allow_html=True,
                    )
                for item in docs.get("not_required", []):
                    st.caption(item)
        with right:
            note("A complete response moves the case forward.", "Collect the relevant documents, review the support request, and replace its placeholders before sending.")
            with st.container(key="escalation-roadmap"):
                with st.expander("Escalation roadmap"):
                    for item in get_escalation_path():
                        st.markdown(f'**{item["tier"]}. {item["action"]}**')
                        st.caption(item["timeline"])
    with letter_tab:
        with panel("Review your support request", "Edits below are included in your download.", key="doc-preview"):
            st.markdown(
                '<div class="draft-status"><span><i></i>Editable draft</span>'
                '<span>Replace placeholders before sending</span><span>Download as plain text</span></div>',
                unsafe_allow_html=True,
            )
            ticket = draft_ticket(diagnosis)
            edited = st.text_area("Support request", value=ticket, height=420, key="a1_ticket_edit", label_visibility="collapsed")
            a, b = st.columns(2)
            a.download_button("Download support request", edited, f"{config.AGGREGATOR_SHORT.lower()}_dispute_ticket.txt", "text/plain", type="primary", width="stretch")
            with b:
                same_tab_link("Open escalation →", urls["agent3"])
    with evidence_tab:
        with panel("Policy evidence", key="evidence-panel"):
            meta = st.session_state.a1_meta or {}
            confidence = meta.get("confidence") or {"score": 0.0, "label": "none"}
            score = float(confidence.get("score") or 0)
            label = str(confidence.get("label") or "none").title()
            confidence_tone = "good" if label == "High" else "warn" if label == "Medium" else "danger"
            score_degrees = max(0, min(round(score * 360), 360))
            st.markdown(
                '<div class="evidence-overview">'
                f'<div class="evidence-ring {confidence_tone}" style="--evidence-score:{score_degrees}deg">'
                f'<div><strong>{score:.0%}</strong><small>{esc(label)}</small></div></div>'
                '<div class="evidence-overview-copy"><span>RETRIEVAL CONFIDENCE</span>'
                f'<h3>Evidence match: {score:.0%} · {esc(label)}</h3>'
                '<p>Similarity between this case query and the strongest indexed policy passage.</p></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                f'{meta.get("retrieval", "Local document search")} · '
                f'{meta.get("confidence_method", "Retrieval relevance")} · '
                f'Checked {meta.get("checked_at", "now")}'
            )
            st.caption(f'Sources: {meta.get("source", "Local policy library")}')
            st.caption("The score measures query-to-source relevance; it is not legal certainty or diagnosis probability.")
            if meta.get("status"):
                st.info(meta["status"])
            st.markdown(st.session_state.a1_evidence)
            st.caption(
                "Refresh runs the same deterministic query again. The score normally stays the same "
                "until the diagnosis query or indexed policy files change."
            )
            if st.button("Refresh evidence"):
                with st.spinner("Searching the policy library…"):
                    previous_signature = evidence_signature(st.session_state.a1_meta)
                    refreshed = fetch_evidence(
                        diagnosis,
                        use_semantic_retrieval=True,
                        reconnect_index=True,
                    )
                    st.session_state.a1_evidence_refreshes += 1
                    refresh_number = st.session_state.a1_evidence_refreshes
                    if evidence_signature(refreshed) == previous_signature:
                        st.session_state.a1_refresh_notice = (
                            f"Recheck {refresh_number} completed. The evidence and match score are unchanged "
                            "because the diagnosis query and indexed sources are unchanged."
                        )
                    else:
                        st.session_state.a1_refresh_notice = (
                            f"Recheck {refresh_number} completed. The retrieved evidence or match score changed."
                        )
                st.rerun()
            with st.expander("Verification guardrail example"):
                st.caption("Demonstration: requests to waive mandatory identity verification should be redirected to completing the required checks.")
    if st.button("Start another diagnosis"):
        st.query_params.clear()
        reset_diagnosis()
        st.rerun()

if not st.session_state.a1_done:
    activity_history("agent1")
footer()
