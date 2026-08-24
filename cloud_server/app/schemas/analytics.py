from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ==========================================
# Analytics Response
# ==========================================

class AnalyticsResponse(BaseModel):
    owner_id: UUID

    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    cancelled_jobs: int

    total_pages: int
    bw_pages: int
    color_pages: int

    total_revenue: Decimal

    successful_payments: int
    failed_payments: int

    peak_queue_length: int

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# AI Prediction Response
# ==========================================

class PredictionResponse(BaseModel):
    predicted_jobs: int
    predicted_pages: int
    predicted_revenue: Decimal

    predicted_peak_hour: Optional[int]

    business_insight: Optional[str]