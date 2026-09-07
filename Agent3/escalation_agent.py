"""
MerchantOS - Agent 3: Formal Escalation & Recovery Bot
Generates RBI-cited formal escalation letters, tracks timelines, recommends next steps.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta

# ─── Escalation tiers (RBI / Consumer Protection Act based) ───────────────────
import os
_agg_name = os.getenv("PAYMENT_AGGREGATOR_NAME", "Razorpay Software Private Limited")
_agg_short = os.getenv("PAYMENT_AGGREGATOR_SHORT", "Razorpay")
_grievance_email = os.getenv("PAYMENT_AGGREGATOR_GRIEVANCE_EMAIL", "grievance.officer@razorpay.com")
_support_url = os.getenv("PAYMENT_AGGREGATOR_SUPPORT_URL", "razorpay.com/support")

ESCALATION_TIERS = [
    {
        "tier": 1,
        "name": f"{_agg_short} Support",
        "trigger_days": 0,
        "deadline_days": 5,
        "description": f"First point of contact. File via {_support_url} or in-app chat.",
        "contact": _support_url,
        "rbi_ref": None,
    },
    {
        "tier": 2,
        "name": f"{_agg_short} Grievance Officer",
        "trigger_days": 5,
        "deadline_days": 30,
        "description": f"If not resolved within 5 business days, escalate to {_agg_short} Grievance Officer.",
        "contact": _grievance_email,
        "rbi_ref": "RBI PA Directions 2025, Para 8 - Grievance Redressal",
    },
    {
        "tier": 3,
        "name": "RBI Integrated Ombudsman",
        "trigger_days": 30,
        "deadline_days": 365,
        "description": "File complaint on cms.rbi.org.in under RBI Integrated Ombudsman Scheme. Valid on procedural grounds (TAT breach, lack of written notice, or arbitrary hold).",
        "contact": "https://cms.rbi.org.in",
        "rbi_ref": "RBI Integrated Ombudsman Scheme 2021 (RBI/2021-22/20)",
    },
    {
        "tier": 4,
        "name": "Consumer Forum / Legal Notice",
        "trigger_days": 90,
        "deadline_days": None,
        "description": "File consumer complaint under Consumer Protection Act 2019 or send legal notice.",
        "contact": "consumerhelpline.gov.in",
        "rbi_ref": "Consumer Protection Act 2019, Section 2(7)",
    },
]

# ─── Issue types and their RBI references ──────────────────────────────────────
ISSUE_TYPES = {
    "kyc_hold":           "KYC / Account Hold",
    "settlement_hold":    "Settlement Hold / Funds On Hold",
    "settlement_missing": "Missing Settlement",
    "fee_overcharge":     "Fee Overcharge",
    "tat_violation":      "Settlement TAT Violation (Beyond T+2)",
    "account_suspended":  "Account Suspended / Deactivated",
    "chargeback_dispute": "Chargeback / Dispute Handling",
    "other":              "Other",
}

ISSUE_RBI_REFS = {
    "kyc_hold":           "RBI PA Directions 2025, Para 4 - KYC Requirements",
    "settlement_hold":    "RBI PA Directions 2025, Para 5.4 - Settlement Hold",
    "settlement_missing": "RBI PA Directions 2025, Para 5.3 - Settlement Timelines",
    "fee_overcharge":     "RBI PA Directions 2025, Para 6 - Charges",
    "tat_violation":      "RBI PA Directions 2025, Para 5.3 - T+2 Settlement Cycle",
    "account_suspended":  "RBI PA Directions 2025, Para 8.2 - Merchant Rights",
    "chargeback_dispute": "RBI PA Directions 2025, Para 7 - Dispute Resolution",
    "other":              "RBI PA Directions 2025, General Provisions",
}

# ─── Evidence checklist per issue type ─────────────────────────────────────────
EVIDENCE_CHECKLIST = {
    "kyc_hold": [
        f"Screenshot of {_agg_short} dashboard showing the hold",
        "All KYC documents you submitted (PAN, Aadhaar, business registration)",
        f"Email from {_agg_short} requesting documents (if any)",
        "Email showing you submitted the documents",
        "Date you first noticed the hold",
    ],
    "settlement_hold": [
        f"Screenshot of {_agg_short} settlement dashboard showing held status",
        "Transaction IDs of all held transactions",
        "Bank statement showing expected but missing credits",
        f"Any emails from {_agg_short} explaining the hold",
        "Your own order fulfillment records (delivery proof, invoices)",
    ],
    "settlement_missing": [
        f"{_agg_short} settlement report / CSV download",
        "Bank statement for the relevant period",
        "List of transaction IDs with expected settlement dates",
        f"Any {_agg_short} communication about settlement",
    ],
    "fee_overcharge": [
        f"{_agg_short} settlement CSV with fee details",
        f"{_agg_short} published pricing at time of transactions",
        "Your own reconciliation showing overcharge calculation",
        "Transaction IDs where overcharge occurred",
    ],
    "tat_violation": [
        f"{_agg_short} settlement CSV showing transaction dates and settlement dates",
        "Calculation showing days between transaction and settlement",
        "Transaction IDs that exceeded T+2",
    ],
    "account_suspended": [
        "Screenshot of account suspension notice",
        f"Any email from {_agg_short} explaining suspension reason",
        "All previously submitted KYC documents",
        "Business registration / license documents",
    ],
    "chargeback_dispute": [
        "Original transaction details",
        "Proof of delivery / fulfillment",
        "Customer communication records",
        "Refund policy (if applicable)",
        f"{_agg_short} chargeback notification email",
    ],
    "other": [
        "All relevant screenshots",
        f"Email communication with {_agg_short}",
        "Transaction IDs / Order IDs affected",
        "Timeline of events (dates and what happened)",
    ],
}

INR = os.getenv("MERCHANT_CURRENCY_SYMBOL", "\u20b9")


class EscalationAgent:
    """Generates formal escalation letters and recommends escalation path."""

    def recommend_tier(self, days_since_issue: int) -> dict:
        """Return the appropriate escalation tier based on days elapsed."""
        recommended = ESCALATION_TIERS[0]
        for tier in ESCALATION_TIERS:
            if days_since_issue >= tier["trigger_days"]:
                recommended = tier
        return recommended

    def get_all_tiers(self) -> list[dict]:
        return ESCALATION_TIERS

    def get_issue_types(self) -> dict:
        return ISSUE_TYPES

    def get_evidence_checklist(self, issue_type: str) -> list[str]:
        return EVIDENCE_CHECKLIST.get(issue_type, EVIDENCE_CHECKLIST["other"])

    def calculate_days(self, issue_date: date) -> int:
        return (date.today() - issue_date).days

    def draft_grievance_letter(self, merchant: dict, issue: dict) -> str:
        """Draft formal Razorpay Grievance Officer letter (Tier 2)."""
        rbi_ref = ISSUE_RBI_REFS.get(issue["issue_type"], ISSUE_RBI_REFS["other"])
        issue_name = ISSUE_TYPES.get(issue["issue_type"], "Issue")

        lines = [
            f"To,",
            f"The Grievance Officer",
            f"{_agg_name}",
            f"1st Floor, SJR Cyber, 22 Laskar Hosur Road, Bengaluru - 560030",
            f"Email: {_grievance_email}",
            f"",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"Subject: Formal Grievance - {issue_name} (Merchant ID: {merchant['merchant_id']})",
            f"",
            f"Dear Grievance Officer,",
            f"",
            f"I, {merchant['name']}, operating as {merchant['business_name']}, am writing to formally",
            f"escalate an unresolved issue with my {_agg_short} merchant account (ID: {merchant['merchant_id']}).",
            f"",
            f"ISSUE DETAILS:",
            f"  Type: {issue_name}",
            f"  First Reported: {issue['first_reported_date']}",
            f"  Days Elapsed: {issue['days_elapsed']} days",
            f"  Amount Affected: {INR}{issue.get('amount', 'N/A')}",
            f"  Transaction IDs: {issue.get('txn_ids', 'As per attached records')}",
            f"",
            f"TIMELINE OF EVENTS:",
        ]
        for i, event in enumerate(issue.get("timeline", []), 1):
            lines.append(f"  {i}. {event}")
        lines += [
            f"",
            f"REGULATORY BASIS:",
            f"  Per {rbi_ref}, I am entitled to a written",
            f"  explanation and resolution within the stipulated timeline.",
            f"  Per RBI PA Directions 2025, Para 8, {_agg_short} is obligated to",
            f"  resolve grievances within 30 days of receipt.",
            f"",
            f"MY REQUEST:",
            f"  1. Immediate resolution of the above issue",
            f"  2. Written explanation citing the specific reason and RBI provision",
            f"  3. Release of any held funds ({INR}{issue.get('amount', 'N/A')}) within 2 business days",
            f"  4. Confirmation of actions taken via email",
            f"",
            f"If this grievance is not resolved within 7 business days from the date of this letter,",
            f"I will be compelled to file a complaint with the RBI Integrated Ombudsman at cms.rbi.org.in",
            f"under the RBI Integrated Ombudsman Scheme 2021.",
            f"",
            f"Merchant ID:        {merchant['merchant_id']}",
            f"Registered Email:   {merchant['email']}",
            f"Registered Phone:   {merchant['phone']}",
            f"Business Name:      {merchant['business_name']}",
            f"",
            f"Yours sincerely,",
            f"{merchant['name']}",
            f"{merchant['business_name']}",
            f"Date: {date.today().strftime('%d %B %Y')}",
        ]
        return "\n".join(lines)

    def draft_rbi_ombudsman_complaint(self, merchant: dict, issue: dict) -> str:
        """Draft RBI Integrated Ombudsman complaint (Tier 3)."""
        rbi_ref = ISSUE_RBI_REFS.get(issue["issue_type"], ISSUE_RBI_REFS["other"])
        issue_name = ISSUE_TYPES.get(issue["issue_type"], "Issue")

        lines = [
            f"COMPLAINT TO RBI INTEGRATED OMBUDSMAN",
            f"Under: RBI Integrated Ombudsman Scheme 2021 (RBI/2021-22/20)",
            f"Portal: cms.rbi.org.in",
            f"",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"TO: The Ombudsman",
            f"    RBI Integrated Ombudsman Scheme",
            f"    (via online portal: cms.rbi.org.in)",
            f"",
            f"SECTION A - COMPLAINANT DETAILS",
            f"  Full Name:       {merchant['name']}",
            f"  Business Name:   {merchant['business_name']}",
            f"  Email:           {merchant['email']}",
            f"  Phone:           {merchant['phone']}",
            f"  State:           {merchant.get('state', '[YOUR STATE]')}",
            f"",
            f"SECTION B - PAYMENT AGGREGATOR DETAILS",
            f"  Name:    {_agg_name}",
            f"  Type:    Payment Aggregator (RBI Licensed)",
            f"  CIN:     U72200KA2013PTC069276",
            f"  Address: 1st Floor, SJR Cyber, 22 Laskar Hosur Road, Bengaluru - 560030",
            f"",
            f"SECTION C - COMPLAINT DETAILS",
            f"  Merchant Account ID: {merchant['merchant_id']}",
            f"  Issue Type:          {issue_name}",
            f"  Issue Start Date:    {issue['first_reported_date']}",
            f"  Amount in Dispute:   {INR}{issue.get('amount', 'N/A')}",
            f"  Days Elapsed:        {issue['days_elapsed']} days",
            f"",
            f"SECTION D - DESCRIPTION OF COMPLAINT",
            f"",
            f"  {issue.get('description', '[Describe the issue in detail]')}",
            f"",
            f"  Despite multiple follow-ups, {_agg_short} has not resolved this issue.",
            f"  The issue has been pending for {issue['days_elapsed']} days, exceeding",
            f"  the 30-day resolution timeline mandated by the RBI.",
            f"",
            f"SECTION E - REGULATORY PROVISIONS VIOLATED",
            f"  1. {rbi_ref}",
            f"  2. RBI PA Directions 2025, Para 8 - Grievance Redressal (30-day resolution)",
            f"  3. RBI Integrated Ombudsman Scheme 2021, Para 8 - Grounds of Complaint",
            f"",
            f"SECTION F - RELIEF SOUGHT",
            f"  1. Release of held/missing funds: {INR}{issue.get('amount', 'N/A')}",
            f"  2. Written explanation from {_agg_short} citing specific RBI provision",
            f"  3. Compensation for loss of business during the dispute period",
            f"  4. Penalty on {_agg_short} for violation of RBI directives",
            f"",
            f"SECTION G - GRIEVANCE HISTORY",
            f"  1. First contacted {_agg_short} Support on: {issue['first_reported_date']}",
        ]
        if issue.get("grievance_ref"):
            lines.append(f"  2. Escalated to Grievance Officer - Ref: {issue['grievance_ref']}")
        lines += [
            f"  Note: 30+ days have passed without satisfactory resolution.",
            f"",
            f"DECLARATION:",
            f"  I hereby declare that the information provided is true and accurate.",
            f"  I have not filed this complaint in any other forum.",
            f"",
            f"Signature: {merchant['name']}",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"--- DOCUMENTS TO ATTACH ---",
            f"  (Upload all documents on cms.rbi.org.in during filing)",
        ]
        for i, doc in enumerate(self.get_evidence_checklist(issue["issue_type"]), 1):
            lines.append(f"  {i}. {doc}")
        return "\n".join(lines)

    def draft_legal_notice(self, merchant: dict, issue: dict) -> str:
        """Draft legal notice under Consumer Protection Act 2019 (Tier 4)."""
        issue_name = ISSUE_TYPES.get(issue["issue_type"], "Issue")
        lines = [
            f"LEGAL NOTICE",
            f"Under: Consumer Protection Act 2019, Section 35",
            f"",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"FROM:",
            f"  {merchant['name']}",
            f"  {merchant['business_name']}",
            f"  {merchant.get('address', '[YOUR ADDRESS]')}",
            f"  {merchant['email']} | {merchant['phone']}",
            f"",
            f"TO:",
            f"  The Managing Director & CEO",
            f"  {_agg_name}",
            f"  1st Floor, SJR Cyber, 22 Laskar Hosur Road",
            f"  Bengaluru - 560030, Karnataka",
            f"",
            f"SUBJECT: Legal Notice for {issue_name} - Merchant ID: {merchant['merchant_id']}",
            f"",
            f"NOTICE IS HEREBY GIVEN THAT:",
            f"",
            f"1. I, {merchant['name']}, am a registered merchant on your platform",
            f"   (Merchant ID: {merchant['merchant_id']}) since [REGISTRATION DATE].",
            f"",
            f"2. On {issue['first_reported_date']}, I experienced: {issue_name}.",
            f"   Amount affected: {INR}{issue.get('amount', 'N/A')}.",
            f"",
            f"3. Despite reporting on {issue['first_reported_date']} and multiple follow-ups,",
            f"   the issue remains unresolved for {issue['days_elapsed']} days.",
            f"",
            f"4. Your conduct constitutes:",
            f"   a) Deficiency in service under Consumer Protection Act 2019, Section 2(11)",
            f"   b) Unfair trade practice under Consumer Protection Act 2019, Section 2(47)",
            f"   c) Violation of RBI PA Directions 2025",
            f"",
            f"DEMAND:",
            f"   1. Resolve the above issue and release {INR}{issue.get('amount', 'N/A')} within",
            f"      15 days of receipt of this notice.",
            f"   2. Pay compensation of {INR}[CLAIM AMOUNT] for business loss.",
            f"",
            f"FAILING WHICH, I shall file a consumer complaint before the appropriate",
            f"Consumer Disputes Redressal Commission without further notice.",
            f"",
            f"{merchant['name']}",
            f"(Authorised Signatory)",
            f"Date: {date.today().strftime('%d %B %Y')}",
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    agent = EscalationAgent()
    # Quick self-test
    merchant = {
        "name": os.getenv("TEST_MERCHANT_NAME", "Merchant Contact"),
        "business_name": os.getenv("TEST_BUSINESS_NAME", "Merchant Store Ltd"),
        "merchant_id": os.getenv("TEST_MERCHANT_ID", "MERCH_001"),
        "email": os.getenv("TEST_MERCHANT_EMAIL", "merchant@example.com"),
        "phone": os.getenv("TEST_MERCHANT_PHONE", "9999999999"),
        "state": os.getenv("TEST_MERCHANT_STATE", "Maharashtra"),
        "address": os.getenv("TEST_MERCHANT_ADDRESS", "123 Commercial Hub, Mumbai - 400001"),
    }
    today = date.today()
    issue = {
        "issue_type": "settlement_hold",
        "first_reported_date": (today - timedelta(days=35)).strftime("%Y-%m-%d"),
        "days_elapsed": 35,
        "amount": "25,000.00",
        "txn_ids": "TXN_001, TXN_002",
        "description": "Settlement of 2 transactions held without explanation.",
        "timeline": [
            f"{(today - timedelta(days=35)):%Y-%m-%d}: Noticed settlement not received",
            f"{(today - timedelta(days=33)):%Y-%m-%d}: Raised support ticket",
            f"{(today - timedelta(days=15)):%Y-%m-%d}: No response - escalated to Grievance Officer",
            f"{(today - timedelta(days=2)):%Y-%m-%d}: Still unresolved",
        ],
        "grievance_ref": f"GRV_{(today - timedelta(days=15)):%Y%m%d}_001",
    }
    rec = agent.recommend_tier(45)
    print(f"Recommended tier: {rec['tier']} - {rec['name']}")
    letter = agent.draft_rbi_ombudsman_complaint(merchant, issue)
    print(f"Ombudsman complaint: {len(letter.splitlines())} lines")
    assert "cms.rbi.org.in" in letter
    print("Self-test PASSED")