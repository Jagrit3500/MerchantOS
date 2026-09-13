from __future__ import annotations

import itertools
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from Agent2.reconciliation_agent import (
    METHOD_ALIASES,
    STATUS_ALIASES,
    ReconciliationAgent,
)
from src import config


HEADER = (
    "transaction_id,amount,fee,tax,settlement_amount,status,payment_method,"
    "transaction_date,settlement_date\n"
)


class Agent2CombinationTests(unittest.TestCase):
    def test_every_status_and_payment_method_alias_is_analyzable(self) -> None:
        rows = []
        expected_status_counts = {"settled": 0, "on_hold": 0, "pending": 0}
        combinations = list(itertools.product(STATUS_ALIASES, METHOD_ALIASES))
        calculator = ReconciliationAgent()

        for index, (status_alias, method_alias) in enumerate(combinations, 1):
            normalized_status = STATUS_ALIASES[status_alias]
            normalized_method = METHOD_ALIASES[method_alias]
            fee, tax = calculator.calculate_expected_fee(1000, normalized_method)
            settlement = 1000 - fee - tax if normalized_status == "settled" else 0
            rows.append(
                f"matrix_{index},1000,{fee},{tax},{settlement},{status_alias},"
                f"{method_alias},2026-09-07,2026-09-08"
            )
            expected_status_counts[normalized_status] += 1

        agent = ReconciliationAgent()
        parsed = agent.parse_csv(HEADER + "\n".join(rows))
        self.assertEqual(parsed, {"parsed": len(combinations), "errors": [], "warnings": []})
        summary = agent.analyze()
        self.assertEqual(summary["settled_count"], expected_status_counts["settled"])
        self.assertEqual(summary["held_count"], expected_status_counts["on_hold"])
        self.assertEqual(summary["pending_count"], expected_status_counts["pending"])
        self.assertEqual(summary["timing_evaluable_count"], len(combinations))
        self.assertEqual(summary["tat_count"], 0)

    def test_accounting_invariants_hold_across_status_and_settlement_variants(self) -> None:
        statuses = ("settled", "on_hold", "pending")
        settlement_variants = (0.0, 400.0, 900.0, 976.4, 980.0, 1000.0)

        for status, settlement in itertools.product(statuses, settlement_variants):
            with self.subTest(status=status, settlement=settlement):
                agent = ReconciliationAgent()
                row = f"case,1000,20,3.6,{settlement},{status},card,,\n"
                self.assertEqual(agent.parse_csv(HEADER + row)["parsed"], 1)
                summary = agent.analyze()

                expected_residual = round(
                    summary["total_gross"]
                    - summary["total_settled"]
                    - summary["recovery_amount_net"]
                    - summary["total_fee_charged"]
                    - summary["total_tax_charged"],
                    2,
                )
                if abs(expected_residual) < config.RECONCILIATION_ZERO_TOLERANCE:
                    expected_residual = 0.0
                self.assertAlmostEqual(summary["residual_variance"], expected_residual, places=2)
                self.assertAlmostEqual(
                    summary["amount_to_review"],
                    round(
                        summary["recovery_amount"]
                        + summary["total_settlement_shortfall"]
                        + summary["total_settlement_excess"]
                        + summary["total_overcharge"],
                        2,
                    ),
                    places=2,
                )
                self.assertAlmostEqual(
                    summary["net_recovery_requested"],
                    round(
                        summary["recovery_amount_net"]
                        + summary["total_settlement_shortfall"]
                        + summary["total_overcharge"],
                        2,
                    ),
                    places=2,
                )
                self.assertGreaterEqual(summary["recovery_amount"], 0)
                self.assertGreaterEqual(summary["recovery_amount_net"], 0)
                self.assertGreaterEqual(summary["net_recovery_requested"], 0)

    def test_configured_balance_tolerance_controls_boundary_behavior(self) -> None:
        content = HEADER + (
            "at_boundary,1000,20,3.6,976.38,settled,card,,\n"
            "outside_boundary,1000,20,3.6,976.37,settled,card,,\n"
        )
        with patch.object(config, "RECONCILIATION_BALANCE_TOLERANCE", 0.02):
            agent = ReconciliationAgent()
            self.assertEqual(agent.parse_csv(content)["parsed"], 2)
            differences = agent.analyze()["settlement_differences"]
        self.assertEqual([item["transaction_id"] for item in differences], ["outside_boundary"])

    def test_configured_timing_window_is_not_cached_in_the_engine(self) -> None:
        content = HEADER + (
            "two_days,1000,20,3.6,976.4,settled,card,2026-09-07,2026-09-09\n"
        )
        with (
            patch.object(config, "EXPECTED_SETTLEMENT_DAYS", 2),
            patch.object(config, "SETTLEMENT_DAY_MODE", "business"),
        ):
            agent = ReconciliationAgent()
            self.assertEqual(agent.parse_csv(content)["parsed"], 1)
            self.assertEqual(agent.analyze()["tat_count"], 0)
        with (
            patch.object(config, "EXPECTED_SETTLEMENT_DAYS", 1),
            patch.object(config, "SETTLEMENT_DAY_MODE", "business"),
        ):
            agent = ReconciliationAgent()
            self.assertEqual(agent.parse_csv(content)["parsed"], 1)
            self.assertEqual(agent.analyze()["tat_count"], 1)

    def test_fee_tolerance_boundary_and_first_amount_above_it(self) -> None:
        content = HEADER + (
            "at_boundary,1000,21,3.6,975.4,settled,card,,\n"
            "above_boundary,1000,21.01,3.6,975.39,settled,card,,\n"
        )
        agent = ReconciliationAgent()
        self.assertEqual(agent.parse_csv(content)["parsed"], 2)
        summary = agent.analyze()
        self.assertEqual(
            [item["transaction_id"] for item in summary["overcharged_fees"]],
            ["above_boundary"],
        )
        self.assertEqual(summary["total_overcharge"], 1.01)

    def test_parser_resets_state_between_success_error_and_success(self) -> None:
        agent = ReconciliationAgent()
        valid = HEADER + "first,1000,20,3.6,976.4,settled,card,,\n"
        self.assertEqual(agent.parse_csv(valid)["parsed"], 1)
        self.assertEqual(agent.analyze()["total_transactions"], 1)

        invalid = "transaction_id,amount\ninvalid,1000\n"
        result = agent.parse_csv(invalid)
        self.assertEqual(result["parsed"], 0)
        self.assertTrue(result["errors"])
        self.assertEqual(agent.transactions, [])
        self.assertIsNone(agent.summary)

        second = HEADER + "second,500,10,1.8,488.2,settled,card,,\n"
        self.assertEqual(agent.parse_csv(second)["parsed"], 1)
        self.assertEqual(agent.analyze()["total_gross"], 500)


