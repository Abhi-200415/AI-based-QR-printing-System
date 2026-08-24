import time
import win32print

from core.logger import info, error


# ==========================================================
# Open Printer
# ==========================================================

def open_printer(printer_name):

    return win32print.OpenPrinter(
        printer_name
    )


# ==========================================================
# Close Printer
# ==========================================================

def close_printer(handle):

    try:
        win32print.ClosePrinter(handle)
    except Exception:
        pass


# ==========================================================
# Get Queue
# ==========================================================

def get_jobs(handle):

    try:
        return win32print.EnumJobs(
            handle,
            0,
            100,
            1
        )
    except Exception:
        return []


# ==========================================================
# Monitor Print Queue
# ==========================================================

def monitor_print(
    printer_name,
    timeout=120,
    settle_time=3
):

    handle = None

    try:

        handle = open_printer(printer_name)

        initial_jobs = len(get_jobs(handle))
        info(
            f"Initial printer queue jobs: {initial_jobs}"
        )

        deadline = time.time() + timeout
        seen_job = initial_jobs > 0

        while time.time() < deadline:

            jobs = get_jobs(handle)
            count = len(jobs)

            if count > initial_jobs:
                seen_job = True

            if count == 0 and (
                seen_job or initial_jobs == 0
            ):
                time.sleep(settle_time)

                final_jobs = len(get_jobs(handle))

                if final_jobs == 0:
                    info(
                        "Printer queue is clear."
                    )
                    return True

            time.sleep(1)

        error(
            f"Print monitoring timed out for {printer_name}"
        )
        return False

    except Exception as e:

        error(
            f"Print monitoring failed : {e}"
        )
        return False

    finally:

        if handle:
            close_printer(handle)
