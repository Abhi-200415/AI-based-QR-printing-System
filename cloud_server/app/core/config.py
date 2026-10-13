import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load .env file from project or cloud_server directory
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# ==========================================================
# Server & Environment Configuration
# ==========================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Base URL for public API access (used for download links, QR codes, and callbacks)
_render_url = os.getenv("RENDER_EXTERNAL_URL")
if _render_url:
    _default_base = _render_url.rstrip("/")
else:
    _default_base = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

BASE_URL = os.getenv("BASE_URL", _default_base).rstrip("/")
API_BASE_URL = os.getenv("API_BASE_URL", f"{BASE_URL}/api")
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", f"ws://localhost:8000/ws/printer")


def resolve_public_base_url(request=None) -> str:
    """
    Intelligently determines the public reachable base URL for the server.
    Priority:
    1. Explicit non-localhost BASE_URL or RENDER_EXTERNAL_URL
    2. Reverse proxy headers (X-Forwarded-Proto, X-Forwarded-Host, Host)
    3. request.base_url fallback
    """
    # Check if BASE_URL is an explicit production URL (not localhost/127.0.0.1/0.0.0.0)
    if BASE_URL and not any(h in BASE_URL for h in ("localhost", "127.0.0.1", "0.0.0.0")):
        return BASE_URL.rstrip("/")

    if request:
        # Check standard reverse-proxy headers from Render, Cloudflare, Nginx, AWS
        proto = request.headers.get("x-forwarded-proto", request.url.scheme or "https")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host and not any(h in host for h in ("localhost", "127.0.0.1", "0.0.0.0")):
            return f"{proto}://{host}".rstrip("/")
        if host:
            return f"{proto}://{host}".rstrip("/")
        return str(request.base_url).rstrip("/")

    return BASE_URL.rstrip("/")


# Database URL (PostgreSQL in production, SQLite fallback for tests)
_raw_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_printing"
)
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = _raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif _raw_db_url.startswith("postgresql://") and not _raw_db_url.startswith("postgresql+"):
    _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
DATABASE_URL = _raw_db_url

# JWT / Security Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-in-production-ai-printing-2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# Storage & Paths Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]

# ==========================================================
# Payment Gateway Configuration & Resolution
# ==========================================================

def mask_key_id(key: str) -> str:
    """Safely masks a public Key ID for logging and diagnostic output. Never leaks secret keys."""
    k = (key or "").strip()
    if not k:
        return "none"
    for prefix in ("rzp_live_", "rzp_test_"):
        if k.startswith(prefix):
            suffix = k[len(prefix):]
            if len(suffix) > 4:
                return f"{prefix}****{suffix[-4:]}"
            return f"{prefix}****"
    if len(k) <= 8:
        return "****" + k[-2:] if len(k) >= 2 else "****"
    return f"{k[:4]}****{k[-4:]}"


