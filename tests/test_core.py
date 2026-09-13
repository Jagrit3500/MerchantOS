from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from Agent1.kyc_agent import KYCDiagnosisAgent, QUESTIONS
from Agent1.ticket_drafter import draft_ticket
from Agent2.reconciliation_agent import ReconciliationAgent
from Agent3.escalation_agent import ESCALATION_TIERS, EscalationAgent
from src import activity_history, auth, config
from src.citation_validator import validate_citations
from src.policy_evidence import get_policy_evidence, search_local_policy


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
                self.assertFalse(
                    activity_history.update_activity_metadata(8, agent1_entries[0]["id"], {"private": "no"})
                )
                self.assertTrue(
                    activity_history.update_activity_metadata(7, agent1_entries[0]["id"], {"snapshot": "saved"})
                )
                self.assertEqual(
                    activity_history.read_activity(7, agent1_entries[0]["id"])["metadata"]["snapshot"],
                    "saved",
                )
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
        self.assertEqual(summary["total_overcharge"], 0)
        self.assertEqual(summary["exception_transaction_count"], 4)
        self.assertEqual(summary["health_score"], {"score": 60, "label": "Needs Attention", "color": "orange"})
        self.assertEqual(summary["timing_assessment_status"], "unavailable")
        self.assertGreaterEqual(summary["recovery_amount_net"], 0)
        self.assertNotIn("FEE / TAX DIFFERENCE", agent.draft_recovery_ticket())
        self.assertIn("MerchantOS Settlement Reconciliation Report", agent.export_report_csv())

    def test_recovery_request_uses_account_policy_timing(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method,transaction_date,settlement_date
pay_MANUAL_HOLD_001,10000,0,0,0,on_hold,upi,2026-09-01,
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 1)
        agent.analyze()
        request = agent.draft_recovery_ticket()
        self.assertIn("applicable merchant-policy or agreement clause", request)
        self.assertIn("published merchant grievance escalation matrix", request)
        self.assertIn("merchant-grievance contact and escalation matrix required by paragraph 8", request)
        self.assertIn(config.AGGREGATOR_SUPPORT_URL, request)
        self.assertIn(config.AGGREGATOR_GRIEVANCE_URL, request)
        self.assertIn("nodal-officer@razorpay.com", request)
        self.assertNotIn("grievance.officer@razorpay.com", request)
        self.assertNotIn("specific RBI provision for each hold", request)
        self.assertNotIn("Settlement of eligible transactions within 2 business days", request)
        self.assertNotIn("If unresolved within 5 business days", request)

    def test_healthy_reconciliation_generates_confirmation(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method,transaction_date,settlement_date
pay_MANUAL_OK_001,10000,200,36,9764,settled,card,2026-09-01,2026-09-02
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 1)
        agent.analyze()
        request = agent.draft_recovery_ticket()
        self.assertIn("Subject: Settlement Reconciliation Confirmation", request)
        self.assertIn("The audit found no hold", request)
        self.assertNotIn("Missing/Held Funds", request)
        self.assertNotIn("If this remains unresolved", request)

    def test_standard_public_pricing_matches_two_percent_plus_gst(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method,transaction_date,settlement_date
upi_standard,1000,20,3.6,976.4,settled,upi,2026-09-01,2026-09-02
card_standard,1000,20,3.6,976.4,settled,card,2026-09-01,2026-09-02
netbanking_standard,1000,20,3.6,976.4,settled,netbanking,2026-09-01,2026-09-02
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 3)
        summary = agent.analyze()
        self.assertEqual(summary["total_expected_fee"], 60)
        self.assertEqual(summary["total_expected_tax"], 10.8)
        self.assertEqual(summary["total_overcharge"], 0)
        self.assertEqual(summary["exception_transaction_count"], 0)
        self.assertEqual(summary["timing_assessment_status"], "complete")
        self.assertEqual(summary["health_score"]["score"], 100)

    def test_missing_dates_are_reported_as_unassessed(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method
no_dates,1000,20,3.6,976.4,settled,card
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 1)
        summary = agent.analyze()
        self.assertEqual(summary["tat_count"], 0)
        self.assertEqual(summary["timing_evaluable_count"], 0)
        self.assertEqual(summary["timing_missing_count"], 1)
        self.assertEqual(summary["timing_assessment_status"], "unavailable")
        request = agent.draft_recovery_ticket()
        self.assertIn("Timing Assessment:         Not assessed", request)
        self.assertNotIn("no hold, pending settlement, timing exception", request)

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

    def test_reconciliation_accepts_common_headers_currency_statuses_and_iso_dates(self) -> None:
        agent = ReconciliationAgent()
        content = """\ufeffTransaction ID,Gross Amount,Platform Fee,GST,Net Amount,Payment Status,Payment Mode,Created At,Settled Date
pay_alias,"₹1,000.00",20,3.60,976.40,Successful,Credit-Card,2026-09-01T09:30:00+05:30,2026-09-02T17:00:00+05:30
"""
        parsed = agent.parse_csv(content)
        self.assertEqual(parsed, {"parsed": 1, "errors": [], "warnings": []})
        summary = agent.analyze()
        self.assertEqual(agent.transactions[0]["status"], "settled")
        self.assertEqual(agent.transactions[0]["payment_method"], "credit_card")
        self.assertEqual(summary["health_score"]["label"], "Healthy")
        self.assertEqual(summary["residual_variance"], 0)

    def test_settled_shortfall_is_an_exception_in_summary_letter_and_export(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method
pay_short,1000,20,3.6,900,settled,card
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 1)
        summary = agent.analyze()
        self.assertEqual(summary["settlement_difference_count"], 1)
        self.assertEqual(summary["total_settlement_shortfall"], 76.4)
        self.assertEqual(summary["amount_to_review"], 76.4)
        self.assertEqual(summary["net_recovery_requested"], 76.4)
        self.assertEqual(summary["residual_variance"], 76.4)
        self.assertEqual(summary["exception_transaction_count"], 1)
        self.assertIn("SETTLEMENT SHORTFALL", agent.draft_recovery_ticket())
        self.assertIn("SETTLEMENT BALANCE DIFFERENCE", agent.export_report_csv())

    def test_excess_settlement_is_flagged_without_becoming_a_recovery_request(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method
pay_excess,1000,20,3.6,980,settled,card
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 1)
        summary = agent.analyze()
        self.assertEqual(summary["total_settlement_excess"], 3.6)
        self.assertEqual(summary["net_recovery_requested"], 0)
        self.assertEqual(summary["residual_variance"], -3.6)
        self.assertIn("EXCESS SETTLEMENT DIFFERENCE", agent.draft_recovery_ticket())

    def test_reconciliation_rejects_values_that_cannot_produce_a_valid_audit(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method,transaction_date,settlement_date
zero,0,0,0,0,settled,card,2026-09-01,2026-09-02
negative,100,-1,0,0,pending,upi,2026-09-01,
deductions,100,90,20,0,pending,upi,2026-09-01,
backwards,100,2,0.36,97.64,settled,card,2026-09-03,2026-09-01
nonfinite,NaN,0,0,0,pending,upi,2026-09-01,
unknown,100,2,0.36,97.64,captured,card,2026-09-01,2026-09-02
"""
        parsed = agent.parse_csv(content)
        self.assertEqual(parsed["parsed"], 0)
        self.assertEqual(len(parsed["warnings"]), 6)
        self.assertFalse(agent.analyze())

    def test_unknown_payment_method_uses_default_rate_with_a_visible_warning(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method
pay_other,100,2,0.36,97.64,paid,bank_transfer
"""
        parsed = agent.parse_csv(content)
        self.assertEqual(parsed["parsed"], 1)
        self.assertEqual(len(parsed["warnings"]), 1)
        self.assertIn("default fee rate", parsed["warnings"][0])
        self.assertEqual(agent.analyze()["residual_variance"], 0)

    def test_mixed_rows_preserve_the_reconciliation_equation(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method
short,1000,20,3.6,900,completed,card
excess,1000,20,3.6,980,processed,card
pending,500,10,1.8,0,in progress,card
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 3)
        summary = agent.analyze()
        self.assertEqual(summary["recovery_amount_net"], 488.2)
        self.assertEqual(summary["total_settlement_shortfall"], 76.4)
        self.assertEqual(summary["total_settlement_excess"], 3.6)
        self.assertEqual(summary["residual_variance"], 72.8)
        self.assertEqual(summary["exception_transaction_count"], 3)

    def test_healthy_multirow_letter_uses_plural_language(self) -> None:
        agent = ReconciliationAgent()
        content = """transaction_id,amount,fee,tax,settlement_amount,status,payment_method
one,100,2,0.36,97.64,settled,card
two,200,4,0.72,195.28,settled,card
"""
        self.assertEqual(agent.parse_csv(content)["parsed"], 2)
        agent.analyze()
        self.assertIn("I have reconciled the transactions below", agent.draft_recovery_ticket())

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

    def test_escalation_ladder_matches_configured_provider_windows(self) -> None:
        self.assertEqual(
            [tier["trigger_days"] for tier in ESCALATION_TIERS],
            [0, config.GRIEVANCE_TRIGGER_DAYS, config.NODAL_TRIGGER_DAYS, config.OMBUDSMAN_TRIGGER_DAYS, config.LEGAL_TRIGGER_DAYS],
        )
        self.assertIn("Assistant Nodal", ESCALATION_TIERS[1]["name"])
        self.assertIn("Nodal Officer", ESCALATION_TIERS[2]["name"])
        self.assertEqual(ESCALATION_TIERS[3]["rbi_ref"], config.OMBUDSMAN_SCHEME_REFERENCE)


class EvidenceTests(unittest.TestCase):
    def test_source_citations_are_checked(self) -> None:
        chunks = [{"source": "policy.txt", "page": 1, "similarity": 0.9}]
        self.assertTrue(validate_citations("Supported. [Source: policy.txt]", chunks)["is_valid"])
        self.assertFalse(validate_citations("Unsupported. [Source: other.txt]", chunks)["is_valid"])

    def test_local_policy_contains_current_direction_reference(self) -> None:
        result = search_local_policy("RBI payment aggregator merchant due diligence paragraph 13")
        combined = result["answer"] + " " + result["source"]
        self.assertIn("rbi_pa_2025_knowledge.txt", combined)

    def test_policy_evidence_preserves_extractive_source_cards(self) -> None:
        result = get_policy_evidence(
            "merchant settlement schedule pricing grievance reconciliation",
            semantic=False,
        )
        self.assertTrue(result["extractive_chunks"])
        self.assertTrue(all(chunk.get("source") and chunk.get("text") for chunk in result["extractive_chunks"]))


if __name__ == "__main__":
    unittest.main()
