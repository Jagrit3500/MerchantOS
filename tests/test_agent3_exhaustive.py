from __future__ import annotations

import unittest
from datetime import date

from Agent3.escalation_agent import ESCALATION_TIERS, ISSUE_TYPES, EscalationAgent
from src import config


class Agent3BoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = EscalationAgent()

    def test_every_escalation_boundary_selects_the_expected_tier(self) -> None:
        self.assertEqual(self.agent.recommend_tier(-1)["tier"], 1)
        for index, tier in enumerate(ESCALATION_TIERS):
            with self.subTest(tier=tier["tier"]):
                self.assertEqual(
                    self.agent.recommend_tier(tier["trigger_days"])["tier"],
                    tier["tier"],
                )
                if index:
                    self.assertEqual(
                        self.agent.recommend_tier(tier["trigger_days"] - 1)["tier"],
                        ESCALATION_TIERS[index - 1]["tier"],
                    )

    def test_mixed_calendar_and_business_day_routes(self) -> None:
        self.assertEqual(self.agent.recommend_tier(12, 9)["tier"], 1)
        self.assertEqual(self.agent.recommend_tier(12, 10)["tier"], 2)
        self.assertEqual(self.agent.recommend_tier(29, 20)["tier"], 3)
        self.assertEqual(self.agent.recommend_tier(30, 20)["tier"], 4)
        self.assertEqual(self.agent.recommend_tier(90, 64)["tier"], 5)

    def test_business_day_counter_excludes_weekends(self) -> None:
        self.assertEqual(
            self.agent.calculate_business_days(
                date(2026, 9, 7), date(2026, 9, 14)
            ),
            5,
        )

    def test_current_ombudsman_scheme_is_used(self) -> None:
        self.assertIn("2026", config.OMBUDSMAN_SCHEME_REFERENCE)

    def test_public_catalog_results_cannot_mutate_global_configuration(self) -> None:
        tiers = self.agent.get_all_tiers()
        tiers[0]["name"] = "changed"
        issues = self.agent.get_issue_types()
        issues["other"] = "changed"
        checklist = self.agent.get_evidence_checklist("other")
        checklist.append("changed")

        self.assertNotEqual(ESCALATION_TIERS[0]["name"], "changed")
        self.assertNotEqual(ISSUE_TYPES["other"], "changed")
        self.assertNotIn("changed", self.agent.get_evidence_checklist("other"))

    def test_every_issue_type_generates_all_three_complete_drafts(self) -> None:
        merchant = {
            "name": "Test Merchant",
            "business_name": "Test Business",
            "merchant_id": "merchant_test",
            "email": "merchant@example.com",
            "phone": "9999999999",
            "state": "Karnataka",
            "address": "Test address",
        }
        for issue_type, issue_name in ISSUE_TYPES.items():
            with self.subTest(issue_type=issue_type):
                issue = {
                    "issue_type": issue_type,
                    "first_reported_date": "2026-09-01",
                    "days_elapsed": config.OMBUDSMAN_TRIGGER_DAYS,
                    "amount": "1000.00",
                    "txn_ids": "pay_test",
                    "description": "A documented test issue.",
                    "timeline": ["2026-09-01: Issue reported"],
                    "grievance_ref": "ticket_test",
                }
                grievance = self.agent.draft_grievance_letter(merchant, issue)
                ombudsman = self.agent.draft_rbi_ombudsman_complaint(merchant, issue)
                legal = self.agent.draft_legal_notice(merchant, issue)

                self.assertIn(issue_name, grievance)
                self.assertIn(config.AGGREGATOR_NAME, grievance)
                self.assertIn(config.AGGREGATOR_GRIEVANCE_EMAIL, grievance)
                self.assertIn(config.OMBUDSMAN_URL, ombudsman)
                self.assertIn("ticket_test", ombudsman)
                self.assertIn(config.CONSUMER_LAW_REFERENCE, legal)
                self.assertIn("QUALIFIED COUNSEL REVIEW REQUIRED", legal)
                self.assertTrue(self.agent.get_evidence_checklist(issue_type))


if __name__ == "__main__":
    unittest.main()