def resolve_payment_settings(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Deterministically resolves payment gateway provider, mode, and credentials
    from environment variables with explicit priority and alias handling:

    1. Mode Resolution:
       - Explicit: PAYMENT_MODE or RAZORPAY_MODE ('live' vs 'test')
       - Inferred: 'live' if any key starts with 'rzp_live_', 'test' if 'rzp_test_'
       - Fallback: 'live' in production, 'test' in development

    2. Key ID & Secret Resolution (Strict Precedence based on mode):
       - Live mode:
         Prioritizes RAZORPAY_LIVE_KEY_ID, then RAZORPAY_KEY_ID (if live),
         then PAYMENT_GATEWAY_KEY_ID (if live), preventing stale test keys
         from overriding newly added live credentials.
       - Test mode:
         Prioritizes RAZORPAY_TEST_KEY_ID, then RAZORPAY_KEY_ID (if test),
         then PAYMENT_GATEWAY_KEY_ID (if test).
       - Secret pairing:
         Prioritizes the secret variable matching the selected Key ID source.

    3. Provider Auto-Detection:
       - If PAYMENT_GATEWAY_PROVIDER is explicitly set, uses it.
       - If unset, automatically detects 'RAZORPAY' if Razorpay keys are present,
         preventing accidental silent fallback to 'MANUAL'.
    """
    if env is None:
        env = os.environ

    # Read all possible alias inputs
    live_id = (env.get("RAZORPAY_LIVE_KEY_ID") or "").strip()
    live_sec = (env.get("RAZORPAY_LIVE_KEY_SECRET") or "").strip()

    test_id = (env.get("RAZORPAY_TEST_KEY_ID") or "").strip()
    test_sec = (env.get("RAZORPAY_TEST_KEY_SECRET") or "").strip()

    rzp_id = (env.get("RAZORPAY_KEY_ID") or "").strip()
    rzp_sec = (env.get("RAZORPAY_KEY_SECRET") or "").strip()

    gw_id = (env.get("PAYMENT_GATEWAY_KEY_ID") or "").strip()
    gw_sec = (env.get("PAYMENT_GATEWAY_KEY_SECRET") or "").strip()

    raw_mode = (env.get("PAYMENT_MODE") or env.get("RAZORPAY_MODE") or "").strip().lower()

    # Determine Payment Mode
    if raw_mode in ("live", "prod", "production"):
        mode = "live"
    elif raw_mode in ("test", "sandbox", "dev", "development"):
        mode = "test"
    else:
        # Inferred mode based on keys
        all_ids = [live_id, rzp_id, gw_id, test_id]
        if any(k.startswith("rzp_live_") for k in all_ids if k):
            mode = "live"
        elif any(k.startswith("rzp_test_") for k in all_ids if k):
            mode = "test"
        else:
            mode = "live" if env.get("ENVIRONMENT", "").strip().lower() == "production" else "test"

    # Select Key ID & Secret according to resolved mode
    selected_id = ""
    selected_sec = ""

    if mode == "live":
        # 1. Live-specific variables
        if live_id:
            selected_id = live_id
            selected_sec = live_sec or rzp_sec or gw_sec
        # 2. Key starting with rzp_live_
        elif rzp_id.startswith("rzp_live_"):
            selected_id = rzp_id
            selected_sec = rzp_sec or gw_sec or live_sec
        elif gw_id.startswith("rzp_live_"):
            selected_id = gw_id
            selected_sec = gw_sec or rzp_sec or live_sec
        # 3. RAZORPAY_KEY_ID (if not explicitly a test key)
        elif rzp_id and not rzp_id.startswith("rzp_test_"):
            selected_id = rzp_id
            selected_sec = rzp_sec or gw_sec
        # 4. PAYMENT_GATEWAY_KEY_ID (if not explicitly a test key)
        elif gw_id and not gw_id.startswith("rzp_test_"):
            selected_id = gw_id
            selected_sec = gw_sec or rzp_sec
        # 5. Last fallback to whatever non-empty key is provided
        else:
            selected_id = rzp_id or gw_id or test_id
            selected_sec = rzp_sec or gw_sec or test_sec
    else:  # mode == "test"
        # 1. Test-specific variables
        if test_id:
            selected_id = test_id
            selected_sec = test_sec or rzp_sec or gw_sec
        # 2. Key starting with rzp_test_
        elif rzp_id.startswith("rzp_test_"):
            selected_id = rzp_id
            selected_sec = rzp_sec or gw_sec or test_sec
        elif gw_id.startswith("rzp_test_"):
            selected_id = gw_id
            selected_sec = gw_sec or rzp_sec or test_sec
        # 3. RAZORPAY_KEY_ID (if not explicitly a live key)
        elif rzp_id and not rzp_id.startswith("rzp_live_"):
            selected_id = rzp_id
            selected_sec = rzp_sec or gw_sec
        # 4. PAYMENT_GATEWAY_KEY_ID (if not explicitly a live key)
        elif gw_id and not gw_id.startswith("rzp_live_"):
            selected_id = gw_id
            selected_sec = gw_sec or rzp_sec
        # 5. Last fallback
        else:
            selected_id = rzp_id or gw_id or live_id
            selected_sec = rzp_sec or gw_sec or live_sec

    # Webhook secret
    webhook_sec = (env.get("PAYMENT_WEBHOOK_SECRET") or env.get("RAZORPAY_WEBHOOK_SECRET") or "").strip()

    # Provider Resolution
    configured_provider = (env.get("PAYMENT_GATEWAY_PROVIDER") or "").strip().upper()
    if configured_provider:
        provider = configured_provider
    else:
        # Auto-detect Razorpay if credentials exist
        if selected_id or selected_sec:
            provider = "RAZORPAY"
        else:
            provider = "MANUAL"

    return {
        "provider": provider,
        "mode": mode,
        "key_id": selected_id,
        "key_secret": selected_sec,
        "webhook_secret": webhook_sec,
        "key_id_masked": mask_key_id(selected_id),
        "key_id_configured": bool(selected_id),
        "key_secret_configured": bool(selected_sec),
        "webhook_secret_configured": bool(webhook_sec)
    }


# Evaluate settings at startup
_payment_cfg = resolve_payment_settings()
PAYMENT_GATEWAY_PROVIDER = _payment_cfg["provider"]
PAYMENT_MODE = _payment_cfg["mode"]
PAYMENT_GATEWAY_KEY_ID = _payment_cfg["key_id"]
PAYMENT_GATEWAY_KEY_SECRET = _payment_cfg["key_secret"]
PAYMENT_WEBHOOK_SECRET = _payment_cfg["webhook_secret"]


def get_payment_diagnostics() -> Dict[str, Any]:
    """Returns safe, masked diagnostics. Never exposes secret keys."""
    cfg = resolve_payment_settings()
    return {
        "provider": cfg["provider"],
        "mode": cfg["mode"],
        "key_id_masked": cfg["key_id_masked"],
        "key_id_configured": cfg["key_id_configured"],
        "key_secret_configured": cfg["key_secret_configured"],
        "webhook_secret_configured": cfg["webhook_secret_configured"]
    }


def log_payment_gateway_status():
    """Logs safe non-secret diagnostic status of payment gateway at server boot."""
    import logging
    log = logging.getLogger("cloud_server.payment")
    diag = get_payment_diagnostics()
    log.info(
        f"[PAYMENT INIT] Provider: {diag['provider']} | Mode: {diag['mode'].upper()} | "
        f"Public Key ID: {diag['key_id_masked']} | Secret Set: {diag['key_secret_configured']} | "
        f"Webhook Secret Set: {diag['webhook_secret_configured']}"
    )
    if diag["provider"] == "RAZORPAY":
        if not diag["key_id_configured"] or not diag["key_secret_configured"]:
            log.warning("[PAYMENT WARNING] Razorpay provider is active but Key ID or Secret is missing!")
        if diag["mode"] == "live" and diag["key_id_masked"].startswith("rzp_test_"):
            log.warning(f"[PAYMENT WARNING] Mode is LIVE but Key ID appears to be a TEST key ({diag['key_id_masked']})!")
        elif diag["mode"] == "test" and diag["key_id_masked"].startswith("rzp_live_"):
            log.warning(f"[PAYMENT WARNING] Mode is TEST but Key ID appears to be a LIVE key ({diag['key_id_masked']})!")

# AI / ML Model Configuration
MODEL_PATH = os.getenv("MODEL_PATH", "models/print_time_predictor.joblib")
ML_MIN_TRAINING_RECORDS = int(os.getenv("ML_MIN_TRAINING_RECORDS", "20"))

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
