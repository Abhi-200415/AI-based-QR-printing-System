from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    JobFile,
    Printer,
    JobStatus,
    PrintType
)


# ==========================================================
# Baseline Printing Time
# ==========================================================

BASE_SECONDS_PER_PAGE = 4

COLOR_MULTIPLIER = 1.35

DUPLEX_MULTIPLIER = 1.15

COPIES_SETUP_SECONDS = 3


# ==========================================================
# Estimate File Printing Time
# ==========================================================

def estimate_file_seconds(
    file: JobFile,
    printer: Printer
) -> float:

    pages = max(
        file.page_count or 1,
        1
    )

    copies = max(
        file.copies or 1,
        1
    )

    seconds_per_page = BASE_SECONDS_PER_PAGE

    # ------------------------------------------------------
    # Color generally takes longer
    # ------------------------------------------------------

    if file.print_type in (
        PrintType.COLOR,
        PrintType.MIXED
    ):

        seconds_per_page *= COLOR_MULTIPLIER

    # ------------------------------------------------------
    # Duplex overhead
    # ------------------------------------------------------

    if file.duplex:

        seconds_per_page *= DUPLEX_MULTIPLIER

    # ------------------------------------------------------
    # Printer historical speed adjustment
    #
    # More completed jobs gives us a small confidence
    # adjustment while keeping the baseline stable.
    # ------------------------------------------------------

    completed_jobs = (
        printer.total_jobs_printed or 0
    )

    if completed_jobs >= 100:

        seconds_per_page *= 0.90

    elif completed_jobs >= 50:

        seconds_per_page *= 0.95

    # ------------------------------------------------------
    # Calculate
    # ------------------------------------------------------

    printing_time = (
        pages
        * copies
        * seconds_per_page
    )

    setup_time = (
        max(copies - 1, 0)
        * COPIES_SETUP_SECONDS
    )

    return printing_time + setup_time


# ==========================================================
# Estimate Job Printing Time
# ==========================================================

def estimate_job_seconds(
    job: ActiveJob,
    printer: Printer
) -> float:

    total = 0.0

    for file in job.files:

        total += estimate_file_seconds(
            file,
            printer
        )

    return total


# ==========================================================
# Estimate Existing Queue Workload
# ==========================================================

def estimate_printer_queue_seconds(
    printer: Printer,
    db: Session
) -> float:

    queued_jobs = (

        db.query(ActiveJob)

        .filter(

            ActiveJob.assigned_printer_id
            == printer.printer_id,

            ActiveJob.status
            == JobStatus.QUEUED

        )

        .order_by(

            ActiveJob.queue_position.asc()

        )

        .all()

    )

    total = 0.0

    for queued_job in queued_jobs:

        total += estimate_job_seconds(
            queued_job,
            printer
        )

    return total


# ==========================================================
# Predict Completion Time
# ==========================================================

def predict_completion_seconds(
    job: ActiveJob,
    printer: Printer,
    db: Session
) -> float:

    queue_seconds = (
        estimate_printer_queue_seconds(
            printer,
            db
        )
    )

    job_seconds = (
        estimate_job_seconds(
            job,
            printer
        )
    )

    return (
        queue_seconds
        + job_seconds
    )