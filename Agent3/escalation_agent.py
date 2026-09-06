"""
MerchantOS - Agent 3: Formal Escalation & Recovery Bot
Generates RBI-cited formal escalation letters, tracks timelines, recommends next steps.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta

# ─── Escalation tiers (RBI / Consumer Protection Act based) ───────────────────
ESCALATION_TIERS = [
    {
        "tier": 1,
        "name": "Razorpay Support",
        "trigger_days": 0,
        "deadline_days": 5,
        "description": "First point of contact. File via razorpay.com/support or in-app chat.",
        "contact": "razorpay.com/support",
        "rbi_ref": None,
    },
    {
        "tier": 2,
        "name": "Razorpay Grievance Officer",
        "trigger_days": 5,
        "deadline_days": 30,
        "description": "If not resolved within 5 business days, escalate to Grievance Officer.",
        "contact": "grievance.officer@razorpay.com",
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
        "Screenshot of Razorpay dashboard showing the hold",
        "All KYC documents you submitted (PAN, Aadhaar, business registration)",
        "Email from Razorpay requesting documents (if any)",
        "Email showing you submitted the documents",
        "Date you first noticed the hold",
    ],
    "settlement_hold": [
        "Screenshot of Razorpay settlement dashboard showing held status",
        "Transaction IDs of all held transactions",
        "Bank statement showing expected but missing credits",
        "Any emails from Razorpay explaining the hold",
        "Your own order fulfillment records (delivery proof, invoices)",
    ],
    "settlement_missing": [
        "Razorpay settlement report / CSV download",
        "Bank statement for the relevant period",
        "List of transaction IDs with expected settlement dates",
        "Any Razorpay communication about settlement",
    ],
    "fee_overcharge": [
        "Razorpay settlement CSV with fee details",
        "Razorpay published pricing at time of transactions",
        "Your own reconciliation showing overcharge calculation",
        "Transaction IDs where overcharge occurred",
    ],
    "tat_violation": [
        "Razorpay settlement CSV showing transaction dates and settlement dates",
        "Calculation showing days between transaction and settlement",
        "Transaction IDs that exceeded T+2",
    ],
    "account_suspended": [
        "Screenshot of account suspension notice",
        "Any email from Razorpay explaining suspension reason",
        "All previously submitted KYC documents",
        "Business registration / license documents",
    ],
    "chargeback_dispute": [
        "Original transaction details",
        "Proof of delivery / fulfillment",
        "Customer communication records",
        "Refund policy (if applicable)",
        "Razorpay chargeback notification email",
    ],
    "other": [
        "All relevant screenshots",
        "Email communication with Razorpay",
        "Transaction IDs / Order IDs affected",
        "Timeline of events (dates and what happened)",
    ],
}

INR = "\u20b9"


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
            f"Razorpay Software Private Limited",
            f"1st Floor, SJR Cyber, 22 Laskar Hosur Road, Bengaluru - 560030",
            f"Email: grievance.officer@razorpay.com",
            f"",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"Subject: Formal Grievance - {issue_name} (Merchant ID: {merchant['merchant_id']})",
            f"",
            f"Dear Grievance Officer,",
            f"",
            f"I, {merchant['name']}, operating as {merchant['business_name']}, am writing to formally",
            f"escalate an unresolved issue with my Razorpay merchant account (ID: {merchant['merchant_id']}).",
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
            f"  Per RBI PA Directions 2025, Para 8, Razorpay is obligated to",
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
            f"  Name:    Razorpay Software Private Limited",
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
            f"  Despite multiple follow-ups, Razorpay has not resolved this issue.",
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
            f"  2. Written explanation from Razorpay citing specific RBI provision",
            f"  3. Compensation for loss of business during the dispute period",
            f"  4. Penalty on Razorpay for violation of RBI directives",
            f"",
            f"SECTION G - GRIEVANCE HISTORY",
            f"  1. First contacted Razorpay Support on: {issue['first_reported_date']}",
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
            f"  Razorpay Software Private Limited",
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
        "name": "Rahul Sharma",
        "business_name": "ShopEasy Pvt Ltd",
        "merchant_id": "MERCH_TEST_001",
        "email": "rahul@shopeasy.in",
        "phone": "9999999999",
        "state": "Maharashtra",
        "address": "123, Test Street, Mumbai - 400001",
    }
    issue = {
        "issue_type": "settlement_hold",
        "first_reported_date": "2024-01-01",
        "days_elapsed": 45,
        "amount": "25,000.00",
        "txn_ids": "RZP_001, RZP_002",
        "description": "Settlement of 2 transactions held without explanation for 45 days.",
        "timeline": [
            "2024-01-01: Noticed settlement not received",
            "2024-01-03: Raised support ticket",
            "2024-01-15: No response - escalated to Grievance Officer",
            "2024-02-15: Still unresolved",
        ],
        "grievance_ref": "GRV_20240115_001",
    }
    rec = agent.recommend_tier(45)
    print(f"Recommended tier: {rec['tier']} - {rec['name']}")
    letter = agent.draft_rbi_ombudsman_complaint(merchant, issue)
    print(f"Ombudsman complaint: {len(letter.splitlines())} lines")
    assert "cms.rbi.org.in" in letter
    print("Self-test PASSED")