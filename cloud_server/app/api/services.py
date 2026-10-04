import uuid
from uuid import UUID
from decimal import Decimal
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.database.models import (
    FinishingService,
    JobFinishingService,
    ActiveJob,
    JobStatus
)
from app.schemas.service import (
    FinishingServiceCreate,
    FinishingServiceUpdate,
    FinishingServiceResponse,
    JobFinishingSelectRequest,
    JobFinishingServiceResponse
)
from app.services.pricing_engine import (
    seed_default_finishing_services,
    apply_finishing_services_to_job,
    calculate_job_cost
)
from app.utils.logger import logger

router = APIRouter(
    prefix="/services",
    tags=["Finishing Services"]
)


# ==========================================================
# Get Shop Finishing Services (Owner / Operator)
# ==========================================================

@router.get("/owner/{owner_id}", response_model=List[FinishingServiceResponse])
def get_owner_finishing_services(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Returns all finishing services configured for this shop owner.
    Seeds default services if none exist.
    """
    seed_default_finishing_services(owner_id, db)

    services = (
        db.query(FinishingService)
        .filter(FinishingService.owner_id == owner_id)
        .order_by(FinishingService.created_at.asc())
        .all()
    )
    return services


# ==========================================================
# Create New Finishing Service (Owner)
# ==========================================================

@router.post("/owner/{owner_id}", response_model=FinishingServiceResponse)
def create_finishing_service(
    owner_id: UUID,
    service_in: FinishingServiceCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new custom finishing service for this shop owner.
    """
    new_service = FinishingService(
        service_id=uuid.uuid4(),
        owner_id=owner_id,
        service_name=service_in.service_name.strip(),
        description=service_in.description.strip() if service_in.description else None,
        price=Decimal(str(service_in.price)),
        charge_type=service_in.charge_type or "PER_ORDER",
        is_enabled=service_in.is_enabled
    )
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    logger.info(f"Created finishing service {new_service.service_name} (Rs {new_service.price}) for owner {owner_id}")
    return new_service


# ==========================================================
# Update Finishing Service (Owner)
# ==========================================================

@router.put("/{service_id}", response_model=FinishingServiceResponse)
def update_finishing_service(
    service_id: UUID,
    service_in: FinishingServiceUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates price, name, description, or enabled status of a service.
    Future orders will use the updated price; existing orders retain snapshots.
    """
    service = db.query(FinishingService).filter(FinishingService.service_id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Finishing service not found.")

    if service_in.service_name is not None:
        service.service_name = service_in.service_name.strip()
    if service_in.description is not None:
        service.description = service_in.description.strip() if service_in.description else None
    if service_in.price is not None:
        service.price = Decimal(str(service_in.price))
    if service_in.charge_type is not None:
        service.charge_type = service_in.charge_type
    if service_in.is_enabled is not None:
        service.is_enabled = service_in.is_enabled

    db.commit()
    db.refresh(service)
    logger.info(f"Updated finishing service {service.service_id} (New Price: Rs {service.price}, Enabled: {service.is_enabled})")
    return service


# ==========================================================
# Delete Finishing Service (Owner)
# ==========================================================

@router.delete("/{service_id}")
def delete_finishing_service(
    service_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Deletes a finishing service from the shop.
    """
    service = db.query(FinishingService).filter(FinishingService.service_id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Finishing service not found.")

    db.delete(service)
    db.commit()
    logger.info(f"Deleted finishing service {service_id}")
    return {"success": True, "message": "Finishing service deleted successfully."}


# ==========================================================
# Public / Customer: Get Available Services For Shop
# ==========================================================

@router.get("/shop/{owner_id}/available", response_model=List[FinishingServiceResponse])
def get_available_shop_services(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Returns only ACTIVE / ENABLED finishing services for this shop.
    Guarantees shop-specific pricing isolation.
    """
    seed_default_finishing_services(owner_id, db)

    services = (
        db.query(FinishingService)
        .filter(
            FinishingService.owner_id == owner_id,
            FinishingService.is_enabled == True
        )
        .order_by(FinishingService.created_at.asc())
        .all()
    )
    return services


# ==========================================================
# Customer: Select Finishing Services for Job
# ==========================================================

@router.post("/job/{job_id}/select")
def select_job_finishing_services(
    job_id: UUID,
    request: JobFinishingSelectRequest,
    db: Session = Depends(get_db)
):
    """
    Authoritative server-side selection of finishing services for an order.
    Enforces that services belong to the order's shop and creates price snapshots.
    Recalculates total price.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    apply_finishing_services_to_job(
        job=job,
        service_selections=request.services,
        customer_reference=request.customer_reference,
        db=db
    )

    # Authoritatively recalculate final job total
    calculate_job_cost(job.job_id, db)
    db.refresh(job)

    # Fetch applied snapshots
    applied = (
        db.query(JobFinishingService)
        .filter(JobFinishingService.job_id == job_id)
        .all()
    )

    return {
        "success": True,
        "job_id": str(job.job_id),
        "customer_reference": job.customer_reference,
        "finishing_status": job.finishing_status,
        "subtotal": float(job.subtotal),
        "tax": float(job.tax),
        "total_amount": float(job.total_amount),
        "services": [
            {
                "id": str(s.id),
                "file_id": str(s.file_id) if s.file_id else None,
                "service_id": str(s.service_id) if s.service_id else None,
                "service_name": s.service_name,
                "unit_price": float(s.unit_price),
                "quantity": s.quantity,
                "total_price": float(s.total_price)
            }
            for s in applied
        ]
    }


# ==========================================================
# Operator: Complete Finishing Work
# ==========================================================

@router.post("/job/{job_id}/complete-finishing")
def complete_operator_finishing(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Marks the manual finishing tasks as completed by the shop operator.
    Sets finishing_status to COMPLETED and finalizes overall order as COMPLETED.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.finishing_status = "COMPLETED"
    job.finishing_completed_at = func.now()
    job.status = JobStatus.COMPLETED
    job.completed_at = func.now()

    db.commit()
    db.refresh(job)
    logger.info(f"Operator completed finishing for job {job_id}. Finishing status: COMPLETED, Job status: {job.status.value}")

    return {
        "success": True,
        "job_id": str(job.job_id),
        "finishing_status": job.finishing_status,
        "status": job.status.value,
        "message": "Finishing work marked as completed."
    }
