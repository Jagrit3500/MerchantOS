import os
from urllib.parse import urlsplit
from dotenv import load_dotenv

# Always load .env from the project root (MerchantOS folder), not cwd
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(ENV_PATH, override=False)

# Force offline mode for HuggingFace
os.environ["TRANSFORMERS_OFFLINE"] = os.getenv("TRANSFORMERS_OFFLINE", "1")
os.environ["HF_DATASETS_OFFLINE"]  = os.getenv("HF_DATASETS_OFFLINE", "1")

# Networking & Service Ports
HOST = os.getenv("MERCHANTOS_HOST", "localhost")
PORT_HOME = int(os.getenv("PORT_HOME", "8501"))
PORT_AGENT1 = int(os.getenv("PORT_AGENT1", "8502"))
PORT_AGENT2 = int(os.getenv("PORT_AGENT2", "8503"))
PORT_AGENT3 = int(os.getenv("PORT_AGENT3", "8504"))
PORT_LANDING = int(os.getenv("PORT_LANDING", "4173"))
FRONTEND_BIND_HOST = os.getenv("FRONTEND_BIND_HOST", "127.0.0.1")
LAUNCH_READINESS_TIMEOUT = float(os.getenv("LAUNCH_READINESS_TIMEOUT", "25"))
LAUNCH_POLL_INTERVAL = float(os.getenv("LAUNCH_POLL_INTERVAL", "0.25"))
PORT_CHECK_TIMEOUT = float(os.getenv("PORT_CHECK_TIMEOUT", "0.2"))
LAUNCH_MONITOR_INTERVAL = float(os.getenv("LAUNCH_MONITOR_INTERVAL", "1"))
LAUNCH_SHUTDOWN_TIMEOUT = float(os.getenv("LAUNCH_SHUTDOWN_TIMEOUT", "8"))
OPEN_BROWSER = os.getenv("MERCHANTOS_OPEN_BROWSER", "1").lower() not in ("0", "false", "no")

# Authentication
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "1").lower() not in ("0", "false", "no")
AUTH_ALLOW_REGISTRATION = os.getenv("AUTH_ALLOW_REGISTRATION", "1").lower() not in ("0", "false", "no")
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "merchantos_session")
AUTH_SESSION_HOURS = int(os.getenv("AUTH_SESSION_HOURS", "168"))
AUTH_PBKDF2_ITERATIONS = int(os.getenv("AUTH_PBKDF2_ITERATIONS", "310000"))
AUTH_MIN_PASSWORD_LENGTH = int(os.getenv("AUTH_MIN_PASSWORD_LENGTH", "10"))
AUTH_MAX_PASSWORD_LENGTH = int(os.getenv("AUTH_MAX_PASSWORD_LENGTH", "256"))
AUTH_MAX_EMAIL_LENGTH = int(os.getenv("AUTH_MAX_EMAIL_LENGTH", "254"))
AUTH_MAX_NAME_LENGTH = int(os.getenv("AUTH_MAX_NAME_LENGTH", "80"))
AUTH_MAX_TOKEN_LENGTH = int(os.getenv("AUTH_MAX_TOKEN_LENGTH", "128"))
AUTH_DB_TIMEOUT_SECONDS = float(os.getenv("AUTH_DB_TIMEOUT_SECONDS", "5"))
AUTH_SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("AUTH_SQLITE_BUSY_TIMEOUT_MS", "5000"))
AUTH_PASSWORD_SALT_BYTES = int(os.getenv("AUTH_PASSWORD_SALT_BYTES", "16"))
AUTH_SESSION_TOKEN_BYTES = int(os.getenv("AUTH_SESSION_TOKEN_BYTES", "32"))
AUTH_MAX_REQUEST_BYTES = int(os.getenv("AUTH_MAX_REQUEST_BYTES", "16384"))
AUTH_RATE_LIMIT_ATTEMPTS = int(os.getenv("AUTH_RATE_LIMIT_ATTEMPTS", "8"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "900"))
AUTH_SECURE_COOKIE = os.getenv("AUTH_SECURE_COOKIE", "0").lower() in ("1", "true", "yes")
AUTH_ALLOWED_EMAIL_DOMAINS = {
    domain.strip().lower()
    for domain in os.getenv("AUTH_ALLOWED_EMAIL_DOMAINS", "").split(",")
    if domain.strip()
}
_auth_db_relative = os.getenv("AUTH_DB_PATH", "runtime/merchantos_auth.sqlite3")
AUTH_DB_PATH = _auth_db_relative if os.path.isabs(_auth_db_relative) else os.path.join(PROJECT_ROOT, _auth_db_relative)

