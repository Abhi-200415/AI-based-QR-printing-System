import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.database.models import ActiveJob, JobFile, JobStatus, PaymentStatus
from app.utils.logger import logger


# ==========================================================
# Delete Physical File
# ==========================================================

def delete_uploaded_file(file_path: Optional[str], job_id: Optional[str] = None):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if not file_path or file_path == "[DELETED]":
        return

    if not os.path.exists(file_path):
        msg = f"[{ts}] [CLOUD CLEANUP] Temporary file already removed or missing: {os.path.basename(file_path)}"
        print(msg, flush=True)
        logger.info(msg)
        return

    try:
        base_name = os.path.basename(file_path)
        print(f"[{ts}] [CLOUD CLEANUP] Temporary file located", flush=True)
        print(f"[{ts}] [CLOUD CLEANUP] Temporary file located: {base_name}", flush=True)
        logger.info(f"[CLOUD CLEANUP] Temporary file located: {base_name}")

        # Overwrite file content before unlinking (application-level data scrubbing)
        size = os.path.getsize(file_path)
        if size > 0:
            with open(file_path, "wb") as f:
                f.write(os.urandom(size))
        os.remove(file_path)

        print(f"[{ts}] [CLOUD CLEANUP] Deletion successful", flush=True)
        print(f"[{ts}] [CLOUD CLEANUP] Deletion successful: {base_name}", flush=True)
        logger.info(f"[CLOUD CLEANUP] Deletion successful: {base_name}")
    except Exception as e:
        safe_err = str(e).replace("\\", "/")
        print(f"[{ts}] [CLOUD CLEANUP] ERROR: Failed to delete temporary file: {safe_err}", flush=True)
        logger.error(f"[CLOUD CLEANUP] ERROR: Failed to delete temporary file: {safe_err}")


# ==========================================================
# Cleanup Single File
# ==========================================================

def cleanup_file(
    job_file: JobFile,
    db: Session,
    job_id: Optional[str] = None
):
    jid = str(job_id or job_file.job_id or "N/A")
    if job_file.file_path and job_file.file_path != "[DELETED]":
        delete_uploaded_file(job_file.file_path, job_id=jid)
        job_file.file_path = "[DELETED]"
        job_file.stored_filename = "[DELETED]"
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
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    jid_str = str(job_id)
    print(f"[{ts}] [CLOUD CLEANUP] Starting cleanup\n[{ts}] [CLOUD CLEANUP] Job ID: {jid_str}", flush=True)
    logger.info(f"[CLOUD CLEANUP] Starting cleanup for Job ID: {jid_str}")

    try:
        files = db.query(JobFile).filter(JobFile.job_id == job_id).all()
        cleaned = 0
        for file in files:
            cleanup_file(file, db, job_id=jid_str)
            cleaned += 1

        print(f"[{ts}] [CLOUD CLEANUP] Cleanup completed", flush=True)
        print(f"[{ts}] [CLOUD CLEANUP] Cleanup completed (Files cleaned: {cleaned})", flush=True)
        logger.info(f"[CLOUD CLEANUP] Cleanup completed for Job ID: {jid_str}")
        return cleaned
    except Exception as e:
        safe_err = str(e).replace("\\", "/")
        print(f"[{ts}] [CLOUD CLEANUP] ERROR: Cleanup failed for job {jid_str}: {safe_err}", flush=True)
        logger.error(f"[CLOUD CLEANUP] ERROR: Cleanup failed for job {jid_str}: {safe_err}")
        return 0


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
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
        print(f"[{ts}] [CLOUD CLEANUP] Cleaned up {count} abandoned pending jobs older than {max_age_hours} hours.", flush=True)
        logger.info(f"[CLOUD CLEANUP] Cleaned up {count} abandoned pending jobs older than {max_age_hours} hours.")

    return count