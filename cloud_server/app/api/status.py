from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ActiveJob

router = APIRouter(
    prefix="/status",
    tags=["Status"]
)


# ==========================================================
# Get Job Status
# ==========================================================

@router.get("/{job_id}")
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return {

        "job_id": str(job.job_id),

        "status": job.status.value,

        "payment_status": job.payment_status.value,

        "queue_position": job.queue_position,

        "assigned_printer_id": (
            str(job.assigned_printer_id)
            if job.assigned_printer_id
            else None
        ),

        "total_files": job.total_files,

        "total_pages": job.total_pages,

        "total_amount": float(job.total_amount)
    }


# ==========================================================
# Printing Progress
# ==========================================================

@router.get("/{job_id}/progress")
def print_progress(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    progress = 0

    if job.status.value == "PENDING":
        progress = 10

    elif job.status.value == "QUEUED":
        progress = 30

    elif job.status.value == "PRINTING":
        progress = 70

    elif job.status.value == "COMPLETED":
        progress = 100

    return {

        "job_id": str(job.job_id),

        "status": job.status.value,

        "progress": progress
    }