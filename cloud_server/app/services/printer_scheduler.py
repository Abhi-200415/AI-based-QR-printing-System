from datetime import datetime
from sqlalchemy.orm import Session
from app.services.cleanup_service import cleanup_job_files
from app.database.models import (
    ActiveJob,
    Printer,
    JobStatus,
    PrinterStatus
)


# ==========================================================
# Schedule Next Job
# ==========================================================

def schedule_next_job(
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

    if printer.status != PrinterStatus.ONLINE:
        return None

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == printer_id,
            ActiveJob.status == JobStatus.QUEUED
        )
        .order_by(
            ActiveJob.priority.desc(),
            ActiveJob.created_at.asc()
        )
        .first()
    )

    if not job:
        return None

    job.status = JobStatus.PRINTING
    job.started_at = datetime.utcnow()

    printer.status = PrinterStatus.BUSY

    db.commit()

    db.refresh(job)

    return job


# ==========================================================
# Complete Current Job
# ==========================================================

def complete_job(
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

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == job.assigned_printer_id
        )
        .first()
    )

    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.utcnow()

    if printer:

        printer.current_queue = max(
            0,
            printer.current_queue - 1
        )

        printer.total_jobs_printed += 1

        printer.status = PrinterStatus.ONLINE

    db.commit()
    
    cleanup_job_files(
    job.job_id,
    db
    )

    return job


# ==========================================================
# Fail Current Job
# ==========================================================

def fail_job(
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

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == job.assigned_printer_id
        )
        .first()
    )

    job.status = JobStatus.FAILED

    if printer:

        printer.current_queue = max(
            0,
            printer.current_queue - 1
        )

        printer.status = PrinterStatus.ONLINE

    db.commit()

    return job