from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from Agent1.kyc_agent import KYCDiagnosisAgent, QUESTIONS
from Agent1.ticket_drafter import draft_ticket
from Agent2.reconciliation_agent import ReconciliationAgent
from Agent3.escalation_agent import EscalationAgent
from src import activity_history, auth, config
from src.citation_validator import validate_citations
from src.policy_evidence import search_local_policy


class AuthenticationTests(unittest.TestCase):
    def test_password_session_and_revocation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "auth.sqlite3")
            with patch.object(config, "AUTH_DB_PATH", database):
                user = auth.register_user(" Merchant@Example.com ", "long-enough-password123", "Merchant")
                self.assertEqual(user["email"], "merchant@example.com")
                self.assertIsNotNone(auth.authenticate_user("merchant@example.com", "long-enough-password123"))
                self.assertIsNone(auth.authenticate_user("merchant@example.com", "wrong-password"))

                token = auth.create_session(user["id"])
                self.assertEqual(auth.get_session_user(token)["id"], user["id"])
                auth.revoke_session(token)
                self.assertIsNone(auth.get_session_user(token))

    def test_oauth_state_is_single_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "auth.sqlite3")
            with patch.object(config, "AUTH_DB_PATH", database):
                state, nonce = auth.create_oauth_state("/")
                consumed = auth.consume_oauth_state(state)
                self.assertEqual(consumed["nonce"], nonce)
        self.assertIsNone(auth.consume_oauth_state(state))

    def test_non_string_session_tokens_are_anonymous(self) -> None:
        self.assertIsNone(auth.get_session_user(object()))
        auth.revoke_session(object())


class ActivityHistoryTests(unittest.TestCase):
    def test_history_is_persistent_scoped_and_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                activity_history.record_activity(7, "agent1", "completed", "First diagnosis", "Medium priority")
                activity_history.record_activity(7, "agent2", "completed", "Settlement audit", "3 transactions")
                activity_history.record_activity(8, "agent1", "completed", "Another user's case")

                all_entries = activity_history.read_activity_history(7)
                self.assertEqual([entry["title"] for entry in all_entries], ["Settlement audit", "First diagnosis"])
                agent1_entries = activity_history.read_activity_history(7, section="agent1")
                self.assertEqual([entry["title"] for entry in agent1_entries], ["First diagnosis"])
                self.assertEqual(activity_history.read_activity(7, agent1_entries[0]["id"])["title"], "First diagnosis")
                self.assertIsNone(activity_history.read_activity(8, agent1_entries[0]["id"]))
                self.assertIsNone(activity_history.read_activity(7, agent1_entries[0]["id"], section="agent2"))
                counts = activity_history.read_activity_counts(7)
                self.assertEqual(sum(row["activity_count"] for row in counts), 2)

                self.assertFalse(activity_history.delete_activity(8, all_entries[0]["id"]))
                self.assertTrue(activity_history.delete_activity(7, all_entries[0]["id"]))
                self.assertEqual(activity_history.clear_activity_history(7, "agent1"), 1)
                self.assertEqual(activity_history.read_activity_history(7), [])

    def test_history_rejects_unknown_sections(self) -> None:
        with self.assertRaises(ValueError):
            activity_history.record_activity(1, "unknown", "completed", "Invalid")