# Google OpenID Connect
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_AUTH_REQUESTED = os.getenv("GOOGLE_AUTH_ENABLED", "1").lower() not in ("0", "false", "no")
GOOGLE_AUTH_CONFIGURED = bool(
    GOOGLE_CLIENT_ID
    and GOOGLE_CLIENT_SECRET
    and not GOOGLE_CLIENT_ID.lower().startswith(("your_", "replace_"))
    and not GOOGLE_CLIENT_SECRET.lower().startswith(("your_", "replace_"))
)
GOOGLE_AUTH_ENABLED = GOOGLE_AUTH_REQUESTED and GOOGLE_AUTH_CONFIGURED
GOOGLE_AUTHORIZATION_URL = os.getenv(
    "GOOGLE_AUTHORIZATION_URL", "https://accounts.google.com/o/oauth2/v2/auth"
)
GOOGLE_TOKEN_URL = os.getenv("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
_landing_public_url = os.getenv("MERCHANTOS_LANDING_URL", f"http://{HOST}:{PORT_LANDING}").rstrip("/")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", f"{_landing_public_url}/api/auth/google/callback"
)
GOOGLE_OAUTH_SCOPES = tuple(
    scope for scope in os.getenv("GOOGLE_OAUTH_SCOPES", "openid email profile").split() if scope
)
GOOGLE_OAUTH_STATE_MINUTES = int(os.getenv("GOOGLE_OAUTH_STATE_MINUTES", "10"))
GOOGLE_OAUTH_TIMEOUT_SECONDS = float(os.getenv("GOOGLE_OAUTH_TIMEOUT_SECONDS", "10"))
GOOGLE_OAUTH_COOKIE_NAME = os.getenv("GOOGLE_OAUTH_COOKIE_NAME", "merchantos_oauth_state")

# Workspace & Entity Metadata
WORKSPACE_NAME = os.getenv("MERCHANT_WORKSPACE_NAME", "Merchant workspace")
CURRENCY = os.getenv("MERCHANT_CURRENCY", "INR")
CURRENCY_SYMBOL = os.getenv("MERCHANT_CURRENCY_SYMBOL", "₹")
REGION = os.getenv("MERCHANT_REGION", "India")
AGGREGATOR_NAME = os.getenv("PAYMENT_AGGREGATOR_NAME", "Razorpay Software Private Limited")
AGGREGATOR_SHORT = os.getenv("PAYMENT_AGGREGATOR_SHORT", "Razorpay")
AGGREGATOR_GRIEVANCE_EMAIL = os.getenv("PAYMENT_AGGREGATOR_GRIEVANCE_EMAIL", "grievance.officer@razorpay.com")
AGGREGATOR_SUPPORT_URL = os.getenv("PAYMENT_AGGREGATOR_SUPPORT_URL", "razorpay.com/support")
AGGREGATOR_KYC_URL = os.getenv(
    "PAYMENT_AGGREGATOR_KYC_URL",
    "https://razorpay.com/docs/payments/business-types-kyc-documents/",
)
AGGREGATOR_ADDRESS = os.getenv("PAYMENT_AGGREGATOR_ADDRESS", "[PAYMENT AGGREGATOR REGISTERED ADDRESS]")
AGGREGATOR_CIN = os.getenv("PAYMENT_AGGREGATOR_CIN", "[PAYMENT AGGREGATOR CIN]")
OMBUDSMAN_URL = os.getenv("OMBUDSMAN_URL", "https://cms.rbi.org.in")
CONSUMER_HELP_URL = os.getenv("CONSUMER_HELP_URL", "consumerhelpline.gov.in")
PA_DIRECTIONS_NAME = os.getenv(
    "PA_DIRECTIONS_NAME", "RBI (Regulation of Payment Aggregators) Directions, 2025"
)
PA_DIRECTIONS_REFERENCE = os.getenv("PA_DIRECTIONS_REFERENCE", "RBI/DPSS/2025-26/141")
PA_DIRECTIONS_URL = os.getenv(
    "PA_DIRECTIONS_URL", "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12896"
)
PA_DUE_DILIGENCE_REFERENCE = os.getenv(
    "PA_DUE_DILIGENCE_REFERENCE", "Chapter IV, paragraph 13"
)
PA_DISPUTE_REFERENCE = os.getenv("PA_DISPUTE_REFERENCE", "paragraph 8")
PA_SETTLEMENT_REFERENCE = os.getenv(
    "PA_SETTLEMENT_REFERENCE", "Chapter V, paragraph 16, Table 1"
)
OMBUDSMAN_SCHEME_REFERENCE = os.getenv(
    "OMBUDSMAN_SCHEME_REFERENCE", "Reserve Bank - Integrated Ombudsman Scheme, 2021"
)
POLICY_LAST_VERIFIED_DATE = os.getenv("POLICY_LAST_VERIFIED_DATE", "2026-09-12")

