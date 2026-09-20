from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database.models import JobStatus


# ==========================================
# Queue Response
# ==========================================

class QueueResponse(BaseModel):
    job_id: UUID

    assigned_printer_id: Optional[UUID] = None

    queue_position: Optional[int] = None

    status: JobStatus

    # Estimated seconds is nullable — 0 when not yet calculated
    estimated_seconds: Optional[int] = 0

    queued_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Queue Update
# ==========================================

class QueueUpdate(BaseModel):
    queue_position: Optional[int] = None

    assigned_printer_id: Optional[UUID] = None

    status: Optional[JobStatus] = None