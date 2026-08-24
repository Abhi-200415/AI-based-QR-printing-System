from datetime import datetime

from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    Printer,
    JobStatus,
)


# ==========================================================
# AI Waiting Time Prediction
# ==========================================================

def estimate_waiting_time(job: ActiveJob) -> int:
    """
    Estimate waiting time in seconds
    based on queue position.
    """

    AVERAGE_PRINT_TIME = 45

    if job.queue_position is None:
        return 0

    return job.queue_position * AVERAGE_PRINT_TIME


# ==========================================================
# AI Printer Load
# ==========================================================

def get_printer_load(
    printer: Printer
) -> str:

    queue = printer.current_queue or 0

    if queue <= 2:
        return "LOW"

    if queue <= 5:
        return "MEDIUM"

    return "HIGH"


# ==========================================================
# AI Recommendation
# ==========================================================

def get_ai_recommendation(
    job: ActiveJob
) -> str:

    estimated_seconds = (
        job.estimated_seconds or 0
    )

    if estimated_seconds < 60:
        return "Printing will start shortly."

    if estimated_seconds < 300:
        return "Normal waiting time."

    return (
        "Queue is busy. "
        "Consider another compatible printer."
    )


# ==========================================================
# Update AI Predictions
# ==========================================================

def update_queue_predictions(
    printer_id,
    db: Session
):

    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == printer_id,
            ActiveJob.status == JobStatus.QUEUED
        )
        .order_by(
            ActiveJob.queue_position.asc()
        )
        .all()
    )

    # ------------------------------------------------------
    # Rebuild queue positions
    # ------------------------------------------------------

    for position, job in enumerate(
        jobs,
        start=1
    ):

        job.queue_position = position

        job.estimated_seconds = (
            position * 45
        )

    db.commit()


# ==========================================================
# Add Job To Queue
# ==========================================================

def add_job_to_queue(
    job_id,
    db: Session
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        return None

    # ------------------------------------------------------
    # Job must have a printer
    # ------------------------------------------------------

    if not job.assigned_printer_id:
        return None

    # ------------------------------------------------------
    # Prevent duplicate queue insertion
    # ------------------------------------------------------

    if job.status == JobStatus.QUEUED:

        return job

    # ------------------------------------------------------
    # Find assigned printer
    # ------------------------------------------------------

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id ==
            job.assigned_printer_id
        )
        .first()
    )

    if not printer:
        return None

    # ------------------------------------------------------
    # Find current queued jobs
    # ------------------------------------------------------

    queue_count = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id ==
            job.assigned_printer_id,

            ActiveJob.status ==
            JobStatus.QUEUED
        )
        .count()
    )

    # ------------------------------------------------------
    # Assign queue position
    # ------------------------------------------------------

    job.queue_position = (
        queue_count + 1
    )

    job.status = JobStatus.QUEUED

    job.queued_at = datetime.utcnow()

    job.estimated_seconds = (
        estimate_waiting_time(job)
    )

    # ------------------------------------------------------
    # Synchronize printer queue count
    # ------------------------------------------------------

    printer.current_queue = (
        queue_count + 1
    )

    db.commit()

    # ------------------------------------------------------
    # Recalculate queue predictions
    # ------------------------------------------------------

    update_queue_predictions(
        printer.printer_id,
        db
    )

    db.refresh(job)

    return job


# ==========================================================
# Remove Job From Queue
# ==========================================================

def remove_job_from_queue(
    job_id,
    db: Session
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        return None

    printer_id = (
        job.assigned_printer_id
    )

    # ------------------------------------------------------
    # Find printer
    # ------------------------------------------------------

    printer = None

    if printer_id:

        printer = (
            db.query(Printer)
            .filter(
                Printer.printer_id ==
                printer_id
            )
            .first()
        )

    # ------------------------------------------------------
    # Remove job from active queue
    # ------------------------------------------------------

    job.queue_position = None

    job.estimated_seconds = 0

    # ------------------------------------------------------
    # Synchronize printer queue count
    # ------------------------------------------------------

    if printer:

        remaining_count = (
            db.query(ActiveJob)
            .filter(
                ActiveJob.assigned_printer_id ==
                printer_id,

                ActiveJob.status ==
                JobStatus.QUEUED,

                ActiveJob.job_id != job.job_id
            )
            .count()
        )

        printer.current_queue = (
            remaining_count
        )

    db.commit()

    # ------------------------------------------------------
    # Rebuild remaining queue
    # ------------------------------------------------------

    if printer_id:

        update_queue_predictions(
            printer_id,
            db
        )

    db.refresh(job)

    return job


# ==========================================================
# Get Queue
# ==========================================================

def get_queue(
    printer_id,
    db: Session
):

    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id ==
            printer_id,

            ActiveJob.status ==
            JobStatus.QUEUED
        )
        .order_by(
            ActiveJob.queue_position.asc()
        )
        .all()
    )

    return jobs


# ==========================================================
# Get Single Queue Job
# ==========================================================

def get_queue_job(
    job_id,
    db: Session
):

    return (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )


# ==========================================================
# Cancel Queue Job
# ==========================================================

def cancel_queue_job(
    job_id,
    db: Session
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        return None

    printer_id = (
        job.assigned_printer_id
    )

    # ------------------------------------------------------
    # Cancel the job
    # ------------------------------------------------------

    job.status = JobStatus.CANCELLED

    # ------------------------------------------------------
    # Remove from queue
    # ------------------------------------------------------

    remove_job_from_queue(
        job_id,
        db
    )

    return job


# ==========================================================
# Complete Queue Job
# ==========================================================

def complete_queue_job(
    job_id,
    db: Session
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        return None

    # ------------------------------------------------------
    # Complete job
    # ------------------------------------------------------

    job.status = JobStatus.COMPLETED

    # ------------------------------------------------------
    # Remove from queue
    # ------------------------------------------------------

    remove_job_from_queue(
        job_id,
        db
    )

    # ------------------------------------------------------
    # Update printer statistics
    # ------------------------------------------------------

    printer_id = (
        job.assigned_printer_id
    )

    if printer_id:

        printer = (
            db.query(Printer)
            .filter(
                Printer.printer_id ==
                printer_id
            )
            .first()
        )

        if printer:

            printer.total_jobs_printed = (
                printer.total_jobs_printed or 0
            ) + 1

            db.commit()

    db.refresh(job)

    return job


# ==========================================================
# Queue Dashboard
# ==========================================================

def get_queue_dashboard(
    printer_id,
    db: Session
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:
        return None

    jobs = get_queue(
        printer_id,
        db
    )

    return {

        "printer_name":
            printer.printer_name,

        "printer_status":
            printer.status.value,

        "queue_length":
            printer.current_queue or 0,

        "printer_load":
            get_printer_load(printer),

        "queued_jobs":
            jobs
    }