# Dynamic Fee & Tax Settings
MDR_RATE_UPI = float(os.getenv("MDR_RATE_UPI", "0.0"))
MDR_RATE_CARD = float(os.getenv("MDR_RATE_CARD", "2.0"))
MDR_RATE_NETBANKING = float(os.getenv("MDR_RATE_NETBANKING", "1.5"))
MDR_RATE_WALLET = float(os.getenv("MDR_RATE_WALLET", "1.5"))
MDR_RATE_EMI = float(os.getenv("MDR_RATE_EMI", "2.5"))
MDR_RATE_PAYLATER = float(os.getenv("MDR_RATE_PAYLATER", "2.0"))
MDR_RATE_DEFAULT = float(os.getenv("MDR_RATE_DEFAULT", "2.0"))
GST_RATE = float(os.getenv("GST_RATE", "18.0"))
EXPECTED_SETTLEMENT_DAYS = int(
    os.getenv("EXPECTED_SETTLEMENT_DAYS", os.getenv("TAT_CALENDAR_DAYS", "2"))
)
SETTLEMENT_DAY_MODE = os.getenv("SETTLEMENT_DAY_MODE", "business").strip().lower()
# Backwards-compatible name retained for older imports and existing deployments.
TAT_CALENDAR_DAYS = EXPECTED_SETTLEMENT_DAYS
SETTLEMENT_WINDOW_LABEL = os.getenv(
    "SETTLEMENT_WINDOW_LABEL", f"configured {EXPECTED_SETTLEMENT_DAYS}-{SETTLEMENT_DAY_MODE}-day window"
)
FEE_OVERCHARGE_TOLERANCE = float(os.getenv("FEE_OVERCHARGE_TOLERANCE", "0.05"))
FEE_DISPUTE_MIN_AMOUNT = float(os.getenv("FEE_DISPUTE_MIN_AMOUNT", "10"))
HEALTH_MISSING_WEIGHT = float(os.getenv("HEALTH_MISSING_WEIGHT", "2.0"))
HEALTH_MISSING_MAX_PENALTY = float(os.getenv("HEALTH_MISSING_MAX_PENALTY", "40"))
HEALTH_TAT_WEIGHT = float(os.getenv("HEALTH_TAT_WEIGHT", "50"))
HEALTH_TAT_MAX_PENALTY = float(os.getenv("HEALTH_TAT_MAX_PENALTY", "20"))
HEALTH_OVERCHARGE_DIVISOR = float(os.getenv("HEALTH_OVERCHARGE_DIVISOR", "100"))
HEALTH_OVERCHARGE_MAX_PENALTY = float(os.getenv("HEALTH_OVERCHARGE_MAX_PENALTY", "20"))
HEALTH_HEALTHY_MIN = int(os.getenv("HEALTH_HEALTHY_MIN", "90"))
HEALTH_MINOR_ISSUES_MIN = int(os.getenv("HEALTH_MINOR_ISSUES_MIN", "70"))
HEALTH_ATTENTION_MIN = int(os.getenv("HEALTH_ATTENTION_MIN", "50"))

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# LLM Settings
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS", "1024"))
TEMPERATURE  = float(os.getenv("TEMPERATURE", "0.0"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "10.0"))
LLM_FALLBACK_CHUNKS = int(os.getenv("LLM_FALLBACK_CHUNKS", "3"))
LLM_FALLBACK_CHARS = int(os.getenv("LLM_FALLBACK_CHARS", "500"))
AUTO_FETCH_POLICY_EVIDENCE = os.getenv("AUTO_FETCH_POLICY_EVIDENCE", "1").lower() in ("1", "true", "yes")
POLICY_EVIDENCE_RESULTS = int(os.getenv("POLICY_EVIDENCE_RESULTS", "3"))
POLICY_EVIDENCE_EXCERPT_CHARS = int(os.getenv("POLICY_EVIDENCE_EXCERPT_CHARS", "650"))
POLICY_EVIDENCE_MIN_CHARS = int(os.getenv("POLICY_EVIDENCE_MIN_CHARS", "45"))
POLICY_EVIDENCE_HEADING_MAX_CHARS = int(os.getenv("POLICY_EVIDENCE_HEADING_MAX_CHARS", "120"))
POLICY_EVIDENCE_TERM_FREQUENCY_CAP = int(os.getenv("POLICY_EVIDENCE_TERM_FREQUENCY_CAP", "3"))

