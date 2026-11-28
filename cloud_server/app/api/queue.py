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
from app.schemas.queue import QueueResponse, QueueFileInfo
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


def _build_queue_response(job: ActiveJob) -> QueueResponse:
    files_info: List[QueueFileInfo] = []
    for f in (job.files or []):
        file_finishing = [
            s.service_name
            for s in (job.finishing_services or [])
            if s.file_id == f.file_id
        ]
        is_lam = any("laminat" in s.lower() for s in file_finishing)
        is_spiral = any("spiral" in s.lower() or "bind" in s.lower() for s in file_finishing)
        f_pname = (
            f.assigned_printer.printer_name
            if f.assigned_printer
            else (job.assigned_printer.printer_name if job.assigned_printer else None)
        )

        files_info.append(
            QueueFileInfo(
                file_id=f.file_id,
                filename=f.original_filename,
                page_count=f.page_count or 1,
                copies=f.copies or 1,
                paper_size=f.paper_size.value if hasattr(f.paper_size, "value") else str(f.paper_size or "A4"),
                orientation=f.orientation.value if hasattr(f.orientation, "value") else str(f.orientation or "PORTRAIT"),
                duplex=bool(f.duplex),
                print_type=f.print_type.value if hasattr(f.print_type, "value") else str(f.print_type or "BW"),
                color_mode=f.color_mode or "AUTO",
                assigned_printer_id=f.assigned_printer_id or job.assigned_printer_id,
                assigned_printer_name=f_pname,
                lamination=is_lam,
                spiral_binding=is_spiral,
                finishing_services=file_finishing,
                status=f.status.value if hasattr(f.status, "value") else str(f.status or "QUEUED")
            )
        )

    pname = job.assigned_printer.printer_name if job.assigned_printer else None
    pmt_status = job.payment_status.value if hasattr(job.payment_status, "value") else str(job.payment_status or "PENDING")

    job_st = job.status.value if hasattr(job.status, "value") else str(job.status or "QUEUED")

    return QueueResponse(
        job_id=job.job_id,
        status=job_st,
        assigned_printer_id=job.assigned_printer_id,
        assigned_printer_name=pname,
        queue_position=job.queue_position,
        estimated_seconds=job.estimated_seconds or 0,
        queued_at=job.queued_at,
        customer_name=job.customer_name or job.customer_reference or "Customer",
        customer_reference=job.customer_reference,
        total_files=job.total_files or len(files_info),
        total_pages=job.total_pages or sum(fi.page_count * fi.copies for fi in files_info),
        total_copies=job.total_copies or 1,
        total_amount=float(job.total_amount or 0.0),
        payment_status=pmt_status,
        finishing_status=job.finishing_status or "NONE",
        files=files_info
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
    Get all queued jobs for a specific printer with rich file and finishing service details.
    """
    jobs = get_queue(printer_id, db)
    return [_build_queue_response(job) for job in jobs]


@router.get("/", response_model=List[QueueResponse])
def get_all_queue(
    db: Session = Depends(get_db)
):
    """
    Get all currently queued jobs across all printers with rich file, customer, and finishing service details.
    """
    jobs = get_all_queue_jobs(db)
    return [_build_queue_response(job) for job in jobs]


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

    return _build_queue_response(job)


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

    return _build_queue_response(job)


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

    job_st = job.status.value if hasattr(job.status, "value") else str(job.status or "QUEUED")

    return QueueResponse(
        job_id=job.job_id,
        status=job_st,
        assigned_printer_id=job.assigned_printer_id,
        queue_position=job.queue_position,
        estimated_seconds=0,
        queued_at=job.queued_at
    )