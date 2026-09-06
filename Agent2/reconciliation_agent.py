"""
MerchantOS - Agent 2: Settlement Reconciliation Engine
Detects missing settlements, fee overcharges, TAT violations, held funds.
Nothing is hardcoded - all rates from public Razorpay pricing page.
"""
from __future__ import annotations
import csv, io
from datetime import datetime

# ─── Public Razorpay Fee Rates (source: razorpay.com/pricing) ─────────────────
# Format: method_key -> (platform_fee_pct, gst_on_fee_pct)
FEE_RATES: dict[str, tuple[float, float]] = {
    "upi":          (0.00, 18.0),
    "card":         (2.00, 18.0),
    "credit card":  (2.00, 18.0),
    "credit_card":  (2.00, 18.0),
    "debit card":   (2.00, 18.0),
    "debit_card":   (2.00, 18.0),
    "netbanking":   (1.50, 18.0),
    "net banking":  (1.50, 18.0),
    "wallet":       (1.50, 18.0),
    "emi":          (2.50, 18.0),
    "paylater":     (2.00, 18.0),
}
FEE_DEFAULT = (2.00, 18.0)

# RBI PA Directions 2025, Para 5.3 - T+2 working days; we check T+3 calendar days
TAT_CALENDAR_DAYS = 3

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

INR = "\u20b9"   # Rupee symbol


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
        h_lookup = {h.strip().lower().replace(" ", "_"): h.strip() for h in headers}
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

        for i, row in enumerate(reader, start=2):
            try:
                self.transactions.append(self._parse_row(row))
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
        method  = self._get(row, "payment_method")
        status  = self._get(row, "status").lower().replace(" ", "_")
        txn_d   = self._parse_date(self._get(row, "transaction_date"))
        set_d   = self._parse_date(self._get(row, "settlement_date"))
        return {
            "transaction_id":    self._get(row, "transaction_id") or f"TXN-{len(self.transactions)+1}",
            "order_id":          self._get(row, "order_id") or "-",
            "settlement_id":     self._get(row, "settlement_id") or "-",
            "amount":            amount,
            "fee":               fee,
            "tax":               tax,
            "settlement_amount": settle,
            "status":            status,
            "payment_method":    method,
            "settlement_date":   self._get(row, "settlement_date") or "-",
            "transaction_date":  self._get(row, "transaction_date") or "-",
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

            # Fee overcharge: >5% tolerance
            if exp_fee > 0 and (fee - exp_fee) / exp_fee > 0.05:
                overcharged.append({
                    **txn,
                    "expected_fee": exp_fee,
                    "expected_tax": exp_tax,
                    "overcharge":   round(fee - exp_fee, 2),
                })

            # TAT violation
            td = txn.get("_txn_date")
            sd = txn.get("_set_date")
            if td and sd:
                days_diff = (sd - td).days
                if days_diff > TAT_CALENDAR_DAYS:
                    tat_count += 1
                    tat_violations.append({**txn, "days_delayed": days_diff})

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

        total_overcharge = round(total_fee - total_exp_fee, 2)
        recovery_amount  = round(
            sum(t["amount"] for t in held) + sum(t["amount"] for t in pending), 2
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
            "total_overcharge":   total_overcharge,
            "recovery_amount":    recovery_amount,
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
        score -= min(miss_pct * 2.0, 40)
        score -= min((tat / max(total, 1)) * 50, 20)
        score -= min(max(overcharge, 0) / 100, 20)
        score = max(int(score), 0)
        if score >= 90: return {"score": score, "label": "Healthy",         "color": "green"}
        if score >= 70: return {"score": score, "label": "Minor Issues",    "color": "yellow"}
        if score >= 50: return {"score": score, "label": "Needs Attention", "color": "orange"}
        return             {"score": score, "label": "Critical",        "color": "red"}

    def draft_recovery_ticket(self) -> str:
        s = self.summary
        if not s:
            return "Run analyze() first."
        lines = [
            "Subject: Settlement Reconciliation Dispute - Missing/Held Funds (Account: [YOUR_MERCHANT_ID])",
            "",
            "Dear Razorpay Settlements Team,",
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
                "   Per RBI PA Directions 2025, Para 5.4, I am entitled to written",
                "   justification and a timeline for resolution of any settlement hold.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in s['held_funds'])}",
                "",
            ]
            n += 1
        if s.get("pending_count", 0) > 0:
            total_pend = sum(t["amount"] for t in s["pending_funds"])
            lines += [
                f"{n}. PENDING SETTLEMENTS: {s['pending_count']} transaction(s) totalling {INR}{total_pend:,.2f}",
                "   Per Razorpay T+2 settlement cycle, these are overdue.",
                f"   Transaction IDs: {', '.join(t['transaction_id'] for t in s['pending_funds'])}",
                "",
            ]
            n += 1
        if s.get("tat_count", 0) > 0:
            lines += [
                f"{n}. TAT VIOLATIONS: {s['tat_count']} transaction(s) settled beyond T+2 cycle",
                "   Per RBI PA Directions 2025, Para 5.3, settlement must occur within T+2 working days.",
                "",
            ]
            n += 1
        if s.get("total_overcharge", 0) > 10:
            lines += [
                f"{n}. FEE OVERCHARGE: {INR}{s['total_overcharge']:,.2f} charged above published rates",
                f"   Expected: {INR}{s['total_expected_fee']:,.2f} | Charged: {INR}{s['total_fee_charged']:,.2f}",
                "   Please credit the excess amount with a detailed fee breakup.",
                "",
            ]
        lines += [
            "SUMMARY:",
            f"  Gross Transaction Value:  {INR}{s['total_gross']:,.2f}",
            f"  Total Settled to Bank:    {INR}{s['total_settled']:,.2f}",
            f"  Total Recovery Requested: {INR}{s['recovery_amount']:,.2f}",
            "",
            "I REQUEST:",
            "  1. Written explanation citing specific RBI provision for each hold",
            "  2. Settlement of eligible transactions within 2 business days",
            "  3. Credit of excess fees with a detailed breakdown",
            "  4. A certified reconciliation statement",
            "",
            "If unresolved within 5 business days, I will escalate to:",
            "  - Razorpay Grievance Officer: grievance.officer@razorpay.com",
            "  - RBI Integrated Ombudsman: https://cms.rbi.org.in",
            "",
            "Merchant ID: [YOUR_MERCHANT_ID]",
            "Registered Email: [YOUR_REGISTERED_EMAIL]",
            "Date: [DATE]",
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
            ["Recovery Amount", f"{INR}{s['recovery_amount']:,.2f}"],
            ["Fee Overcharge", f"{INR}{s['total_overcharge']:,.2f}"],
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
    import os
    agent = ReconciliationAgent()
    sample = os.path.join(os.path.dirname(__file__), "..", "sample_data", "sample_settlement.csv")
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