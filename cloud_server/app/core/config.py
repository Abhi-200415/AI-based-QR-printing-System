import os
from pathlib import Path
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
    _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
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
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"]

# Payment Gateway Configuration
PAYMENT_GATEWAY_PROVIDER = os.getenv("PAYMENT_GATEWAY_PROVIDER", "MANUAL")  # RAZORPAY, CASHFREE, STRIPE, MANUAL
PAYMENT_GATEWAY_KEY_ID = os.getenv("PAYMENT_GATEWAY_KEY_ID", "")
PAYMENT_GATEWAY_KEY_SECRET = os.getenv("PAYMENT_GATEWAY_KEY_SECRET", "")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")

# AI / ML Model Configuration
MODEL_PATH = os.getenv("MODEL_PATH", "models/print_time_predictor.joblib")
ML_MIN_TRAINING_RECORDS = int(os.getenv("ML_MIN_TRAINING_RECORDS", "20"))

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
