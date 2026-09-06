"""
Ticket Drafter ? generates a legally-worded support ticket
based on KYCDiagnosisAgent output + RAG evidence.
"""
from datetime import date

def draft_ticket(diagnosis: dict, rag_answer: str = "") -> str:
    hold_reason = diagnosis["hold_reason"]
    merchant_type = diagnosis["merchant_type"]
    docs = diagnosis["required_docs"]
    rbi_ref = docs.get("rbi_ref", "RBI PA Master Directions 2025")
    answers = diagnosis.get("answers", {})

    days_on_hold = answers.get("days_on_hold", "Not Specified")
    today_str = date.today().strftime("%d %B %Y")

    # Generate personalized statutory duration clause
    if "> 30 days" in days_on_hold or "over 30" in days_on_hold.lower():
        duration_clause = (
            f"STATUTORY BREACH NOTICE: This hold has now been in place for {days_on_hold} "
            "(exceeding the 30-day statutory resolution window prescribed under the RBI Integrated Ombudsman Scheme 2021). "
            "As the 30-day statutory window has elapsed without remediation, this matter is immediately eligible for "
            "Level 3 filing before the RBI Integrated Ombudsman."
        )
        sla_timeline = "Immediate release or final written rejection within 48 hours, failing which a formal complaint will be lodged with the RBI Ombudsman (cms.rbi.org.in)."
    elif "15 to 30 days" in days_on_hold:
        duration_clause = (
            f"URGENT ESCALATION: This hold has been in effect for {days_on_hold}. "
            "Aggregators are required to conclude dispute reviews within 30 days per RBI Grievance Redressal norms. "
            "We are within days of statutory Ombudsman escalation."
        )
        sla_timeline = "Resolution within 3 business days per RBI Turnaround Time (TAT) framework."
    elif "4 to 14 days" in days_on_hold:
        duration_clause = (
            f"HOLD DURATION: This settlement hold has persisted for {days_on_hold}, "
            "exceeding standard turnaround expectations under Payment Aggregator operational directions."
        )
        sla_timeline = "Confirmation of document receipt and resolution timeline within 48 hours."
    elif "< 3 days" in days_on_hold or "1 to 3" in days_on_hold:
        duration_clause = (
            f"INITIAL INQUIRY: This hold was placed recently ({days_on_hold}). "
            "Per RBI Master Directions 2025, aggregators must provide written reasons for merchant settlement restrictions."
        )
        sla_timeline = "Written acknowledgment within 24 hours per RBI guidelines."
    else:
        duration_clause = f"HOLD DURATION: {days_on_hold}. I request formal timeline clarification under RBI PA Directions 2025."
        sla_timeline = "Written acknowledgment within 24 hours per RBI guidelines."

    base_templates = {
        "KYC_WRONG_DOCS": f"""Subject: Settlement Hold ? Incorrect KYC Document Request (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Compliance / KYC Team,

My account [YOUR_MERCHANT_ID] has been placed on hold. I am registered as a {merchant_type}.

{duration_clause}

I note that your team has requested a GST Certificate. I respectfully submit that this document is NOT legally mandated for my merchant category under the {rbi_ref}.

MANDATORY DOCUMENTS I AM PROVIDING:
{chr(10).join(f"  - {d}" for d in docs['mandatory'])}

ANY ONE OF:
{chr(10).join(f"  - {d}" for d in docs['one_of'])}

NOT REQUIRED FOR MY CATEGORY (per RBI PA Master Directions):
{chr(10).join(f"  - {d}" for d in docs['not_required'])}

I formally request:
1. Written confirmation of the specific legal provision requiring GST from a {merchant_type}
2. Acceptance of the compliant alternate documents listed above
3. Immediate release of my settlement hold

RESOLUTION TIMELINE REQUIRED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date of Notice: {today_str}

Regards,
[YOUR_NAME]
""",

        "KYC_MISSING_DOCS": f"""Subject: Settlement Hold ? KYC Document Submission (Account: [YOUR_MERCHANT_ID])

Dear Razorpay KYC Team,

My account [YOUR_MERCHANT_ID] is on hold pending KYC verification. I am registered as a {merchant_type}.

{duration_clause}

I am attaching the complete set of verified documents required under {rbi_ref}:

MANDATORY DOCUMENTS ATTACHED:
{chr(10).join(f"  - {d}" for d in docs['mandatory'])}

SUPPORTING DOCUMENT (ONE OF):
{chr(10).join(f"  - {d}" for d in docs['one_of'])}

RESOLUTION TIMELINE REQUIRED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date of Submission: {today_str}

Regards,
[YOUR_NAME]
""",

        "RISK_TXN_SPIKE": f"""Subject: Settlement Hold ? Clarification on Transaction Volume (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Risk Team,

My account [YOUR_MERCHANT_ID] appears to be on hold following an increase in processing volume.

{duration_clause}

I want to formally clarify that this volume increase reflects genuine customer demand due to: [EXPLAIN REASON ? e.g., marketing campaign, seasonal sale, new product launch].

I am providing the following records to substantiate transaction authenticity:
  - Recent sales invoices confirming legitimate order fulfillment
  - Proof of delivery / shipment tracking details
  - Direct customer communication records
  - Business explanation declaration

RESOLUTION TIMELINE REQUIRED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",

        "RISK_CHARGEBACK": f"""Subject: Settlement Hold ? Chargeback & Dispute Remediation (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Risk Team,

My account [YOUR_MERCHANT_ID] is currently restricted regarding dispute and chargeback monitoring.

{duration_clause}

I am providing comprehensive documentation to address disputed transactions:
  - Verified proof of delivery / shipment tracking for disputed orders
  - Direct customer communications and resolution logs
  - Published terms of service and refund policy documentation

I am committed to maintaining my chargeback ratio strictly within card network monitoring thresholds (Visa VDMP 0.9% / Mastercard ECP 1.0%) and RBI risk governance norms, and formally request:
1. An itemized breakdown of specific transactions triggering this hold
2. Clear and actionable remediation criteria required for hold release
3. Defined timeline for settlement release following this submission

RESOLUTION TIMELINE REQUIRED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",

        "REGULATORY_LEA": f"""Subject: Account Freeze ? Formal Request for Written Notice & Reason (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Legal & Compliance Directorate,

My merchant account [YOUR_MERCHANT_ID] has been frozen without formal prior written notification.

{duration_clause}

Under RBI Master Directions on Payment Aggregators 2025 and basic administrative due process, merchants are entitled to transparent communication regarding account restrictions.

If this freeze is pursuant to a Law Enforcement Agency (LEA) or judicial directive, I formally request:
1. Written confirmation of the formal notice or LEA order reference number
2. Name and jurisdiction of the issuing authority / investigation agency
3. Specific scope, affected transaction IDs, and designated duration of the freeze

I have retained legal counsel and request all future communication in formal writing.

RESOLUTION TIMELINE REQUIRED:
{sla_timeline}

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Date: {today_str}

Regards,
[YOUR_NAME]
""",
    }

    ticket = base_templates.get(hold_reason, base_templates["KYC_MISSING_DOCS"])

    _rag_ok = bool(rag_answer) and not any(p in rag_answer.lower() for p in ["i could not find", "not found in", "not present in the context", "insufficient statutory"])
    if _rag_ok:
        ticket += f"\n---\nRELEVANT RBI PROVISION (auto-retrieved):\n{rag_answer}\n"

    return ticket


def get_escalation_path() -> list[dict]:
    return [
        {"tier": 1, "action": "Submit Razorpay support ticket", "timeline": "Wait 24-48 hours for response"},
        {"tier": 2, "action": "Escalate to Razorpay Grievance Officer", "timeline": "If no resolution after 5 business days"},
        {"tier": 3, "action": "File complaint with RBI Integrated Ombudsman", "timeline": "If 30 days pass without resolution", "url": "https://cms.rbi.org.in"},
    ]
