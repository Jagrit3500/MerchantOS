"""
Generate a policy-reviewed support-request draft from the diagnosis.

Retrieved evidence remains separate so it cannot silently alter the draft.
"""
from src import config
from datetime import date


def _merchant_with_article(merchant_type: str) -> str:
    article = "an" if merchant_type[:1].lower() in "aeiou" or merchant_type.startswith("NGO") else "a"
    return f"{article} {merchant_type}"


def draft_ticket(diagnosis: dict, rag_answer: str = "") -> str:
    """Build an editable case draft; raw retrieval evidence is intentionally kept separate."""
    hold_reason = diagnosis["hold_reason"]
    merchant_type = diagnosis["merchant_type"]
    merchant_phrase = _merchant_with_article(merchant_type)
    docs = diagnosis["required_docs"]
    rbi_ref = docs.get("rbi_ref", config.PA_DIRECTIONS_REFERENCE).rstrip(". ")
    answers = diagnosis.get("answers", {})
    kyc_request = {
        "Yes - asking for GST Certificate": "a GST certificate",
        "Yes - asking for other documents": "other KYC documents",
        "Yes - asking for IPV, video, or in-person verification": "IPV, video, or in-person verification",
    }.get(answers.get("kyc_email", ""), "KYC verification")

    days_on_hold_answer = answers.get("days_on_hold", "Not Specified")
    days_on_hold = days_on_hold_answer.split(" (", 1)[0]
    if days_on_hold.startswith("> "):
        days_on_hold = f"more than {days_on_hold[2:]}"
    dashboard_status = answers.get("dashboard_status", "Not specified")
    if dashboard_status.startswith("Custom Issue:"):
        dashboard_status = dashboard_status.removeprefix("Custom Issue:").strip()
    today_str = date.today().strftime("%d %B %Y")

    # Duration controls workflow urgency only; it does not establish legal eligibility.
    if f"> {config.OMBUDSMAN_TRIGGER_DAYS} days" in days_on_hold_answer or f"over {config.OMBUDSMAN_TRIGGER_DAYS}" in days_on_hold_answer.lower():
        duration_clause = (
            f"FORMAL ESCALATION REVIEW: This issue has now remained unresolved for {days_on_hold}. "
            "Elapsed time from the restriction alone does not establish Ombudsman eligibility. If a prior written complaint to a covered regulated entity was rejected or remained unanswered for one month, "
            "check the eligibility and exclusions in the Reserve Bank - Integrated Ombudsman Scheme, 2021 before filing."
        )
        sla_timeline = f"Please acknowledge within {config.FOLLOWUP_ACK_HOURS} hours and provide a final response or a dated resolution plan."
    elif f"{config.HOLD_URGENT_TRIGGER_DAYS} to {config.OMBUDSMAN_TRIGGER_DAYS} days" in days_on_hold_answer:
        duration_clause = (
            f"URGENT ESCALATION: This issue has remained unresolved for {days_on_hold}. "
            "Please route this to the published merchant-grievance contact and provide the applicable escalation matrix."
        )
        sla_timeline = f"Please provide a substantive response within {config.URGENT_RESOLUTION_BUSINESS_DAYS} business days."
    elif f"{config.HOLD_RECENT_MAX_DAYS + 1} to {config.HOLD_STANDARD_MAX_DAYS} days" in days_on_hold_answer:
        duration_clause = (
            f"FOLLOW-UP REQUEST: This issue has remained unresolved for {days_on_hold}. "
            "Please provide a written status update and dated resolution plan."
        )
        sla_timeline = f"Please acknowledge and provide a dated resolution timeline within {config.FOLLOWUP_ACK_HOURS} hours."
    elif f"1 to {config.HOLD_RECENT_MAX_DAYS}" in days_on_hold_answer:
        duration_clause = (
            f"INITIAL INQUIRY: This issue was noticed recently ({days_on_hold}). "
            "Please confirm the reason, required remediation, and expected review date in writing."
        )
        sla_timeline = f"Please acknowledge this request within {config.INITIAL_ACK_HOURS} hours."
    else:
        duration_clause = f"ISSUE DURATION: {days_on_hold}. I request a written explanation and resolution timeline."
        sla_timeline = f"Please acknowledge this request within {config.INITIAL_ACK_HOURS} hours."

    base_templates = {
        "KYC_DOCUMENT_CLARIFICATION": f"""Subject: Account Review — KYC Document Clarification Request (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} Compliance / KYC Team,

My account [YOUR_MERCHANT_ID] appears to be restricted, and a GST certificate was requested. I am registered as {merchant_phrase}.

{duration_clause}

I note that your team has requested a GST Certificate. The PA Directions require merchant due diligence under the RBI KYC Direction, but do not publish the merchant-type GST checklist previously attributed to them. Please identify whether this request arises from law, your current onboarding policy, or my business profile, and confirm any acceptable alternative. {rbi_ref}.

CORE RECORDS TO REVIEW BEFORE SENDING:
{chr(10).join(f"  - {d}" for d in docs['mandatory'])}

CASE-DEPENDENT RECORDS (ONLY IF APPLICABLE OR REQUESTED):
{chr(10).join(f"  - {d}" for d in docs['one_of'])}

DOCUMENT REQUESTS TO CLARIFY:
{chr(10).join(f"  - {d}" for d in docs['not_required'])}

I formally request:
1. Written confirmation of the legal, contractual, or policy basis for requiring GST from {merchant_phrase}
2. Confirmation of any acceptable alternative business document
3. Review and removal of any restriction once the applicable checks are complete

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date of Notice: {today_str}

Regards,
[YOUR_NAME]
""",

        "KYC_ACTION_REQUIRED": f"""Subject: Account Review — KYC Verification Response (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} KYC Team,

My account [YOUR_MERCHANT_ID] appears to be restricted, and I received a request for {kyc_request}. I am registered as {merchant_phrase}.

{duration_clause}

I am responding to the reported KYC request. Before sending, I will list and attach only the records I am actually providing. Please confirm the exact current checklist shown for this account. {rbi_ref}.

CORE RECORDS TO REVIEW BEFORE SENDING:
{chr(10).join(f"  - {d}" for d in docs['mandatory'])}

CASE-DEPENDENT RECORDS (ONLY IF APPLICABLE OR REQUESTED):
{chr(10).join(f"  - {d}" for d in docs['one_of'])}

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date of Submission: {today_str}

Regards,
[YOUR_NAME]
""",

        "RISK_TXN_SPIKE": f"""Subject: Account Restriction — Transaction Volume Clarification (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} Risk Team,

My account [YOUR_MERCHANT_ID] appears to be restricted, and my processing volume recently increased. Please confirm whether these events are related and identify any applicable review criteria.

{duration_clause}

The volume change may be explained by: [DESCRIBE THE FACTUAL REASON — e.g., marketing campaign, seasonal sale, new product launch].

I can provide the following records, where applicable, to explain and document the activity:
  - Recent sales invoices and order records
  - Proof of delivery / shipment tracking details
  - Direct customer communication records
  - A dated explanation of the business activity

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",

        "RISK_CHARGEBACK": f"""Subject: Account Restriction — Chargeback & Dispute Clarification (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} Risk Team,

My account [YOUR_MERCHANT_ID] appears to be restricted, and I have received dispute or chargeback notices. Please confirm whether these events are related and identify the applicable provider or card-network rule.

{duration_clause}

I can provide the following documentation, where applicable, for the disputed transactions:
  - Verified proof of delivery / shipment tracking for disputed orders
  - Direct customer communications and resolution logs
  - Published terms of service and refund policy documentation

I am committed to addressing any applicable card-network or provider risk requirements that you identify, and formally request:
1. An itemized breakdown of transactions relevant to this restriction or review
2. Clear and actionable remediation criteria for reviewing the restriction
3. A dated update on the expected resolution and settlement status

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",

        "REGULATORY_LEA": f"""Subject: Account Restriction — Formal Request for Written Notice & Reason (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} Legal & Compliance Directorate,

The dashboard for merchant account [YOUR_MERCHANT_ID] reportedly indicates a law-enforcement or regulatory restriction. I am preserving the exact notice and request written clarification.

{duration_clause}

Under the {config.PA_DIRECTIONS_NAME}, payment aggregators must publish merchant policies, appoint an officer for merchant issues, and publish an escalation matrix. I therefore request clear written communication regarding this restriction.

If this freeze is pursuant to a Law Enforcement Agency (LEA) or judicial directive, I formally request:
1. Written confirmation of the formal notice or LEA order reference number
2. Name and jurisdiction of the issuing authority / investigation agency
3. Specific scope, affected transaction IDs, and duration or current review status, where disclosure is permitted

I am seeking appropriate legal advice and request all future communication in formal writing.

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",

        "SETTLEMENT_DELAY": f"""Subject: Delayed Settlement - Request for Status and Reconciliation (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} Settlements Team,

A settlement has not reached my bank account, while the account otherwise appears normal. The reported dashboard status is: {dashboard_status}.

{duration_clause}

Please provide:
1. The affected settlement and transaction IDs, current status, and expected credit date
2. The settlement calculation, including fees, tax, refunds, chargebacks, and adjustments
3. Any bank reference number or failure reason
4. Any account-specific hold, reserve, risk review, or KYC action affecting settlement
5. The applicable settlement timeline under my merchant agreement and dashboard

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Affected Settlement IDs: [ADD_SETTLEMENT_IDS]
Date: {today_str}

Regards,
[YOUR_NAME]
""",

        "RESTRICTION_UNCONFIRMED": f"""Subject: Account Restriction - Request for Reason and Remediation (Account: [YOUR_MERCHANT_ID])

Dear {config.AGGREGATOR_SHORT} Support Team,

My merchant account shows the following status: {dashboard_status}.

{duration_clause}

The information currently available does not establish whether this is a KYC, risk, settlement, contractual, or regulatory restriction. Please provide:
1. The specific reason and effective date of the restriction
2. The affected products, settlements, and transaction IDs
3. The exact remediation steps and documents required
4. The applicable merchant-policy or agreement clause
5. The expected review date and merchant-grievance escalation matrix

RESOLUTION TIMELINE REQUESTED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",
    }

    ticket = base_templates.get(hold_reason, base_templates["RESTRICTION_UNCONFIRMED"])
    return ticket


def get_escalation_path() -> list[dict]:
    return [
        {"tier": 1, "action": f"Submit {config.AGGREGATOR_SHORT} support ticket", "timeline": f"Wait {config.INITIAL_ACK_HOURS}-{config.FOLLOWUP_ACK_HOURS} hours for response"},
        {"tier": 2, "action": f"Escalate to {config.AGGREGATOR_SHORT} Grievance Officer", "timeline": f"If no resolution after {config.GRIEVANCE_TRIGGER_DAYS} business days"},
        {"tier": 3, "action": "Check RBI Ombudsman eligibility before filing", "timeline": "After a covered entity rejects the prior complaint or does not reply within one month", "url": config.OMBUDSMAN_URL},
    ]
