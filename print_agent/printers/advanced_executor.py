import os
import subprocess
import time

from core.logger import (
    info,
    error,
    warn
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
    temp_converted_file = None

    try:

        # --------------------------------------------------
        # Read Job Information
        # --------------------------------------------------

        printer_name = job["printer_name"]
        file_path = os.path.abspath(job["file_path"])

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
        # Validate File
        # --------------------------------------------------

        if not os.path.exists(file_path):

            raise Exception(
                f"File not found: {file_path}"
            )

        ext = os.path.splitext(file_path)[1].lower()

        # --------------------------------------------------
        # PRIMARY ENGINE: Microsoft Word A4 Engine
        # Microsoft Word formats and spools each page into an exact
        # 210 x 297 mm A4 layout using Office OpenXPS. This guarantees
        # 100% full-page output on all printers (including HP PCLmS Class Driver).
        # --------------------------------------------------
        copies = int(job.get("copies", 1))
        is_color = (job.get("print_type") or "").upper() == "COLOR"
        effective_orientation = job.get("orientation", "PORTRAIT")

        # --------------------------------------------------
        # Direct Native Vector Print for PDFs (Official HP Driver)
        # Directly scales the PDF vectors to fit the full A4 printable area
        # without converting to images or adding Word paragraph margins.
        # --------------------------------------------------
        if ext == ".pdf":
            try:
                info(f"Using Direct PDF Engine with fit scaling for crisp A4 output: {file_path}")
                pdf_cmd = [SUMATRA_PATH, "-silent", "-print-to", printer_name]
                pdf_settings = ["fit", "paper=A4"]
                if effective_orientation and effective_orientation.upper() in ["PORTRAIT", "LANDSCAPE"]:
                    pdf_settings.append(effective_orientation.lower())
                if page_ranges:
                    pdf_settings.append(str(page_ranges))
                pdf_cmd.extend(["-print-settings", ",".join(pdf_settings), file_path])

                info(f"Submitting direct PDF print command: {pdf_cmd}")
                for copy_idx in range(copies):
                    p = subprocess.Popen(pdf_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR)
                    time.sleep(2)
                    if not monitor_print(printer_name):
                        raise Exception("Print queue monitoring reported failure.")

                info("Direct vector PDF print completed successfully.")
                return True
            except Exception as pdf_err:
                warn(f"Direct PDF engine encountered an issue ({pdf_err}). Falling back to Word A4 engine...")

        # --------------------------------------------------
        # Word A4 Engine for DOCX and Fallback
        # --------------------------------------------------
        if ext in [".docx", ".doc", ".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            try:
                from printers.word_a4_executor import print_via_word_a4
                info(f"Using Microsoft Word A4 Engine for guaranteed full-page A4 output: {file_path}")
                if print_via_word_a4(
                    printer_name=printer_name,
                    file_path=file_path,
                    copies=copies,
                    orientation=effective_orientation,
                    page_ranges=page_ranges
                ):
                    return True
            except Exception as word_err:
                warn(f"Microsoft Word A4 Engine error ({word_err}). Falling back to Native GDI...")

        # --------------------------------------------------
        # Secondary: Native Windows GDI Engine
        # --------------------------------------------------
        try:
            if ext == ".pdf":
                info(f"Using Native Windows GDI engine for A4 PDF printing: {file_path}")
                from printers.native_gdi_executor import print_pdf_native_gdi
                if print_pdf_native_gdi(
                    printer_name=printer_name,
                    pdf_path=file_path,
                    copies=copies,
                    orientation=effective_orientation,
                    page_ranges=page_ranges,
                    color=is_color
                ):
                    info("Waiting for Windows Print Queue...")
                    completed = monitor_print(printer_name)
                    if completed:
                        info("Print job completed successfully via Native GDI engine.")
                        return True
                    else:
                        raise Exception("Print queue monitoring reported failure.")

            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
                info(f"Using Native Windows GDI engine for A4 Image printing: {file_path}")
                from printers.native_gdi_executor import print_image_native_gdi
                if print_image_native_gdi(
                    printer_name=printer_name,
                    image_path=file_path,
                    copies=copies,
                    orientation=effective_orientation,
                    color=is_color
                ):
                    info("Waiting for Windows Print Queue...")
                    completed = monitor_print(printer_name)
                    if completed:
                        info("Print job completed successfully via Native GDI engine.")
                        return True
                    else:
                        raise Exception("Print queue monitoring reported failure.")

        except Exception as gdi_err:
            warn(f"Native GDI printing encountered an issue ({gdi_err}). Falling back to SumatraPDF executor...")

        # --------------------------------------------------
        # Fallback Image Handling: Convert to Full-Size A4 PDF
        # --------------------------------------------------
        file_to_print = file_path

        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            info(f"Preparing image '{os.path.basename(file_path)}' for full-page A4 printing via Sumatra...")
            from services.image_converter import convert_image_to_printable_pdf
            paper_size = job.get("paper_size", "A4")
            req_orientation = job.get("orientation", "PORTRAIT")
            converted_pdf, eff_ori = convert_image_to_printable_pdf(
                file_path,
                paper_size=paper_size,
                orientation=req_orientation
            )
            temp_converted_file = converted_pdf
            file_to_print = converted_pdf
            effective_orientation = eff_ori

        # --------------------------------------------------
        # Fallback: SumatraPDF
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
            f"File: {file_to_print}"
        )

        info(
            f"Sumatra path: {SUMATRA_PATH}"
        )

        # --------------------------------------------------
        # Try Printer Configuration (DEVMODE)
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

            warn(
                f"Printer system DEVMODE configuration skipped ({e}); using command-level print settings."
            )

            info(
                "Continuing with command-level print settings."
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
        # Assemble Print Settings for SumatraPDF
        # (Strictly valid keywords: fit, paper=<SIZE>, portrait, landscape, duplex, color, <pages>)
        # --------------------------------------------------
        settings_parts = ["fit"]

        paper_size = (job.get("paper_size") or "A4").upper()
        settings_parts.append(f"paper={paper_size}")

        if effective_orientation and effective_orientation.upper() in ["PORTRAIT", "LANDSCAPE"]:
            settings_parts.append(effective_orientation.lower())

        if job.get("duplex"):
            settings_parts.append("duplex")

        if (job.get("print_type") or "").upper() == "COLOR":
            settings_parts.append("color")

        if page_ranges:
            settings_parts.append(str(page_ranges))

        if settings_parts:
            command.extend([
                "-print-settings",
                ",".join(settings_parts)
            ])

        # --------------------------------------------------
        # Printable File Path
        # --------------------------------------------------

        command.append(
            file_to_print
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

        copies = int(job.get("copies", 1))
        for copy_idx in range(copies):
            if copy_idx > 0:
                info(f"Submitting copy {copy_idx + 1} of {copies}...")

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

                if stdout:
                    info(
                        f"Sumatra stdout: {stdout}"
                    )

                if stderr:
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

            # Clean up process for this copy if still running
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

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

        # --------------------------------------------------
        # Clean up temporary converted full-page PDF
        # --------------------------------------------------
        if temp_converted_file and os.path.exists(temp_converted_file):
            try:
                from services.cleanup import secure_delete
                secure_delete(temp_converted_file)
            except Exception:
                try:
                    os.remove(temp_converted_file)
                except Exception:
                    pass
