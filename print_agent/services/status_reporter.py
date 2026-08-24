import requests

from core.config import CLOUD_API_URL

from core.logger import (
    info,
    error
)


# ==========================================================
# Send Job Status
# ==========================================================

def send_status(
    job_id: str,
    status: str,
    message: str = "",
    actual_seconds: int = None
):

    status_map = {
        "PRINTING": "Printing",
        "COMPLETED": "Completed",
        "FAILED": "Failed",
        "QUEUED": "Queued",
        "ASSIGNED": "Assigned",
        "CANCELLED": "Cancelled",
        "PENDING": "Pending"
    }

    cloud_status = status_map.get(
        status,
        status
    )

    params = {
        "status": cloud_status,
        "message": message
    }

    if actual_seconds is not None:

        params["actual_seconds"] = actual_seconds

    try:

        response = requests.put(

            f"{CLOUD_API_URL}/jobs/{job_id}/status",

            params=params,

            timeout=10

        )

        response.raise_for_status()

        info(
            f"{job_id} -> {cloud_status}"
        )

        if actual_seconds is not None:

            info(
                f"{job_id} -> Actual print time: "
                f"{actual_seconds} seconds"
            )

        return True

    except Exception as e:

        error(
            f"Status update failed : {e}"
        )

        return False
# ==========================================================
# Job Started
# ==========================================================

def report_job_started(
    job_id: str
):

    return send_status(

        job_id,

        "PRINTING"

    )


# ==========================================================
# Job Completed
# ==========================================================

def report_job_completed(
    job_id: str,
    actual_seconds: int
):

    return send_status(

        job_id,

        "COMPLETED",

        "Printing completed successfully.",

        actual_seconds

    )


# ==========================================================
# Job Failed
# ==========================================================

def report_job_failed(
    job_id: str,
    reason: str
):

    return send_status(

        job_id,

        "FAILED",

        reason

    )


# ==========================================================
# Printer Online
# ==========================================================

def report_printer_online(
    printer_id: str
):

    payload = {

        "status": "ONLINE"

    }

    try:

        response = requests.put(

            f"{CLOUD_API_URL}/printer/{printer_id}/status",

            json=payload,

            timeout=10

        )

        response.raise_for_status()

        info(
            f"Printer {printer_id} ONLINE"
        )

        return True

    except Exception as e:

        error(
            str(e)
        )

        return False


# ==========================================================
# Printer Offline
# ==========================================================

def report_printer_offline(
    printer_id: str
):

    payload = {

        "status": "OFFLINE"

    }

    try:

        response = requests.put(

            f"{CLOUD_API_URL}/printer/{printer_id}/status",

            json=payload,

            timeout=10

        )

        response.raise_for_status()

        info(
            f"Printer {printer_id} OFFLINE"
        )

        return True

    except Exception as e:

        error(
            str(e)
        )

        return False