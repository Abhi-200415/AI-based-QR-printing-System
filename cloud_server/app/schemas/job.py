from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database.models import (
    JobStatus,
    PaymentStatus
)


# ==========================================
# Create Job
# ==========================================

class JobCreate(BaseModel):

    customer_name: Optional[str] = None

    customer_phone: Optional[str] = None


# ==========================================
# Update Job
# ==========================================

class JobUpdate(BaseModel):

    status: Optional[JobStatus] = None

    payment_status: Optional[PaymentStatus] = None

    assigned_printer_id: Optional[UUID] = None

    queue_position: Optional[int] = None


# ==========================================
# Job Response
# ==========================================

class JobResponse(BaseModel):

    job_id: UUID

    owner_id: UUID

    assigned_printer_id: Optional[UUID] = None

    customer_name: Optional[str] = None

    customer_phone: Optional[str] = None

    status: JobStatus

    payment_status: PaymentStatus

    queue_position: Optional[int] = None

    total_files: int = 0

    total_pages: int = 0

    total_copies: int = 0

    subtotal: Decimal = Decimal("0.00")

    tax: Decimal = Decimal("0.00")

    total_amount: Decimal = Decimal("0.00")

    # ------------------------------------------------------
    # Printing time is not known when a job is first created
    # ------------------------------------------------------

    estimated_seconds: Optional[int] = 0

    created_at: datetime

    queued_at: Optional[datetime] = None

    started_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )