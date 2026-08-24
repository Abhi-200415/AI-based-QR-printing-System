from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database.models import (
    PaymentProvider,
    PaymentMethod,
    PaymentStatus,
)

# ==========================================
# Create Payment
# ==========================================

class PaymentCreate(BaseModel):
    job_id: UUID

    provider: PaymentProvider
    payment_method: PaymentMethod = PaymentMethod.UPI

    amount: Decimal


# ==========================================
# Update Payment
# ==========================================

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None

    transaction_id: Optional[str] = None

    qr_reference: Optional[str] = None

    paid_at: Optional[datetime] = None

    failure_reason: Optional[str] = None


# ==========================================
# Payment Response
# ==========================================

class PaymentResponse(BaseModel):
    payment_id: UUID
    job_id: UUID

    provider: PaymentProvider
    payment_method: PaymentMethod

    amount: Decimal
    currency: str

    status: PaymentStatus

    transaction_id: Optional[str]
    provider_payment_id: Optional[str]

    qr_reference: Optional[str]

    verified: bool
    verified_at: Optional[datetime]

    paid_at: Optional[datetime]

    failure_reason: Optional[str]

    refund_amount: Decimal

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)