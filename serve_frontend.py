"""Serve only the MerchantOS landing assets and runtime service URLs."""
from __future__ import annotations

import json
import os
import hmac
import threading
import time
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import requests as http_requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import id_token as google_id_token

from src import config
from src.auth import (
    AuthError,
    authenticate_google_identity,
    authenticate_user,
    consume_oauth_state,
    create_oauth_state,
    create_session,
    get_session_user,
    register_user,
    revoke_session,
)


ROOT = Path(__file__).resolve().parent
PUBLIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/landing.css": ("landing.css", "text/css; charset=utf-8"),
    "/landing.js": ("landing.js", "text/javascript; charset=utf-8"),
}


class AttemptLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - config.AUTH_RATE_LIMIT_WINDOW_SECONDS
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] < cutoff:
                attempts.popleft()
            if len(attempts) >= config.AUTH_RATE_LIMIT_ATTEMPTS:
                return False
            attempts.append(now)
            return True

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


ATTEMPT_LIMITER = AttemptLimiter()


class LandingHandler(BaseHTTPRequestHandler):
    def _security_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "media-src 'self' https: data:; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def _session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(config.AUTH_COOKIE_NAME)
        return morsel.value if morsel else None

    def _cookie_header(
        self,
        token: str = "",
        clear: bool = False,
        name: str | None = None,
        max_age: int | None = None,
    ) -> str:
        cookie_name = name or config.AUTH_COOKIE_NAME
        lifetime = config.AUTH_SESSION_HOURS * 3600 if max_age is None else max_age
        parts = [f"{cookie_name}={token}", "Path=/", "HttpOnly", "SameSite=Lax"]
        parts.append("Max-Age=0" if clear else f"Max-Age={lifetime}")
        if config.AUTH_SECURE_COOKIE:
            parts.append("Secure")
        return "; ".join(parts)

    def _redirect(self, destination: str, cookies: tuple[str, ...] = ()) -> None:
        self.send_response(302)
        self.send_header("Location", destination)
        self.send_header("Cache-Control", "no-store")
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()

    def _safe_destination(self, candidate: str | None) -> str:
        allowed = tuple(config.app_urls()[key].rstrip("/") for key in ("home", "agent1", "agent2", "agent3"))
        if not candidate:
            return allowed[0]
        parsed = urlsplit(candidate)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        return normalized if normalized in allowed else allowed[0]

    def _oauth_failure(self, code: str) -> None:
        query = urlencode({"auth": "signin", "oauth_error": code})
        self._redirect(
            f"{config.app_urls()['landing'].rstrip('/')}?{query}",
            (self._cookie_header(clear=True, name=config.GOOGLE_OAUTH_COOKIE_NAME),),
        )

    def _start_google_auth(self) -> None:
        if not config.AUTH_ENABLED or not config.GOOGLE_AUTH_ENABLED:
            self._oauth_failure("not_configured")
            return
        query = parse_qs(urlsplit(self.path).query)
        destination = self._safe_destination(query.get("next", [None])[0])
        state, nonce = create_oauth_state(destination)
        authorization_query = urlencode(
            {
                "client_id": config.GOOGLE_CLIENT_ID,
                "redirect_uri": config.GOOGLE_REDIRECT_URI,
                "response_type": "code",
                "scope": " ".join(config.GOOGLE_OAUTH_SCOPES),
                "state": state,
                "nonce": nonce,
                "prompt": "select_account",
            }
        )
        oauth_cookie = self._cookie_header(
            state,
            name=config.GOOGLE_OAUTH_COOKIE_NAME,
            max_age=config.GOOGLE_OAUTH_STATE_MINUTES * 60,
        )
        self._redirect(f"{config.GOOGLE_AUTHORIZATION_URL}?{authorization_query}", (oauth_cookie,))

    def _finish_google_auth(self) -> None:
        if not config.AUTH_ENABLED or not config.GOOGLE_AUTH_ENABLED:
            self._oauth_failure("not_configured")
            return
        query = parse_qs(urlsplit(self.path).query)
        state = query.get("state", [""])[0]
        state_cookie = SimpleCookie(self.headers.get("Cookie", "")).get(config.GOOGLE_OAUTH_COOKIE_NAME)
        if not state_cookie or not hmac.compare_digest(state, state_cookie.value):
            self._oauth_failure("state")
            return
        oauth_state = consume_oauth_state(state)
        if not oauth_state:
            self._oauth_failure("expired")
            return
        if query.get("error") or not query.get("code"):
            self._oauth_failure("cancelled")
            return
        try:
            token_response = http_requests.post(
                config.GOOGLE_TOKEN_URL,
                data={
                    "code": query["code"][0],
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": config.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                timeout=config.GOOGLE_OAUTH_TIMEOUT_SECONDS,
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            encoded_id_token = token_payload.get("id_token")
            if not encoded_id_token:
                raise ValueError("Missing ID token")
            claims = google_id_token.verify_oauth2_token(
                encoded_id_token,
                GoogleAuthRequest(),
                config.GOOGLE_CLIENT_ID,
            )
            if not hmac.compare_digest(str(claims.get("nonce", "")), oauth_state["nonce"]):
                raise ValueError("Invalid nonce")
            if claims.get("email_verified") is not True:
                raise ValueError("Unverified email")
            user = authenticate_google_identity(
                str(claims.get("sub", "")),
                str(claims.get("email", "")),
                str(claims.get("name", "")),
            )
            session_token = create_session(user["id"])
        except (AuthError, GoogleAuthError, ValueError, http_requests.RequestException):
            self._oauth_failure("verification")
            return
        self._redirect(
            oauth_state["next_url"],
            (
                self._cookie_header(session_token),
                self._cookie_header(clear=True, name=config.GOOGLE_OAUTH_COOKIE_NAME),
            ),
        )

    def _json(self, status: int, payload: dict, cookie: str | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict | None:
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"ok": False, "error": "Use application/json."})
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > config.AUTH_MAX_REQUEST_BYTES:
            self._json(400, {"ok": False, "error": "Invalid request size."})
            return None
        origin = self.headers.get("Origin", "")
        parsed_origin = urlsplit(origin)
        configured_origin = urlsplit(config.app_urls()["landing"])
        host_matches_request = (
            parsed_origin.scheme in {"http", "https"}
            and parsed_origin.netloc == self.headers.get("Host", "")
            and not parsed_origin.path.rstrip("/")
        )
        matches_configured_origin = (
            parsed_origin.scheme == configured_origin.scheme
            and parsed_origin.netloc == configured_origin.netloc
            and not parsed_origin.path.rstrip("/")
        )
        if not (host_matches_request or matches_configured_origin):
            self._json(403, {"ok": False, "error": "Request origin was not accepted."})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"ok": False, "error": "Invalid JSON request."})
            return None
        if not isinstance(payload, dict):
            self._json(400, {"ok": False, "error": "Invalid request."})
            return None
        return payload

    def _rate_key(self, email: str) -> str:
        return f"{self.client_address[0]}:{email.strip().lower()[:config.AUTH_MAX_EMAIL_LENGTH]}"

    def _response(self) -> tuple[int, str, bytes]:
        path = urlsplit(self.path).path
        if path == "/runtime-config.js":
            exposed_config = {
                **{key: value for key, value in config.app_urls().items() if key != "landing"},
                "videos": {"hero": config.HERO_VIDEO_URL, "about": config.ABOUT_VIDEO_URL},
                "videoRetryIntervalMs": config.VIDEO_RETRY_INTERVAL_MS,
                "googleAuthEnabled": config.GOOGLE_AUTH_ENABLED,
                "googleAuthSetupMessage": (
                    "Google sign-in is ready."
                    if config.GOOGLE_AUTH_ENABLED
                    else "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env, then restart MerchantOS."
                ),
                "authMinPasswordLength": config.AUTH_MIN_PASSWORD_LENGTH,
                "authMaxPasswordLength": config.AUTH_MAX_PASSWORD_LENGTH,
                "authMaxNameLength": config.AUTH_MAX_NAME_LENGTH,
            }
            payload = "window.MERCHANTOS_CONFIG = " + json.dumps(exposed_config) + ";\n"
            return 200, "text/javascript; charset=utf-8", payload.encode("utf-8")
        asset = PUBLIC_ASSETS.get(path)
        if not asset:
            return 404, "text/plain; charset=utf-8", b"Not found\n"
        filename, content_type = asset
        return 200, content_type, (ROOT / filename).read_bytes()

    def _send(self, include_body: bool) -> None:
        status, content_type, payload = self._response()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/runtime-config") else "public, max-age=300")
        self._security_headers()
        self.end_headers()
        if include_body:
            self.wfile.write(payload)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/auth/google/start":
            self._start_google_auth()
            return
        if path == "/api/auth/google/callback":
            self._finish_google_auth()
            return
        if path == "/api/auth/me":
            user = get_session_user(self._session_token()) if config.AUTH_ENABLED else {"display_name": "Local user", "email": ""}
            self._json(200, {"ok": True, "authenticated": bool(user), "user": user})
            return
        if path == "/api/health":
            self._json(200, {
                "ok": True,
                "authEnabled": config.AUTH_ENABLED,
                "googleAuthEnabled": config.GOOGLE_AUTH_ENABLED,
            })
            return
        self._send(include_body=True)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {"/api/auth/login", "/api/auth/register", "/api/auth/logout"}:
            self._json(404, {"ok": False, "error": "Not found."})
            return
        payload = self._read_json()
        if payload is None:
            return
        if path == "/api/auth/logout":
            revoke_session(self._session_token())
            self._json(200, {"ok": True}, self._cookie_header(clear=True))
            return
        if not config.AUTH_ENABLED:
            self._json(409, {"ok": False, "error": "Authentication is disabled."})
            return
        email = str(payload.get("email", ""))
        password = str(payload.get("password", ""))
        rate_key = self._rate_key(email)
        if not ATTEMPT_LIMITER.allow(rate_key):
            self._json(429, {"ok": False, "error": "Too many attempts. Try again later."})
            return
        try:
            if path == "/api/auth/register":
                user = register_user(email, password, str(payload.get("displayName", "")))
            else:
                user = authenticate_user(email, password)
                if not user:
                    self._json(401, {"ok": False, "error": "Email or password is incorrect."})
                    return
            token = create_session(user["id"])
        except AuthError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        ATTEMPT_LIMITER.clear(rate_key)
        self._json(200, {"ok": True, "user": user}, self._cookie_header(token))

    def do_HEAD(self) -> None:
        self._send(include_body=False)

    def log_message(self, message: str, *args) -> None:
        print(f"[landing] {self.address_string()} - {message % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((config.FRONTEND_BIND_HOST, config.PORT_LANDING), LandingHandler)
    print(f"MerchantOS landing page: {config.app_urls()['landing']}", flush=True)
    if config.GOOGLE_AUTH_REQUESTED and not config.GOOGLE_AUTH_CONFIGURED:
        print(
            "Google sign-in disabled: add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env, then restart.",
            flush=True,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
