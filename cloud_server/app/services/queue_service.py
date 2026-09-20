from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    Printer,
    JobStatus,
)
from app.utils.logger import logger


# ==========================================================
# Waiting Time Estimation
# ==========================================================

def estimate_waiting_time(job: ActiveJob) -> int:
    AVERAGE_PRINT_TIME = 45
    if job.queue_position is None:
        return 0
    return job.queue_position * AVERAGE_PRINT_TIME


def get_printer_load(printer: Printer) -> str:
    queue = printer.current_queue or 0
    if queue <= 2:
        return "LOW"
    if queue <= 5:
        return "MEDIUM"
    return "HIGH"


def get_ai_recommendation(job: ActiveJob) -> str:
    estimated_seconds = job.estimated_seconds or 0
    if estimated_seconds < 60:
        return "Printing will start shortly."
    if estimated_seconds < 300:
        return "Normal waiting time."
    return "Queue is busy. Consider another compatible printer."


# ==========================================================
# Update Queue Positions and ETAs
# ==========================================================

def update_queue_predictions(printer_id, db: Session):
    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == printer_id,
            ActiveJob.status == JobStatus.QUEUED
        )
        .order_by(ActiveJob.queue_position.asc())
        .all()
    )

    for position, job in enumerate(jobs, start=1):
        job.queue_position = position
        job.estimated_seconds = position * 45

    db.commit()


# ==========================================================
# Add Job To Queue
# ==========================================================

def add_job_to_queue(
    job_id,
    db: Session
) -> Optional[ActiveJob]:
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job or not job.assigned_printer_id:
        return None

    # Prevent requeuing already completed/failed/cancelled jobs
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        return job

    # If already queued, return job
    if job.status == JobStatus.QUEUED:
        return job

    printer = (
        db.query(Printer)
        .filter(Printer.printer_id == job.assigned_printer_id)
        .first()
    )

    if not printer:
        return None

    # Count current queued jobs for this printer
    queue_count = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == job.assigned_printer_id,
            ActiveJob.status == JobStatus.QUEUED
        )
        .count()
    )

    job.queue_position = queue_count + 1
    job.status = JobStatus.QUEUED
    job.queued_at = datetime.utcnow()
    job.estimated_seconds = estimate_waiting_time(job)

    # Synchronize printer queue count
    printer.current_queue = queue_count + 1
    db.commit()

    update_queue_predictions(printer.printer_id, db)
    db.refresh(job)

    logger.info(f"Job {job.job_id} added to queue at position {job.queue_position} for printer {printer.printer_name}")
    return job


# ==========================================================
# Remove Job From Queue
# ==========================================================

def remove_job_from_queue(
    job_id,
    db: Session
) -> Optional[ActiveJob]:
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        return None

    printer_id = job.assigned_printer_id
    job.queue_position = None
    job.estimated_seconds = 0

    if printer_id:
        printer = db.query(Printer).filter(Printer.printer_id == printer_id).first()
        if printer:
            remaining = (
                db.query(ActiveJob)
                .filter(
                    ActiveJob.assigned_printer_id == printer_id,
                    ActiveJob.status == JobStatus.QUEUED,
                    ActiveJob.job_id != job.job_id
                )
                .count()
            )
            printer.current_queue = remaining

        db.commit()
        update_queue_predictions(printer_id, db)

    db.refresh(job)
    return job


# ==========================================================
# Cancel Queue Job
# ==========================================================

def cancel_queue_job(
    job_id,
    db: Session
) -> Optional[ActiveJob]:
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        return None

    if job.status == JobStatus.CANCELLED:
        return job

    job.status = JobStatus.CANCELLED
    remove_job_from_queue(job_id, db)
    return job


# ==========================================================
# Complete Queue Job
# ==========================================================

def complete_queue_job(
    job_id,
    db: Session
) -> Optional[ActiveJob]:
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        return None

    job.status = JobStatus.COMPLETED
    remove_job_from_queue(job_id, db)

    printer_id = job.assigned_printer_id
    if printer_id:
        printer = db.query(Printer).filter(Printer.printer_id == printer_id).first()
        if printer:
            printer.total_jobs_printed = (printer.total_jobs_printed or 0) + 1
            db.commit()

    db.refresh(job)
    return job


# ==========================================================
# Get Queues
# ==========================================================

def get_queue(
    printer_id,
    db: Session
) -> List[ActiveJob]:
    return (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == printer_id,
            ActiveJob.status == JobStatus.QUEUED
        )
        .order_by(ActiveJob.queue_position.asc())
        .all()
    )


def get_all_queue_jobs(
    db: Session
) -> List[ActiveJob]:
    return (
        db.query(ActiveJob)
        .filter(ActiveJob.status == JobStatus.QUEUED)
        .order_by(ActiveJob.queued_at.asc())
        .all()
    )


def get_queue_job(
    job_id,
    db: Session
) -> Optional[ActiveJob]:
    return (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )
