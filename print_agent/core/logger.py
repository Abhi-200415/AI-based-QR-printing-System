import logging
import os

# ==========================================================
# Create Logs Directory
# ==========================================================

LOG_FOLDER = "logs"

os.makedirs(
    LOG_FOLDER,
    exist_ok=True
)

LOG_FILE = os.path.join(
    LOG_FOLDER,
    "agent.log"
)

# ==========================================================
# Logger Configuration
# ==========================================================

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(message)s",

    handlers=[

        logging.FileHandler(LOG_FILE),

        logging.StreamHandler()

    ]

)

logger = logging.getLogger("PrintAgent")


# ==========================================================
# Helper Functions
# ==========================================================

def info(message: str):

    logger.info(message)


def warning(message: str):

    logger.warning(message)


def error(message: str):

    logger.error(message)


def critical(message: str):

    logger.critical(message)