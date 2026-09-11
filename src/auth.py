"""Shared MerchantOS password/OIDC authentication and server-side sessions."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from src import config


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthError(ValueError):
    """A safe validation message that may be shown to the user."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    path = Path(config.AUTH_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=config.AUTH_DB_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {config.AUTH_SQLITE_BUSY_TIMEOUT_MS}")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            password_hash BLOB NOT NULL,
            password_salt BLOB NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT,
            disabled INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS sessions_expires_at ON sessions(expires_at);
        CREATE TABLE IF NOT EXISTS external_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            subject TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            UNIQUE(provider, subject)
        );
        CREATE INDEX IF NOT EXISTS external_identities_user_id ON external_identities(user_id);
        CREATE TABLE IF NOT EXISTS oauth_states (
            state_hash TEXT PRIMARY KEY,
            nonce TEXT NOT NULL,
            next_url TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS oauth_states_expires_at ON oauth_states(expires_at);
        """
    )
    return connection


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    """Commit or roll back a unit of work and always release its file handle."""
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > config.AUTH_MAX_EMAIL_LENGTH or not _EMAIL_RE.fullmatch(normalized):
        raise AuthError("Enter a valid email address.")
    allowed = config.AUTH_ALLOWED_EMAIL_DOMAINS
    if allowed and normalized.rsplit("@", 1)[-1] not in allowed:
        raise AuthError("This email domain is not allowed for this workspace.")
    return normalized


def _validate_password(password: str) -> None:
    if len(password) < config.AUTH_MIN_PASSWORD_LENGTH:
        raise AuthError(f"Use at least {config.AUTH_MIN_PASSWORD_LENGTH} characters for your password.")
    if len(password) > config.AUTH_MAX_PASSWORD_LENGTH:
        raise AuthError("Password is too long.")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise AuthError("Use a password containing both letters and numbers.")


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        config.AUTH_PBKDF2_ITERATIONS,
    )


def _public_user(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
    }


def register_user(email: str, password: str, display_name: str) -> dict:
    if not config.AUTH_ALLOW_REGISTRATION:
        raise AuthError("New account registration is disabled.")
    normalized = normalize_email(email)
    _validate_password(password)
    name = " ".join(display_name.split())
    if not name or len(name) > config.AUTH_MAX_NAME_LENGTH:
        raise AuthError("Enter your name.")
    salt = secrets.token_bytes(config.AUTH_PASSWORD_SALT_BYTES)
    try:
        with _database() as connection:
            cursor = connection.execute(
                "INSERT INTO users (email, display_name, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
                (normalized, name, _password_hash(password, salt), salt, _timestamp(_now())),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as exc:
        raise AuthError("An account with this email already exists.") from exc
    return _public_user(row)


def authenticate_user(email: str, password: str) -> dict | None:
    try:
        normalized = normalize_email(email)
    except AuthError:
        return None
    with _database() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ? AND disabled = 0", (normalized,)).fetchone()
        candidate_salt = row["password_salt"] if row else bytes(config.AUTH_PASSWORD_SALT_BYTES)
        candidate = _password_hash(password, candidate_salt)
        expected = row["password_hash"] if row else bytes(len(candidate))
        valid = bool(row) and hmac.compare_digest(candidate, expected)
        if not valid:
            return None
        connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_timestamp(_now()), row["id"]))
        return _public_user(row)


def create_oauth_state(next_url: str) -> tuple[str, str]:
    """Persist a short-lived OIDC state and nonce without storing the raw state."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(minutes=config.GOOGLE_OAUTH_STATE_MINUTES)
    state_hash = hashlib.sha256(state.encode("ascii")).hexdigest()
    with _database() as connection:
        connection.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (_timestamp(now),))
        connection.execute(
            "INSERT INTO oauth_states (state_hash, nonce, next_url, expires_at) VALUES (?, ?, ?, ?)",
            (state_hash, nonce, next_url, _timestamp(expires)),
        )
    return state, nonce


