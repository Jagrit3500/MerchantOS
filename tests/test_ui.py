from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src import activity_history, config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ActivityInterfaceTests(unittest.TestCase):
    AGENT1_ANSWERS = [
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
                activity_history.record_activity(0, "agent1", "completed", "KYC diagnosis")
            app = self._render("home.py", database)
            self.assertFalse(list(app.exception))
            markup = self._markup(app)
            self.assertTrue(any(value.startswith('<div class="heatmap-card">') for value in markup))
            self.assertFalse(any(value.startswith('<a class="activity-card-link"') for value in markup))

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
            card = next(value for value in self._markup(app) if value.startswith('<a class="activity-card-link"'))
            self.assertIn(config.app_urls()["agent1"], card)
            self.assertIn(f"activity={activity_id}", card)

            with (
                patch.object(config, "ACTIVITY_DB_PATH", database),
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
            ):
                app.button(key=f"delete_activity_{activity_id}").click().run(timeout=30)
                self.assertEqual(activity_history.read_activity_history(0, "agent1"), [])

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
            self.assertTrue(any("Regulatory / Law Enforcement Restriction Reported" in value for value in markup))
            self.assertFalse(any("Activity history" in value for value in markup))
            self.assertFalse(any((button.key or "").startswith("delete_activity_") for button in app.button))

            app.query_params["activity"] = str(second_activity_id)
            with (
                patch.object(config, "AUTH_ENABLED", False),
                patch.object(config, "AUTO_FETCH_POLICY_EVIDENCE", False),
                patch.object(config, "ACTIVITY_DB_PATH", database),
            ):
                app.run(timeout=30)
            self.assertFalse(list(app.exception))
            markup = self._markup(app)
            self.assertTrue(any("KYC - Verification Action Required" in value for value in markup))
            self.assertFalse(any("Activity history" in value for value in markup))
            with patch.object(config, "ACTIVITY_DB_PATH", database):
                self.assertEqual(len(activity_history.read_activity_history(0, "agent1")), 2)

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
                self.assertEqual(len(activity_history.read_activity_history(0, "agent2")), 2)
                app.button(key="confirm_clear_history_agent2").click().run(timeout=30)
                self.assertEqual(activity_history.read_activity_history(0, "agent2"), [])

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
                self.assertTrue(any("Top cosine similarity" in value for value in initial_captions))
                self.assertTrue(any("Evidence match:" in value for value in initial_markup))
                refresh = next(button for button in app.button if button.label == "Refresh evidence")
                refresh.click().run(timeout=45)
                self.assertFalse(list(app.exception))
                self.assertEqual(app.session_state.a1_evidence_refreshes, 1)
                captions = [str(element.value) for element in app.caption]
                markup = self._markup(app)
                self.assertTrue(any("Top cosine similarity" in value for value in captions))
                self.assertTrue(any("Sources:" in value for value in captions))
                self.assertTrue(any("Evidence match:" in value for value in markup))
                self.assertTrue(
                    any(
                        "Recheck 1 completed. The evidence and match score are unchanged" in str(element.value)
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
