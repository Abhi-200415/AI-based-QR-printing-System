from uuid import UUID
from datetime import datetime
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ActiveJob,
    JobStatus,
    PaymentStatus
)
from app.schemas.job import (
    JobCreate,
    JobResponse
)
from app.services.job_service import (
    create_job,
    get_job,
    prepare_job,
    cancel_job,
    complete_job
)
from app.services.queue_service import (
    complete_queue_job,
    get_queue
)
from app.services.dispatch_service import (
    dispatch_job_to_agent
)
from app.utils.logger import logger

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


# ==========================================================
# Dispatch Next Queued Job for Printer
# ==========================================================

@router.post("/dispatch-next/{printer_id}")
async def dispatch_next_queued_job(
    printer_id: UUID,
    db: Session = Depends(get_db)
):
    jobs = get_queue(printer_id, db)
    if not jobs:
        raise HTTPException(status_code=404, detail="No queued jobs found for this printer.")

    job = jobs[0]
    dispatched = await dispatch_job_to_agent(job)
    return {
        "job_id": str(job.job_id),
        "queue_position": job.queue_position,
        "dispatched": dispatched
    }


# ==========================================================
# Create Job
# ==========================================================

@router.post("/owner/{owner_id}", response_model=JobResponse)
def create_new_job(
    owner_id: UUID,
    data: JobCreate,
    db: Session = Depends(get_db)
):
    job = ActiveJob(
        owner_id=owner_id,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PENDING
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ==========================================================
# Get Single Job
# ==========================================================

@router.get("/{job_id}", response_model=JobResponse)
def get_single_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


# ==========================================================
# Update Job Status (Called by Print Agent or Operator)
# ==========================================================

@router.put("/{job_id}/status")
async def update_job_status(
    job_id: UUID,
    status: JobStatus,
    message: str = "",
    actual_seconds: Optional[int] = None,
    db: Session = Depends(get_db)
):
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.status = status
    job.updated_at = datetime.utcnow()

    if status == JobStatus.QUEUED:
        job.queued_at = datetime.utcnow()

    elif status == JobStatus.PRINTING:
        job.started_at = datetime.utcnow()

    elif status == JobStatus.COMPLETED:
        job.completed_at = datetime.utcnow()
        # Complete this job in queue and update printer count
        completed_job = complete_queue_job(job.job_id, db)

        # Automatically dispatch next job in queue for this printer
        if completed_job and completed_job.assigned_printer_id:
            next_jobs = get_queue(completed_job.assigned_printer_id, db)
            if next_jobs:
                await dispatch_job_to_agent(next_jobs[0])

    calculated_seconds = actual_seconds
    if (
        calculated_seconds is None
        and status == JobStatus.COMPLETED
        and job.started_at
        and job.completed_at
    ):
        calculated_seconds = int(
            (job.completed_at.replace(tzinfo=None) - job.started_at.replace(tzinfo=None)).total_seconds()
        )

    db.commit()
    db.refresh(job)

    logger.info(f"Updated Job {job.job_id} status to '{status.value}' (duration: {calculated_seconds}s)")

    return {
        "success": True,
        "job_id": str(job.job_id),
        "status": job.status.value,
        "actual_seconds": calculated_seconds,
        "message": message or "Job status updated."
    }


# ==========================================================
# Get Real-Time Job Status (For Customer / Dashboard Polling)
# ==========================================================

@router.get("/{job_id}/status")
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    actual_seconds = None
    if job.started_at:
        end_time = job.completed_at or datetime.utcnow()
        actual_seconds = int(
            (end_time.replace(tzinfo=None) - job.started_at.replace(tzinfo=None)).total_seconds()
        )

    return {
        "job_id": str(job.job_id),
        "status": job.status.value,
        "payment_status": job.payment_status.value,
        "assigned_printer": str(job.assigned_printer_id) if job.assigned_printer_id else None,
        "assigned_printer_name": job.assigned_printer.printer_name if job.assigned_printer else None,
        "queue_position": job.queue_position,
        "estimated_seconds": job.estimated_seconds or 0,
        "actual_seconds": actual_seconds,
        "total_files": job.total_files or len(job.files or []),
        "total_pages": job.total_pages or 0,
        "total_amount": float(job.total_amount or 0),
        "created_at": job.created_at,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "updated_at": job.updated_at
    }


# ==========================================================
# Cancel Job
# ==========================================================

@router.put("/{job_id}/cancel")
def cancel_job_endpoint(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = cancel_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "success": True,
        "job_id": str(job.job_id),
        "status": job.status.value,
        "message": "Job cancelled."
    }
