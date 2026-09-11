from __future__ import annotations

import itertools
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from Agent1.kyc_agent import (
    CUSTOM_ISSUE_MAX_LENGTH,
    HOLD_REASONS,
    MERCHANT_TYPES,
    QUESTIONS,
    RAG_QUERIES,
    KYCDiagnosisAgent,
)
from Agent1.ticket_drafter import draft_ticket
from src import config
from src.policy_evidence import get_policy_evidence, search_local_policy


SPECIAL_GST_MERCHANTS = {
    "Sole Proprietor (Unregistered)",
    "Individual Freelancer",
    "NGO / Trust / Society",
}


def expected_reason(answers: tuple[str, ...]) -> str:
    dashboard, kyc_email, merchant_type, transaction_spike, chargeback, _ = answers
    if "law enforcement" in dashboard.lower() or "regulatory restriction" in dashboard.lower():
        return "REGULATORY_LEA"
    if chargeback == "Yes":
        return "RISK_CHARGEBACK"
    if transaction_spike == "Yes - much higher than usual":
        return "RISK_TXN_SPIKE"
    if "GST" in kyc_email and merchant_type in SPECIAL_GST_MERCHANTS:
        return "KYC_DOCUMENT_CLARIFICATION"
    if kyc_email.startswith("Yes"):
        return "KYC_ACTION_REQUIRED"
    if dashboard == "Settlement not arriving (account looks normal)":
        return "SETTLEMENT_DELAY"
    return "RESTRICTION_UNCONFIRMED"


class Agent1CombinationTests(unittest.TestCase):
    def test_all_selectable_answer_combinations(self) -> None:
        branch_markers = {
            "KYC_DOCUMENT_CLARIFICATION": "KYC Document Clarification Request",
            "KYC_ACTION_REQUIRED": "KYC Verification Response",
            "RISK_TXN_SPIKE": "Transaction Volume Clarification",
            "RISK_CHARGEBACK": "Chargeback & Dispute Clarification",
            "REGULATORY_LEA": "Formal Request for Written Notice & Reason",
            "SETTLEMENT_DELAY": "Delayed Settlement - Request for Status and Reconciliation",
            "RESTRICTION_UNCONFIRMED": "Request for Reason and Remediation",
        }
        forbidden_ticket_text = (
            "a Individual",
            "a NGO",
            "configured operational",
            "configured 24h",
            "triggering this hold",
            "Regulatory baseline reviewed: Regulatory baseline",
            "Directions, 2025 requires",
            "statutory T+2",
            "Visa VDMP 0.9%",
            "Mastercard ECP 1.0%",
        )
        option_sets = [question[2] for question in QUESTIONS]
        tested = 0

        for answers in itertools.product(*option_sets):
            agent = KYCDiagnosisAgent()
            result = None
            for answer in answers:
                result = agent.step(answer)
            self.assertIsNotNone(result)
            self.assertTrue(result["done"])
            diagnosis = result["diagnosis"]
            reason = expected_reason(answers)
            self.assertEqual(diagnosis["hold_reason"], reason, answers)
            self.assertEqual(diagnosis["hold_info"], HOLD_REASONS[reason])
            self.assertEqual(diagnosis["merchant_type"], answers[2])
            self.assertTrue(diagnosis["required_docs"]["mandatory"])
            self.assertIn(reason, RAG_QUERIES)

            ticket = draft_ticket(diagnosis, "RAW RETRIEVAL MUST STAY SEPARATE")
            self.assertIn(branch_markers[reason], ticket)
            self.assertIn("RESOLUTION TIMELINE REQUESTED:", ticket)
            self.assertIn("[YOUR_MERCHANT_ID]", ticket)
            self.assertNotIn("RAW RETRIEVAL MUST STAY SEPARATE", ticket)
            self.assertNotIn(answers[-1], ticket)
            if reason in {"KYC_DOCUMENT_CLARIFICATION", "KYC_ACTION_REQUIRED"}:
                article = "an" if answers[2].startswith(("Individual", "NGO")) else "a"
                self.assertIn(f"registered as {article} {answers[2]}", ticket)
            for forbidden in forbidden_ticket_text:
                self.assertNotIn(forbidden, ticket)
            tested += 1

        self.assertEqual(tested, math.prod(len(options) for options in option_sets))
        self.assertEqual(tested, 3136)

    def test_custom_issue_validation_and_safe_ticket_rendering(self) -> None:
        agent = KYCDiagnosisAgent()
        with self.assertRaises(ValueError):
            agent.step("Custom Issue:   ")
        with self.assertRaises(ValueError):
            agent.step("Custom Issue: " + "x" * (CUSTOM_ISSUE_MAX_LENGTH + 1))

        custom_text = "Payouts paused; dashboard gives no reason"
        answers = [
            f"Custom Issue: {custom_text}",
            "No email received",
            "Sole Proprietor (Unregistered)",
            "No - normal volume",
            "No",
            QUESTIONS[-1][2][-1],
        ]
        result = None
        for answer in answers:
            result = agent.step(answer)
        diagnosis = result["diagnosis"]
        self.assertEqual(diagnosis["hold_reason"], "RESTRICTION_UNCONFIRMED")
        ticket = draft_ticket(diagnosis)
        self.assertIn(custom_text, ticket)
        self.assertNotIn("Custom Issue:", ticket)

    def test_agent1_has_no_direct_environment_or_deployment_defaults(self) -> None:
        agent_directory = Path(__file__).resolve().parents[1] / "Agent1"
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(agent_directory.glob("*.py"))
        )
        self.assertNotIn("os.getenv(", combined)
        self.assertNotIn("localhost:", combined)
        self.assertNotIn("razorpay.com", combined.lower())


