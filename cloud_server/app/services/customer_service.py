import re
import html
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models import ActiveJob, JobFile, JobStatus
from app.utils.logger import logger

# Regex allowing letters (including Unicode letters \w), spaces, hyphens, apostrophes, and periods
# Rejects control characters, HTML brackets < >, slashes, script injections
_NAME_VALID_REGEX = re.compile(r"^[\w\s\.\'\,\-]+$", re.UNICODE)


def validate_customer_name(name: Optional[str]) -> str:
    """
    Validates and sanitizes mandatory customer name according to Objective 2:
    - Rejects empty and whitespace-only names.
    - Trims leading and trailing whitespace.
    - Enforces reasonable length (2 to 100 characters).
    - Supports ordinary names with spaces, hyphens, apostrophes, dots, and Unicode characters.
    - Safely strips/escapes any potential HTML/XSS injection.
    - Raises HTTPException(400) on invalid or missing names.
    """
    if name is None:
        raise HTTPException(
            status_code=400,
            detail="Customer Name is required. Please provide your name to confirm your print order."
        )

    clean_name = str(name).strip()

    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail="Customer Name cannot be empty or whitespace only."
        )

    if len(clean_name) < 2:
        raise HTTPException(
            status_code=400,
            detail="Customer Name must be at least 2 characters long."
        )

    if len(clean_name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Customer Name cannot exceed 100 characters."
        )

    # Check for HTML injection characters
    if any(char in clean_name for char in ("<", ">", "{", "}", "\\", "`", "$")):
        raise HTTPException(
            status_code=400,
            detail="Customer Name contains invalid characters. HTML tags or special symbols are not allowed."
        )

    # Validate allowed name characters (letters in any language, spaces, hyphens, apostrophes, dots)
    if not _NAME_VALID_REGEX.match(clean_name):
        raise HTTPException(
            status_code=400,
            detail="Customer Name contains invalid characters. Please enter a valid name."
        )

    # Validated clean name (contains only valid unicode letters, digits, spaces, hyphens, apostrophes)
    return clean_name


def is_order_completely_finished(job: ActiveJob, db: Session) -> bool:
    """
    Checks if all required child print jobs / files in the parent order
    have successfully completed printing.
    """
    files = job.files or []
    if not files:
        files = db.query(JobFile).filter(JobFile.job_id == job.job_id).all()

    if not files:
        return job.status == JobStatus.COMPLETED

    # Check every file: must be print_completed or status COMPLETED
    for f in files:
        is_done = f.print_completed or (f.status == JobStatus.COMPLETED)
        if not is_done:
            return False

    return job.status == JobStatus.COMPLETED


def clear_customer_name_after_completion(job_or_id, db: Session) -> bool:
    """
    Temporary Data Retention Enforcement (Objective 2.3 & 2.4).
    Accepts either an ActiveJob instance or a job_id UUID/str.
    """
    if not job_or_id:
        return False

    if not isinstance(job_or_id, ActiveJob):
        job = db.query(ActiveJob).filter(ActiveJob.job_id == job_or_id).first()
        if not job:
            return False
    else:
        job = job_or_id

    # Only clear if already has a name to clear
    if not job.customer_name and not job.customer_phone:
        return False

    # Rule 3 & 4: Do not clear until ALL required child jobs and parent order have completed successfully
    if not is_order_completely_finished(job, db):
        logger.debug(f"Job {job.job_id} not completely finished; customer name retained for operator identification.")
        return False

    # Rule 10: Generate and persist genuine PDF receipt before clearing name from DB
    try:
        from app.services.receipt_pdf_service import ensure_cached_pdf_receipt
        ensure_cached_pdf_receipt(job, db)
    except Exception as e:
        logger.warning(f"Could not pre-generate PDF receipt prior to customer name cleanup: {e}")

    # Transactional cleanup
    try:
        job.customer_name = None
        job.customer_phone = None
        db.commit()
        logger.info(f"Customer name scrubbed from DB for completed order {job.job_id} (temporary retention policy).")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to scrub customer name for completed order {job.job_id}: {e}")
        return False
