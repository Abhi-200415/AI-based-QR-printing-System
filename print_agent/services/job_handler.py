import time
import os
from typing import List, Dict, Any

from core.logger import (
    info,
    error,
    warn
)
from services.downloader import (
    download_file,
    verify_download
)
from printers.advanced_executor import (
    execute_print_job
)
from services.status_reporter import (
    report_job_started,
    report_job_completed,
    report_job_failed
)
from services.cleanup import (
    secure_delete
)
from services.file_validator import (
    validate_file
)


# ==========================================================
# Handle Multi-File / Single-File Print Job
# ==========================================================

def handle_job(job: dict) -> bool:
    """
    Executes a print job containing one or more files.
    Downloads, validates, applies per-file print settings, prints, and cleans up.
    """
    downloaded_files: List[str] = []
    job_id = job.get("job_id")

    try:
        info(f"Processing Print Job: {job_id}")

        # --------------------------------------
        # Determine files to process
        # --------------------------------------
        files = job.get("files")
        if not files:
            # Single file payload fallback
            files = [{
                "file_id": job.get("file_id"),
                "download_url": job.get("download_url"),
                "stored_filename": job.get("stored_filename"),
                "file_type": job.get("file_type"),
                "page_count": job.get("page_count", 1),
                "copies": job.get("copies", 1),
                "paper_size": job.get("paper_size", "A4"),
                "orientation": job.get("orientation", "PORTRAIT"),
                "duplex": job.get("duplex", False),
                "print_type": job.get("print_type", "BW"),
                "color_mode": job.get("color_mode", "AUTO"),
                "page_ranges": job.get("page_ranges")
            }]

        total_files = len(files)
        info(f"Job {job_id} contains {total_files} file(s) to print.")

        # --------------------------------------
        # Notify Cloud: Printing Started
        # --------------------------------------
        report_job_started(job_id)
        start_time = time.time()

        # --------------------------------------
        # Process each file sequentially
        # --------------------------------------
        for idx, file_info in enumerate(files, start=1):
            info(f"Downloading file {idx}/{total_files} ({file_info.get('stored_filename')})...")

            file_download_payload = {
                "download_url": file_info.get("download_url"),
                "stored_filename": file_info.get("stored_filename")
            }

            file_path = download_file(file_download_payload)
            if not file_path or not verify_download(file_path):
                raise Exception(f"Download verification failed for file {idx} ({file_info.get('stored_filename')})")

            downloaded_files.append(file_path)

            # Validate file format and integrity
            if not validate_file(file_path):
                raise Exception(f"Validation failed for file {idx} ({file_info.get('stored_filename')})")

            # Prepare print execution payload for this file
            file_print_job = {
                "job_id": job_id,
                "file_id": file_info.get("file_id"),
                "file_path": file_path,
                "printer_name": job.get("printer_name"),
                "copies": file_info.get("copies", 1),
                "paper_size": file_info.get("paper_size", "A4"),
                "orientation": file_info.get("orientation", "PORTRAIT"),
                "duplex": file_info.get("duplex", False),
                "print_type": file_info.get("print_type", "BW"),
                "color_mode": file_info.get("color_mode", "AUTO"),
                "page_ranges": file_info.get("page_ranges")
            }

            info(f"Printing file {idx}/{total_files} on '{job.get('printer_name')}'...")
            print_success = execute_print_job(file_print_job)

            if not print_success:
                raise Exception(f"Physical printing failed for file {idx} ({file_info.get('stored_filename')})")

            # Clean up printed file immediately
            secure_delete(file_path)
            downloaded_files.remove(file_path)

        actual_duration = int(time.time() - start_time)
        info(f"All {total_files} files printed successfully for Job {job_id} in {actual_duration}s.")

        # Notify Cloud: Printing Completed
        report_job_completed(job_id, actual_duration)
        return True

    except Exception as e:
        err_msg = str(e)
        error(f"Job {job_id} failed: {err_msg}")
        report_job_failed(job_id, err_msg)

        # Clean up any leftover downloaded files
        for fp in downloaded_files:
            if fp and os.path.exists(fp):
                secure_delete(fp)

        return False