class Agent1EvidenceTests(unittest.TestCase):
    EXPECTED_SOURCES = {
        "KYC_DOCUMENT_CLARIFICATION": {"rbi_pa_2025_knowledge.txt", "razorpay_policies.txt"},
        "KYC_ACTION_REQUIRED": {"rbi_pa_2025_knowledge.txt", "merchant_recovery_playbook.txt"},
        "RISK_TXN_SPIKE": {"rbi_pa_2025_knowledge.txt", "razorpay_policies.txt"},
        "RISK_CHARGEBACK": {"rbi_pa_2025_knowledge.txt"},
        "REGULATORY_LEA": {"rbi_pa_2025_knowledge.txt"},
        "SETTLEMENT_DELAY": {"rbi_pa_2025_knowledge.txt", "razorpay_policies.txt"},
        "RESTRICTION_UNCONFIRMED": {"rbi_pa_2025_knowledge.txt", "merchant_recovery_playbook.txt"},
    }

    def _assert_evidence(self, reason: str, result: dict) -> None:
        self.assertTrue(result["answer"].strip(), reason)
        self.assertTrue(result["chunks"], reason)
        confidence = result["confidence"]
        self.assertGreaterEqual(confidence["score"], 0)
        self.assertLessEqual(confidence["score"], 1)
        self.assertIn(confidence["label"], {"low", "medium", "high"})
        sources = {chunk["source"] for chunk in result["chunks"]}
        self.assertTrue(sources.intersection(self.EXPECTED_SOURCES[reason]), (reason, sources))

    def test_every_diagnosis_has_current_local_evidence_and_confidence(self) -> None:
        for reason, query in RAG_QUERIES.items():
            result = search_local_policy(query)
            self._assert_evidence(reason, result)
            self.assertEqual(result["retrieval"], "Local document search")
            self.assertEqual(result["confidence_method"], "Weighted query-term coverage")

    def test_every_diagnosis_has_semantic_evidence_and_cosine_confidence(self) -> None:
        # The semantic index is tested without an external LLM so this check is
        # deterministic and verifies the vector fallback used during outages.
        with patch.object(config, "GROQ_API_KEY", ""):
            for reason, query in RAG_QUERIES.items():
                result = get_policy_evidence(query, semantic=True)
                self._assert_evidence(reason, result)
                self.assertEqual(result["retrieval"], "Semantic source recheck")
                self.assertEqual(result["confidence_method"], "Top cosine similarity")
                self.assertFalse(result["llm_used"])


if __name__ == "__main__":
    unittest.main()
