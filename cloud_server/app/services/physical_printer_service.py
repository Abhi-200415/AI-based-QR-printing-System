import sys
from app.utils.logger import logger


def check_printer_available(
    printer_name: str,
    printer_type: str = "PHYSICAL"
) -> bool:
    """
    Physical printer availability is managed by the Windows Print Agent.
    The cloud server relies on the database state synced via Agent heartbeats.
    This helper provides a safe fallback that never crashes the cloud server.
    """
    # In cloud environment, trust registered online state
    return True
