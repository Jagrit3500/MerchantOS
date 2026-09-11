"""Persistent, per-user activity history shared by every MerchantOS service."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from src import config


VALID_SECTIONS = {"home", "agent1", "agent2", "agent3"}


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    path = Path(config.ACTIVITY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=config.AUTH_DB_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {config.AUTH_SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            section TEXT NOT NULL,
            action TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS activity_history_user_time "
        "ON activity_history(user_key, created_at DESC, id DESC)"
    )
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _user_key(user_id: int | str | None) -> str:
    return str(user_id if user_id is not None else "local")[:128]


def record_activity(
    user_id: int | str | None,
    section: str,
    action: str,
    title: str,
    detail: str = "",
    metadata: dict | None = None,
) -> int:
    """Append one meaningful workflow event and return its identifier."""
    if section not in VALID_SECTIONS:
        raise ValueError(f"Unknown activity section: {section}")
    clean_title = " ".join(str(title).split())[: config.ACTIVITY_TITLE_MAX_LENGTH]
    clean_detail = " ".join(str(detail).split())[: config.ACTIVITY_DETAIL_MAX_LENGTH]
    if not clean_title:
        raise ValueError("Activity title is required")
    payload = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"), default=str)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _database() as connection:
        cursor = connection.execute(
            """INSERT INTO activity_history
               (user_key, section, action, title, detail, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                _user_key(user_id),
                section,
                str(action)[: config.ACTIVITY_ACTION_MAX_LENGTH],
                clean_title,
                clean_detail,
                payload,
                created_at,
            ),
        )
        return int(cursor.lastrowid)


def read_activity_history(
    user_id: int | str | None,
    section: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Read newest-first history for one user, optionally scoped to a workspace."""
    if section is not None and section not in VALID_SECTIONS:
        raise ValueError(f"Unknown activity section: {section}")
    maximum = min(
        max(int(limit or config.ACTIVITY_HISTORY_DISPLAY_LIMIT), 1),
        config.ACTIVITY_HISTORY_QUERY_LIMIT,
    )
    where = "user_key = ?"
    parameters: list[object] = [_user_key(user_id)]
    if section:
        where += " AND section = ?"
        parameters.append(section)
    parameters.append(maximum)
    with _database() as connection:
        rows = connection.execute(
            f"SELECT * FROM activity_history WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ?",
            parameters,
        ).fetchall()
    history = []
    for row in rows:
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json"))
        except (json.JSONDecodeError, TypeError):
            item["metadata"] = {}
            item.pop("metadata_json", None)
        history.append(item)
    return history


def read_activity(
    user_id: int | str | None,
    activity_id: int,
    section: str | None = None,
) -> dict | None:
    """Read one owned history record, optionally requiring a workspace section."""
    if section is not None and section not in VALID_SECTIONS:
        raise ValueError(f"Unknown activity section: {section}")
    where = "id = ? AND user_key = ?"
    parameters: list[object] = [int(activity_id), _user_key(user_id)]
    if section:
        where += " AND section = ?"
        parameters.append(section)
    with _database() as connection:
        row = connection.execute(
            f"SELECT * FROM activity_history WHERE {where}",
            parameters,
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    try:
        item["metadata"] = json.loads(item.pop("metadata_json"))
    except (json.JSONDecodeError, TypeError):
        item["metadata"] = {}
        item.pop("metadata_json", None)
    return item


def delete_activity(user_id: int | str | None, activity_id: int) -> bool:
    """Delete one history record only when it belongs to the requesting user."""
    with _database() as connection:
        cursor = connection.execute(
            "DELETE FROM activity_history WHERE id = ? AND user_key = ?",
            (int(activity_id), _user_key(user_id)),
        )
        return cursor.rowcount == 1


def clear_activity_history(user_id: int | str | None, section: str) -> int:
    """Delete every record for one user in one workspace."""
    if section not in VALID_SECTIONS:
        raise ValueError(f"Unknown activity section: {section}")
    with _database() as connection:
        cursor = connection.execute(
            "DELETE FROM activity_history WHERE user_key = ? AND section = ?",
            (_user_key(user_id), section),
        )
        return max(cursor.rowcount, 0)


def read_activity_counts(user_id: int | str | None, days: int | None = None) -> list[dict]:
    """Return daily, per-workspace counts for the contribution heatmap."""
    window = max(int(days or config.ACTIVITY_HEATMAP_DAYS), 1)
    today = datetime.now(timezone.utc).date()
    since = (today - timedelta(days=window - 1)).isoformat()
    with _database() as connection:
        rows = connection.execute(
            """SELECT substr(created_at, 1, 10) AS activity_date, section, COUNT(*) AS activity_count
               FROM activity_history
               WHERE user_key = ? AND substr(created_at, 1, 10) BETWEEN ? AND ?
               GROUP BY activity_date, section
               ORDER BY activity_date ASC""",
            (_user_key(user_id), since, today.isoformat()),
        ).fetchall()
    return [dict(row) for row in rows]
