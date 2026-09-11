"""Evidence-aware KYC and settlement-restriction triage for MerchantOS."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
CUSTOM_ISSUE_MAX_LENGTH = getattr(
    config,
    "KYC_CUSTOM_ISSUE_MAX_LENGTH",
    config.ACTIVITY_DETAIL_MAX_LENGTH,
)
MERCHANT_TYPES = {
    "sole_proprietor_unregistered": "Sole Proprietor (Unregistered)",
    "sole_proprietor_registered":   "Sole Proprietor (Registered / Udyam)",
    "partnership":                  "Partnership Firm",
    "pvt_ltd":                      "Private Limited Company",
    "public_ltd":                   "Public Limited Company",
    "ngo_trust":                    "NGO / Trust / Society",
    "freelancer":                   "Individual Freelancer",
}

HOLD_REASONS = {
    "KYC_ACTION_REQUIRED": {
        "label": "KYC - Verification Action Required", "urgency": "HIGH", "color": "red",
        "description": (
            f"A {config.AGGREGATOR_SHORT} KYC request was reported. Complete the exact dashboard request, "
            "or ask support to confirm the current requirement and any accepted alternative."
        ),
    },
    "KYC_DOCUMENT_CLARIFICATION": {
        "label": "KYC - Document Request Needs Clarification", "urgency": "HIGH", "color": "red",
        "description": (
            f"{config.AGGREGATOR_SHORT} requested a GST certificate. Ask whether this is based on "
            "its merchant policy, your business profile, or a regulatory requirement, and whether another "
            "accepted business document can satisfy the check."
        ),
    },
    "RISK_TXN_SPIKE": {
        "label": "Possible Risk Review - Unusual Transaction Volume", "urgency": "MEDIUM", "color": "orange",
        "description": "The reported volume spike is a possible risk-review signal; only the provider can confirm the actual reason for the restriction.",
    },
    "RISK_CHARGEBACK": {
        "label": "Possible Risk Review - Chargeback or Dispute Activity", "urgency": "MEDIUM", "color": "orange",
        "description": "The reported disputes may be relevant to provider or card-network monitoring, but the applicable trigger must be confirmed. Gather records for the affected transactions.",
    },
    "REGULATORY_LEA": {
        "label": "Regulatory / Law Enforcement Restriction Reported", "urgency": "CRITICAL", "color": "darkred",
        "description": (
            "The dashboard reportedly identifies a regulatory or law-enforcement restriction. "
            "Preserve the exact notice, request written clarification, and consider qualified legal advice."
        ),
    },
    "SETTLEMENT_DELAY": {
        "label": "Settlement Delay - Cause Unconfirmed", "urgency": "MEDIUM", "color": "orange",
        "description": (
            "The account reportedly looks normal, but a settlement has not arrived. Check the settlement "
            "timeline, agreement, adjustments, bank statement, and any hold notice before assigning a cause."
        ),
    },
    "RESTRICTION_UNCONFIRMED": {
        "label": "Account Restriction - Cause Unconfirmed", "urgency": "HIGH", "color": "red",
        "description": (
            "The selected answers do not establish a KYC, risk, or regulatory cause. Preserve the exact "
            "dashboard message and ask the provider for the reason and required remediation."
        ),
    },
}

REQUIRED_DOCS = {
    "sole_proprietor_unregistered": {
        "mandatory": ["PAN or Form 60, as applicable", "Officially valid identity/address document", "Bank-account proof"],
        "one_of": ["Business documents requested in the current dashboard", "Udyam / business registration, if held", "GST registration, if registered", "Recent invoices, contracts, or other accepted business proof"],
        "not_required": ["The PA Directions do not create a merchant-type GST checklist; ask the provider to state the basis for requesting GST."],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
    "sole_proprietor_registered": {
        "mandatory": ["Proprietor PAN", "Authorised-signatory identity/address proof", "Bank-account proof"],
        "one_of": ["Business documents requested in the current dashboard", "Udyam / MSME registration, if applicable", "GST registration, if registered", "Other accepted registration or licence"],
        "not_required": [],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
    "partnership": {
        "mandatory": ["Firm PAN", "Partnership deed", "Authorised-signatory identity/address proof", "Bank-account proof"],
        "one_of": ["Registration, GST, or licence requested in the current dashboard", "Authorisation for the signatory, if applicable", "Beneficial-owner details where the applicable threshold is met"],
        "not_required": [],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
    "pvt_ltd": {
        "mandatory": ["Certificate of Incorporation", "Company PAN", "MOA / AOA", "Authorised-signatory identity/address proof", "Bank-account proof"],
        "one_of": ["Board resolution or power of attorney for the signatory", "Beneficial-owner declaration/details where the applicable threshold is met", "GST registration, if registered", "Category-specific licence or certification"],
        "not_required": [],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
    "public_ltd": {
        "mandatory": ["Certificate of Incorporation", "Company PAN", "MOA / AOA", "Authorised-signatory identity/address proof", "Bank-account proof"],
        "one_of": ["Board resolution or power of attorney for the signatory", "Beneficial-owner declaration/details where the applicable threshold is met", "GST registration, if registered", "Category-specific licence or certification"],
        "not_required": [],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
    "ngo_trust": {
        "mandatory": ["Trust deed / society registration certificate", "Entity PAN", "Authorised-signatory identity/address proof", "Bank-account proof"],
        "one_of": ["Trustee, committee-member, or beneficial-owner details where applicable", "12A / 80G certificate, if applicable", "FCRA certificate only when applicable to foreign contributions", "Other category-specific registration or licence"],
        "not_required": ["Tax-registration requirements depend on the entity's activities and applicable tax law; confirm with a qualified adviser."],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
    "freelancer": {
        "mandatory": ["PAN or Form 60, as applicable", "Officially valid identity/address document", "Bank-account proof"],
        "one_of": ["Business documents requested in the current dashboard", "Recent invoices or work contracts", "Portfolio or other accepted business proof", "GST or Udyam registration, if held"],
        "not_required": ["The PA Directions do not set a freelancer GST threshold; tax-registration requirements must be checked separately."],
        "rbi_ref": f"Regulatory baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DUE_DILIGENCE_REFERENCE}. Provider checklist controls the case-specific request.",
    },
}

CASE_DOCUMENTS = {
    "RISK_TXN_SPIKE": {
        "mandatory": [
            "Affected transaction and settlement IDs",
            "Recent sales invoices or order records",
            "Fulfilment, delivery, or service-completion evidence",
            "A dated explanation for the volume change",
        ],
        "one_of": [
            "Campaign, launch, or seasonal-sale records",
            "Customer communications",
            "Supplier or inventory records",
            "Relevant bank and settlement statements",
        ],
        "not_required": [],
        "rbi_ref": "Case evidence for a possible provider risk review; the provider must confirm the actual trigger and remediation criteria.",
    },
    "RISK_CHARGEBACK": {
        "mandatory": [
            "Each chargeback or dispute notice",
            "Affected transaction and order IDs",
            "Proof of delivery, fulfilment, or service completion",
            "Customer communications and refund records",
        ],
        "one_of": [
            "Terms, cancellation, and refund policy accepted by the customer",
            "Authentication or payment records available to the merchant",
            "Prior dispute responses and provider decisions",
        ],
        "not_required": [],
        "rbi_ref": "Case evidence for reported dispute activity; ask the provider to identify the applicable provider or card-network rule.",
    },
    "REGULATORY_LEA": {
        "mandatory": [
            "Exact dashboard restriction notice or screenshot",
            "Provider emails, messages, and support responses",
            "Affected transaction and settlement IDs",
            "A dated timeline of the restriction and communications",
        ],
        "one_of": [
            "Any order, notice, authority name, or reference disclosed to you",
            "Relevant bank and settlement statements",
            "Company authorisation for the person handling the matter",
            "Correspondence reviewed with qualified legal counsel",
        ],
        "not_required": [
            "Do not infer or invent an authority, order number, or legal basis that the provider has not disclosed."
        ],
        "rbi_ref": f"Communication baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE}. Any authority order controls what may be disclosed and how the restriction is handled.",
    },
    "SETTLEMENT_DELAY": {
        "mandatory": [
            "Affected settlement and transaction IDs",
            "Settlement report and expected credit date",
            "Bank statement covering the expected credit period",
            "Dashboard status and any provider notice",
        ],
        "one_of": [
            "Fee, tax, refund, chargeback, and adjustment breakdown",
            "Bank reference number or failure message",
            "Relevant merchant-agreement settlement clause",
        ],
        "not_required": [],
        "rbi_ref": f"Settlement baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_SETTLEMENT_REFERENCE}. The account-specific agreement and dashboard timeline control the expected date.",
    },
    "RESTRICTION_UNCONFIRMED": {
        "mandatory": [
            "Exact dashboard status or screenshot",
            "Provider emails, messages, and support responses",
            "Affected product, transaction, or settlement IDs",
            "A dated timeline of events",
        ],
        "one_of": [
            "Relevant bank or settlement statements",
            "Previously submitted documents and acknowledgements",
            "Merchant agreement or policy shown for the account",
        ],
        "not_required": ["Do not assign a KYC, risk, or regulatory cause until the available evidence supports it."],
        "rbi_ref": f"Clarification baseline: {config.PA_DIRECTIONS_REFERENCE}, {config.PA_DISPUTE_REFERENCE}. Ask for the reason, remediation steps, and escalation route in writing.",
    },
}

# Use consistent regular hyphens (no em dashes) for reliable string matching
QUESTIONS = [
    ("dashboard_status", f"What does your {config.AGGREGATOR_SHORT} dashboard show?",
     ["Live Disabled", "Payment Disabled", "Under Review / Pending", "Account Suspended", "Law enforcement / regulatory restriction shown", "Settlement not arriving (account looks normal)", "Something else / Not listed (Custom Issue)"]),
    ("kyc_email", f"Did you receive a KYC-related email from {config.AGGREGATOR_SHORT}?",
     ["Yes - asking for GST Certificate", "Yes - asking for other documents", "Yes - asking for IPV, video, or in-person verification", "No email received"]),
    ("merchant_type", "What type of business are you?",
     list(MERCHANT_TYPES.values())),
    ("txn_spike", f"In the last {config.TRANSACTION_LOOKBACK_DAYS} days, did your transaction volume spike suddenly?",
     ["Yes - much higher than usual", "No - normal volume"]),
    ("chargeback", "Have you received any chargeback or dispute notices?",
     ["Yes", "No"]),
    ("days_on_hold", "How many days has this hold or restriction been in place?",
     [f"1 to {config.HOLD_RECENT_MAX_DAYS} days (Recent)",
      f"{config.HOLD_RECENT_MAX_DAYS + 1} to {config.HOLD_STANDARD_MAX_DAYS} days (Follow-up needed)",
      f"{config.HOLD_URGENT_TRIGGER_DAYS} to {config.OMBUDSMAN_TRIGGER_DAYS} days (Formal provider escalation)",
      f"> {config.OMBUDSMAN_TRIGGER_DAYS} days (Review prior complaint and escalation eligibility)"]),
]

RAG_QUERIES = {
    "KYC_DOCUMENT_CLARIFICATION": f"What does {config.PA_DIRECTIONS_REFERENCE} {config.PA_DUE_DILIGENCE_REFERENCE} require for merchant due diligence, and what does it not specify about GST documents?",
    "KYC_ACTION_REQUIRED": f"What does {config.PA_DIRECTIONS_REFERENCE} {config.PA_DUE_DILIGENCE_REFERENCE} require for merchant due diligence and CKYCR checks?",
    "RISK_TXN_SPIKE":   "What records should a merchant preserve when an account restriction coincides with unusual transaction volume, and how should the merchant ask the provider to confirm the reason and remediation criteria?",
    "RISK_CHARGEBACK":  "What records should a merchant preserve when chargebacks or disputes coincide with an account restriction, and what do the current sources say about fixed card-network thresholds and settlement timing?",
    "REGULATORY_LEA": f"What does {config.PA_DIRECTIONS_REFERENCE} paragraph 8 require about merchant policies, the officer for merchant issues, and the grievance escalation matrix?",
    "SETTLEMENT_DELAY": f"What settlement schedule, merchant agreement timeline, dashboard status, bank statement, fees, tax, refunds, chargebacks, and adjustments should a {config.AGGREGATOR_SHORT} merchant verify?",
    "RESTRICTION_UNCONFIRMED": "What dashboard status, transaction and settlement IDs, dates, screenshots, emails, support responses, bank statement, reason, remediation items, policy clause, and expected review date should a merchant preserve or request?",
}


class KYCDiagnosisAgent:
    """
    DebugQuest-style diagnostic agent.
    Mirrors the reset -> step -> done loop from DebugQuest.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Start a fresh diagnosis session. Returns first question."""
        self.step_idx = 0
        self.answers = {}
        self.done = False
        self.diagnosis = None
        q = QUESTIONS[0]
        return {
            "question": q[1],
            "options": q[2],
            "key": q[0],
            "step": 1,
            "total": len(QUESTIONS),
        }

    def step(self, answer: str):
        """
        Record answer, advance to next question or produce diagnosis.
        Returns: {"done": False, "next": {...}} OR {"done": True, "diagnosis": {...}}
        """
        if self.done or self.step_idx >= len(QUESTIONS):
            raise RuntimeError("Diagnosis is already complete; call reset() to start again.")
        custom_issue = self.step_idx == 0 and answer.startswith("Custom Issue:")
        custom_text = answer.removeprefix("Custom Issue:").strip() if custom_issue else ""
        if answer not in QUESTIONS[self.step_idx][2] and not custom_issue:
            raise ValueError("Answer must be one of the options for the current question.")
        if custom_issue and not custom_text:
            raise ValueError("Custom issue text is required.")
        if custom_issue and len(custom_text) > CUSTOM_ISSUE_MAX_LENGTH:
            raise ValueError("Custom issue text is too long.")
        key = QUESTIONS[self.step_idx][0]
        self.answers[key] = answer
        self.step_idx += 1

        if self.step_idx >= len(QUESTIONS):
            self.done = True
            self.diagnosis = self._diagnose()
            return {"done": True, "diagnosis": self.diagnosis}

        q = QUESTIONS[self.step_idx]
        return {
            "done": False,
            "next": {
                "question": q[1],
                "options": q[2],
                "key": q[0],
                "step": self.step_idx + 1,
                "total": len(QUESTIONS),
            },
        }

    def _get_merchant_key(self, label: str) -> str:
        """Map display label back to internal key."""
        for k, v in MERCHANT_TYPES.items():
            if v == label:
                return k
        return "sole_proprietor_unregistered"

    def _diagnose(self) -> dict:
        """
        Priority-ordered diagnosis:
        LEA (most critical) -> Risk signals -> KYC wrong docs -> KYC missing docs
        """
        a = self.answers
        merchant_key = self._get_merchant_key(a.get("merchant_type", ""))
        kyc_email = a.get("kyc_email", "")
        txn_spike = a.get("txn_spike", "")
        chargeback = a.get("chargeback", "")
        dashboard = a.get("dashboard_status", "")

        # Normalise: strip and lower for comparisons
        kyc_lower = kyc_email.strip().lower()
        txn_lower = txn_spike.strip().lower()
        dashboard_lower = dashboard.strip().lower()

        if "law enforcement" in dashboard_lower or "regulatory restriction" in dashboard_lower:
            hold_reason = "REGULATORY_LEA"
        elif chargeback.strip() == "Yes":
            hold_reason = "RISK_CHARGEBACK"
        elif "much higher" in txn_lower:
            hold_reason = "RISK_TXN_SPIKE"
        elif "gst" in kyc_lower and merchant_key in ["sole_proprietor_unregistered", "freelancer", "ngo_trust"]:
            hold_reason = "KYC_DOCUMENT_CLARIFICATION"
        elif kyc_lower.startswith("yes"):
            hold_reason = "KYC_ACTION_REQUIRED"
        elif "settlement not arriving" in dashboard_lower:
            hold_reason = "SETTLEMENT_DELAY"
        else:
            hold_reason = "RESTRICTION_UNCONFIRMED"

        merchant_label = MERCHANT_TYPES.get(merchant_key, "Unknown")
        rag_query = RAG_QUERIES.get(hold_reason, "").format(merchant_type=merchant_label)
        required_docs = CASE_DOCUMENTS.get(
            hold_reason,
            REQUIRED_DOCS.get(merchant_key, REQUIRED_DOCS["sole_proprietor_unregistered"]),
        )
        required_docs = {
            key: list(value) if isinstance(value, list) else value
            for key, value in required_docs.items()
        }
        if hold_reason == "KYC_ACTION_REQUIRED" and "ipv" in kyc_lower:
            required_docs["one_of"].insert(
                0,
                "Current IPV/video-verification instructions and appointment details",
            )

        return {
            "hold_reason": hold_reason,
            "hold_info": HOLD_REASONS[hold_reason],
            "merchant_type": merchant_label,
            "merchant_type_key": merchant_key,
            "required_docs": required_docs,
            "rag_query": rag_query,
            "answers": self.answers,
        }


if __name__ == "__main__":
    # Quick self-test
    agent = KYCDiagnosisAgent()
    agent.reset()
    for ans in ["Live Disabled", "Yes - asking for GST Certificate", "Sole Proprietor (Unregistered)", "No - normal volume", "No", QUESTIONS[-1][2][1]]:
        result = agent.step(ans)
    d = result["diagnosis"]
    print("Self-test:", d["hold_reason"], "|", d["merchant_type"])
    assert d["hold_reason"] == "KYC_DOCUMENT_CLARIFICATION", "Self-test FAILED"
    print("Self-test PASSED")
