from uuid import UUID
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ActiveJob,
    JobStatus
)
from app.schemas.queue import QueueResponse
from app.services.queue_service import (
    add_job_to_queue,
    get_queue,
    get_all_queue_jobs,
    get_queue_job,
    cancel_queue_job
)

router = APIRouter(
    prefix="/queue",
    tags=["Queue"]
)


# ==========================================================
# 1. Static Routes First (Prevent Route Shadowing)
# ==========================================================

@router.get("/statistics/summary")
def queue_statistics(
    db: Session = Depends(get_db)
):
    """
    Get queue statistics summary across all jobs.
    """
    jobs = db.query(ActiveJob).all()

    return {
        "total_jobs": len(jobs),
        "waiting": sum(1 for job in jobs if job.status == JobStatus.PENDING),
        "queued": sum(1 for job in jobs if job.status == JobStatus.QUEUED),
        "assigned": sum(1 for job in jobs if job.status == JobStatus.ASSIGNED),
        "printing": sum(1 for job in jobs if job.status == JobStatus.PRINTING),
        "completed": sum(1 for job in jobs if job.status == JobStatus.COMPLETED),
        "failed": sum(1 for job in jobs if job.status == JobStatus.FAILED),
        "cancelled": sum(1 for job in jobs if job.status == JobStatus.CANCELLED)
    }


@router.get("/printer/{printer_id}", response_model=List[QueueResponse])
def get_printer_queue(
    printer_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get all queued jobs for a specific printer.
    """
    jobs = get_queue(printer_id, db)
    return [
        QueueResponse(
            job_id=job.job_id,
            status=job.status,
            assigned_printer_id=job.assigned_printer_id,
            queue_position=job.queue_position,
            estimated_seconds=job.estimated_seconds or 0,
            queued_at=job.queued_at
        )
        for job in jobs
    ]


@router.get("/", response_model=List[QueueResponse])
def get_all_queue(
    db: Session = Depends(get_db)
):
    """
    Get all currently queued jobs across all printers.
    """
    jobs = get_all_queue_jobs(db)
    return [
        QueueResponse(
            job_id=job.job_id,
            status=job.status,
            assigned_printer_id=job.assigned_printer_id,
            queue_position=job.queue_position,
            estimated_seconds=job.estimated_seconds or 0,
            queued_at=job.queued_at
        )
        for job in jobs
    ]


# ==========================================================
# 2. Dynamic Parameterized Routes
# ==========================================================

@router.post("/{job_id}", response_model=QueueResponse)
def queue_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = add_job_to_queue(job_id, db)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or not assigned to a printer."
        )

    return QueueResponse(
        job_id=job.job_id,
        status=job.status,
        assigned_printer_id=job.assigned_printer_id,
        queue_position=job.queue_position,
        estimated_seconds=job.estimated_seconds or 0,
        queued_at=job.queued_at
    )


@router.get("/{job_id}", response_model=QueueResponse)
def get_queue_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = get_queue_job(job_id, db)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return QueueResponse(
        job_id=job.job_id,
        status=job.status,
        assigned_printer_id=job.assigned_printer_id,
        queue_position=job.queue_position,
        estimated_seconds=job.estimated_seconds or 0,
        queued_at=job.queued_at
    )


@router.delete("/{job_id}", response_model=QueueResponse)
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = cancel_queue_job(job_id, db)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return QueueResponse(
        job_id=job.job_id,
        status=job.status,
        assigned_printer_id=job.assigned_printer_id,
        queue_position=job.queue_position,
        estimated_seconds=0,
        queued_at=job.queued_at
    )