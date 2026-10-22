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
    valid_name = None
    if data.customer_name:
        from app.services.customer_service import validate_customer_name
        valid_name = validate_customer_name(data.customer_name)

    job = ActiveJob(
        owner_id=owner_id,
        customer_name=valid_name,
        customer_phone=data.customer_phone,
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PENDING
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ==========================================================
# Get All Jobs for Shop Owner
# ==========================================================

@router.get("/owner/{owner_id}")
def get_owner_jobs(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    jobs = (
        db.query(ActiveJob)
        .filter(ActiveJob.owner_id == owner_id)
        .order_by(ActiveJob.created_at.desc())
        .all()
    )
    result = []
    for j in jobs:
        files = []
        for f in (j.files or []):
            files.append({
                "file_id": str(f.file_id),
                "filename": f.original_filename,
                "file_type": f.file_type,
                "page_count": f.page_count,
                "copies": f.copies,
                "paper_size": f.paper_size.value if hasattr(f.paper_size, "value") else str(f.paper_size),
                "print_type": f.print_type.value if hasattr(f.print_type, "value") else str(f.print_type),
                "duplex": f.duplex,
                "orientation": f.orientation.value if hasattr(f.orientation, "value") else str(f.orientation),
                "page_ranges": f.page_ranges,
                "color_page_ranges": f.color_page_ranges,
                "estimated_cost": float(f.estimated_cost or 0.0),
                "assigned_printer_id": str(f.assigned_printer_id) if f.assigned_printer_id else str(j.assigned_printer_id) if j.assigned_printer_id else None,
                "assigned_printer_name": f.assigned_printer.printer_name if f.assigned_printer else (j.assigned_printer.printer_name if j.assigned_printer else None),
                "status": f.status.value if hasattr(f.status, "value") else str(f.status or "Pending"),
                "print_completed": bool(f.print_completed)
            })
        pmt = j.payment
        finishing_list = []
        for s in (j.finishing_services or []):
            finishing_list.append({
                "id": str(s.id),
                "file_id": str(s.file_id) if s.file_id else None,
                "service_id": str(s.service_id) if s.service_id else None,
                "service_name": s.service_name,
                "unit_price": float(s.unit_price),
                "quantity": s.quantity,
                "total_price": float(s.total_price)
            })

        display_cust_name = j.customer_name
        is_cleared = False
        if not display_cust_name:
            if j.status == JobStatus.COMPLETED:
                display_cust_name = "[Privacy Protected]"
                is_cleared = True
            elif j.customer_reference:
                display_cust_name = j.customer_reference
            else:
                display_cust_name = "Walk-in Customer"

        result.append({
            "job_id": str(j.job_id),
            "customer_name": display_cust_name,
            "customer_name_cleared": is_cleared,
            "raw_customer_name": j.customer_name,
            "customer_phone": j.customer_phone or "",
            "customer_reference": j.customer_reference,
            "status": j.status.value,
            "finishing_status": j.finishing_status or "NONE",
            "finishing_completed_at": j.finishing_completed_at.strftime("%Y-%m-%d %H:%M:%S") if j.finishing_completed_at else None,
            "payment_status": j.payment_status.value,
            "payment_method": pmt.payment_method.value if pmt and pmt.payment_method else "UPI",
            "assigned_printer_id": str(j.assigned_printer_id) if j.assigned_printer_id else None,
            "assigned_printer_name": j.assigned_printer.printer_name if j.assigned_printer else None,
            "queue_position": j.queue_position,
            "total_files": j.total_files or len(files),
            "total_pages": j.total_pages or sum(f["page_count"] * f["copies"] for f in files),
            "total_copies": j.total_copies or 1,
            "subtotal": float(j.subtotal or 0.0),
            "tax": float(j.tax or 0.0),
            "total_amount": float(j.total_amount or (pmt.amount if pmt else 0.0) or 0.0),
            "estimated_seconds": j.estimated_seconds or 0,
            "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S") if j.created_at else "-",
            "queued_at": j.queued_at.strftime("%Y-%m-%d %H:%M:%S") if j.queued_at else None,
            "started_at": j.started_at.strftime("%Y-%m-%d %H:%M:%S") if j.started_at else None,
            "completed_at": j.completed_at.strftime("%Y-%m-%d %H:%M:%S") if j.completed_at else None,
            "files": files,
            "finishing_services": finishing_list
        })
    return result


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

    job.updated_at = datetime.utcnow()

    if status == JobStatus.QUEUED:
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.utcnow()

    elif status == JobStatus.PRINTING:
        job.status = JobStatus.PRINTING
        job.started_at = datetime.utcnow()

    elif status == JobStatus.COMPLETED:
        # Complete this job in queue and update printer count
        completed_job = complete_queue_job(job.job_id, db)

        # If finishing is pending, do not set overall job to completed yet
        if job.finishing_status == "PENDING":
            job.status = JobStatus.PRINTING
        else:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            for f in (job.files or []):
                f.print_completed = True
                f.status = JobStatus.COMPLETED
                if not f.completed_at:
                    f.completed_at = datetime.utcnow()

            from app.services.customer_service import clear_customer_name_after_completion
            clear_customer_name_after_completion(job, db)

        # Automatically dispatch next job in queue for this printer
        if completed_job and completed_job.assigned_printer_id:
            next_jobs = get_queue(completed_job.assigned_printer_id, db)
            if next_jobs:
                await dispatch_job_to_agent(next_jobs[0])
    else:
        job.status = status

    calculated_seconds = actual_seconds
    if (
        calculated_seconds is None
        and job.status == JobStatus.COMPLETED
        and job.started_at
        and job.completed_at
    ):
        calculated_seconds = int(
            (job.completed_at.replace(tzinfo=None) - job.started_at.replace(tzinfo=None)).total_seconds()
        )

    db.commit()
    db.refresh(job)

    logger.info(f"Updated Job {job.job_id} status to '{job.status.value}' (Finishing: {job.finishing_status})")

    return {
        "success": True,
        "job_id": str(job.job_id),
        "status": job.status.value,
        "finishing_status": job.finishing_status,
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

    finishing_list = [
        {
            "id": str(s.id),
            "file_id": str(s.file_id) if s.file_id else None,
            "service_id": str(s.service_id) if s.service_id else None,
            "service_name": s.service_name,
            "unit_price": float(s.unit_price),
            "quantity": s.quantity,
            "total_price": float(s.total_price)
        }
        for s in (job.finishing_services or [])
    ]

    from app.services.assignment_service import get_job_time_estimates
    timing_estimate = get_job_time_estimates(job, db)

    files_data = [
        {
            "file_id": str(f.file_id),
            "filename": f.original_filename,
            "page_count": f.page_count,
            "copies": f.copies,
            "paper_size": f.paper_size.value if f.paper_size else "A4",
            "print_type": f.print_type.value if f.print_type else "BW",
            "duplex": bool(f.duplex),
            "status": f.status.value if getattr(f, 'status', None) else ("Completed" if f.print_completed else job.status.value),
            "print_completed": bool(f.print_completed),
            "assigned_printer_name": f.assigned_printer.printer_name if getattr(f, 'assigned_printer', None) else (job.assigned_printer.printer_name if job.assigned_printer else None)
        }
        for f in (job.files or [])
    ]

    return {
        "job_id": str(job.job_id),
        "customer_name": job.customer_name,
        "customer_reference": job.customer_reference,
        "customer_name_cleared": bool(not job.customer_name and (job.customer_reference or job.status == JobStatus.COMPLETED)),
        "status": job.status.value,
        "finishing_status": job.finishing_status or "NONE",
        "finishing_completed_at": job.finishing_completed_at,
        "finishing_services": finishing_list,
        "payment_status": job.payment_status.value,
        "payment_method": job.payment.payment_method.value if job.payment else None,
        "assigned_printer": str(job.assigned_printer_id) if job.assigned_printer_id else None,
        "assigned_printer_name": job.assigned_printer.printer_name if job.assigned_printer else (timing_estimate.get("printer_name") if timing_estimate.get("available") else None),
        "queue_position": job.queue_position,
        "estimated_seconds": job.estimated_seconds or (timing_estimate.get("total_seconds") or 0),
        "actual_seconds": actual_seconds,
        "timing_estimate": timing_estimate,
        "estimated_queue_wait_seconds": timing_estimate.get("queue_wait_seconds"),
        "estimated_queue_wait_display": timing_estimate.get("queue_wait_display"),
        "estimated_print_duration_seconds": timing_estimate.get("print_duration_seconds"),
        "estimated_print_duration_display": timing_estimate.get("print_duration_display"),
        "estimated_total_seconds": timing_estimate.get("total_seconds"),
        "estimated_total_display": timing_estimate.get("total_display"),
        "estimate_available": timing_estimate.get("available", False),
        "timing_disclaimer": timing_estimate.get("disclaimer"),
        "total_files": job.total_files or len(job.files or []),
        "total_pages": job.total_pages or 0,
        "subtotal": float(job.subtotal or 0),
        "tax": float(job.tax or 0),
        "total_amount": float(job.total_amount or 0),
        "files": files_data,
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


# ==========================================================
# Update Customer Name Endpoint (Objective 2.1)
# ==========================================================

from pydantic import BaseModel

class CustomerNameUpdateRequest(BaseModel):
    customer_name: str

@router.put("/{job_id}/customer-name")
def update_job_customer_name(
    job_id: UUID,
    data: CustomerNameUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Validates and updates customer name on an active print order.
    """
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    from app.services.customer_service import validate_customer_name
    valid_name = validate_customer_name(data.customer_name)

    job.customer_name = valid_name
    job.customer_reference = valid_name
    db.commit()
    db.refresh(job)

    return {
        "success": True,
        "job_id": str(job.job_id),
        "customer_name": job.customer_name,
        "message": "Customer name updated successfully."
    }


# ==========================================================
# Safe Job Retry Endpoint (Objective 6.3)
# ==========================================================

@router.post("/{job_id}/retry")
async def retry_failed_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Safely retries an eligible failed or blocked print job.
    Enforces strict state validation to prevent duplicate printing:
    - Verifies payment is already confirmed (PAID).
    - Verifies job is currently in FAILED or CANCELLED status.
    - Preserves already printed files; only retries unfinished files.
    - Re-evaluates printer assignment and re-queues job.
    """
    job = get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry job in '{job.status.value}' state. Only Failed or Cancelled jobs may be retried."
        )

    if job.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry job without confirmed payment."
        )

    # Reset status of unfinished files only (prevents re-printing completed files)
    for f in (job.files or []):
        if not f.print_completed and f.status != JobStatus.COMPLETED:
            f.status = JobStatus.QUEUED
            f.started_at = None
            f.completed_at = None

    from app.services.job_service import assign_paid_job
    prepared = assign_paid_job(job.job_id, db)
    if not prepared:
        raise HTTPException(status_code=500, detail="Unable to assign printer for retry.")

    prepared.status = JobStatus.QUEUED
    prepared.queued_at = datetime.utcnow()
    db.commit()
    db.refresh(prepared)

    # If first in queue, dispatch to agent
    if prepared.queue_position == 1 and prepared.assigned_printer_id:
        await dispatch_job_to_agent(prepared)

    logger.info(f"Safely re-queued failed job {job.job_id} for retry.")
    return {
        "success": True,
        "job_id": str(prepared.job_id),
        "status": prepared.status.value,
        "queue_position": prepared.queue_position,
        "assigned_printer": str(prepared.assigned_printer_id) if prepared.assigned_printer_id else None,
        "message": "Job re-queued for printing successfully."
    }