def consume_oauth_state(state: str) -> dict | None:
    """Atomically consume a valid state so an OAuth callback cannot be replayed."""
    if not state or len(state) > config.AUTH_MAX_TOKEN_LENGTH:
        return None
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    now = _now()
    with _database() as connection:
        row = connection.execute(
            "SELECT nonce, next_url FROM oauth_states WHERE state_hash = ? AND expires_at > ?",
            (state_hash, _timestamp(now)),
        ).fetchone()
        connection.execute("DELETE FROM oauth_states WHERE state_hash = ?", (state_hash,))
        if not row:
            return None
        return {"nonce": row["nonce"], "next_url": row["next_url"]}


def authenticate_google_identity(subject: str, email: str, display_name: str) -> dict:
    """Resolve a verified Google identity, linking it by verified email when safe."""
    normalized = normalize_email(email)
    clean_subject = subject.strip()
    if not clean_subject or len(clean_subject) > config.AUTH_MAX_TOKEN_LENGTH:
        raise AuthError("Google did not return a valid account identifier.")
    name = " ".join(display_name.split())[: config.AUTH_MAX_NAME_LENGTH]
    if not name:
        name = normalized.split("@", 1)[0]
    now = _timestamp(_now())
    try:
        with _database() as connection:
            row = connection.execute(
                """SELECT users.* FROM external_identities
                   JOIN users ON users.id = external_identities.user_id
                   WHERE external_identities.provider = ? AND external_identities.subject = ?
                     AND users.disabled = 0""",
                ("google", clean_subject),
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE external_identities SET last_login_at = ? WHERE provider = ? AND subject = ?",
                    (now, "google", clean_subject),
                )
                connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
                return _public_user(row)

            row = connection.execute("SELECT * FROM users WHERE email = ? AND disabled = 0", (normalized,)).fetchone()
            if not row:
                salt = secrets.token_bytes(config.AUTH_PASSWORD_SALT_BYTES)
                unusable_password = secrets.token_urlsafe(48)
                cursor = connection.execute(
                    "INSERT INTO users (email, display_name, password_hash, password_salt, created_at, last_login_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (normalized, name, _password_hash(unusable_password, salt), salt, now, now),
                )
                row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            connection.execute(
                "INSERT INTO external_identities (user_id, provider, subject, created_at, last_login_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row["id"], "google", clean_subject, now, now),
            )
            connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
            return _public_user(row)
    except sqlite3.IntegrityError as exc:
        raise AuthError("This Google account could not be linked. Please try again.") from exc


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(config.AUTH_SESSION_TOKEN_BYTES)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    created = _now()
    expires = created + timedelta(hours=config.AUTH_SESSION_HOURS)
    with _database() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (_timestamp(created),))
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
            (token_hash, user_id, _timestamp(created), _timestamp(expires), _timestamp(created)),
        )
    return token


def get_session_user(token: str | None) -> dict | None:
    # Streamlit's cookie proxy can return a non-string sentinel when cookies are
    # unavailable (notably during its test runner and some first-load states).
    # Treat anything except a real token as an anonymous session.
    if not isinstance(token, str) or not token or len(token) > config.AUTH_MAX_TOKEN_LENGTH:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = _now()
    with _database() as connection:
        row = connection.execute(
            """SELECT users.* FROM sessions
               JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ? AND sessions.expires_at > ? AND users.disabled = 0""",
            (token_hash, _timestamp(now)),
        ).fetchone()
        if not row:
            return None
        connection.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
            (_timestamp(now), token_hash),
        )
        return _public_user(row)


def revoke_session(token: str | None) -> None:
    if not isinstance(token, str) or not token or len(token) > config.AUTH_MAX_TOKEN_LENGTH:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _database() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def auth_database_stats() -> dict[str, int]:
    """Small health helper used by automated verification."""
    with _database() as connection:
        users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sessions = connection.execute("SELECT COUNT(*) FROM sessions WHERE expires_at > ?", (_timestamp(_now()),)).fetchone()[0]
    return {"users": int(users), "active_sessions": int(sessions)}
