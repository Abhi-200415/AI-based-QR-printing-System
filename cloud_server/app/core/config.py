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

# Base URL for public API access (used for download links and callbacks)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
API_BASE_URL = os.getenv("API_BASE_URL", f"{BASE_URL}/api")
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", f"ws://localhost:8000/ws/printer")

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

# Storage Configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
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
