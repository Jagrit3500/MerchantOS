"""
MerchantOS - Agent 2: Settlement Reconciliation Engine
Detects missing settlements, fee/tax differences, TAT violations, and held funds.
All variable rates and thresholds come from the shared MerchantOS configuration.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import config
import csv, io, math, re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime

# ─── Configured fee rates ───────────────────────────────────────────────
# Format: method_key -> (platform_fee_pct, gst_on_fee_pct)
_gst = float(config.GST_RATE)
_mdr_upi = float(config.MDR_RATE_UPI)
_mdr_card = float(config.MDR_RATE_CARD)
_mdr_netbanking = float(config.MDR_RATE_NETBANKING)
_mdr_wallet = float(config.MDR_RATE_WALLET)
_mdr_emi = float(config.MDR_RATE_EMI)
_mdr_paylater = float(config.MDR_RATE_PAYLATER)
_mdr_default = float(config.MDR_RATE_DEFAULT)

FEE_RATES: dict[str, tuple[float, float]] = {
    "upi":          (_mdr_upi, _gst),
    "card":         (_mdr_card, _gst),
    "credit card":  (_mdr_card, _gst),
    "credit_card":  (_mdr_card, _gst),
    "debit card":   (_mdr_card, _gst),
    "debit_card":   (_mdr_card, _gst),
    "netbanking":   (_mdr_netbanking, _gst),
    "net banking":  (_mdr_netbanking, _gst),
    "wallet":       (_mdr_wallet, _gst),
    "emi":          (_mdr_emi, _gst),
    "paylater":     (_mdr_paylater, _gst),
}
FEE_DEFAULT = (_mdr_default, _gst)

# Merchant/provider agreements define settlement timing under the 2025 PA Directions.
# MerchantOS compares reports with operator-configured expectations and tolerances.

STATUS_ALIASES = {
    "settled": "settled",
    "success": "settled",
    "successful": "settled",
    "paid": "settled",
    "completed": "settled",
    "processed": "settled",
    "on_hold": "on_hold",
    "onhold": "on_hold",
    "hold": "on_hold",
    "held": "on_hold",
    "pending": "pending",
    "processing": "pending",
    "in_process": "pending",
    "in_progress": "pending",
}

METHOD_ALIASES = {
    "upi": "upi",
    "card": "card",
    "credit_card": "credit_card",
    "debit_card": "debit_card",
    "netbanking": "netbanking",
    "net_banking": "netbanking",
    "wallet": "wallet",
    "emi": "emi",
    "paylater": "paylater",
    "pay_later": "paylater",
}

# Column name aliases so we accept many CSV formats
COL_ALIASES: dict[str, list[str]] = {
    "settlement_id":     ["settlement_id", "setl_id", "settle_id"],
    "settlement_date":   ["settlement_date", "settled_date", "settle_date", "date"],
    "transaction_id":    ["transaction_id", "txn_id", "txn", "payment_id"],
    "order_id":          ["order_id", "order", "orderid", "merchant_order_id"],
    "amount":            ["amount", "txn_amount", "gross", "gross_amount"],
    "fee":               ["fee", "fees", "platform_fee", "pg_fee"],
    "tax":               ["tax", "gst", "service_tax"],
    "settlement_amount": ["settlement_amount", "net_amount", "net", "net_settlement"],
    "status":            ["status", "txn_status", "payment_status"],
    "payment_method":    ["payment_method", "method", "payment_mode", "mode"],
    "transaction_date":  ["transaction_date", "txn_date", "created_at", "created_date"],
}

REQUIRED_COLS = [
    "transaction_id", "amount", "fee", "tax",
    "settlement_amount", "status", "payment_method",
]

INR = config.CURRENCY_SYMBOL


class ReconciliationAgent:
    """Parses settlement data and detects discrepancies."""

    def __init__(self):
        self.transactions: list[dict] = []
        self.summary: dict | None = None
        self._col_map: dict[str, str] = {}

    # ─── CSV Parsing ─────────────────────────────────────────────────────────

    def _normalize_cols(self, headers: list[str]) -> dict[str, str]:
        """Map raw CSV header -> normalized column name."""
        col_map: dict[str, str] = {}
        h_lookup = {self._normalize_token(h.lstrip("\ufeff")): h for h in headers}
        for norm, aliases in COL_ALIASES.items():
            for alias in aliases:
                alias_key = self._normalize_token(alias)
                if alias_key in h_lookup:
                    col_map[h_lookup[alias_key]] = norm
                    break
        return col_map

    @staticmethod
    def _normalize_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")

    @staticmethod
    def _parse_money(value: str, field: str) -> float:
        raw = str(value or "").strip()
        if not raw:
            return 0.0
        negative_parentheses = raw.startswith("(") and raw.endswith(")")
        if negative_parentheses:
            raw = "-" + raw[1:-1]
        cleaned = raw.replace(",", "").replace(config.CURRENCY_SYMBOL, "").strip()
        cleaned = re.sub(r"^(?:inr|rs\.?)\s*", "", cleaned, flags=re.IGNORECASE)
        try:
            number = float(Decimal(cleaned))
        except (InvalidOperation, ValueError):
            raise ValueError(f"invalid {field}: {value or '(empty)'}") from None
        if not math.isfinite(number):
            raise ValueError(f"non-finite value in {field}")
        return number

    @classmethod
    def _normalize_method(cls, value: str) -> str:
        key = cls._normalize_token(value)
        return METHOD_ALIASES.get(key, key)

    def _missing_cols(self, col_map: dict) -> list[str]:
        found = set(col_map.values())
        return [c for c in REQUIRED_COLS if c not in found]

    def parse_csv(self, csv_content: str) -> dict:
        """Parse CSV string. Returns {'parsed', 'errors', 'warnings'}."""
        self.transactions = []
        self.summary = None
        errors, warnings = [], []
        try:
            reader = csv.DictReader(io.StringIO(csv_content.strip()))
            headers = list(reader.fieldnames or [])
        except Exception as exc:
            return {"parsed": 0, "errors": [f"CSV error: {exc}"], "warnings": []}

        self._col_map = self._normalize_cols(headers)
        missing = self._missing_cols(self._col_map)
        if missing:
            return {
                "parsed": 0,
                "errors": [
                    f"Missing required columns: {', '.join(missing)}. "
                    f"CSV has: {', '.join(headers)}"
                ],
                "warnings": [],
            }

        seen_transaction_ids: set[str] = set()
        for i, row in enumerate(reader, start=2):
            try:
                transaction = self._parse_row(row)
                transaction_id = transaction["transaction_id"]
                if transaction_id in seen_transaction_ids:
                    warnings.append(f"Row {i} skipped: duplicate transaction ID {transaction_id}")
                    continue
                seen_transaction_ids.add(transaction_id)
                self.transactions.append(transaction)
                if transaction.get("_uses_default_fee_rate"):
                    warnings.append(
                        f"Row {i}: payment method '{transaction['payment_method']}' uses the configured default fee rate."
                    )
            except Exception as exc:
                warnings.append(f"Row {i} skipped: {exc}")

        return {"parsed": len(self.transactions), "errors": errors, "warnings": warnings}

    def _get(self, row: dict, norm_key: str, default: str = "") -> str:
        for csv_col, norm in self._col_map.items():
            if norm == norm_key:
                return (row.get(csv_col) or "").strip()
        return default

    def _parse_row(self, row: dict) -> dict:
        amount = self._parse_money(self._get(row, "amount"), "amount")
        fee = self._parse_money(self._get(row, "fee"), "fee")
        tax = self._parse_money(self._get(row, "tax"), "tax")
        settle = self._parse_money(self._get(row, "settlement_amount"), "settlement amount")
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        if fee < 0 or tax < 0 or settle < 0:
            raise ValueError("amount, fee, tax, and settlement amount must not be negative")
        if fee + tax > amount + config.RECONCILIATION_BALANCE_TOLERANCE:
            raise ValueError("fee and tax exceed the gross amount")
        method_raw = self._get(row, "payment_method")
        method = self._normalize_method(method_raw)
        status_raw = self._normalize_token(self._get(row, "status"))
        status = STATUS_ALIASES.get(status_raw)
        transaction_id = self._get(row, "transaction_id")
        transaction_date = self._get(row, "transaction_date")
        settlement_date = self._get(row, "settlement_date")
        txn_d = self._parse_date(transaction_date)
        set_d = self._parse_date(settlement_date)
        if not transaction_id:
            raise ValueError("transaction ID is empty")
        if not method:
            raise ValueError("payment method is empty")
        if not status:
            raise ValueError(f"unsupported status: {status_raw or '(empty)'}")
        if transaction_date and not txn_d:
            raise ValueError(f"unsupported transaction date: {transaction_date}")
        if settlement_date and not set_d:
            raise ValueError(f"unsupported settlement date: {settlement_date}")
        if txn_d and set_d and set_d < txn_d:
            raise ValueError("settlement date is before transaction date")
        return {
            "transaction_id":    transaction_id,
            "order_id":          self._get(row, "order_id") or "-",
            "settlement_id":     self._get(row, "settlement_id") or "-",
            "amount":            amount,
            "fee":               fee,
            "tax":               tax,
            "settlement_amount": settle,
            "status":            status,
            "payment_method":    method,
            "settlement_date":   settlement_date or "-",
            "transaction_date":  transaction_date or "-",
            "_txn_date":         txn_d,
            "_set_date":         set_d,
            "_uses_default_fee_rate": method not in FEE_RATES,
        }

    @staticmethod
    def _parse_date(s: str):
        if not s or s in ("-", ""):
            return None
        value = s.strip()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
            "%d-%b-%Y",
            "%d-%B-%Y",
            "%d-%m-%y",
            "%d/%m/%y",
            "%d %b %y",
            "%d %B %y",
            "%d-%b-%y",
            "%d-%B-%y",
        ):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _settlement_elapsed_days(start: date, end: date) -> int:
        calendar_days = (end - start).days
        if config.SETTLEMENT_DAY_MODE == "calendar":
            return calendar_days
        return sum(
            1 for offset in range(1, calendar_days + 1)
            if date.fromordinal(start.toordinal() + offset).weekday() < 5
        )

    # ─── Fee Calculator ──────────────────────────────────────────────────────

    def calculate_expected_fee(self, amount: float, method: str) -> tuple[float, float]:
        rate_pct, gst_pct = FEE_RATES.get(method.strip().lower(), FEE_DEFAULT)
        fee = round(amount * rate_pct / 100, 2)
        gst = round(fee * gst_pct / 100, 2)
        return fee, gst

    # ─── Analysis ────────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        if not self.transactions:
            self.summary = {}
            return self.summary

        total_gross = total_fee = total_tax = total_settled = 0.0
        total_exp_fee = total_exp_tax = 0.0
        total_fee_overcharge = total_tax_overcharge = 0.0
        held, pending, overcharged, tat_violations, settlement_differences = [], [], [], [], []
        missing: list[dict] = []
        method_stats: dict[str, dict] = {}
        settled_count = held_count = pending_count = tat_count = 0
        timing_evaluable_count = 0
        total_settlement_shortfall = total_settlement_excess = 0.0

        for txn in self.transactions:
            amt    = txn["amount"]
            fee    = txn["fee"]
            tax    = txn["tax"]
            method = txn["payment_method"]
            status = txn["status"]

            total_gross   += amt
            total_fee     += fee
            total_tax     += tax
            total_settled += txn["settlement_amount"]

            exp_fee, exp_tax = self.calculate_expected_fee(amt, method)
            total_exp_fee += exp_fee
            total_exp_tax += exp_tax

            fee_delta = round(fee - exp_fee, 2)
            tax_delta = round(tax - exp_tax, 2)
            fee_exceeds = fee_delta > 0 and (
                exp_fee == 0 or fee_delta / exp_fee > config.FEE_OVERCHARGE_TOLERANCE
            )
            tax_exceeds = tax_delta > 0 and (
                exp_tax == 0 or tax_delta / exp_tax > config.FEE_OVERCHARGE_TOLERANCE
            )
            if fee_exceeds or tax_exceeds:
                fee_overcharge = max(fee_delta, 0) if fee_exceeds else 0.0
                tax_overcharge = max(tax_delta, 0) if tax_exceeds else 0.0
                total_fee_overcharge += fee_overcharge
                total_tax_overcharge += tax_overcharge
                overcharged.append({
                    **txn,
                    "expected_fee": exp_fee,
                    "expected_tax": exp_tax,
                    "fee_overcharge": round(fee_overcharge, 2),
                    "tax_overcharge": round(tax_overcharge, 2),
                    "overcharge": round(fee_overcharge + tax_overcharge, 2),
                })

            expected_net = round(amt - fee - tax, 2)
            settlement_delta = round(expected_net - txn["settlement_amount"], 2)
            balance_tolerance = config.RECONCILIATION_BALANCE_TOLERANCE
            should_check_balance = status == "settled" or settlement_delta < -balance_tolerance
            if should_check_balance and abs(settlement_delta) > balance_tolerance:
                difference_type = "shortfall" if settlement_delta > 0 else "excess"
                shortfall = max(settlement_delta, 0.0)
                excess = max(-settlement_delta, 0.0)
                total_settlement_shortfall += shortfall
                total_settlement_excess += excess
                settlement_differences.append({
                    **txn,
                    "expected_net_settlement": expected_net,
                    "settlement_difference": settlement_delta,
                    "difference_type": difference_type,
                    "shortfall": round(shortfall, 2),
                    "excess": round(excess, 2),
                })

            # TAT violation
            td = txn.get("_txn_date")
            sd = txn.get("_set_date")
            if td and sd:
                timing_evaluable_count += 1
                days_diff = self._settlement_elapsed_days(td, sd)
                if days_diff > config.EXPECTED_SETTLEMENT_DAYS:
                    tat_count += 1
                    tat_violations.append({
                        **txn,
                        "days_delayed": days_diff,
                        "days_over_window": days_diff - config.EXPECTED_SETTLEMENT_DAYS,
                    })

            # Status
            outstanding_amount = round(max(amt - txn["settlement_amount"], 0), 2)
            status_txn = {**txn, "outstanding_amount": outstanding_amount}
            if status == "settled":
                settled_count += 1
            elif status == "on_hold":
                held_count += 1
                held.append(status_txn)
                missing.append({**status_txn, "issue": "on_hold"})
            elif status == "pending":
                pending_count += 1
                pending.append(status_txn)
                missing.append({**status_txn, "issue": "pending"})

            # Method breakdown
            mk = method.strip().lower() if method else "unknown"
            if mk not in method_stats:
                method_stats[mk] = {"count": 0, "gross": 0.0, "held": 0, "pending": 0}
            method_stats[mk]["count"] += 1
            method_stats[mk]["gross"] += amt
            if status == "on_hold":
                method_stats[mk]["held"] += 1
            elif status == "pending":
                method_stats[mk]["pending"] += 1

        total_fee_overcharge = round(total_fee_overcharge, 2)
        total_tax_overcharge = round(total_tax_overcharge, 2)
        total_overcharge = round(total_fee_overcharge + total_tax_overcharge, 2)
        total_settlement_shortfall = round(total_settlement_shortfall, 2)
        total_settlement_excess = round(total_settlement_excess, 2)
        recovery_amount = round(sum(
            max(t["amount"] - t["settlement_amount"], 0) for t in held + pending
        ), 2)
        recovery_amount_net = round(
            sum(max(t["amount"] - t["fee"] - t["tax"] - t["settlement_amount"], 0) for t in held + pending), 2
        )
        residual_variance = round(total_gross - total_settled - recovery_amount_net - total_fee - total_tax, 2)
        if abs(residual_variance) < config.RECONCILIATION_ZERO_TOLERANCE:
            residual_variance = 0.0
        issue_ids = {
            txn["transaction_id"]
            for group in (held, pending, overcharged, tat_violations, settlement_differences)
            for txn in group
        }
        timing_missing_count = len(self.transactions) - timing_evaluable_count
        timing_assessment_status = (
            "complete"
            if timing_evaluable_count == len(self.transactions)
            else "unavailable"
            if timing_evaluable_count == 0
            else "partial"
        )
        amount_to_review = round(
            recovery_amount
            + total_settlement_shortfall
            + total_settlement_excess
            + total_overcharge,
            2,
        )
        net_recovery_requested = round(
            recovery_amount_net + total_settlement_shortfall + total_overcharge,
            2,
        )

        self.summary = {
            "total_transactions": len(self.transactions),
            "settled_count":      settled_count,
            "held_count":         held_count,
            "pending_count":      pending_count,
            "tat_count":          tat_count,
            "timing_evaluable_count": timing_evaluable_count,
            "timing_missing_count": timing_missing_count,
            "timing_assessment_status": timing_assessment_status,
            "total_gross":        round(total_gross,   2),
            "total_settled":      round(total_settled, 2),
            "total_fee_charged":  round(total_fee,     2),
            "total_tax_charged":  round(total_tax,     2),
            "total_expected_fee": round(total_exp_fee, 2),
            "total_expected_tax": round(total_exp_tax, 2),
            "total_fee_overcharge": total_fee_overcharge,
            "total_tax_overcharge": total_tax_overcharge,
            "total_overcharge":   total_overcharge,
            "total_settlement_shortfall": total_settlement_shortfall,
            "total_settlement_excess": total_settlement_excess,
            "settlement_difference_count": len(settlement_differences),
            "exception_transaction_count": len(issue_ids),
            "amount_to_review": amount_to_review,
            "net_recovery_requested": net_recovery_requested,
            "residual_variance": residual_variance,
            "recovery_amount":    recovery_amount,
            "recovery_amount_net": recovery_amount_net,
            "missing_settlements":missing,
            "overcharged_fees":   overcharged,
            "held_funds":         held,
            "pending_funds":      pending,
            "tat_violations":     tat_violations,
            "settlement_differences": settlement_differences,
            "method_stats":       method_stats,
            "health_score":       self._health_score(
                len(self.transactions), held_count, pending_count,
                tat_count, total_overcharge, len(settlement_differences)
            ),
        }
        return self.summary

    def _health_score(self, total, held, pending, tat, overcharge, balance_differences=0) -> dict:
        if total == 0:
            return {"score": 0, "label": "No Data", "color": "gray"}
        score = 100
        miss_pct = (held + pending + balance_differences) / total * 100
        score -= min(miss_pct * config.HEALTH_MISSING_WEIGHT, config.HEALTH_MISSING_MAX_PENALTY)
        score -= min((tat / max(total, 1)) * config.HEALTH_TAT_WEIGHT, config.HEALTH_TAT_MAX_PENALTY)
        score -= min(max(overcharge, 0) / config.HEALTH_OVERCHARGE_DIVISOR, config.HEALTH_OVERCHARGE_MAX_PENALTY)
        score = max(int(score), 0)
        if score >= config.HEALTH_HEALTHY_MIN: return {"score": score, "label": "Healthy",         "color": "green"}
        if score >= config.HEALTH_MINOR_ISSUES_MIN: return {"score": score, "label": "Minor Issues",    "color": "yellow"}
        if score >= config.HEALTH_ATTENTION_MIN: return {"score": score, "label": "Needs Attention", "color": "orange"}
        return             {"score": score, "label": "Critical",        "color": "red"}

    def draft_recovery_ticket(self) -> str:
        s = self.summary
        if not s:
            return "Run analyze() first."
        agg_short = config.AGGREGATOR_SHORT
        has_held = s.get("held_count", 0) > 0
        has_pending = s.get("pending_count", 0) > 0
        has_timing = s.get("tat_count", 0) > 0
        has_fee_difference = bool(s.get("overcharged_fees"))
        has_settlement_difference = s.get("settlement_difference_count", 0) > 0
        has_exceptions = has_held or has_pending or has_timing or has_fee_difference or has_settlement_difference
        transaction_word = lambda count: "transaction" if count == 1 else "transactions"
        timing_exception_phrase = lambda count: (
            f"{count} timing exception was identified"
            if count == 1
            else f"{count} timing exceptions were identified"
        )
        timing_status = s.get("timing_assessment_status", "complete")
        timing_evaluable = s.get("timing_evaluable_count", s.get("total_transactions", 0))
        timing_exceptions = timing_exception_phrase(s["tat_count"])
        if timing_status == "unavailable":
            timing_summary = "Not assessed - transaction and settlement dates were not supplied."
        elif timing_status == "partial":
            timing_summary = (
                f"Partially assessed - {timing_evaluable} of {s['total_transactions']} "
                f"{transaction_word(s['total_transactions'])} had both required dates; "
                f"{timing_exceptions} in those rows."
            )
        else:
            timing_scope = (
                "Assessed for the transaction"
                if s["total_transactions"] == 1
                else f"Assessed for all {s['total_transactions']} transactions"
            )
            timing_summary = (
                f"{timing_scope}; {timing_exceptions}."
            )
        if has_held or has_pending:
            subject = "Settlement Reconciliation Request - Held or Pending Funds"
        elif has_exceptions:
            subject = "Settlement Reconciliation Review - Exceptions Identified"
        else:
            subject = "Settlement Reconciliation Confirmation"
        lines = [
            f"Subject: {subject} (Account: [YOUR_MERCHANT_ID])",
            "",
            f"Dear {agg_short} Settlements Team,",
            "",
            (
                "I am requesting review of settlement discrepancies in account [YOUR_MERCHANT_ID]."
                if has_exceptions
                else f"I have reconciled the {transaction_word(s['total_transactions'])} below for account [YOUR_MERCHANT_ID]."
            ),
            (
                "After reconciling my records, I identified the following items:"
                if has_exceptions
                else "The audit found no hold, pending settlement, fee difference, or settlement balance difference under the configured account rules."
            ),
            "",
        ]
        n = 1
        if has_held:
            total_held = sum(t["amount"] for t in s["held_funds"])
            held_outstanding = sum(t["outstanding_amount"] for t in s["held_funds"])
            lines += [
                (
                    f"{n}. FUNDS ON HOLD: {s['held_count']} {transaction_word(s['held_count'])} "
                    f"with {INR}{held_outstanding:,.2f} outstanding "
                    f"({INR}{total_held:,.2f} gross transaction value)"
                ),
                "   Please provide the reason, required remediation, applicable merchant-policy or agreement clause, and expected release date.",
                f"   Please also provide the merchant-grievance contact and escalation matrix required by {config.PA_DISPUTE_REFERENCE} of {config.PA_DIRECTIONS_REFERENCE}.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in s['held_funds'])}",
                "",
            ]
            n += 1
        if has_pending:
            total_pend = sum(t["amount"] for t in s["pending_funds"])
            pending_outstanding = sum(t["outstanding_amount"] for t in s["pending_funds"])
            lines += [
                (
                    f"{n}. PENDING SETTLEMENTS: {s['pending_count']} {transaction_word(s['pending_count'])} "
                    f"marked pending with {INR}{pending_outstanding:,.2f} outstanding "
                    f"({INR}{total_pend:,.2f} gross transaction value)"
                ),
                (
                    "   This transaction remains marked pending in the provider report. "
                    if s["pending_count"] == 1
                    else "   These transactions remain marked pending in the provider report. "
                )
                + "Please confirm the applicable settlement schedule and expected settlement date.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in s['pending_funds'])}",
                "",
            ]
            n += 1
        if has_timing:
            timing_detail_lines = []
            for violation in s["tat_violations"]:
                elapsed = violation["days_delayed"]
                over_window = violation["days_over_window"]
                day_basis = config.SETTLEMENT_DAY_MODE.lower()
                elapsed_unit = f"{day_basis} day" if elapsed == 1 else f"{day_basis} days"
                over_unit = f"{day_basis} day" if over_window == 1 else f"{day_basis} days"
                timing_detail_lines.append(
                    f"   - {violation['transaction_id']}: "
                    f"{violation['transaction_date']} to {violation['settlement_date']} "
                    f"({elapsed} {elapsed_unit}; {over_window} {over_unit} beyond the configured window)"
                )
            lines += [
                f"{n}. SETTLEMENT WINDOW EXCEPTIONS: {s['tat_count']} {transaction_word(s['tat_count'])} exceeded the {config.SETTLEMENT_WINDOW_LABEL}",
                "   Affected transactions:",
                *timing_detail_lines,
                f"   Please reconcile these dates against the settlement timeline stated in our agreement, as contemplated by {config.PA_SETTLEMENT_REFERENCE} of {config.PA_DIRECTIONS_REFERENCE}.",
                "",
            ]
            n += 1
        if has_settlement_difference:
            differences = s["settlement_differences"]
            shortfall = s["total_settlement_shortfall"]
            excess = s["total_settlement_excess"]
            if shortfall and excess:
                difference_label = "SETTLEMENT BALANCE DIFFERENCES"
                amount_line = f"Shortfall: {INR}{shortfall:,.2f} | Excess settlement: {INR}{excess:,.2f}"
            elif shortfall:
                difference_label = "SETTLEMENT SHORTFALL"
                amount_line = f"Net amount not reconciled to the recorded settlement: {INR}{shortfall:,.2f}"
            else:
                difference_label = "EXCESS SETTLEMENT DIFFERENCE"
                amount_line = f"Settlement recorded above the calculated net amount: {INR}{excess:,.2f}"
            lines += [
                f"{n}. {difference_label}: {len(differences)} {transaction_word(len(differences))}",
                f"   {amount_line}",
                "   Please verify the gross amount, charged fee and tax, and bank settlement for each listed transaction.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in differences)}",
                "",
            ]
            n += 1
        if has_fee_difference:
            lines += [
                f"{n}. FEE / TAX DIFFERENCE: {INR}{s['total_overcharge']:,.2f} above the configured pricing benchmark",
                f"   Fee difference: {INR}{s['total_fee_overcharge']:,.2f} | Tax difference: {INR}{s['total_tax_overcharge']:,.2f}",
                "   Please confirm the contracted rates, provide a detailed fee breakup, and credit any confirmed excess charge.",
                "",
            ]
        lines += [
            "SUMMARY:",
            f"  Gross Transaction Value:  {INR}{s['total_gross']:,.2f}",
            f"  Total Settled to Bank:    {INR}{s['total_settled']:,.2f}",
            f"  Outstanding Held / Pending: {INR}{s['recovery_amount']:,.2f}",
            f"  Net Recovery Requested:    {INR}{s.get('net_recovery_requested', s['recovery_amount_net']):,.2f}",
            f"  Timing Assessment:         {timing_summary}",
            "",
            "I REQUEST:",
        ]
        requests: list[str] = []
        if has_held:
            requests.append(
                "The specific reason for each hold, required remediation, the applicable merchant-policy "
                "or agreement clause, and the expected review or settlement date"
            )
        if has_pending:
            requests.append(
                "Confirmation of the settlement schedule applicable to this account and the expected settlement date"
            )
        if has_timing:
            requests.append(
                "An explanation for the recorded delay and confirmation of the settlement schedule applicable to this account"
            )
        if has_settlement_difference:
            requests.append(
                "A transaction-level reconciliation of each settlement balance difference and correction of any confirmed shortfall"
            )
        if has_fee_difference:
            requests.append("A detailed fee and tax breakdown and credit of any confirmed excess charge")
        requests.append(f"A detailed reconciliation statement for the listed {transaction_word(s['total_transactions'])}")
        lines.extend(f"  {index}. {request}" for index, request in enumerate(requests, 1))
        lines.append("")
        if has_exceptions:
            lines += [
                "If this remains unresolved, I will use your published merchant grievance escalation matrix:",
                f"  - Level 1 support: {config.AGGREGATOR_SUPPORT_URL}",
                f"  - Published escalation policy: {getattr(config, 'AGGREGATOR_GRIEVANCE_URL', config.AGGREGATOR_SUPPORT_URL)}",
                f"  - Nodal Officer: {config.AGGREGATOR_GRIEVANCE_EMAIL}",
                (
                    "  - I will assess eligibility for external remedies separately based on entity coverage, "
                    f"the applicable waiting period, and the requirements at {config.OMBUDSMAN_URL}"
                ),
                "",
            ]
        lines += [
            "Merchant ID: [YOUR_MERCHANT_ID]",
            "Registered Email: [YOUR_REGISTERED_EMAIL]",
            f"Date: {date.today().strftime('%d %B %Y')}",
            "",
            "Regards,",
            "[YOUR_NAME / BUSINESS NAME]",
        ]
        return "\n".join(lines)

    def export_report_csv(self) -> str:
        """Export full analysis as CSV for download."""
        s = self.summary
        if not s or not self.transactions:
            return ""
        import datetime as dt
        rows = [
            ["MerchantOS Settlement Reconciliation Report"],
            [f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            [],
            ["SUMMARY"],
            ["Metric", "Value"],
            ["Total Transactions", s["total_transactions"]],
            ["Settled", s["settled_count"]],
            ["On Hold", s["held_count"]],
            ["Pending", s["pending_count"]],
            ["TAT Violations", s["tat_count"]],
            ["Timing Rows Assessed", s.get("timing_evaluable_count", s["total_transactions"])],
            ["Timing Assessment", s.get("timing_assessment_status", "complete")],
            ["Total Gross", f"{INR}{s['total_gross']:,.2f}"],
            ["Total Settled", f"{INR}{s['total_settled']:,.2f}"],
            ["Outstanding Held / Pending", f"{INR}{s['recovery_amount']:,.2f}"],
            ["Net Recovery Amount", f"{INR}{s['recovery_amount_net']:,.2f}"],
            ["Net Recovery Requested", f"{INR}{s.get('net_recovery_requested', s['recovery_amount_net']):,.2f}"],
            ["Settlement Shortfall", f"{INR}{s.get('total_settlement_shortfall', 0):,.2f}"],
            ["Settlement Excess", f"{INR}{s.get('total_settlement_excess', 0):,.2f}"],
            ["Residual Variance", f"{INR}{s.get('residual_variance', 0):,.2f}"],
            ["Fee Difference", f"{INR}{s['total_fee_overcharge']:,.2f}"],
            ["Tax Difference", f"{INR}{s['total_tax_overcharge']:,.2f}"],
            ["Health Score", f"{s['health_score']['score']}/100 ({s['health_score']['label']})"],
            [],
            ["TRANSACTION DETAILS"],
            ["Transaction ID", "Order ID", "Amount", "Fee", "Tax", "Settlement Amt",
             "Status", "Method", "TXN Date", "Settlement Date", "Issue"],
        ]
        issues_by_transaction: dict[str, list[str]] = {}
        for key, label in [
            ("held_funds", "HELD"),
            ("pending_funds", "PENDING"),
            ("tat_violations", "SETTLEMENT WINDOW EXCEPTION"),
            ("overcharged_fees", "FEE / TAX DIFFERENCE"),
            ("settlement_differences", "SETTLEMENT BALANCE DIFFERENCE"),
        ]:
            for item in s.get(key, []):
                labels = issues_by_transaction.setdefault(item["transaction_id"], [])
                if label not in labels:
                    labels.append(label)
        for txn in self.transactions:
            issue = " | ".join(issues_by_transaction.get(txn["transaction_id"], []))
            rows.append([
                txn["transaction_id"], txn["order_id"],
                f"{txn['amount']:.2f}", f"{txn['fee']:.2f}", f"{txn['tax']:.2f}",
                f"{txn['settlement_amount']:.2f}", txn["status"],
                txn["payment_method"], txn["transaction_date"],
                txn["settlement_date"], issue,
            ])
        out = io.StringIO()
        csv.writer(out).writerows(rows)
        return out.getvalue()


if __name__ == "__main__":
    agent = ReconciliationAgent()
    sample = config.SAMPLE_SETTLEMENT_PATH
    with open(sample) as f:
        content = f.read()
    r = agent.parse_csv(content)
    print(f"Parsed: {r['parsed']} | Errors: {r['errors']} | Warnings: {len(r['warnings'])}")
    s = agent.analyze()
    print(f"Health: {s['health_score']['label']} ({s['health_score']['score']}/100)")
    print(f"Gross: {INR}{s['total_gross']:,.2f} | Settled: {INR}{s['total_settled']:,.2f}")
    print(f"Recovery: {INR}{s['recovery_amount']:,.2f}")
    print(f"Held: {s['held_count']} | Pending: {s['pending_count']} | TAT: {s['tat_count']}")
    assert s["health_score"]["score"] >= 0, "Health score error"
    print("Self-test PASSED")
