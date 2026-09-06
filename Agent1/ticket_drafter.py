"""
Ticket Drafter — generates a legally-worded support ticket
based on KYCDiagnosisAgent output + RAG evidence.
"""

def draft_ticket(diagnosis: dict, rag_answer: str = "") -> str:
    hold_reason = diagnosis["hold_reason"]
    merchant_type = diagnosis["merchant_type"]
    docs = diagnosis["required_docs"]
    rbi_ref = docs.get("rbi_ref", "RBI PA Master Directions 2025")

    base_templates = {
        "KYC_WRONG_DOCS": f"""Subject: Settlement Hold — Incorrect KYC Document Request (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Compliance / KYC Team,

My account [YOUR_MERCHANT_ID] has been placed on hold. I am a {merchant_type}.

I note that your team has requested a GST Certificate. I respectfully submit that this document is NOT legally mandated for my merchant category under the {rbi_ref}.

MANDATORY DOCUMENTS I AM PROVIDING:
{chr(10).join(f"  - {d}" for d in docs['mandatory'])}

ANY ONE OF:
{chr(10).join(f"  - {d}" for d in docs['one_of'])}

NOT REQUIRED FOR MY CATEGORY (per RBI):
{chr(10).join(f"  - {d}" for d in docs['not_required'])}

I request:
1. Written confirmation of the specific RBI provision requiring GST from a {merchant_type}
2. Acceptance of the alternate documents listed above
3. Immediate release of my settlement hold

If I do not receive a response within 5 business days, I will escalate to:
- Razorpay Grievance Officer
- RBI Integrated Ombudsman (https://cms.rbi.org.in)

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]
Hold Start Date: [DATE]

Regards,
[YOUR_NAME]
""",

        "KYC_MISSING_DOCS": f"""Subject: Settlement Hold — KYC Document Submission (Account: [YOUR_MERCHANT_ID])

Dear Razorpay KYC Team,

My account [YOUR_MERCHANT_ID] is on hold pending KYC verification. I am a {merchant_type}.

I am attaching the following documents as required under {rbi_ref}:

MANDATORY:
{chr(10).join(f"  - {d}" for d in docs['mandatory'])}

SUPPORTING (ONE OF):
{chr(10).join(f"  - {d}" for d in docs['one_of'])}

Please confirm receipt and provide a resolution timeline within 2 business days per RBI's Turnaround Time (TAT) framework.

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]

Regards,
[YOUR_NAME]
""",

        "RISK_TXN_SPIKE": """Subject: Settlement Hold — Clarification on Transaction Volume (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Risk Team,

My account [YOUR_MERCHANT_ID] appears to be on hold. I believe this may be related to a recent increase in transaction volume.

I want to clarify that the volume increase is due to: [EXPLAIN REASON — e.g., seasonal sale, marketing campaign].

I am providing the following to support my case:
  - Recent invoices confirming legitimate orders
  - Customer communication records
  - Business explanation letter

Please review and release my settlement hold. Per RBI TAT guidelines, I expect acknowledgment within 24 hours.

Merchant ID: [YOUR_MERCHANT_ID]
Registered Email: [YOUR_EMAIL]

Regards,
[YOUR_NAME]
""",

        "RISK_CHARGEBACK": """Subject: Settlement Hold — Chargeback Ratio Dispute (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Risk Team,

My account [YOUR_MERCHANT_ID] is on hold. I believe this may be related to chargeback ratio.

I am providing:
  - Order fulfillment records (proof of delivery)
  - Customer communication for disputed transactions
  - Refund policy documentation

I am committed to maintaining my chargeback ratio below the 0.5% RBI threshold and request:
1. A breakdown of which transactions triggered the hold
2. Clear guidelines on remediation steps
3. Timeline for hold resolution

If unresolved within 30 days, I will escalate to the RBI Ombudsman.

Merchant ID: [YOUR_MERCHANT_ID]
Regards, [YOUR_NAME]
""",

        "REGULATORY_LEA": """Subject: Account Freeze — Request for Written Communication (Account: [YOUR_MERCHANT_ID])

Dear Razorpay Legal / Compliance Team,

My account [YOUR_MERCHANT_ID] appears frozen without clear communication.

If this freeze is pursuant to a Law Enforcement Agency (LEA) directive, I formally request:
1. Written confirmation of the LEA order reference number
2. Name of the issuing authority
3. Scope and duration of the freeze

I am engaging legal counsel and request all future communication in writing.

IMPORTANT: If I have not received written communication within 48 hours,
I will approach the RBI Integrated Ombudsman.

Merchant ID: [YOUR_MERCHANT_ID]
Regards, [YOUR_NAME]
""",
    }

    ticket = base_templates.get(hold_reason, base_templates["KYC_MISSING_DOCS"])

    _rag_ok = bool(rag_answer) and not any(p in rag_answer.lower() for p in ["i could not find", "not found in", "not present in the context"])
    if _rag_ok:
        ticket += f"\n---\nRELEVANT RBI PROVISION (auto-retrieved):\n{rag_answer}\n"

    return ticket


def get_escalation_path() -> list[dict]:
    return [
        {"tier": 1, "action": "Submit Razorpay support ticket", "timeline": "Wait 24-48 hours for response"},
        {"tier": 2, "action": "Escalate to Razorpay Grievance Officer", "timeline": "If no resolution after 5 business days"},
        {"tier": 3, "action": "File complaint with RBI Integrated Ombudsman", "timeline": "If 30 days pass without resolution", "url": "https://cms.rbi.org.in"},
    ]