# Embedding Settings
EMBEDDING_MODEL      = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))
EMBEDDING_CACHE_DIR = os.path.expanduser(os.getenv(
    "EMBEDDING_CACHE_DIR", os.getenv("HF_HUB_CACHE", "~/.cache/huggingface/hub")
))

# Chunking Settings
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# ChromaDB - ABSOLUTE PATH so it works from any working directory
_chroma_relative = os.getenv("CHROMA_DB_PATH", "chroma_db")
CHROMA_DB_PATH = (
    _chroma_relative
    if os.path.isabs(_chroma_relative)
    else os.path.join(PROJECT_ROOT, _chroma_relative)
)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "pdf_chunks")

# Retrieval Settings
TOP_K_RESULTS        = int(os.getenv("TOP_K_RESULTS", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))
CONFIDENCE_HIGH_THRESHOLD = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.80"))
RETRIEVAL_SMALL_MAX = int(os.getenv("RETRIEVAL_SMALL_MAX", "40"))
RETRIEVAL_MEDIUM_MAX = int(os.getenv("RETRIEVAL_MEDIUM_MAX", "150"))
RETRIEVAL_LARGE_MAX = int(os.getenv("RETRIEVAL_LARGE_MAX", "450"))
RETRIEVAL_K_SMALL = int(os.getenv("RETRIEVAL_K_SMALL", "5"))
RETRIEVAL_K_MEDIUM = int(os.getenv("RETRIEVAL_K_MEDIUM", "8"))
RETRIEVAL_K_LARGE = int(os.getenv("RETRIEVAL_K_LARGE", "15"))
RETRIEVAL_K_XL = int(os.getenv("RETRIEVAL_K_XL", "20"))

# File Settings
_upload_relative = os.getenv("UPLOAD_DIR", "uploads")
UPLOAD_DIR = (
    _upload_relative
    if os.path.isabs(_upload_relative)
    else os.path.join(PROJECT_ROOT, _upload_relative)
)