class ConfigurationOwnershipTests(unittest.TestCase):
    def test_operational_defaults_live_only_in_shared_configuration(self) -> None:
        root = Path(__file__).resolve().parents[1]
        production_files = [
            *root.glob("*.py"),
            *root.glob("Agent*/*.py"),
            *root.glob("src/*.py"),
        ]
        production_files = [path for path in production_files if path != root / "src" / "config.py"]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

        self.assertNotIn("os.getenv(", combined)
        self.assertNotIn("razorpay.com", combined.lower())
        self.assertNotIn("nodal-officer@", combined.lower())
        self.assertNotIn("localhost:", combined.lower())
        self.assertNotIn("FEE_DISPUTE_MIN_AMOUNT", combined)
        self.assertNotRegex(combined, r"\bBALANCE_TOLERANCE\s*=")

    def test_every_direct_environment_setting_is_documented(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config_text = (root / "src" / "config.py").read_text(encoding="utf-8")
        example_text = (root / ".env.example").read_text(encoding="utf-8")
        direct_keys = set(re.findall(r'os\.getenv\(\s*["\']([A-Z][A-Z0-9_]*)["\']', config_text))
        documented_keys = set(
            re.findall(r"(?m)^\s*#?\s*([A-Z][A-Z0-9_]*)=", example_text)
        )
        self.assertFalse(direct_keys - documented_keys)
        self.assertNotIn("FEE_DISPUTE_MIN_AMOUNT", documented_keys)


if __name__ == "__main__":
    unittest.main()
