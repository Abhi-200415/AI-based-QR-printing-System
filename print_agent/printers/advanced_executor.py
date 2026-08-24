import os
import subprocess
import time

from core.logger import (
    info,
    error
)

from printers.devmode import (
    configure_printer,
    restore_devmode,
    close_printer
)

from printers.print_monitor import (
    monitor_print
)

from services.printer_availability import (
    verify_physical_printer
)


# ==========================================================
# Paths
# ==========================================================

# advanced_executor.py
#     â†“
# PRINT_AGENT/
#     â†“
# tools/
#     â†“
# SumatraPDF.exe

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

SUMATRA_PATH = os.path.join(
    BASE_DIR,
    "tools",
    "SumatraPDF.exe"
)


# ==========================================================
# Execute Advanced Print Job
# ==========================================================

def execute_print_job(job):

    handle = None
    backup = None
    printer_info = None
    devmode_applied = False
    process = None

    try:

        # --------------------------------------------------
        # Read Job Information
        # --------------------------------------------------

        printer_name = job["printer_name"]

        file_path = job["file_path"]

        # --------------------------------------------------
        # FINAL PHYSICAL PRINTER CHECK
        # --------------------------------------------------

        if not verify_physical_printer(
            printer_name
        ):

            raise Exception(
                f"Printer is not physically available: "
                f"{printer_name}"
            )

        info(
            f"Final printer availability check passed: "
            f"{printer_name}"
        )

        page_ranges = job.get(
            "page_ranges"
        )

        # --------------------------------------------------
        # Validate PDF
        # --------------------------------------------------

        if not os.path.exists(file_path):

            raise Exception(
                f"File not found: {file_path}"
            )

        # --------------------------------------------------
        # Validate SumatraPDF
        # --------------------------------------------------

        if not os.path.exists(SUMATRA_PATH):

            raise Exception(
                f"SumatraPDF.exe not found: "
                f"{SUMATRA_PATH}"
            )

        info(
            f"Printer: {printer_name}"
        )

        info(
            f"File: {file_path}"
        )

        info(
            f"Sumatra path: {SUMATRA_PATH}"
        )

        # --------------------------------------------------
        # Try Printer Configuration
        # --------------------------------------------------

        try:

            handle, printer_info, backup = (
                configure_printer(
                    printer_name,
                    job
                )
            )

            devmode_applied = True

            info(
                "Printer configured successfully."
            )

        except Exception as e:

            error(
                f"Printer configuration skipped: {e}"
            )

            info(
                "Continuing with printer default settings."
            )

            handle = None
            printer_info = None
            backup = None

        # --------------------------------------------------
        # Build SumatraPDF Command
        # --------------------------------------------------

        command = [

            SUMATRA_PATH,

            "-silent",

            "-print-to",

            printer_name

        ]

        # --------------------------------------------------
        # Page Range
        # --------------------------------------------------

        if page_ranges:

            command.extend([

                "-print-settings",

                page_ranges

            ])

        # --------------------------------------------------
        # PDF File
        # --------------------------------------------------

        command.append(
            file_path
        )

        # --------------------------------------------------
        # Log Exact Command
        # --------------------------------------------------

        info(
            "Starting SumatraPDF..."
        )

        info(
            f"Sumatra command: {command}"
        )

        # --------------------------------------------------
        # Launch SumatraPDF
        #
        # IMPORTANT:
        # Do NOT use subprocess.run().
        #
        # SumatraPDF may remain open while Windows is
        # communicating with the printer.
        #
        # The Windows print queue is the real source
        # of truth for print completion.
        # --------------------------------------------------

        process = subprocess.Popen(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            cwd=BASE_DIR

        )

        info(
            f"Sumatra process started. "
            f"PID: {process.pid}"
        )

        # --------------------------------------------------
        # Give Sumatra a short moment to submit the job
        # --------------------------------------------------

        time.sleep(2)

        # --------------------------------------------------
        # Check whether Sumatra exited immediately
        # --------------------------------------------------

        return_code = process.poll()

        if return_code is not None:

            stdout, stderr = (
                process.communicate()
            )

            info(
                f"Sumatra exited early. "
                f"Return code: {return_code}"
            )

            info(
                f"Sumatra stdout: {stdout}"
            )

            error(
                f"Sumatra stderr: {stderr}"
            )

            if return_code != 0:

                raise Exception(
                    "SumatraPDF failed to submit "
                    "the print job."
                )

        else:

            info(
                "SumatraPDF is still running."
            )

            info(
                "Continuing with Windows "
                "Print Queue monitoring."
            )

        # --------------------------------------------------
        # Monitor Windows Print Queue
        # --------------------------------------------------

        info(
            "Waiting for Windows Print Queue..."
        )

        completed = monitor_print(
            printer_name
        )

        if not completed:

            raise Exception(
                "Printing failed or timed out."
            )

        # --------------------------------------------------
        # Print Successful
        # --------------------------------------------------

        info(
            "Print job completed successfully."
        )

        # --------------------------------------------------
        # Cleanly close Sumatra if still running
        # --------------------------------------------------

        if process is not None:

            if process.poll() is None:

                info(
                    "Closing SumatraPDF process..."
                )

                try:

                    process.terminate()

                    process.wait(
                        timeout=5
                    )

                except Exception:

                    try:

                        process.kill()

                    except Exception:

                        pass

            else:

                try:

                    stdout, stderr = (
                        process.communicate(
                            timeout=2
                        )
                    )

                    info(
                        f"Final Sumatra stdout: "
                        f"{stdout}"
                    )

                    if stderr:

                        error(
                            f"Final Sumatra stderr: "
                            f"{stderr}"
                        )

                except Exception:

                    pass

        return True

    except Exception as e:

        error(
            f"Print execution failed: {e}"
        )

        # --------------------------------------------------
        # Clean up Sumatra process after failure
        # --------------------------------------------------

        if process is not None:

            try:

                if process.poll() is None:

                    process.terminate()

                    process.wait(
                        timeout=3
                    )

            except Exception:

                try:

                    process.kill()

                except Exception:

                    pass

        return False

    finally:

        # --------------------------------------------------
        # Restore Printer Settings
        # --------------------------------------------------

        if devmode_applied and handle:

            try:

                restore_devmode(

                    handle,

                    printer_info,

                    backup

                )

                info(
                    "Printer settings restored."
                )

            except Exception as e:

                error(
                    f"Printer settings restoration failed: {e}"
                )

            finally:

                close_printer(
                    handle
                )