_docs_relative = os.getenv("DOCS_DIR", "docs")
DOCS_DIR = _docs_relative if os.path.isabs(_docs_relative) else os.path.join(PROJECT_ROOT, _docs_relative)
_sample_relative = os.getenv("SAMPLE_SETTLEMENT_PATH", "Agent2/sample_data/sample_settlement.csv")
SAMPLE_SETTLEMENT_PATH = _sample_relative if os.path.isabs(_sample_relative) else os.path.join(PROJECT_ROOT, _sample_relative)
_state_relative = os.getenv("SHARED_STATE_PATH", "runtime/latest_reconciliation.json")
SHARED_STATE_PATH = _state_relative if os.path.isabs(_state_relative) else os.path.join(PROJECT_ROOT, _state_relative)
_activity_db_relative = os.getenv("ACTIVITY_DB_PATH", "runtime/merchantos_activity.sqlite3")
ACTIVITY_DB_PATH = _activity_db_relative if os.path.isabs(_activity_db_relative) else os.path.join(PROJECT_ROOT, _activity_db_relative)
ACTIVITY_HISTORY_DISPLAY_LIMIT = int(os.getenv("ACTIVITY_HISTORY_DISPLAY_LIMIT", "50"))
ACTIVITY_HISTORY_QUERY_LIMIT = int(os.getenv("ACTIVITY_HISTORY_QUERY_LIMIT", "500"))
ACTIVITY_TITLE_MAX_LENGTH = int(os.getenv("ACTIVITY_TITLE_MAX_LENGTH", "160"))
ACTIVITY_DETAIL_MAX_LENGTH = int(os.getenv("ACTIVITY_DETAIL_MAX_LENGTH", "800"))
ACTIVITY_ACTION_MAX_LENGTH = int(os.getenv("ACTIVITY_ACTION_MAX_LENGTH", "80"))
ACTIVITY_HEATMAP_DAYS = int(os.getenv("ACTIVITY_HEATMAP_DAYS", "365"))
ACTIVITY_HEATMAP_LEVELS = tuple(
    int(value.strip())
    for value in os.getenv("ACTIVITY_HEATMAP_LEVELS", "1,3,5").split(",")
    if value.strip()
)
DASHBOARD_REFRESH_INTERVAL_SECONDS = float(os.getenv("DASHBOARD_REFRESH_INTERVAL_SECONDS", "2"))
INGEST_SOURCE_ID_MAX_LENGTH = int(os.getenv("INGEST_SOURCE_ID_MAX_LENGTH", "20"))
TXT_CHUNKS_PER_PAGE = int(os.getenv("TXT_CHUNKS_PER_PAGE", "3"))
SAMPLE_PREVIEW_ROWS = int(os.getenv("SAMPLE_PREVIEW_ROWS", "4"))
MANUAL_AMOUNT_STEP = float(os.getenv("MANUAL_AMOUNT_STEP", "50"))

# Recovery workflow timelines
SUPPORT_DEADLINE_DAYS = int(os.getenv("SUPPORT_DEADLINE_DAYS", "5"))
GRIEVANCE_TRIGGER_DAYS = int(os.getenv("GRIEVANCE_TRIGGER_DAYS", "5"))
GRIEVANCE_DEADLINE_DAYS = int(os.getenv("GRIEVANCE_DEADLINE_DAYS", "30"))
OMBUDSMAN_TRIGGER_DAYS = int(os.getenv("OMBUDSMAN_TRIGGER_DAYS", "30"))
OMBUDSMAN_DEADLINE_DAYS = int(os.getenv("OMBUDSMAN_DEADLINE_DAYS", "365"))
LEGAL_TRIGGER_DAYS = int(os.getenv("LEGAL_TRIGGER_DAYS", "90"))
GRIEVANCE_LETTER_DEADLINE_DAYS = int(os.getenv("GRIEVANCE_LETTER_DEADLINE_DAYS", "7"))
SETTLEMENT_RELEASE_REQUEST_DAYS = int(os.getenv("SETTLEMENT_RELEASE_REQUEST_DAYS", "2"))
LEGAL_NOTICE_DEADLINE_DAYS = int(os.getenv("LEGAL_NOTICE_DEADLINE_DAYS", "15"))
HOLD_RECENT_MAX_DAYS = int(os.getenv("HOLD_RECENT_MAX_DAYS", "3"))
HOLD_STANDARD_MAX_DAYS = int(os.getenv("HOLD_STANDARD_MAX_DAYS", "14"))
HOLD_URGENT_TRIGGER_DAYS = int(os.getenv("HOLD_URGENT_TRIGGER_DAYS", "15"))
INITIAL_ACK_HOURS = int(os.getenv("INITIAL_ACK_HOURS", "24"))
FOLLOWUP_ACK_HOURS = int(os.getenv("FOLLOWUP_ACK_HOURS", "48"))
URGENT_RESOLUTION_BUSINESS_DAYS = int(os.getenv("URGENT_RESOLUTION_BUSINESS_DAYS", "3"))
TRANSACTION_LOOKBACK_DAYS = int(os.getenv("TRANSACTION_LOOKBACK_DAYS", "30"))
KYC_CUSTOM_ISSUE_MAX_LENGTH = int(os.getenv("KYC_CUSTOM_ISSUE_MAX_LENGTH", "500"))

# Landing page media and behavior
HERO_VIDEO_URL = os.getenv(
    "HERO_VIDEO_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260823_050407_500d0339-ab28-41c1-9688-132a74a3b5aa.mp4",
)
ABOUT_VIDEO_URL = os.getenv(
    "ABOUT_VIDEO_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260823_063501_2e2c8971-de1e-473a-8611-a0c9ae7ee186.mp4",
)
VIDEO_RETRY_INTERVAL_MS = int(os.getenv("VIDEO_RETRY_INTERVAL_MS", "1000"))


