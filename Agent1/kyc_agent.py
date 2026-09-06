"""
Agent 1: KYC + Fund Hold Diagnosis Agent (MerchantOS)
DebugQuest-style loop: reset -> step -> done
Diagnoses why a Razorpay merchant account is held, using RBI PA Directions 2025.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    "KYC_MISSING_DOCS": {
        "label": "KYC - Missing Documents", "urgency": "HIGH", "color": "red",
        "description": "Your account is held because required KYC documents are missing or incomplete.",
    },
    "KYC_WRONG_DOCS": {
        "label": "KYC - Wrong Documents Requested", "urgency": "HIGH", "color": "red",
        "description": "Razorpay has asked for documents NOT required by RBI for your merchant type. You have the right to dispute this.",
    },
    "RISK_TXN_SPIKE": {
        "label": "Risk Flag - Unusual Transaction Volume", "urgency": "MEDIUM", "color": "orange",
        "description": "A sudden spike in transaction volume triggered an automated risk hold.",
    },
    "RISK_CHARGEBACK": {
        "label": "Risk Flag - Card Network Dispute / Chargeback Threshold", "urgency": "MEDIUM", "color": "orange",
        "description": "Your dispute ratio triggered card network monitoring (Visa VDMP 0.9% / Mastercard ECP 1.0%) or aggregator risk thresholds. Requires fulfillment and delivery documentation to substantiate legitimate sales.",
    },
    "REGULATORY_LEA": {
        "label": "Regulatory / Law Enforcement Hold", "urgency": "CRITICAL", "color": "darkred",
        "description": "This hold is likely from a law enforcement or regulatory directive. Requires immediate legal counsel.",
    },
}

REQUIRED_DOCS = {
    "sole_proprietor_unregistered": {
        "mandatory": ["PAN Card", "Aadhaar Card"],
        "one_of": ["Bank Statement (last 6 months)", "Udyam Registration Certificate", "IEC Code"],
        "not_required": ["GST Certificate - NOT mandatory per RBI PA Directions 2025 Para 4.3(ii)"],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.3(ii), Page 12",
    },
    "sole_proprietor_registered": {
        "mandatory": ["PAN Card", "Aadhaar Card", "Udyam / MSME Registration Certificate"],
        "one_of": ["GST Certificate", "Bank Statement (last 6 months)"],
        "not_required": [],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.3(i), Page 12",
    },
    "partnership": {
        "mandatory": ["Firm PAN Card", "Partnership Deed", "PAN + Aadhaar of all partners"],
        "one_of": ["GST Certificate", "Bank Statement (last 6 months)"],
        "not_required": [],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.4, Page 13",
    },
    "pvt_ltd": {
        "mandatory": ["Certificate of Incorporation", "Company PAN Card", "MOA / AOA", "Board Resolution", "Director PAN + Aadhaar"],
        "one_of": ["GST Certificate", "Audited Financial Statements"],
        "not_required": [],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.5, Page 13",
    },
    "public_ltd": {
        "mandatory": ["Certificate of Incorporation", "Company PAN Card", "MOA / AOA", "Board Resolution", "Director PAN + Aadhaar", "Shareholder list (>10% holders)"],
        "one_of": ["GST Certificate", "Audited Financial Statements"],
        "not_required": [],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.5, Page 14",
    },
    "ngo_trust": {
        "mandatory": ["Trust Deed / Society Registration Certificate", "PAN Card", "Trustee / Committee Member PAN + Aadhaar"],
        "one_of": ["12A / 80G Certificate", "FCRA Certificate (for foreign donations)"],
        "not_required": ["GST Certificate - NGOs typically exempt from GST"],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.6, Page 14",
    },
    "freelancer": {
        "mandatory": ["PAN Card", "Aadhaar Card"],
        "one_of": ["Bank Statement (last 6 months)", "Work contracts / Portfolio as proof of business"],
        "not_required": ["GST Certificate - NOT mandatory below GST threshold per RBI Para 4.3(ii)"],
        "rbi_ref": "RBI PA Master Directions 2025, Para 4.3(ii), Page 12",
    },
}

# Use consistent regular hyphens (no em dashes) for reliable string matching
QUESTIONS = [
    ("dashboard_status", "What does your Razorpay dashboard show?",
     ["Live Disabled", "Payment Disabled", "Under Review / Pending", "Account Suspended", "Settlement not arriving (account looks normal)"]),
    ("kyc_email", "Did you receive a KYC-related email from Razorpay?",
     ["Yes - asking for GST Certificate", "Yes - asking for other documents", "Yes - asking for IPV (in-person verification)", "No email received"]),
    ("merchant_type", "What type of business are you?",
     list(MERCHANT_TYPES.values())),
    ("txn_spike", "In the last 30 days, did your transaction volume spike suddenly?",
     ["Yes - much higher than usual", "No - normal volume"]),
    ("chargeback", "Have you received any chargeback or dispute notices?",
     ["Yes", "No"]),
]

RAG_QUERIES = {
    "KYC_WRONG_DOCS":   "Is GST certificate mandatory for {merchant_type} under RBI PA Directions 2025? What alternative documents are accepted?",
    "KYC_MISSING_DOCS": "What KYC documents must a {merchant_type} submit to Razorpay under RBI PA Directions 2025?",
    "RISK_TXN_SPIKE":   "What should a merchant do when their settlement is held due to unusual transaction volume? What documents resolve a risk hold?",
    "RISK_CHARGEBACK":  "What evidence must a merchant provide to resolve a chargeback or risk hold under Payment Aggregator guidelines? How do card network dispute thresholds impact settlement releases?",
    "REGULATORY_LEA":   "What happens when a payment aggregator merchant account is frozen due to a law enforcement or regulatory directive?",
}


class KYCDiagnosisAgent:
    """
    DebugQuest-style diagnostic agent.
    Mirrors the reset -> step -> done loop from DebugQuest.
    """

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

        if "no email" in kyc_lower and "suspended" in dashboard_lower:
            hold_reason = "REGULATORY_LEA"
        elif chargeback.strip() == "Yes":
            hold_reason = "RISK_CHARGEBACK"
        elif "much higher" in txn_lower:
            hold_reason = "RISK_TXN_SPIKE"
        elif "gst" in kyc_lower and merchant_key in ["sole_proprietor_unregistered", "freelancer", "ngo_trust"]:
            hold_reason = "KYC_WRONG_DOCS"
        else:
            hold_reason = "KYC_MISSING_DOCS"

        merchant_label = MERCHANT_TYPES.get(merchant_key, "Unknown")
        rag_query = RAG_QUERIES.get(hold_reason, "").format(merchant_type=merchant_label)

        return {
            "hold_reason": hold_reason,
            "hold_info": HOLD_REASONS[hold_reason],
            "merchant_type": merchant_label,
            "merchant_type_key": merchant_key,
            "required_docs": REQUIRED_DOCS.get(merchant_key, REQUIRED_DOCS["sole_proprietor_unregistered"]),
            "rag_query": rag_query,
            "answers": self.answers,
        }


if __name__ == "__main__":
    # Quick self-test
    agent = KYCDiagnosisAgent()
    agent.reset()
    for ans in ["Live Disabled", "Yes - asking for GST Certificate", "Sole Proprietor (Unregistered)", "No - normal volume", "No"]:
        result = agent.step(ans)
    d = result["diagnosis"]
    print("Self-test:", d["hold_reason"], "|", d["merchant_type"])
    assert d["hold_reason"] == "KYC_WRONG_DOCS", "Self-test FAILED"
    print("Self-test PASSED")
