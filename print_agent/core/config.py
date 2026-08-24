import os
from dotenv import load_dotenv

# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv()


# ==========================================================
# Cloud Server Configuration
# ==========================================================

CLOUD_API_URL = os.getenv(
    "CLOUD_API_URL",
    "http://localhost:8000"
)

WEBSOCKET_URL = os.getenv(
    "WEBSOCKET_URL",
    "ws://localhost:8000/ws/printer"
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
# Heartbeat Configuration
# ==========================================================

HEARTBEAT_INTERVAL = int(
    os.getenv(
        "HEARTBEAT_INTERVAL",
        "30"
    )
)


# ==========================================================
# Retry Configuration
# ==========================================================

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
# ==========================================================
# Printer Synchronization
# ==========================================================

PRINTER_SYNC_INTERVAL = int(
    os.getenv(
        "PRINTER_SYNC_INTERVAL",
        "60"
    )
)