def _validate_settings() -> None:
    ports = [PORT_HOME, PORT_AGENT1, PORT_AGENT2, PORT_AGENT3, PORT_LANDING]
    if any(port < 1 or port > 65535 for port in ports):
        raise ValueError("MerchantOS ports must be between 1 and 65535")
    if len(set(ports)) != len(ports):
        raise ValueError("MerchantOS services must use distinct ports")
    if CHUNK_SIZE <= 0 or CHUNK_OVERLAP < 0 or CHUNK_OVERLAP >= CHUNK_SIZE:
        raise ValueError("CHUNK_SIZE must be positive and CHUNK_OVERLAP must be between 0 and CHUNK_SIZE")
    if HEALTH_OVERCHARGE_DIVISOR <= 0:
        raise ValueError("HEALTH_OVERCHARGE_DIVISOR must be positive")
    if VIDEO_RETRY_INTERVAL_MS <= 0:
        raise ValueError("VIDEO_RETRY_INTERVAL_MS must be positive")
    if DASHBOARD_REFRESH_INTERVAL_SECONDS <= 0:
        raise ValueError("DASHBOARD_REFRESH_INTERVAL_SECONDS must be positive")
    if min(
        AUTH_SESSION_HOURS,
        AUTH_PBKDF2_ITERATIONS,
        AUTH_MIN_PASSWORD_LENGTH,
        AUTH_MAX_PASSWORD_LENGTH,
        AUTH_MAX_EMAIL_LENGTH,
        AUTH_MAX_NAME_LENGTH,
        AUTH_MAX_TOKEN_LENGTH,
        AUTH_DB_TIMEOUT_SECONDS,
        AUTH_SQLITE_BUSY_TIMEOUT_MS,
        AUTH_PASSWORD_SALT_BYTES,
        AUTH_SESSION_TOKEN_BYTES,
        AUTH_MAX_REQUEST_BYTES,
        AUTH_RATE_LIMIT_ATTEMPTS,
        AUTH_RATE_LIMIT_WINDOW_SECONDS,
        GOOGLE_OAUTH_STATE_MINUTES,
        GOOGLE_OAUTH_TIMEOUT_SECONDS,
        LAUNCH_MONITOR_INTERVAL,
        LAUNCH_SHUTDOWN_TIMEOUT,
    ) <= 0:
        raise ValueError("Authentication limits must be positive")
    if AUTH_MAX_PASSWORD_LENGTH < AUTH_MIN_PASSWORD_LENGTH:
        raise ValueError("AUTH_MAX_PASSWORD_LENGTH must not be lower than AUTH_MIN_PASSWORD_LENGTH")
    if not AUTH_COOKIE_NAME or any(char in AUTH_COOKIE_NAME for char in " ;,=\t\r\n"):
        raise ValueError("AUTH_COOKIE_NAME contains an invalid character")
    if not GOOGLE_OAUTH_COOKIE_NAME or any(char in GOOGLE_OAUTH_COOKIE_NAME for char in " ;,=\t\r\n"):
        raise ValueError("GOOGLE_OAUTH_COOKIE_NAME contains an invalid character")
    if GOOGLE_AUTH_ENABLED and "openid" not in GOOGLE_OAUTH_SCOPES:
        raise ValueError("GOOGLE_OAUTH_SCOPES must include openid")
    if GOOGLE_AUTH_REQUESTED and bool(GOOGLE_CLIENT_ID) != bool(GOOGLE_CLIENT_SECRET):
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set together")
    if min(
        POLICY_EVIDENCE_RESULTS,
        POLICY_EVIDENCE_EXCERPT_CHARS,
        POLICY_EVIDENCE_MIN_CHARS,
        POLICY_EVIDENCE_HEADING_MAX_CHARS,
        POLICY_EVIDENCE_TERM_FREQUENCY_CAP,
        ACTIVITY_HISTORY_DISPLAY_LIMIT,
        ACTIVITY_HISTORY_QUERY_LIMIT,
        ACTIVITY_TITLE_MAX_LENGTH,
        ACTIVITY_DETAIL_MAX_LENGTH,
        ACTIVITY_ACTION_MAX_LENGTH,
        ACTIVITY_HEATMAP_DAYS,
        KYC_CUSTOM_ISSUE_MAX_LENGTH,
    ) <= 0:
        raise ValueError("Policy evidence and activity-history limits must be positive")
    if (
        len(ACTIVITY_HEATMAP_LEVELS) != 3
        or min(ACTIVITY_HEATMAP_LEVELS) <= 0
        or tuple(sorted(ACTIVITY_HEATMAP_LEVELS)) != ACTIVITY_HEATMAP_LEVELS
        or len(set(ACTIVITY_HEATMAP_LEVELS)) != 3
    ):
        raise ValueError("ACTIVITY_HEATMAP_LEVELS must contain three ascending integers")
    if ACTIVITY_HEATMAP_DAYS > 730:
        raise ValueError("ACTIVITY_HEATMAP_DAYS must not exceed 730")
    if not (HEALTH_HEALTHY_MIN > HEALTH_MINOR_ISSUES_MIN > HEALTH_ATTENTION_MIN):
        raise ValueError("Health score thresholds must be ordered from healthy to attention")
    if not (RETRIEVAL_SMALL_MAX < RETRIEVAL_MEDIUM_MAX < RETRIEVAL_LARGE_MAX):
        raise ValueError("Retrieval collection-size thresholds must be strictly increasing")
    if min(TOP_K_RESULTS, RETRIEVAL_K_SMALL, RETRIEVAL_K_MEDIUM, RETRIEVAL_K_LARGE, RETRIEVAL_K_XL) <= 0:
        raise ValueError("Retrieval result counts must be positive")
    if not 0 <= SIMILARITY_THRESHOLD <= 1 or not 0 <= CONFIDENCE_HIGH_THRESHOLD <= 1:
        raise ValueError("Retrieval confidence thresholds must be between 0 and 1")
    if EXPECTED_SETTLEMENT_DAYS < 0:
        raise ValueError("EXPECTED_SETTLEMENT_DAYS must not be negative")
    if SETTLEMENT_DAY_MODE not in {"business", "calendar"}:
        raise ValueError("SETTLEMENT_DAY_MODE must be business or calendar")
    if any(rate < 0 for rate in (
        MDR_RATE_UPI,
        MDR_RATE_CARD,
        MDR_RATE_NETBANKING,
        MDR_RATE_WALLET,
        MDR_RATE_EMI,
        MDR_RATE_PAYLATER,
        MDR_RATE_DEFAULT,
        GST_RATE,
    )):
        raise ValueError("Fee and tax rates must not be negative")
    for name, value in {
        "PA_DIRECTIONS_URL": PA_DIRECTIONS_URL,
        "OMBUDSMAN_URL": OMBUDSMAN_URL,
        "AGGREGATOR_KYC_URL": AGGREGATOR_KYC_URL,
    }.items():
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{name} must be an absolute HTTP(S) URL")


