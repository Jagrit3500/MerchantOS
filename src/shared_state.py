"""Small, atomic cross-process state store for the local MerchantOS services."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from src import config


SUMMARY_FIELDS = (
    "total_transactions",
    "settled_count",
    "held_count",
    "pending_count",
    "total_gross",
    "total_settled",
    "total_overcharge",
    "recovery_amount",
    "held_funds",
    "pending_funds",
)


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items() if not key.startswith("_")}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def write_reconciliation_state(summary: dict, source: str) -> None:
    """Publish the latest successful reconciliation for the command center."""
    destination = Path(config.SHARED_STATE_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "summary": {field: _json_value(summary.get(field)) for field in SUMMARY_FIELDS},
    }
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, separators=(",", ":"))
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, destination)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def read_reconciliation_state() -> dict | None:
    """Return the latest valid reconciliation, or None before the first audit."""
    try:
        payload = json.loads(Path(config.SHARED_STATE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("version") != 1 or not isinstance(payload.get("summary"), dict):
        return None
    return payload
