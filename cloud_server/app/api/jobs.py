from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from datetime import datetime

from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.database.models import (
    ActiveJob,
    JobStatus
)

from app.schemas.job import (
    JobCreate,
    JobResponse
)

from app.services.job_service import (
    create_job, get_job, prepare_job, cancel_job, complete_job
)

from app.services.queue_service import complete_queue_job, get_queue
from app.services.dispatch_service import dispatch_job_to_agent



router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


# ==========================================================
# TEST: Dispatch First Queued Job
# ==========================================================

@router.post("/dispatch-next/{printer_id}")
async def dispatch_next_queued_job(
    printer_id: UUID,
    db: Session = Depends(get_db)
):

    jobs = get_queue(
        printer_id,
        db
    )

    if not jobs:
        raise HTTPException(
            status_code=404,
            detail="No queued jobs found."
        )

    job = jobs[0]

    dispatched = await dispatch_job_to_agent(
        job
    )

    return {
        "job_id": str(job.job_id),
        "queue_position": job.queue_position,
        "dispatched": dispatched
    }


# ==========================================================
# Create Job
# ==========================================================
# ==========================================================

# Create Job
# ==========================================================

@router.post(
    "/owner/{owner_id}",
    response_model=JobResponse
)
def create_new_job(
    owner_id: UUID,
    data: JobCreate,
    db: Session = Depends(get_db)
):

    job = ActiveJob(

        owner_id=owner_id,

        customer_name=data.customer_name,

        customer_phone=data.customer_phone

    )

    return create_job(
        job,
        db
    )


# ==========================================================
# Get Job
# ==========================================================

@router.get(
    "/{job_id}",
    response_model=JobResponse
)
def get_job_details(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = get_job(
        job_id,
        db
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return job


# ==========================================================
# Prepare Job
# ==========================================================

@router.post(
    "/{job_id}/prepare"
)
def prepare_print_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = prepare_job(
        job_id,
        db
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return {

        "success": True,

        "message":
            "Job prepared successfully.",

        "job_id":
            str(job.job_id)

    }


# ==========================================================
# Cancel Job
# ==========================================================

@router.delete(
    "/{job_id}"
)
def cancel_print_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = cancel_job(
        job_id,
        db
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return {

        "success": True,

        "message":
            "Job cancelled."

    }


# ==========================================================
# Complete Job
# ==========================================================

@router.put(
    "/{job_id}/complete"
)
def complete_print_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = complete_job(
        job_id,
        db
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return {

        "success": True,

        "message":
            "Job completed successfully."

    }


# ==========================================================
# Update Job Status
# Print Agent -> Cloud
# ==========================================================

@router.put(
    "/{job_id}/status"
)
async def update_job_status(
    job_id: UUID,
    status: JobStatus,
    message: str = "",
    actual_seconds: int = None,
    db: Session = Depends(get_db)
):

    job = get_job(
        job_id,
        db
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    # ------------------------------------------------------
    # Update Status
    # ------------------------------------------------------

    job.status = status

    job.updated_at = datetime.utcnow()

    # ------------------------------------------------------
    # QUEUED
    # ------------------------------------------------------

    if status == JobStatus.QUEUED:

        job.queued_at = datetime.utcnow()

    # ------------------------------------------------------
    # PRINTING
    # ------------------------------------------------------

    elif status == JobStatus.PRINTING:

        job.started_at = datetime.utcnow()

    # ------------------------------------------------------
    # COMPLETED
    # ------------------------------------------------------

    elif status == JobStatus.COMPLETED:

        job.completed_at = datetime.utcnow()

        # Complete this job in its printer-specific queue
        completed_job = complete_queue_job(
            job.job_id,
            db
        )

        # Only this printer receives its next queued job
        if (
            completed_job
            and completed_job.assigned_printer_id
        ):

            next_jobs = get_queue(
                completed_job.assigned_printer_id,
                db
            )

            if next_jobs:

                next_job = next_jobs[0]

                await dispatch_job_to_agent(
                    next_job
                )

    # ------------------------------------------------------
    # Calculate actual printing duration
    # ------------------------------------------------------

    calculated_seconds = actual_seconds

    if (
        calculated_seconds is None
        and status == JobStatus.COMPLETED
        and job.started_at
        and job.completed_at
    ):

        calculated_seconds = int(
            (
                job.completed_at.replace(
                    tzinfo=None
                )
                -
                job.started_at.replace(
                    tzinfo=None
                )
            ).total_seconds()
        )

    db.commit()

    db.refresh(job)

    return {

        "success": True,

        "job_id":
            str(job.job_id),

        "status":
            job.status.value,

        "actual_seconds":
            calculated_seconds,

        "message":
            message or "Job status updated."

    }


# ==========================================================
# Get Job Status
# ==========================================================

@router.get(
    "/{job_id}/status"
)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = get_job(
        job_id,
        db
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    # ------------------------------------------------------
    # Calculate actual printing duration dynamically
    # ------------------------------------------------------

    actual_seconds = None

    if job.started_at:

        end_time = (
            job.completed_at
            or datetime.utcnow()
        )

        actual_seconds = int(
            (
                end_time.replace(
                    tzinfo=None
                )
                -
                job.started_at.replace(
                    tzinfo=None
                )
            ).total_seconds()
        )

    return {

        "job_id":
            str(job.job_id),

        "status":
            job.status.value,

        "payment_status":
            job.payment_status.value,

        "assigned_printer":
            (
                str(job.assigned_printer_id)
                if job.assigned_printer_id
                else None
            ),

        "queue_position":
            job.queue_position,

        "estimated_seconds":
            0,

        "actual_seconds":
            actual_seconds,

        "created_at":
            job.created_at,

        "updated_at":
            job.updated_at,

        "started_at":
            job.started_at,

        "completed_at":
            job.completed_at

    }



