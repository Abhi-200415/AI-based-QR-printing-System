from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.database.models import ActiveJob

from app.schemas.queue import QueueResponse

from app.services.queue_service import (
    add_job_to_queue,
    get_queue,
    get_queue_job,
    cancel_queue_job,
)

router = APIRouter(
    prefix="/queue",
    tags=["Queue"],
)


# ==========================================================
# Add Job To Queue
# ==========================================================

@router.post("/{job_id}", response_model=QueueResponse)
def queue_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = add_job_to_queue(
        job_id,
        db
    )

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
        queued_at=job.queued_at
    )


# ==========================================================
# Get Queue
# ==========================================================

@router.get("/", response_model=list[QueueResponse])
def get_all_queue(
    db: Session = Depends(get_db)
):

    jobs = get_queue(db)

    return [

        QueueResponse(

            job_id=job.job_id,

            status=job.status,

            assigned_printer_id=job.assigned_printer_id,

            queue_position=job.queue_position,

            queued_at=job.queued_at

        )

        for job in jobs

    ]


# ==========================================================
# Get Queue Job
# ==========================================================

@router.get("/{job_id}", response_model=QueueResponse)
def get_queue_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = get_queue_job(
        job_id,
        db
    )

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

        queued_at=job.queued_at
    )


# ==========================================================
# Cancel Queue Job
# ==========================================================

@router.delete("/{job_id}", response_model=QueueResponse)
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):

    job = cancel_queue_job(
        job_id,
        db
    )

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

        queued_at=job.queued_at
    )


# ==========================================================
# Queue Statistics
# ==========================================================

@router.get("/statistics/summary")
def queue_statistics(
    db: Session = Depends(get_db)
):

    jobs = db.query(ActiveJob).all()

    return {

        "total_jobs": len(jobs),

        "waiting": sum(
            1 for job in jobs
            if str(job.status) == "PENDING"
        ),

        "queued": sum(
            1 for job in jobs
            if str(job.status) == "QUEUED"
        ),

        "printing": sum(
            1 for job in jobs
            if str(job.status) == "PRINTING"
        ),

        "completed": sum(
            1 for job in jobs
            if str(job.status) == "COMPLETED"
        )
    }