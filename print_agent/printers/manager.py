import requests

from core.config import (
    CLOUD_API_URL,
    AGENT_ID
)

from core.logger import (
    info,
    error
)

from printers.discovery import (
    discover_printers
)


# ==========================================================
# Build Printer Payload
# ==========================================================

def build_printer_payload(
    owner_id: str,
    printer: dict
):

    return {

        # --------------------------------------------------
        # Owner / Agent
        # --------------------------------------------------

        "owner_id": owner_id,

        "agent_id": AGENT_ID,

        # --------------------------------------------------
        # Printer Identity
        # --------------------------------------------------

        "printer_name":
            printer.get(
                "printer_name"
            ),

        "printer_model":
            printer.get(
                "printer_model"
            ),

        "printer_type":
            printer.get(
                "printer_type"
            ),

        # --------------------------------------------------
        # Physical / Virtual
        # --------------------------------------------------

        "is_physical":
            printer.get(
                "is_physical",
                False
            ),

        "is_virtual":
            printer.get(
                "is_virtual",
                False
            ),

        # --------------------------------------------------
        # Windows Availability
        # --------------------------------------------------

        "status":
            printer.get(
                "status",
                "Offline"
            ),

        "is_available":
            printer.get(
                "is_available",
                False
            ),

        # --------------------------------------------------
        # Capabilities
        # --------------------------------------------------

        "supports_bw":
            printer.get(
                "supports_bw",
                True
            ),

        "supports_color":
            printer.get(
                "supports_color",
                False
            ),

        "supports_duplex":
            printer.get(
                "supports_duplex",
                False
            ),

        "supports_a3":
            printer.get(
                "supports_a3",
                False
            ),

        "supports_legal":
            printer.get(
                "supports_legal",
                False
            ),

        # --------------------------------------------------
        # Default Printer
        # --------------------------------------------------

        "is_default":
            printer.get(
                "is_default",
                False
            )
    }


# ==========================================================
# Register / Update One Printer
# ==========================================================

def register_printer(
    owner_id: str,
    printer: dict
):

    printer_name = printer.get(
        "printer_name",
        "Unknown"
    )

    payload = build_printer_payload(
        owner_id,
        printer
    )

    try:

        response = requests.post(

            f"{CLOUD_API_URL}/printer/register",

            json=payload,

            timeout=15

        )

        if response.status_code == 200:

            info(
                f"Synchronized: "
                f"{printer_name}"
            )

            return True

        error(
            f"Synchronization failed: "
            f"{printer_name} "
            f"({response.status_code}) "
            f"{response.text}"
        )

        return False

    except Exception as e:

        error(
            f"Printer synchronization error: "
            f"{printer_name} : {e}"
        )

        return False


# ==========================================================
# Register All Printers
# ==========================================================

def register_printers(
    owner_id: str
):

    printers = discover_printers()

    if not printers:

        error(
            "No printers found."
        )

        return False

    success = 0

    for printer in printers:

        if register_printer(
            owner_id,
            printer
        ):

            success += 1

    info(
        f"{success}/{len(printers)} "
        f"printer(s) registered."
    )

    return success == len(printers)


# ==========================================================
# Update Printer Status
# ==========================================================

def update_printer_status(
    printer_id: str,
    status: str,
    current_queue: int = 0
):

    payload = {

        "status": status,

        "current_queue":
            current_queue

    }

    try:

        response = requests.put(

            f"{CLOUD_API_URL}/printer/"
            f"{printer_id}/status",

            json=payload,

            timeout=10

        )

        response.raise_for_status()

        return True

    except Exception as e:

        error(
            f"Printer status update failed: "
            f"{e}"
        )

        return False


# ==========================================================
# Get Cloud Printers For Owner
# ==========================================================

def get_cloud_printers(
    owner_id: str
):

    try:

        response = requests.get(

            f"{CLOUD_API_URL}/printer/owner/"
            f"{owner_id}",

            timeout=10

        )

        response.raise_for_status()

        return response.json()

    except Exception as e:

        error(
            f"Unable to read Cloud printers: "
            f"{e}"
        )

        return None


# ==========================================================
# Synchronize Printers
# ==========================================================

def sync_printers(
    owner_id: str
):

    info(
        "Synchronizing printers..."
    )

    # ------------------------------------------------------
    # Discover Current Windows Printers
    # ------------------------------------------------------

    printers = discover_printers()

    if not printers:

        error(
            "Printer discovery returned no "
            "printers. Skipping Cloud cleanup "
            "for safety."
        )

        return False

    # ------------------------------------------------------
    # Register / Update Current Printers
    # ------------------------------------------------------

    success = 0

    current_names = set()

    for printer in printers:

        printer_name = printer.get(
            "printer_name"
        )

        if not printer_name:

            continue

        current_names.add(
            printer_name
        )

        if register_printer(
            owner_id,
            printer
        ):

            success += 1

    # ------------------------------------------------------
    # Get Current Cloud Printers
    # ------------------------------------------------------

    cloud_printers = get_cloud_printers(
        owner_id
    )

    if cloud_printers is None:

        error(
            "Cloud printer list unavailable. "
            "Skipping removed-printer cleanup."
        )

        info(
            f"Printer synchronization "
            f"completed with errors: "
            f"{success}/{len(printers)}"
        )

        return False

    # ------------------------------------------------------
    # Detect Removed Printers
    # ------------------------------------------------------

    for cloud_printer in cloud_printers:

        cloud_name = cloud_printer.get(
            "printer_name"
        )

        printer_id = cloud_printer.get(
            "printer_id"
        )

        cloud_agent_id = cloud_printer.get(
            "agent_id"
        )

        if not printer_id:

            continue

        # --------------------------------------------------
        # Only manage this agent's printers
        # --------------------------------------------------

        if cloud_agent_id != AGENT_ID:

            continue

        # --------------------------------------------------
        # Printer no longer detected locally
        # --------------------------------------------------

        if cloud_name not in current_names:

            info(
                f"Printer no longer detected: "
                f"{cloud_name}"
            )

            update_printer_status(

                printer_id,

                "Offline",

                0

            )

    # ------------------------------------------------------
    # Summary
    # ------------------------------------------------------

    info(
        f"Printer synchronization complete: "
        f"{success}/{len(printers)}"
    )

    return success == len(printers)