import streamlit as st
import sys, os
from datetime import date, timedelta

_AGENT3_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR   = os.path.dirname(_AGENT3_DIR)
if _AGENT3_DIR not in sys.path: sys.path.insert(0, _AGENT3_DIR)
if _ROOT_DIR   not in sys.path: sys.path.insert(1, _ROOT_DIR)

from escalation_agent import EscalationAgent, ISSUE_TYPES, ESCALATION_TIERS

INR = "₹"
HOME_URL   = os.getenv("MERCHANTOS_HOME_URL", "http://localhost:8501")
AGENT1_URL = os.getenv("MERCHANTOS_AGENT1_URL", "http://localhost:8502")
AGENT2_URL = os.getenv("MERCHANTOS_AGENT2_URL", "http://localhost:8503")

st.set_page_config(
    page_title="MerchantOS — Agent 3: Formal Escalation & Legal Bot",
    page_icon="⚖️",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,.stApp { font-family: 'Inter', sans-serif; }
.stApp { background: #070a13; color: #e2e8f0; }

/* Top Nav */
.top-nav {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 24px; background: #0d121f; border-bottom: 1px solid #1e293b;
    border-radius: 12px; margin-bottom: 24px;
}
.nav-brand {
    font-size: 18px; font-weight: 800;
    background: linear-gradient(135deg, #ef4444, #f59e0b);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.nav-link {
    color: #94a3b8; font-size: 13px; text-decoration: none; font-weight: 500;
}
.nav-link:hover { color: #ef4444; }

/* Hero Box */
.hero-box {
    background: linear-gradient(135deg, rgba(239,68,68,0.08) 0%, rgba(245,158,11,0.05) 100%);
    border: 1px solid #1e293b; border-radius: 16px; padding: 24px 28px;
    margin-bottom: 24px;
}
.hero-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(239,68,68,0.12); color: #ef4444; border: 1px solid rgba(239,68,68,0.3);
    padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;
}
.hero-title {
    font-size: 30px; font-weight: 800; color: #f8fafc; line-height: 1.2; margin-bottom: 6px;
}
.hero-sub {
    font-size: 14px; color: #94a3b8; max-width: 820px; line-height: 1.5;
}

/* Tier Cards */
.tier-card {
    background: #0d1322; border-radius: 14px; padding: 18px 22px;
    border: 1px solid #1e293b; border-left: 4px solid transparent;
    margin: 10px 0; transition: all 0.25s ease;
}
.tier-active   { border-left-color: #ef4444; box-shadow: 0 4px 20px rgba(239,68,68,0.12); }
.tier-done     { border-left-color: #10b981; }
.tier-upcoming { border-left-color: #334155; opacity: 0.7; }

.badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
}
.badge-active   { background: rgba(239,68,68,0.2);  color: #ef4444; border: 1px solid rgba(239,68,68,0.4); }
.badge-done     { background: rgba(16,185,129,0.2); color: #10b981; border: 1px solid rgba(16,185,129,0.4); }
.badge-upcoming { background: rgba(100,116,139,0.2); color: #94a3b8; border: 1px solid rgba(100,116,139,0.4); }

/* Steps */
.step-box {
    background: #0b1120; border-radius: 12px; padding: 16px 20px;
    border: 1px solid #1e293b; margin: 10px 0;
}
.step-num {
    background: linear-gradient(135deg, #ef4444, #f59e0b);
    border-radius: 50%; width: 28px; height: 28px;
    font-size: 13px; font-weight: 800; color: #000;
    display: flex; align-items: center; justify-content: center;
    line-height: 28px; text-align: center; flex-shrink: 0;
}

/* Checklist */
.evidence-item {
    background: #0b1120; border-radius: 10px; padding: 12px 16px;
    margin: 6px 0; display: flex; align-items: center; gap: 12px;
    font-size: 13px; color: #cbd5e1; border: 1px solid #1e293b;
}

/* Buttons */
div[data-testid="stButton"] > button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: 12px 18px !important;
    transition: all 0.25s ease !important;
    background: linear-gradient(135deg, #7f1d1d, #ef4444) !important;
    color: #ffffff !important;
    border: none !important;
}
div[data-testid="stDownloadButton"] > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border: 1px solid #334155 !important;
    background: #0f172a !important;
    color: #f8fafc !important;
}
</style>
""", unsafe_allow_html=True)

# Top Nav
st.markdown(f"""
<div class='top-nav'>
  <div class='nav-brand'>⚖️ MerchantOS &nbsp;|&nbsp; Agent 3</div>
  <div>
    <a class='nav-link' href='{HOME_URL}' target='_blank'>← Command Center</a> &nbsp;&nbsp;|&nbsp;&nbsp;
    <a class='nav-link' href='{AGENT1_URL}' target='_blank'>Agent 1: KYC</a> &nbsp;&nbsp;|&nbsp;&nbsp;
    <a class='nav-link' href='{AGENT2_URL}' target='_blank'>Agent 2: Reconciliation</a>
  </div>
</div>
""", unsafe_allow_html=True)

# Hero
st.markdown("""
<div class='hero-box'>
  <div class='hero-badge'>Statutory Grievance & Escalation Copilot</div>
  <div class='hero-title'>Formal Grievance, Ombudsman & Resolution Copilot</div>
  <div class='hero-sub'>
    Structured escalation copilot for unresolved merchant disputes. Tracks statutory timelines, verifies jurisdictional eligibility under the RBI Integrated Ombudsman Scheme, and auto-generates formal grievance letters and legal notices.
  </div>
</div>
""", unsafe_allow_html=True)

agent = EscalationAgent()

st.markdown("### 👤 Step 1: Merchant Credentials")
col_m1, col_m2 = st.columns(2)
with col_m1:
    merchant_name = st.text_input("Full Name *", placeholder="e.g. Rahul Sharma")
    business_name = st.text_input("Business / Legal Entity Name *", placeholder="e.g. ShopEasy Retail Pvt Ltd")
    merchant_id   = st.text_input("Razorpay Merchant ID (MID) *", placeholder="e.g. M_ABC123XYZ")
with col_m2:
    email   = st.text_input("Registered Email Address *", placeholder="e.g. accounts@shopeasy.com")
    phone   = st.text_input("Phone Number *", placeholder="e.g. +91 9876543210")
    state   = st.text_input("State / UT", placeholder="e.g. Karnataka")
    address = st.text_area("Registered Business Address (for legal notice)", placeholder="e.g. 102, Tech Park, Indiranagar, Bengaluru - 560038", height=68)

st.markdown("---")
st.markdown("### 📋 Step 2: Dispute Parameters")
col_i1, col_i2 = st.columns(2)
with col_i1:
    issue_type_key = st.selectbox(
        "Dispute Category *",
        options=list(ISSUE_TYPES.keys()),
        format_func=lambda k: ISSUE_TYPES[k],
    )
    amount = st.text_input(f"Disputed Amount ({INR})", placeholder="e.g. 45000.00")
    txn_ids = st.text_input("Affected Transaction / Order IDs", placeholder="e.g. pay_Nabc123, pay_Nxyz789")
with col_i2:
    issue_date = st.date_input("When did this hold / delay commence? *", value=date.today() - timedelta(days=12))
    grievance_ref = st.text_input("Previous Support / Grievance Ticket ID (if any)", placeholder="e.g. RZP_TICKET_98765")

description = st.text_area(
    "Detailed Chronological Summary of the Issue *",
    placeholder="e.g. On Jan 10, Razorpay suspended settlements without sending prior notice. We have delivered all items and submitted invoices. Support ticket #123 has remained unaddressed for 12 days...",
    height=100,
)

timeline_text = st.text_area(
    "Key Event Milestones (one per line, format: 'YYYY-MM-DD: Event')",
    placeholder=f"{date.today() - timedelta(days=12)}: Settlements paused by Razorpay\n{date.today() - timedelta(days=10)}: Submitted delivery proofs via portal\n{date.today() - timedelta(days=5)}: Sent follow-up to support team\n{date.today()}: No resolution provided",
    height=90,
)

days_elapsed = agent.calculate_days(issue_date)
recommended  = agent.recommend_tier(days_elapsed)
timeline_events = [l.strip() for l in timeline_text.strip().splitlines() if l.strip()]
evidence_list   = agent.get_evidence_checklist(issue_type_key)

merchant = {
    "name":          merchant_name or "[YOUR NAME]",
    "business_name": business_name or "[YOUR BUSINESS NAME]",
    "merchant_id":   merchant_id   or "[YOUR MERCHANT ID]",
    "email":         email         or "[YOUR REGISTERED EMAIL]",
    "phone":         phone         or "[YOUR REGISTERED PHONE]",
    "state":         state         or "[YOUR STATE]",
    "address":       address       or "[YOUR REGISTERED ADDRESS]",
}
issue = {
    "issue_type":          issue_type_key,
    "first_reported_date": issue_date.strftime("%d %B %Y"),
    "days_elapsed":        days_elapsed,
    "amount":              amount or "N/A",
    "txn_ids":             txn_ids or "As per attached statement",
    "description":         description or "Settlement hold without statutory justification.",
    "timeline":            timeline_events if timeline_events else ["Issue initiated without prior written communication."],
    "grievance_ref":       grievance_ref or "",
}

st.markdown("---")

# TIMELINE & PATH
col_time, col_tiers = st.columns([1, 2])
with col_time:
    dc = "#10b981" if days_elapsed < 5 else ("#f59e0b" if days_elapsed < 30 else "#ef4444")
    st.markdown(f"""
    <div style='background:#0d1322;border:1px solid #1e293b;border-radius:16px;padding:26px;text-align:center;'>
      <div style='font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;font-weight:700;'>Resolution Timeline</div>
      <div style='font-size:58px;font-weight:900;color:{dc};line-height:1;margin:12px 0 4px;'>{days_elapsed}</div>
      <div style='font-size:13px;color:{dc};font-weight:600;'>Days Unresolved</div>
      <div style='margin-top:16px;font-size:12px;color:#64748b;'>Commenced: {issue_date.strftime("%d %b %Y")}</div>
      <div style='margin-top:14px;padding:10px 14px;background:rgba(239,68,68,0.12);border-radius:10px;font-size:13px;font-weight:700;color:{dc};border:1px solid rgba(239,68,68,0.3)'>
        Recommended: {recommended['name']}
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_tiers:
    st.markdown("### Statutory Escalation Stages")
    for tier in agent.get_all_tiers():
        status_cls = "tier-upcoming"
        badge_cls  = "badge-upcoming"
        badge_txt  = "Upcoming"
        if days_elapsed >= tier["trigger_days"]:
            dl = tier.get("deadline_days")
            if dl and days_elapsed >= dl:
                status_cls, badge_cls, badge_txt = "tier-done", "badge-done", "Eligible / Overdue"
            else:
                status_cls, badge_cls, badge_txt = "tier-active", "badge-active", "ACTIVE NOW"

        st.markdown(f"""
        <div class='tier-card {status_cls}'>
          <div style='display:flex;justify-content:space-between;align-items:center'>
            <span style='font-size:16px;font-weight:700;color:#f8fafc'>Tier {tier['tier']}: {tier['name']}</span>
            <span class='badge {badge_cls}'>{badge_txt}</span>
          </div>
          <div style='font-size:13px;color:#94a3b8;margin:6px 0'>{tier['description']}</div>
          <div style='font-size:11px;color:#64748b'>Filing Target: <strong style='color:#cbd5e1'>{tier['contact']}</strong></div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# EVIDENCE CHECKLIST
st.markdown("### 📎 Evidence Dossier Checklist")
st.caption(f"Required documentation for **{ISSUE_TYPES[issue_type_key]}** claims:")
for ev in evidence_list:
    st.markdown(f"""
    <div class='evidence-item'>
      <span style='color:#10b981;font-size:16px;font-weight:700'>✓</span>
      <span>{ev}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# FORMAL LETTER GENERATOR
st.markdown("### 📝 Auto-Drafted Statutory Notice & Letter Suite")

tab1, tab2, tab3, tab4 = st.tabs([
    "📬 Tier 2: Grievance Officer Letter",
    "🏛️ Tier 3: RBI Ombudsman Complaint",
    "⚖️ Tier 4: Formal Legal Notice",
    "📘 Step-by-Step RBI Portal Filing Walkthrough"
])

with tab1:
    st.markdown("#### Razorpay Principal Grievance Officer Letter (Tier 2)")
    st.caption("Mandated per RBI PA Directions 2025 Para 8. Deliverable after 5 business days without normal support resolution.")
    letter1 = agent.draft_grievance_letter(merchant, issue)
    st.text_area("Letter Text", value=letter1, height=350, key="let1")
    st.download_button("⬇️ Download Grievance Letter (.txt)", data=letter1, file_name="razorpay_grievance_letter.txt", mime="text/plain", use_container_width=True)

with tab2:
    st.markdown("#### Complaint to RBI Integrated Ombudsman (Tier 3)")
    st.caption("Filing format adhering to RBI Integrated Ombudsman Scheme (portal: cms.rbi.org.in).")
    st.markdown("""
    <div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);border-radius:10px;padding:12px 16px;margin-bottom:14px;font-size:12px;color:#fde68a'>
      <strong>⚖️ Statutory Jurisdiction Note:</strong> The Ombudsman Scheme excludes complaints solely challenging an aggregator's commercial risk judgment or underwriting discretion. Filing is valid on <em>procedural grounds</em>: failure to communicate reasons in writing within 24 hours, withholding settlements beyond statutory TAT, or failing to resolve grievances within 30 days.
    </div>
    """, unsafe_allow_html=True)
    letter2 = agent.draft_rbi_ombudsman_complaint(merchant, issue)
    st.text_area("Ombudsman Complaint Text", value=letter2, height=350, key="let2")
    st.download_button("⬇️ Download Ombudsman Complaint (.txt)", data=letter2, file_name="rbi_ombudsman_complaint.txt", mime="text/plain", use_container_width=True)

with tab3:
    st.markdown("#### Legal Notice under Consumer Protection Act 2019 (Tier 4)")
    st.caption("For prolonged freezes exceeding 90 days or large frozen capital amounts.")
    letter3 = agent.draft_legal_notice(merchant, issue)
    st.text_area("Legal Notice Text", value=letter3, height=350, key="let3")
    st.download_button("⬇️ Download Legal Notice (.txt)", data=letter3, file_name="legal_notice_razorpay.txt", mime="text/plain", use_container_width=True)

with tab4:
    st.markdown("#### How to File on cms.rbi.org.in in 8 Minutes")
    steps = [
        ("Access Portal", "Open <strong>cms.rbi.org.in</strong> and click on <em>'File a Complaint'</em>."),
        ("Merchant Authentication", "Enter mobile number / email and verify via SMS OTP."),
        ("Entity Selection", "Select Entity Category: <strong>Payment Aggregator / Pre-paid Instruments</strong>."),
        ("Select Regulated Entity", "Search for <strong>'Razorpay Software Private Limited'</strong> (CIN: U72200KA2013PTC069276)."),
        ("Enter Complaint Narrative", "Copy the Ombudsman Complaint text generated in Tab 2 and paste into the description field."),
        ("Upload Document Evidence", "Attach screenshots, settlement statements, and KYC submissions as PDF attachments."),
        ("Obtain CRN", "Submit and record your <strong>Complaint Reference Number (CRN)</strong> for statutory tracking."),
    ]
    for i, (ttl, desc) in enumerate(steps, 1):
        st.markdown(f"""
        <div class='step-box'>
          <div style='display:flex;align-items:flex-start;gap:14px'>
            <div class='step-num'>{i}</div>
            <div>
              <div style='font-size:14px;font-weight:700;color:#f8fafc;margin-bottom:4px'>{ttl}</div>
              <div style='font-size:13px;color:#94a3b8;line-height:1.5'>{desc}</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
