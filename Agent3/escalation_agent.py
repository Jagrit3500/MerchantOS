"""
MerchantOS - Agent 3: Formal Escalation & Recovery Bot
Generates RBI-cited formal escalation letters, tracks timelines, recommends next steps.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import config
from datetime import date, datetime, timedelta

# ─── Escalation tiers (RBI / Consumer Protection Act based) ───────────────────
_agg_name = config.AGGREGATOR_NAME
_agg_short = config.AGGREGATOR_SHORT
_grievance_email = config.AGGREGATOR_GRIEVANCE_EMAIL
_support_url = config.AGGREGATOR_SUPPORT_URL

ESCALATION_TIERS = [
    {
        "tier": 1,
        "name": f"{_agg_short} Support",
        "trigger_days": 0,
        "deadline_days": config.SUPPORT_DEADLINE_DAYS,
        "description": f"First point of contact. File via {_support_url} or in-app chat.",
        "contact": _support_url,
        "rbi_ref": None,
    },
    {
        "tier": 2,
        "name": f"{_agg_short} Grievance Officer",
        "trigger_days": config.GRIEVANCE_TRIGGER_DAYS,
        "deadline_days": config.GRIEVANCE_DEADLINE_DAYS,
        "description": f"If not resolved within {config.GRIEVANCE_TRIGGER_DAYS} business days, escalate to {_agg_short} Grievance Officer.",
        "contact": _grievance_email,
        "rbi_ref": f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE}",
    },
    {
        "tier": 3,
        "name": "RBI Integrated Ombudsman",
        "trigger_days": config.OMBUDSMAN_TRIGGER_DAYS,
        "deadline_days": config.OMBUDSMAN_DEADLINE_DAYS,
        "description": f"Check coverage, exclusions, and prior-complaint requirements before filing on {config.OMBUDSMAN_URL} under the RBI Integrated Ombudsman Scheme.",
        "contact": config.OMBUDSMAN_URL,
        "rbi_ref": "RBI Integrated Ombudsman Scheme 2021 (RBI/2021-22/20)",
    },
    {
        "tier": 4,
        "name": "Consumer Forum / Legal Notice",
        "trigger_days": config.LEGAL_TRIGGER_DAYS,
        "deadline_days": None,
        "description": "Ask qualified counsel whether consumer status and jurisdiction apply before sending a legal notice or filing a complaint.",
        "contact": config.CONSUMER_HELP_URL,
        "rbi_ref": "Consumer Protection Act 2019 - eligibility and commercial-purpose exclusions require review",
    },
]

# ─── Issue types and their RBI references ──────────────────────────────────────
ISSUE_TYPES = {
    "kyc_hold":           "KYC / Account Hold",
    "settlement_hold":    "Settlement Hold / Funds On Hold",
    "settlement_missing": "Missing Settlement",
    "fee_overcharge":     "Fee Overcharge",
    "tat_violation":      "Settlement Timeline Exception",
    "account_suspended":  "Account Suspended / Deactivated",
    "chargeback_dispute": "Chargeback / Dispute Handling",
    "other":              "Other",
}

ISSUE_RBI_REFS = {
    "kyc_hold":           f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}",
    "settlement_hold":    f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE} and {config.PA_SETTLEMENT_REFERENCE}",
    "settlement_missing": f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_SETTLEMENT_REFERENCE}",
    "fee_overcharge":     f"Merchant agreement and published pricing; {config.PA_DIRECTIONS_REFERENCE}, paragraph 10(c), only where its MDR directions apply",
    "tat_violation":      f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_SETTLEMENT_REFERENCE}, plus the merchant agreement",
    "account_suspended":  f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE}",
    "chargeback_dispute": f"{config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE}",
    "other":              config.PA_DIRECTIONS_REFERENCE,
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
        f"Transaction IDs that exceeded the {config.SETTLEMENT_WINDOW_LABEL}",
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

INR = config.CURRENCY_SYMBOL


class EscalationAgent:
    """Generates formal escalation letters and recommends escalation path."""

    def recommend_tier(self, days_since_issue: int) -> dict:
        """Return the appropriate escalation tier based on days elapsed."""
        days_since_issue = max(int(days_since_issue), 0)
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
        return max((date.today() - issue_date).days, 0)

    def draft_grievance_letter(self, merchant: dict, issue: dict) -> str:
        """Draft formal Razorpay Grievance Officer letter (Tier 2)."""
        rbi_ref = ISSUE_RBI_REFS.get(issue["issue_type"], ISSUE_RBI_REFS["other"])
        issue_name = ISSUE_TYPES.get(issue["issue_type"], "Issue")

        lines = [
            f"To,",
            f"The Grievance Officer",
            f"{_agg_name}",
            f"{config.AGGREGATOR_ADDRESS}",
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
            f"  I request review under {rbi_ref} and under the settlement and grievance terms",
            f"  published by {_agg_short}. Please provide a written outcome and the applicable escalation path.",
            f"",
            f"MY REQUEST:",
            f"  1. Immediate resolution of the above issue",
            f"  2. Written explanation citing the specific reason and RBI provision",
            f"  3. Release of any held funds ({INR}{issue.get('amount', 'N/A')}) within {config.SETTLEMENT_RELEASE_REQUEST_DAYS} business days",
            f"  4. Confirmation of actions taken via email",
            f"",
            f"If I receive no satisfactory response, I will review whether this complaint is eligible under",
            f"the {config.OMBUDSMAN_SCHEME_REFERENCE} and, if eligible, use {config.OMBUDSMAN_URL}.",
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
        days_elapsed = max(int(issue.get("days_elapsed", 0)), 0)
        timing_statement = (
            f"The issue has remained unresolved for {days_elapsed} days."
            if days_elapsed >= config.OMBUDSMAN_TRIGGER_DAYS
            else (
                f"This issue has currently been open for {days_elapsed} days. "
                "Confirm complaint eligibility and the provider's final response before filing this draft."
            )
        )
        contact_statement = (
            f"I previously escalated this matter under reference {issue['grievance_ref']}."
            if issue.get("grievance_ref")
            else "[ADD DETAILS OF YOUR PRIOR WRITTEN COMPLAINT AND THE PROVIDER'S RESPONSE]"
        )

        lines = [
            f"COMPLAINT TO RBI INTEGRATED OMBUDSMAN",
            f"Under: RBI Integrated Ombudsman Scheme 2021 (RBI/2021-22/20)",
            f"Portal: {config.OMBUDSMAN_URL}",
            f"",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"TO: The Ombudsman",
            f"    RBI Integrated Ombudsman Scheme",
            f"    (via online portal: {config.OMBUDSMAN_URL})",
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
            f"  Type:    Payment Aggregator",
            f"  CIN:     {config.AGGREGATOR_CIN}",
            f"  Address: {config.AGGREGATOR_ADDRESS}",
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
            f"  {contact_statement}",
            f"  {timing_statement}",
            f"",
            f"SECTION E - REGULATORY PROVISIONS VIOLATED",
            f"  1. {rbi_ref}",
            f"  2. {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE} - merchant grievance officer and escalation matrix",
            f"  3. {config.OMBUDSMAN_SCHEME_REFERENCE} - subject to coverage, maintainability, and exclusions",
            f"",
            f"SECTION F - RELIEF SOUGHT",
            f"  1. Release of held/missing funds: {INR}{issue.get('amount', 'N/A')}",
            f"  2. Written explanation from {_agg_short} citing specific RBI provision",
            f"  3. Any other relief the Ombudsman considers permissible, if this complaint is maintainable",
            f"",
            f"SECTION G - GRIEVANCE HISTORY",
            f"  1. First contacted {_agg_short} Support on: {issue['first_reported_date']}",
        ]
        if issue.get("grievance_ref"):
            lines.append(f"  2. Escalated to Grievance Officer - Ref: {issue['grievance_ref']}")
        lines += [
            f"  Filing note: Confirm that the applicable complaint prerequisites and waiting period are satisfied.",
            f"",
            f"DECLARATION:",
            f"  I hereby declare that the information provided is true and accurate.",
            f"  [CONFIRM WHETHER THIS MATTER HAS BEEN FILED IN ANY OTHER FORUM]",
            f"",
            f"Signature: {merchant['name']}",
            f"Date: {date.today().strftime('%d %B %Y')}",
            f"",
            f"--- DOCUMENTS TO ATTACH ---",
            f"  (Upload all documents on {config.OMBUDSMAN_URL} during filing)",
        ]
        for i, doc in enumerate(self.get_evidence_checklist(issue["issue_type"]), 1):
            lines.append(f"  {i}. {doc}")
        return "\n".join(lines)

    def draft_legal_notice(self, merchant: dict, issue: dict) -> str:
        """Draft a counsel-review legal notice for the optional Tier 4 route."""
        issue_name = ISSUE_TYPES.get(issue["issue_type"], "Issue")
        followup_statement = (
            "Despite the prior written complaint referenced in the attached record,"
            if issue.get("grievance_ref")
            else "As of the date of this draft,"
        )
        lines = [
            f"DRAFT LEGAL NOTICE - QUALIFIED COUNSEL REVIEW REQUIRED",
            f"Potential consumer-law route only if the merchant and transaction are eligible",
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
            f"  {config.AGGREGATOR_ADDRESS}",
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
            f"3. {followup_statement}",
            f"   the issue remains unresolved for {issue['days_elapsed']} days.",
            f"",
            f"4. Subject to review by a qualified advocate, the facts may raise issues under:",
            f"   a) The applicable service agreement and provider policies",
            f"   b) Consumer Protection Act 2019, if the complainant and transaction qualify",
            f"   c) {config.PA_DIRECTIONS_NAME}",
            f"",
            f"DEMAND:",
            f"   1. Resolve the above issue and release {INR}{issue.get('amount', 'N/A')} within",
            f"      {config.LEGAL_NOTICE_DEADLINE_DAYS} days of receipt of this notice.",
            f"   2. Address any documented loss or compensation claim supported by evidence and legal advice.",
            f"",
            f"If unresolved, I reserve any remedies available under the agreement and applicable law,",
            f"including a consumer complaint only if counsel confirms eligibility and jurisdiction.",
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
        "name": "Merchant Contact",
        "business_name": "Merchant Store Ltd",
        "merchant_id": "MERCH_001",
        "email": "merchant@example.com",
        "phone": "9999999999",
        "state": "Maharashtra",
        "address": "123 Commercial Hub, Mumbai - 400001",
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
    assert config.OMBUDSMAN_URL in letter
    print("Self-test PASSED")
