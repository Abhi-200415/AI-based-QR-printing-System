from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import (
    PaperSize,
    Orientation,
    PrintType,
)


# ==========================================================
# Update File Settings
# ==========================================================

class FileSettingsUpdate(BaseModel):

    copies: int = Field(
        default=1,
        ge=1
    )

    paper_size: PaperSize = PaperSize.A4

    orientation: Orientation = Orientation.PORTRAIT

    print_type: PrintType = PrintType.BW

    duplex: bool = False

    page_ranges: Optional[str] = None

    # Used only when print_type = MIXED
    # Example: "2-5,8,10-12"
    color_page_ranges: Optional[str] = None


# ==========================================================
# File Response
# ==========================================================

class FileResponse(BaseModel):

    file_id: UUID
    job_id: UUID

    # File Information
    original_filename: str
    stored_filename: Optional[str] = None
    file_path: Optional[str] = None

    file_type: str
    file_size: int

    # Document Information
    page_count: int
    copies: int

    # Paper Settings
    paper_size: PaperSize
    orientation: Orientation

    # Print Settings
    print_type: PrintType
    duplex: bool

    color_mode: str

    # Page Selection
    page_ranges: Optional[str] = None

    # Mixed Printing
    color_page_ranges: Optional[str] = None
    bw_pages: int
    color_pages: int

    # AI
    ai_color_detected: bool

    # Pricing
    estimated_cost: Decimal

    # Print Status
    print_completed: bool

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )