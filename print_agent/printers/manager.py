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
            info(f"Synchronized: {printer_name}")
            return True

        err_detail = response.text
        if err_detail and err_detail.strip().startswith("<"):
            err_detail = "Server temporarily unavailable / gateway error"
        error(f"Synchronization failed: {printer_name} ({response.status_code}): {err_detail[:120]}")
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
            f"{CLOUD_API_URL}/printer/owner/{owner_id}",
            timeout=25
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        error(
            f"Unable to read Cloud printers: {e}"
        )
        return None


def delete_cloud_printer(
    printer_id: str
):
    try:
        response = requests.delete(
            f"{CLOUD_API_URL}/printer/{printer_id}",
            timeout=25
        )
        return response.status_code in (200, 204)
    except Exception as e:
        error(f"Failed to delete cloud printer {printer_id}: {e}")
        return False


# ==========================================================
# Synchronize Printers
# ==========================================================

def sync_printers(
    owner_id: str
):

    info(
        "Synchronizing physical printers..."
    )

    # ------------------------------------------------------
    # Discover Current Windows Printers
    # ------------------------------------------------------

    all_printers = discover_printers()

    if not all_printers:

        error(
            "Printer discovery returned no "
            "printers. Skipping Cloud cleanup "
            "for safety."
        )

        return False

    # Filter out virtual printers (OneNote, Print to PDF, Fax, etc.)
    printers = [p for p in all_printers if not p.get("is_virtual", False)]

    if not printers:
        info("No physical printers detected (only virtual/software printers found).")

    # ------------------------------------------------------
    # Register / Update Current Physical Printers
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
    # Detect & Remove Virtual / Stale Printers from Cloud
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

        is_virt = cloud_printer.get("is_virtual", False)

        if not printer_id:

            continue

        # --------------------------------------------------
        # Only manage this agent's printers
        # --------------------------------------------------

        if cloud_agent_id != AGENT_ID:

            continue

        # --------------------------------------------------
        # Printer is virtual or no longer detected locally
        # --------------------------------------------------

        if cloud_name not in current_names or is_virt:

            info(
                f"Cleaning up virtual/stale printer from Cloud: {cloud_name}"
            )

            deleted = delete_cloud_printer(printer_id)
            if not deleted:
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
        f"{success}/{len(printers)} physical printer(s) active."
    )

    return success == len(printers)