_validate_settings()


def app_urls() -> dict[str, str]:
    return {
        key: os.getenv(env, f"http://{HOST}:{port}")
        for key, env, port in [
            ("home", "MERCHANTOS_HOME_URL", PORT_HOME),
            ("agent1", "MERCHANTOS_AGENT1_URL", PORT_AGENT1),
            ("agent2", "MERCHANTOS_AGENT2_URL", PORT_AGENT2),
            ("agent3", "MERCHANTOS_AGENT3_URL", PORT_AGENT3),
            ("landing", "MERCHANTOS_LANDING_URL", PORT_LANDING),
        ]
    }


def validate_groq_key():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in .env file!")


if __name__ == "__main__":
    print("MerchantOS Config Check:")
    print(f"  PROJECT_ROOT:    {PROJECT_ROOT}")
    print(f"  ENV_PATH:        {ENV_PATH} | exists={os.path.exists(ENV_PATH)}")
    print(f"  CHROMA_DB_PATH:  {CHROMA_DB_PATH} | exists={os.path.exists(CHROMA_DB_PATH)}")
    print(f"  HOST & PORTS:    {HOST} -> Website:{PORT_LANDING}, Home:{PORT_HOME}, A1:{PORT_AGENT1}, A2:{PORT_AGENT2}, A3:{PORT_AGENT3}")
    print(f"  AGGREGATOR:      {AGGREGATOR_NAME} ({AGGREGATOR_SHORT})")
    print(f"  WORKSPACE:       {WORKSPACE_NAME} [{CURRENCY}]")
