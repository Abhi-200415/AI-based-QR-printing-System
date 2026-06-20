from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ActiveJob
from app.schemas.job import JobCreate

router = APIRouter(
    prefix="/job",
    tags=["Jobs"]
)


@router.post("/create")
def create_job(
    job: JobCreate,
    db: Session = Depends(get_db)
):
    new_job = ActiveJob(
        session_id=job.session_id,
        username=job.username,
        payment_method=job.payment_method,
        total_files=0,
        total_pages=0,
        total_amount=0,
        payment_status="pending",
        print_status="uploaded"
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return {
        "message": "Job created",
        "job_id": str(new_job.job_id)
    }


@router.get("/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job


@router.get("/queue/all")
def get_queue(
    db: Session = Depends(get_db)
):
    return (
        db.query(ActiveJob)
        .order_by(ActiveJob.created_at)
        .all()
    )