class WorkflowTests(unittest.TestCase):
    @staticmethod
    def _kyc_diagnosis(answers: list[str]) -> dict:
        agent = KYCDiagnosisAgent()
        result = None
        for answer in answers:
            result = agent.step(answer)
        return result["diagnosis"]

    def test_kyc_flow_validates_order_and_completes(self) -> None:
        agent = KYCDiagnosisAgent()
        with self.assertRaises(ValueError):
            agent.step("not an option")
        result = None
        for _, _, options in QUESTIONS:
            result = agent.step(options[0])
        self.assertTrue(result["done"])
        with self.assertRaises(RuntimeError):
            agent.step(QUESTIONS[-1][2][0])

    def test_kyc_does_not_infer_law_enforcement_from_silence(self) -> None:
        diagnosis = self._kyc_diagnosis([
            "Account Suspended",
            "No email received",
            "Sole Proprietor (Registered / Udyam)",
            "No - normal volume",
            "No",
            QUESTIONS[-1][2][0],
        ])
        self.assertEqual(diagnosis["hold_reason"], "RESTRICTION_UNCONFIRMED")

    def test_explicit_regulatory_notice_controls_regulatory_result(self) -> None:
        diagnosis = self._kyc_diagnosis([
            "Law enforcement / regulatory restriction shown",
            "No email received",
            "Private Limited Company",
            "Yes - much higher than usual",
            "Yes",
            QUESTIONS[-1][2][-1],
        ])
        self.assertEqual(diagnosis["hold_reason"], "REGULATORY_LEA")

    def test_normal_account_with_late_settlement_is_not_misclassified_as_kyc(self) -> None:
        diagnosis = self._kyc_diagnosis([
            "Settlement not arriving (account looks normal)",
            "No email received",
            "Partnership Firm",
            "No - normal volume",
            "No",
            QUESTIONS[-1][2][1],
        ])
        self.assertEqual(diagnosis["hold_reason"], "SETTLEMENT_DELAY")

    def test_support_request_keeps_raw_retrieval_evidence_separate(self) -> None:
        diagnosis = self._kyc_diagnosis([
            "Live Disabled",
            "Yes - asking for GST Certificate",
            "Individual Freelancer",
            "No - normal volume",
            "No",
            QUESTIONS[-1][2][1],
        ])
        ticket = draft_ticket(diagnosis, "RAW RETRIEVAL EVIDENCE")
        self.assertNotIn("RAW RETRIEVAL EVIDENCE", ticket)
        self.assertIn("registered as an Individual Freelancer", ticket)

    def test_reconciliation_sample_balances_and_exports(self) -> None:
        agent = ReconciliationAgent()
        content = Path(config.SAMPLE_SETTLEMENT_PATH).read_text(encoding="utf-8")
        parsed = agent.parse_csv(content)
        self.assertEqual(parsed["parsed"], 15)
        self.assertFalse(parsed["errors"])
        summary = agent.analyze()
        self.assertEqual(summary["total_transactions"], 15)
        self.assertGreaterEqual(summary["recovery_amount_net"], 0)
        self.assertIn("MerchantOS Settlement Reconciliation Report", agent.export_report_csv())

    def test_partial_settlement_and_invalid_rows(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method,transaction_date,settlement_date
partial,1000,20,3.6,400,on_hold,card,2026-09-04,2026-09-08
bad,100,2,0.36,0,unknown,card,2026-09-04,2026-09-08
"""
        parsed = agent.parse_csv(content)
        self.assertEqual(parsed["parsed"], 1)
        self.assertEqual(len(parsed["warnings"]), 1)
        summary = agent.analyze()
        self.assertEqual(summary["recovery_amount"], 600)
        self.assertEqual(summary["recovery_amount_net"], 576.4)

    def test_business_day_elapsed(self) -> None:
        with patch.object(config, "SETTLEMENT_DAY_MODE", "business"):
            self.assertEqual(
                ReconciliationAgent._settlement_elapsed_days(date(2026, 9, 4), date(2026, 9, 7)),
                1,
            )
        with patch.object(config, "SETTLEMENT_DAY_MODE", "calendar"):
            self.assertEqual(
                ReconciliationAgent._settlement_elapsed_days(date(2026, 9, 4), date(2026, 9, 7)),
                3,
            )

    def test_negative_escalation_days_choose_first_tier(self) -> None:
        self.assertEqual(EscalationAgent().recommend_tier(-5)["tier"], 1)


class EvidenceTests(unittest.TestCase):
    def test_source_citations_are_checked(self) -> None:
        chunks = [{"source": "policy.txt", "page": 1, "similarity": 0.9}]
        self.assertTrue(validate_citations("Supported. [Source: policy.txt]", chunks)["is_valid"])
        self.assertFalse(validate_citations("Unsupported. [Source: other.txt]", chunks)["is_valid"])

    def test_local_policy_contains_current_direction_reference(self) -> None:
        result = search_local_policy("RBI payment aggregator merchant due diligence paragraph 13")
        combined = result["answer"] + " " + result["source"]
        self.assertIn("rbi_pa_2025_knowledge.txt", combined)


if __name__ == "__main__":
    unittest.main()
