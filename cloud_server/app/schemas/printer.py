from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database.models import PrinterStatus


# ==========================================================
# Create / Register Printer
# ==========================================================

class PrinterCreate(BaseModel):

    # ------------------------------------------------------
    # Owner / Agent
    # ------------------------------------------------------

    owner_id: UUID

    agent_id: str

    # ------------------------------------------------------
    # Printer Information
    # ------------------------------------------------------

    printer_name: str

    printer_model: Optional[str] = None

    printer_type: Optional[str] = None

    # ------------------------------------------------------
    # Physical / Virtual
    # ------------------------------------------------------

    is_physical: bool = True

    is_virtual: bool = False

    # ------------------------------------------------------
    # Availability
    # ------------------------------------------------------

    is_available: bool = False

    # ------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------

    supports_bw: bool = True

    supports_color: bool = False

    supports_duplex: bool = False

    supports_a3: bool = False

    supports_legal: bool = False

    # ------------------------------------------------------
    # Default Printer
    # ------------------------------------------------------

    is_default: bool = False


# ==========================================================
# Update Printer
# ==========================================================

class PrinterUpdate(BaseModel):

    printer_name: Optional[str] = None

    printer_model: Optional[str] = None

    printer_type: Optional[str] = None

    is_physical: Optional[bool] = None

    is_virtual: Optional[bool] = None

    is_available: Optional[bool] = None

    supports_bw: Optional[bool] = None

    supports_color: Optional[bool] = None

    supports_duplex: Optional[bool] = None

    supports_a3: Optional[bool] = None

    supports_legal: Optional[bool] = None

    is_default: Optional[bool] = None


# ==========================================================
# Update Printer Status
# ==========================================================

class PrinterStatusUpdate(BaseModel):

    status: PrinterStatus

    current_queue: int = 0


# ==========================================================
# Printer Response
# ==========================================================

class PrinterResponse(BaseModel):

    # ------------------------------------------------------
    # IDs
    # ------------------------------------------------------

    printer_id: UUID

    owner_id: UUID

    agent_id: Optional[str] = None

    # ------------------------------------------------------
    # Printer Information
    # ------------------------------------------------------

    printer_name: str

    printer_model: Optional[str] = None

    printer_type: Optional[str] = None

    # ------------------------------------------------------
    # Physical / Virtual
    # ------------------------------------------------------

    is_physical: bool

    is_virtual: bool

    # ------------------------------------------------------
    # Availability
    # ------------------------------------------------------

    is_available: bool

    # ------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------

    supports_bw: bool

    supports_color: bool

    supports_duplex: bool

    supports_a3: bool

    supports_legal: bool

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    status: PrinterStatus

    current_queue: int

    # ------------------------------------------------------
    # Default
    # ------------------------------------------------------

    is_default: bool

    # ------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------

    last_seen: Optional[datetime] = None

    created_at: datetime

    updated_at: datetime

    # ------------------------------------------------------
    # SQLAlchemy → Pydantic
    # ------------------------------------------------------

    model_config = ConfigDict(
        from_attributes=True
    )