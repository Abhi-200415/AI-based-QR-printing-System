import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.database.models import ActiveJob, JobFile, JobStatus, PaymentStatus
from app.utils.logger import logger


# ==========================================================
# Delete Physical File
# ==========================================================

def delete_uploaded_file(file_path: Optional[str]):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")


# ==========================================================
# Cleanup Single File
# ==========================================================

def cleanup_file(
    job_file: JobFile,
    db: Session
):
    if job_file.file_path:
        delete_uploaded_file(job_file.file_path)
        job_file.file_path = None
        job_file.stored_filename = None
        db.commit()
        db.refresh(job_file)
    return job_file


# ==========================================================
# Cleanup Entire Job Files
# ==========================================================

def cleanup_job_files(
    job_id,
    db: Session
) -> int:
    files = db.query(JobFile).filter(JobFile.job_id == job_id).all()
    cleaned = 0
    for file in files:
        cleanup_file(file, db)
        cleaned += 1
    return cleaned


# ==========================================================
# Cleanup Abandoned Incomplete Jobs (TTL)
# ==========================================================

def cleanup_abandoned_jobs(
    db: Session,
    max_age_hours: int = 2
) -> int:
    """
    Cleans up abandoned QR-scan jobs that never progressed past PENDING status.
    """
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

    abandoned_jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.status == JobStatus.PENDING,
            ActiveJob.payment_status == PaymentStatus.PENDING,
            ActiveJob.created_at < cutoff
        )
        .all()
    )

    count = 0
    for job in abandoned_jobs:
        cleanup_job_files(job.job_id, db)
        db.delete(job)
        count += 1

    if count > 0:
        db.commit()
        logger.info(f"Cleaned up {count} abandoned pending jobs older than {max_age_hours} hours.")

    return count