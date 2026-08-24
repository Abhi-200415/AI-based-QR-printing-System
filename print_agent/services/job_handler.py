import time

from core.logger import (
    info,
    error
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
# Handle Print Job
# ==========================================================

def handle_job(job: dict):

    file_path = None

    try:

        info(
            f"Received Job : {job['job_id']}"
        )
        info(
            f"Received Job Data: {job}"
        )

        # --------------------------------------
        # Download
        # --------------------------------------

        file_path = download_file(job)

        if not verify_download(file_path):

            raise Exception(
                "Download verification failed."
            )

        # --------------------------------------
        # Validate File
        # --------------------------------------

        if not validate_file(file_path):

            raise Exception(
                "File validation failed."
            )

        job["file_path"] = file_path

        # --------------------------------------
        # Notify Cloud - Printing Started
        # --------------------------------------

        report_job_started(
            job["job_id"]
        )

        # --------------------------------------
        # Print
        # --------------------------------------

        info(
            "Starting print execution..."
        )

        print_start_time = time.time()

        success = execute_print_job(
            job
        )

        actual_seconds = int(
            time.time() - print_start_time
        )

        info(
            f"Actual print execution time: "
            f"{actual_seconds} seconds"
        )

        if not success:

            raise Exception(
                "Printing failed."
            )

        # --------------------------------------
        # Notify Cloud - Printing Completed
        # --------------------------------------

        report_job_completed(

            job["job_id"],

            actual_seconds

        )

        # --------------------------------------
        # Secure Delete
        # --------------------------------------

        secure_delete(
            file_path
        )

        info(
            f"Job Completed : {job['job_id']}"
        )

        return True

    except Exception as e:

        error(
            str(e)
        )

        report_job_failed(

            job["job_id"],

            str(e)

        )

        # --------------------------------------
        # Cleanup On Failure
        # --------------------------------------

        if file_path:

            secure_delete(
                file_path
            )

        return False