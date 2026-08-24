from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    JobFile,
    JobStatus,
    PaymentStatus,
)

from app.services.pricing_engine import calculate_job_cost
from app.services.assignment_service import assign_printer
from app.services.queue_service import add_job_to_queue


# ==========================================================
# Create Job
# ==========================================================

def create_job(
    job: ActiveJob,
    db: Session
):

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


# ==========================================================
# Get Job
# ==========================================================

def get_job(
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
# Update Job Summary
# ==========================================================

def update_job_summary(
    job_id,
    db: Session
):

    job = get_job(
        job_id,
        db
    )

    if not job:
        return None

    files = (
        db.query(JobFile)
        .filter(
            JobFile.job_id == job_id
        )
        .all()
    )

    job.total_files = len(files)

    job.total_pages = sum(
        file.page_count or 0
        for file in files
    )

    job.total_copies = sum(
        file.copies or 0
        for file in files
    )

    db.commit()
    db.refresh(job)

    return job


# ==========================================================
# AI Job Priority
# ==========================================================

def calculate_priority(
    job: ActiveJob
) -> int:

    score = 0

    score += job.total_pages or 0

    if (job.total_pages or 0) > 100:
        score += 20

    if (job.total_files or 0) > 5:
        score += 10

    if (job.total_copies or 0) > 10:
        score += 10

    return score


# ==========================================================
# Calculate / Prepare Job For Payment
#
# IMPORTANT:
# This function calculates:
#     - file summary
#     - priority
#     - pricing
#
# It DOES NOT assign a printer.
# It DOES NOT add the job to queue.
#
# Printer assignment happens only AFTER payment.
# ==========================================================

def prepare_job(
    job_id,
    db: Session
):

    job = update_job_summary(
        job_id,
        db
    )

    if not job:
        return None

    # ------------------------------------------------------
    # Calculate AI priority
    # ------------------------------------------------------

    job.priority = calculate_priority(
        job
    )

    db.commit()

    # ------------------------------------------------------
    # Calculate pricing
    # ------------------------------------------------------

    calculate_job_cost(
        job_id,
        db
    )

    db.refresh(job)

    return job


# ==========================================================
# Assign Job After Payment
# ==========================================================

def assign_paid_job(
    job_id,
    db: Session
):

    job = get_job(
        job_id,
        db
    )

    if not job:
        return None

    # ------------------------------------------------------
    # Payment must be completed first
    # ------------------------------------------------------

    if job.payment_status != PaymentStatus.PAID:

        return None

    # ------------------------------------------------------
    # Prevent duplicate assignment
    # ------------------------------------------------------

    if job.assigned_printer_id:

        return job

    # ------------------------------------------------------
    # AI Printer Assignment
    # ------------------------------------------------------

    printer = assign_printer(
        job,
        db
    )

    if not printer:

        return job

    # ------------------------------------------------------
    # Add to Queue
    # ------------------------------------------------------

    add_job_to_queue(
        job.job_id,
        db
    )

    db.refresh(job)

    return job


# ==========================================================
# Mark Payment Success
# ==========================================================

def mark_payment_success(
    job_id,
    db: Session
):

    job = get_job(
        job_id,
        db
    )

    if not job:
        return None

    job.payment_status = PaymentStatus.PAID

    db.commit()
    db.refresh(job)

    return job


# ==========================================================
# Cancel Job
# ==========================================================

def cancel_job(
    job_id,
    db: Session
):

    job = get_job(
        job_id,
        db
    )

    if not job:
        return None

    job.status = JobStatus.CANCELLED

    db.commit()
    db.refresh(job)

    return job


# ==========================================================
# Complete Job
# ==========================================================

def complete_job(
    job_id,
    db: Session
):

    job = get_job(
        job_id,
        db
    )

    if not job:
        return None

    job.status = JobStatus.COMPLETED

    db.commit()
    db.refresh(job)

    return job