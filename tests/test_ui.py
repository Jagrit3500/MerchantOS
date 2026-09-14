from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src import activity_history, config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ActivityInterfaceTests(unittest.TestCase):
    AGENT1_ANSWERS: ClassVar[list[str]] = [
        "Law enforcement / regulatory restriction shown",
        "No email received",
        "Private Limited Company",
        "No - normal volume",
        "No",
        "1 to 3 days (Recent)",
    ]

    def _render(self, app_path: str, database: str) -> AppTest:
        with (
            patch.object(config, "AUTH_ENABLED", False),
            patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
            patch.object(config, "ACTIVITY_DB_PATH", database),
        ):
            return AppTest.from_file(PROJECT_ROOT / app_path).run(timeout=30)

    @staticmethod
    def _markup(app: AppTest) -> list[str]:
        return [str(element.value) for element in app.markdown]

    def test_home_uses_aggregate_heatmap_without_detail_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                activity_history.record_activity(
                    0, "agent1", "completed", "KYC diagnosis"
                )
            app = self._render("home.py", database)
            self.assertFalse(list(app.exception))
            markup = self._markup(app)
            self.assertTrue(
                any(value.startswith('<div class="heatmap-card">') for value in markup)
            )
            self.assertFalse(
                any(
                    value.startswith('<a class="activity-card-link"')
                    for value in markup
                )
            )

    def test_home_and_escalation_use_command_desk_designs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            home = self._render("home.py", database)
            escalation = self._render("Agent3/app.py", database)

            self.assertFalse(list(home.exception))
            self.assertFalse(list(escalation.exception))
            self.assertTrue(
                any('class="home-hero"' in value for value in self._markup(home))
            )
            self.assertTrue(
                any('class="a3-hero"' in value for value in self._markup(escalation))
            )
            self.assertEqual(len(escalation.tabs), 3)
            self.assertTrue(
                any(
                    "Evidence room locked" in value
                    for value in self._markup(escalation)
                )
            )
            self.assertTrue(
                any(
                    "Correspondence locked" in value
                    for value in self._markup(escalation)
                )
            )
            self.assertFalse(
                any(
                    "Collect the source record" in value
                    for value in self._markup(escalation)
                )
            )
            self.assertFalse(
                any(
                    (area.key or "").startswith("a3_grievance")
                    for area in escalation.text_area
                )
            )
            self.assertTrue(
                any(
                    "Assistant Nodal Officer" in value
                    for value in self._markup(escalation)
                )
            )

    def test_agent3_requires_case_then_evidence_before_generating_snapshot_drafts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            app = AppTest.from_file(PROJECT_ROOT / "Agent3/app.py")
            policy_result = {
                "answer": "Settlement-hold evidence selected for the submitted case.",
                "source": "test_policy.txt",
            }

            def run_app() -> None:
                with (
                    patch.object(config, "AUTH_ENABLED", False),
                    patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
                    patch.object(config, "ACTIVITY_DB_PATH", database),
                    patch(
                        "src.policy_evidence.search_local_policy",
                        return_value=policy_result,
                    ),
                ):
                    app.run(timeout=30)

            run_app()
            self.assertFalse(list(app.exception))
            self.assertEqual(len(app.tabs), 3)
            self.assertFalse(
                any("Collect the source record" in value for value in self._markup(app))
            )

            values = {
                "Full name *": "Rahul Sharma",
                "Business or legal entity *": "Test Retail Pvt Ltd",
                f"{config.AGGREGATOR_SHORT} Merchant ID *": "M_TEST_8504",
                "Registered email *": "rahul@example.com",
                "Phone number *": "+91 9876543210",
                "State or UT *": "Karnataka",
                f"Disputed amount ({config.CURRENCY_SYMBOL})": "45000.00",
                "Transaction or order IDs": "pay_TEST_001, pay_TEST_002",
                "Previous ticket ID": "RZP_TEST_001",
            }
            for label, value in values.items():
                next(
                    widget for widget in app.text_input if widget.label == label
                ).set_value(value)
            text_values = {
                "Registered address *": "Bengaluru, Karnataka",
                "Chronological issue summary *": (
                    "Two settlements remain on hold despite submitting the requested documents. "
                    "No reason or expected release date has been provided."
                ),
                "Key milestones · one per line *": (
                    "2026-08-15: Settlements placed on hold\n"
                    "2026-08-16: Contacted support\n"
                    "2026-08-18: Submitted requested documents"
                ),
            }
            for label, value in text_values.items():
                next(
                    widget for widget in app.text_area if widget.label == label
                ).set_value(value)
            issue_started = datetime.now().astimezone().date() - timedelta(days=30)
            app.selectbox[0].set_value("settlement_hold")
            app.date_input[0].set_value(issue_started)
            run_app()

            app.button(key="a3_submit_case").click()
            run_app()
            self.assertFalse(list(app.exception))
            self.assertEqual(app.session_state.a3_step, 1)
            self.assertEqual(
                app.session_state.a3_submitted_case["merchant"]["name"], "Rahul Sharma"
            )
            self.assertEqual(
                app.session_state.a3_submitted_case["issue_type"], "settlement_hold"
            )
            self.assertEqual(
                app.session_state.a3_submitted_case["issue"]["amount"], "45,000.00"
            )
            self.assertTrue(
                any("Collect the source record" in value for value in self._markup(app))
            )
            self.assertTrue(
                any("Correspondence locked" in value for value in self._markup(app))
            )
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                self.assertEqual(
                    len(activity_history.read_activity_history(0, "agent3")), 1
                )

            app.button(key="a3_submit_case").click()
            run_app()
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                self.assertEqual(
                    len(activity_history.read_activity_history(0, "agent3")), 1
                )

            app.checkbox(key="a3_evidence_reviewed").set_value(True)
            run_app()
            app.button(key="a3_prepare_correspondence").click()
            run_app()
            self.assertFalse(list(app.exception))
            self.assertEqual(app.session_state.a3_step, 2)
            self.assertEqual(len(app.tabs), 7)

            drafts = [
                app.text_area(key="a3_grievance_edit").value,
                app.text_area(key="a3_ombudsman_edit").value,
                app.text_area(key="a3_legal_edit").value,
            ]
            for draft in drafts:
                self.assertIn("Rahul Sharma", draft)
                self.assertIn("Test Retail Pvt Ltd", draft)
                self.assertIn("M_TEST_8504", draft)
                self.assertIn("Settlement Hold / Funds On Hold", draft)
                self.assertIn(issue_started.strftime("%d %B %Y"), draft)
                self.assertNotIn("[YOUR NAME]", draft)
                self.assertNotIn("[YOUR BUSINESS NAME]", draft)
                self.assertNotIn("[YOUR MERCHANT ID]", draft)

    def test_workspace_history_links_and_deletes_own_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                activity_id = activity_history.record_activity(
                    0,
                    "agent1",
                    "completed",
                    "Linked diagnosis",
                    "Test record",
                    {"answers": self.AGENT1_ANSWERS},
                )
            app = self._render("Agent1/app.py", database)
            self.assertFalse(list(app.exception))
            card = next(
                value
                for value in self._markup(app)
                if value.startswith('<a class="activity-card-link"')
            )
            self.assertIn(config.app_urls()["agent1"], card)
            self.assertIn(f"activity={activity_id}", card)

            with (
                patch.object(config, "ACTIVITY_DB_PATH", database),
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
            ):
                app.button(key=f"delete_activity_{activity_id}").click().run(timeout=30)
                self.assertEqual(
                    activity_history.read_activity_history(0, "agent1"), []
                )

    def test_agent1_history_record_reopens_result_without_history_list(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                activity_id = activity_history.record_activity(
                    0,
                    "agent1",
                    "diagnosis_completed",
                    "Regulatory / Law Enforcement Restriction Reported",
                    "Critical priority · Private Limited Company",
                    {"answers": self.AGENT1_ANSWERS},
                )
                second_activity_id = activity_history.record_activity(
                    0,
                    "agent1",
                    "diagnosis_completed",
                    "KYC - Verification Action Required",
                    "High priority · Private Limited Company",
                    {
                        "answers": [
                            "Live Disabled",
                            "Yes - asking for other documents",
                            "Private Limited Company",
                            "No - normal volume",
                            "No",
                            "1 to 3 days (Recent)",
                        ]
                    },
                )
            app = AppTest.from_file(PROJECT_ROOT / "Agent1/app.py")
            app.query_params["activity"] = str(activity_id)
            with (
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
                patch.object(config, "ACTIVITY_DB_PATH", database),
            ):
                app.run(timeout=30)

            self.assertFalse(list(app.exception))
            markup = self._markup(app)
            self.assertTrue(
                any(
                    "Regulatory / Law Enforcement Restriction Reported" in value
                    for value in markup
                )
            )
            self.assertFalse(any("Activity history" in value for value in markup))
            self.assertFalse(
                any(
                    (button.key or "").startswith("delete_activity_")
                    for button in app.button
                )
            )

            app.query_params["activity"] = str(second_activity_id)
            with (
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
                patch.object(config, "ACTIVITY_DB_PATH", database),
            ):
                app.run(timeout=30)
            self.assertFalse(list(app.exception))
            markup = self._markup(app)
            self.assertTrue(
                any("KYC - Verification Action Required" in value for value in markup)
            )
            self.assertFalse(any("Activity history" in value for value in markup))
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                self.assertEqual(
                    len(activity_history.read_activity_history(0, "agent1")), 2
                )

    def test_clear_history_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                activity_history.record_activity(0, "agent2", "completed", "First")
                activity_history.record_activity(0, "agent2", "completed", "Second")
            app = self._render("Agent2/app.py", database)
            self.assertFalse(list(app.exception))

            with (
                patch.object(config, "ACTIVITY_DB_PATH", database),
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
            ):
                app.button(key="clear_history_agent2").click().run(timeout=30)
                self.assertEqual(
                    len(activity_history.read_activity_history(0, "agent2")), 2
                )
                app.button(key="confirm_clear_history_agent2").click().run(timeout=30)
                self.assertEqual(
                    activity_history.read_activity_history(0, "agent2"), []
                )

    def test_agent2_result_hides_workspace_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            app = self._render("Agent2/app.py", database)
            self.assertFalse(list(app.exception))
            self.assertTrue(
                any("Activity history" in value for value in self._markup(app))
            )
            reconcile_sample = next(
                button
                for button in app.button
                if button.label.startswith("Reconcile sample")
            )
            with (
                patch.object(config, "ACTIVITY_DB_PATH", database),
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
            ):
                reconcile_sample.click().run(timeout=30)

            self.assertFalse(list(app.exception))
            self.assertTrue(app.session_state.a2_done)
            self.assertFalse(
                any("Activity history" in value for value in self._markup(app))
            )
            self.assertFalse(
                any(
                    (button.key or "").startswith("delete_activity_")
                    for button in app.button
                )
            )
            self.assertTrue(
                any(
                    "Settlement timing was not assessed" in value
                    for value in self._markup(app)
                )
            )

    def test_agent2_history_record_reopens_its_reconciliation_result(self) -> None:
        report = (
            "settlement_date,transaction_id,amount,fee,tax,settlement_amount,status,payment_method,transaction_date\n"
            ",pay_SAVED_HOLD_001,12500,0,0,0,on_hold,upi,2026-09-01\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                activity_id = activity_history.record_activity(
                    0,
                    "agent2",
                    "reconciliation_completed",
                    "Reconciled saved report",
                    "1 transaction · 1 held or pending · ₹12,500.00 to review",
                    {"source": "saved-report.csv", "input_csv": report},
                )

            history_app = self._render("Agent2/app.py", database)
            history_card = next(
                value
                for value in self._markup(history_app)
                if value.startswith('<a class="activity-card-link"')
            )
            self.assertIn(f"activity={activity_id}", history_card)

            app = AppTest.from_file(PROJECT_ROOT / "Agent2/app.py")
            app.query_params["activity"] = str(activity_id)
            with (
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "ACTIVITY_DB_PATH", database),
                patch(
                    "src.policy_evidence.get_policy_evidence",
                    return_value={
                        "answer": "Saved policy evidence",
                        "confidence": {"score": 0.72, "label": "medium"},
                        "source": "test_policy.txt",
                        "retrieval": "Semantic source recheck",
                        "confidence_method": "Top cosine similarity",
                        "checked_at": "12 Sep 2026",
                    },
                ),
            ):
                app.run(timeout=30)

            self.assertFalse(list(app.exception))
            self.assertTrue(app.session_state.a2_done)
            self.assertEqual(app.session_state.a2_source, "saved-report.csv")
            self.assertEqual(app.session_state.a2_summary["total_gross"], 12500)
            self.assertTrue(
                any("pay_SAVED_HOLD_001" in value for value in self._markup(app))
            )
            self.assertFalse(
                any("Activity history" in value for value in self._markup(app))
            )
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                self.assertEqual(
                    len(activity_history.read_activity_history(0, "agent2")), 1
                )

    def test_agent1_refreshes_semantic_evidence_and_displays_confidence(self) -> None:
        answers = [
            "Live Disabled",
            "Yes - asking for other documents",
            "Private Limited Company",
            "No - normal volume",
            "No",
            "1 to 3 days (Recent)",
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = str(Path(temporary_directory) / "activity.sqlite3")
            app = AppTest.from_file(PROJECT_ROOT / "Agent1/app.py")
            with (
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", True),
                patch.object(config, "ACTIVITY_DB_PATH", database),
                patch.object(config, "GROQ_API_KEY", ""),
            ):
                app.run(timeout=30)
                for answer in answers:
                    app.radio[0].set_value(answer).run(timeout=30)
                    proceed = next(
                        button
                        for button in app.button
                        if button.label in {"Continue →", "Prepare my response →"}
                    )
                    proceed.click().run(timeout=30)

                self.assertFalse(list(app.exception))
                initial_captions = [str(element.value) for element in app.caption]
                initial_markup = self._markup(app)
                self.assertTrue(
                    any("Top cosine similarity" in value for value in initial_captions)
                )
                self.assertTrue(
                    any("Evidence match:" in value for value in initial_markup)
                )
                refresh = next(
                    button
                    for button in app.button
                    if button.label == "Refresh evidence"
                )
                refresh.click().run(timeout=45)
                self.assertFalse(list(app.exception))
                self.assertEqual(app.session_state.a1_evidence_refreshes, 1)
                captions = [str(element.value) for element in app.caption]
                markup = self._markup(app)
                self.assertTrue(
                    any("Top cosine similarity" in value for value in captions)
                )
                self.assertTrue(any("Sources:" in value for value in captions))
                self.assertTrue(any("Evidence match:" in value for value in markup))
                self.assertTrue(
                    any(
                        "Recheck 1 completed. The evidence and match score are unchanged"
                        in str(element.value)
                        for element in app.toast
                    )
                )
                self.assertFalse(
                    any(
                        "Recheck 1 completed" in str(element.value)
                        for element in app.success
                    )
                )


if __name__ == "__main__":
    unittest.main()
