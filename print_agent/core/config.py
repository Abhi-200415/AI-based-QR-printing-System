import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from PRINT_AGENT directory or parent
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# ==========================================================
# Cloud Server Configuration
# ==========================================================

CLOUD_API_URL = os.getenv(
    "CLOUD_API_URL",
    "http://localhost:8000"
).rstrip("/")

# WebSocket URL: derives from CLOUD_API_URL if not explicitly provided
default_ws = CLOUD_API_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws/printer"
WEBSOCKET_URL = os.getenv(
    "WEBSOCKET_URL",
    default_ws
)

# ==========================================================
# Agent Configuration
# ==========================================================

AGENT_ID = os.getenv(
    "AGENT_ID",
    "agent_001"
)

SHOP_ID = os.getenv(
    "SHOP_ID",
    ""
)

# ==========================================================
# Download Configuration
# ==========================================================

DOWNLOAD_FOLDER = os.getenv(
    "DOWNLOAD_FOLDER",
    "downloads"
)

# ==========================================================
# Heartbeat & Timing Configuration
# ==========================================================

HEARTBEAT_INTERVAL = int(
    os.getenv(
        "HEARTBEAT_INTERVAL",
        "30"
    )
)

MAX_RETRY = int(
    os.getenv(
        "MAX_RETRY",
        "3"
    )
)

RETRY_DELAY = int(
    os.getenv(
        "RETRY_DELAY",
        "5"
    )
)

PRINTER_SYNC_INTERVAL = int(
    os.getenv(
        "PRINTER_SYNC_INTERVAL",
        "60"
    )
)