from uuid import UUID
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.database.models import JobStatus


# ==========================================
# Queue File Details
# ==========================================

class QueueFileInfo(BaseModel):
    file_id: UUID
    filename: str
    page_count: int = 1
    copies: int = 1
    paper_size: str = "A4"
    orientation: str = "PORTRAIT"
    duplex: bool = False
    print_type: str = "BW"
    color_mode: str = "AUTO"
    assigned_printer_id: Optional[UUID] = None
    assigned_printer_name: Optional[str] = None
    lamination: bool = False
    spiral_binding: bool = False
    finishing_services: List[str] = []
    status: str = "QUEUED"

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Queue Response
# ==========================================

class QueueResponse(BaseModel):
    job_id: UUID

    assigned_printer_id: Optional[UUID] = None
    assigned_printer_name: Optional[str] = None

    queue_position: Optional[int] = None

    status: JobStatus

    # Estimated seconds is nullable — 0 when not yet calculated
    estimated_seconds: Optional[int] = 0

    queued_at: Optional[datetime] = None

    customer_name: Optional[str] = None
    customer_reference: Optional[str] = None
    total_files: int = 1
    total_pages: int = 1
    total_copies: int = 1
    total_amount: float = 0.0
    payment_status: str = "PENDING"
    finishing_status: str = "NONE"
    files: List[QueueFileInfo] = []

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Queue Update
# ==========================================

class QueueUpdate(BaseModel):
    queue_position: Optional[int] = None

    assigned_printer_id: Optional[UUID] = None

    status: Optional[JobStatus] = None