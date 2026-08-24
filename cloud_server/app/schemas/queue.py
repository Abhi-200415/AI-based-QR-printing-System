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

    assigned_printer_id: Optional[UUID]

    queue_position: int

    status: JobStatus

    estimated_seconds: int

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Queue Update
# ==========================================

class QueueUpdate(BaseModel):
    queue_position: Optional[int] = None

    assigned_printer_id: Optional[UUID] = None

    status: Optional[JobStatus] = None