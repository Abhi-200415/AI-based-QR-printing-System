from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ==========================================================
# Create Finishing Service
# ==========================================================

class FinishingServiceCreate(BaseModel):
    service_name: str
    description: Optional[str] = None
    price: Decimal
    charge_type: str = "PER_ORDER"
    is_enabled: bool = True


# ==========================================================
# Update Finishing Service
# ==========================================================

class FinishingServiceUpdate(BaseModel):
    service_name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    charge_type: Optional[str] = None
    is_enabled: Optional[bool] = None


# ==========================================================
# Finishing Service Response
# ==========================================================

class FinishingServiceResponse(BaseModel):
    service_id: UUID
    owner_id: UUID
    service_name: str
    description: Optional[str] = None
    price: Decimal
    charge_type: str
    is_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )


# ==========================================================
# Customer Service Selection Request
# ==========================================================

class JobFinishingServiceItem(BaseModel):
    service_id: UUID
    quantity: int = 1
    file_id: Optional[UUID] = None


class JobFinishingSelectRequest(BaseModel):
    customer_reference: Optional[str] = None
    services: List[JobFinishingServiceItem] = []


# ==========================================================
# Job Finishing Service Snapshot Response
# ==========================================================

class JobFinishingServiceResponse(BaseModel):
    id: UUID
    job_id: Optional[UUID] = None
    file_id: Optional[UUID] = None
    service_id: Optional[UUID] = None
    service_name: str
    unit_price: Decimal
    quantity: int
    total_price: Decimal
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )
