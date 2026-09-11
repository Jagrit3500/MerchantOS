"""
MerchantOS - Agent 2: Settlement Reconciliation Engine
Detects missing settlements, fee/tax differences, TAT violations, and held funds.
All variable rates and thresholds come from the shared MerchantOS configuration.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import config
import csv, io, math
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
# MerchantOS compares reports with this operator-configured expectation.
TAT_CALENDAR_DAYS = int(config.TAT_CALENDAR_DAYS)
KNOWN_STATUSES = {"settled", "on_hold", "hold", "pending", "processing"}

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
        h_lookup = {h.strip().lower().replace(" ", "_"): h for h in headers}
        for norm, aliases in COL_ALIASES.items():
            for alias in aliases:
                if alias in h_lookup:
                    col_map[h_lookup[alias]] = norm
                    break
        return col_map

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
            except Exception as exc:
                warnings.append(f"Row {i} skipped: {exc}")

        return {"parsed": len(self.transactions), "errors": errors, "warnings": warnings}

    def _get(self, row: dict, norm_key: str, default: str = "") -> str:
        for csv_col, norm in self._col_map.items():
            if norm == norm_key:
                return (row.get(csv_col) or "").strip()
        return default

    def _parse_row(self, row: dict) -> dict:
        amount  = float(self._get(row, "amount")           or 0)
        fee     = float(self._get(row, "fee")              or 0)
        tax     = float(self._get(row, "tax")              or 0)
        settle  = float(self._get(row, "settlement_amount")or 0)
        numeric_values = {
            "amount": amount,
            "fee": fee,
            "tax": tax,
            "settlement_amount": settle,
        }
        invalid = [name for name, value in numeric_values.items() if not math.isfinite(value)]
        if invalid:
            raise ValueError(f"non-finite value in {', '.join(invalid)}")
        if amount < 0 or fee < 0 or tax < 0 or settle < 0:
            raise ValueError("amount, fee, tax, and settlement amount must not be negative")
        method  = self._get(row, "payment_method")
        status  = self._get(row, "status").lower().replace(" ", "_")
        transaction_id = self._get(row, "transaction_id")
        transaction_date = self._get(row, "transaction_date")
        settlement_date = self._get(row, "settlement_date")
        txn_d = self._parse_date(transaction_date)
        set_d = self._parse_date(settlement_date)
        if not transaction_id:
            raise ValueError("transaction ID is empty")
        if not method:
            raise ValueError("payment method is empty")
        if status not in KNOWN_STATUSES:
            raise ValueError(f"unsupported status: {status or '(empty)'}")
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
        }

    @staticmethod
    def _parse_date(s: str):
        if not s or s in ("-", ""):
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y"):
            try:
                return datetime.strptime(s.strip(), fmt).date()
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
        held, pending, overcharged, tat_violations = [], [], [], []
        missing: list[dict] = []
        method_stats: dict[str, dict] = {}
        settled_count = held_count = pending_count = tat_count = 0

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

            # TAT violation
            td = txn.get("_txn_date")
            sd = txn.get("_set_date")
            if td and sd:
                days_diff = self._settlement_elapsed_days(td, sd)
                if days_diff > TAT_CALENDAR_DAYS:
                    tat_count += 1
                    tat_violations.append({
                        **txn,
                        "days_delayed": days_diff,
                        "days_over_window": days_diff - TAT_CALENDAR_DAYS,
                    })

            # Status
            if status == "settled":
                settled_count += 1
            elif status in ("on_hold", "hold"):
                held_count += 1
                held.append(txn)
                missing.append({**txn, "issue": "on_hold"})
            elif status in ("pending", "processing"):
                pending_count += 1
                pending.append(txn)
                missing.append({**txn, "issue": "pending"})

            # Method breakdown
            mk = method.strip().lower() if method else "unknown"
            if mk not in method_stats:
                method_stats[mk] = {"count": 0, "gross": 0.0, "held": 0, "pending": 0}
            method_stats[mk]["count"] += 1
            method_stats[mk]["gross"] += amt
            if status in ("on_hold", "hold"):
                method_stats[mk]["held"] += 1
            elif status in ("pending", "processing"):
                method_stats[mk]["pending"] += 1

        total_fee_overcharge = round(total_fee_overcharge, 2)
        total_tax_overcharge = round(total_tax_overcharge, 2)
        total_overcharge = round(total_fee_overcharge + total_tax_overcharge, 2)
        recovery_amount = round(sum(
            max(t["amount"] - t["settlement_amount"], 0) for t in held + pending
        ), 2)
        recovery_amount_net = round(
            sum(max(t["amount"] - t["fee"] - t["tax"] - t["settlement_amount"], 0) for t in held + pending), 2
        )

        self.summary = {
            "total_transactions": len(self.transactions),
            "settled_count":      settled_count,
            "held_count":         held_count,
            "pending_count":      pending_count,
            "tat_count":          tat_count,
            "total_gross":        round(total_gross,   2),
            "total_settled":      round(total_settled, 2),
            "total_fee_charged":  round(total_fee,     2),
            "total_tax_charged":  round(total_tax,     2),
            "total_expected_fee": round(total_exp_fee, 2),
            "total_expected_tax": round(total_exp_tax, 2),
            "total_fee_overcharge": total_fee_overcharge,
            "total_tax_overcharge": total_tax_overcharge,
            "total_overcharge":   total_overcharge,
            "recovery_amount":    recovery_amount,
            "recovery_amount_net": recovery_amount_net,
            "missing_settlements":missing,
            "overcharged_fees":   overcharged,
            "held_funds":         held,
            "pending_funds":      pending,
            "tat_violations":     tat_violations,
            "method_stats":       method_stats,
            "health_score":       self._health_score(
                len(self.transactions), held_count, pending_count,
                tat_count, total_overcharge
            ),
        }
        return self.summary

    def _health_score(self, total, held, pending, tat, overcharge) -> dict:
        if total == 0:
            return {"score": 0, "label": "No Data", "color": "gray"}
        score = 100
        miss_pct = (held + pending) / total * 100
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
        lines = [
            f"Subject: Settlement Reconciliation Dispute - Missing/Held Funds (Account: [YOUR_MERCHANT_ID])",
            "",
            f"Dear {agg_short} Settlements Team,",
            "",
            "I am formally disputing settlement discrepancies in account [YOUR_MERCHANT_ID].",
            "After reconciling my records, I have identified the following issues:",
            "",
        ]
        n = 1
        if s.get("held_count", 0) > 0:
            total_held = sum(t["amount"] for t in s["held_funds"])
            lines += [
                f"{n}. FUNDS ON HOLD: {s['held_count']} transaction(s) totalling {INR}{total_held:,.2f}",
                f"   Please provide the reason, required remediation, and expected release date under your published merchant policy and {config.PA_DISPUTE_REFERENCE} of {config.PA_DIRECTIONS_REFERENCE}.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in s['held_funds'])}",
                "",
            ]
            n += 1
        if s.get("pending_count", 0) > 0:
            total_pend = sum(t["amount"] for t in s["pending_funds"])
            lines += [
                f"{n}. PENDING SETTLEMENTS: {s['pending_count']} transaction(s) totalling {INR}{total_pend:,.2f}",
                f"   These items exceed the {config.SETTLEMENT_WINDOW_LABEL} used for this audit.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in s['pending_funds'])}",
                "",
            ]
            n += 1
        if s.get("tat_count", 0) > 0:
            lines += [
                f"{n}. SETTLEMENT WINDOW EXCEPTIONS: {s['tat_count']} transaction(s) exceeded the {config.SETTLEMENT_WINDOW_LABEL}",
                f"   Please reconcile these dates against the settlement timeline stated in our agreement, as contemplated by {config.PA_SETTLEMENT_REFERENCE} of {config.PA_DIRECTIONS_REFERENCE}.",
                "",
            ]
            n += 1
        if s.get("total_overcharge", 0) > config.FEE_DISPUTE_MIN_AMOUNT:
            lines += [
                f"{n}. FEE / TAX OVERCHARGE: {INR}{s['total_overcharge']:,.2f} charged above configured rates",
                f"   Fee difference: {INR}{s['total_fee_overcharge']:,.2f} | Tax difference: {INR}{s['total_tax_overcharge']:,.2f}",
                "   Please credit the excess amount with a detailed fee breakup.",
                "",
            ]
        lines += [
            "SUMMARY:",
            f"  Gross Transaction Value:  {INR}{s['total_gross']:,.2f}",
            f"  Total Settled to Bank:    {INR}{s['total_settled']:,.2f}",
            f"  Gross Held / Pending:      {INR}{s['recovery_amount']:,.2f}",
            f"  Net Recovery Requested:    {INR}{s['recovery_amount_net']:,.2f}",
            "",
            "I REQUEST:",
            "  1. Written explanation citing specific RBI provision for each hold",
            f"  2. Settlement of eligible transactions within {config.SETTLEMENT_RELEASE_REQUEST_DAYS} business days",
            "  3. Credit of excess fees with a detailed breakdown",
            "  4. A certified reconciliation statement",
            "",
            f"If unresolved within {config.GRIEVANCE_TRIGGER_DAYS} business days, I will escalate to:",
            f"  - {config.AGGREGATOR_SHORT} Grievance Officer: {config.AGGREGATOR_GRIEVANCE_EMAIL}",
            f"  - RBI Integrated Ombudsman: {config.OMBUDSMAN_URL}",
            "",
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
            ["Total Gross", f"{INR}{s['total_gross']:,.2f}"],
            ["Total Settled", f"{INR}{s['total_settled']:,.2f}"],
            ["Gross Held / Pending", f"{INR}{s['recovery_amount']:,.2f}"],
            ["Net Recovery Amount", f"{INR}{s['recovery_amount_net']:,.2f}"],
            ["Fee Overcharge", f"{INR}{s['total_fee_overcharge']:,.2f}"],
            ["Tax Overcharge", f"{INR}{s['total_tax_overcharge']:,.2f}"],
            ["Health Score", f"{s['health_score']['score']}/100 ({s['health_score']['label']})"],
            [],
            ["TRANSACTION DETAILS"],
            ["Transaction ID", "Order ID", "Amount", "Fee", "Tax", "Settlement Amt",
             "Status", "Method", "TXN Date", "Settlement Date", "Issue"],
        ]
        for txn in self.transactions:
            issue = ""
            st = txn["status"]
            if st in ("on_hold", "hold"):     issue = "HELD"
            elif st in ("pending","processing"): issue = "PENDING"
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
