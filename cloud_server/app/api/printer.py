from uuid import UUID
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.database.models import (
    Printer,
    PrinterStatus
)

from app.schemas.printer import (
    PrinterCreate,
    PrinterUpdate,
    PrinterStatusUpdate,
    PrinterResponse
)


router = APIRouter(
    prefix="/printer",
    tags=["Printer"]
)


# ==========================================================
# Register / Update Printer
# ==========================================================

@router.post("/register")
def register_printer(
    printer: PrinterCreate,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(Printer)
        .filter(
            Printer.agent_id == printer.agent_id,
            Printer.printer_name == printer.printer_name
        )
        .first()
    )

    # ======================================================
    # Update Existing Printer
    # ======================================================

    if existing:

        existing.owner_id = printer.owner_id

        existing.printer_name = printer.printer_name

        existing.printer_model = printer.printer_model

        existing.printer_type = printer.printer_type

        # --------------------------------------------------
        # Physical / Virtual
        # --------------------------------------------------

        existing.is_physical = printer.is_physical

        existing.is_virtual = printer.is_virtual

        # --------------------------------------------------
        # Availability
        # --------------------------------------------------

        existing.is_available = printer.is_available

        # --------------------------------------------------
        # Capabilities
        # --------------------------------------------------

        existing.supports_bw = printer.supports_bw

        existing.supports_color = printer.supports_color

        existing.supports_duplex = printer.supports_duplex

        existing.supports_a3 = printer.supports_a3

        existing.supports_legal = printer.supports_legal

        # --------------------------------------------------
        # Default
        # --------------------------------------------------

        existing.is_default = printer.is_default

        # --------------------------------------------------
        # Status
        # --------------------------------------------------

        existing.status = (
            PrinterStatus.ONLINE
            if printer.is_available
            else PrinterStatus.OFFLINE
        )

        existing.last_seen = datetime.utcnow()

        db.commit()

        db.refresh(existing)

        return {

            "success": True,

            "printer_id":
                str(existing.printer_id),

            "printer_name":
                existing.printer_name,

            "is_physical":
                existing.is_physical,

            "is_virtual":
                existing.is_virtual,

            "is_available":
                existing.is_available,

            "status":
                existing.status.value,

            "message":
                "Printer updated successfully."

        }

    # ======================================================
    # Register New Printer
    # ======================================================

    new_printer = Printer(

        owner_id=printer.owner_id,

        printer_name=printer.printer_name,

        printer_model=printer.printer_model,

        printer_type=printer.printer_type,

        # --------------------------------------------------
        # Physical / Virtual
        # --------------------------------------------------

        is_physical=printer.is_physical,

        is_virtual=printer.is_virtual,

        # --------------------------------------------------
        # Availability
        # --------------------------------------------------

        is_available=printer.is_available,

        # --------------------------------------------------
        # Capabilities
        # --------------------------------------------------

        supports_bw=printer.supports_bw,

        supports_color=printer.supports_color,

        supports_duplex=printer.supports_duplex,

        supports_a3=printer.supports_a3,

        supports_legal=printer.supports_legal,

        # --------------------------------------------------
        # Agent
        # --------------------------------------------------

        agent_id=printer.agent_id,

        # --------------------------------------------------
        # Default
        # --------------------------------------------------

        is_default=printer.is_default,

        # --------------------------------------------------
        # Status
        # --------------------------------------------------

        status=(
            PrinterStatus.ONLINE
            if printer.is_available
            else PrinterStatus.OFFLINE
        ),

        last_seen=datetime.utcnow()

    )

    db.add(new_printer)

    db.commit()

    db.refresh(new_printer)

    return {

        "success": True,

        "printer_id":
            str(new_printer.printer_id),

        "printer_name":
            new_printer.printer_name,

        "is_physical":
            new_printer.is_physical,

        "is_virtual":
            new_printer.is_virtual,

        "is_available":
            new_printer.is_available,

        "status":
            new_printer.status.value,

        "message":
            "Printer registered successfully."

    }


# ==========================================================
# Get All Printers For Owner
# ==========================================================

@router.get(
    "/owner/{owner_id}",
    response_model=list[PrinterResponse]
)
def get_printers(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return (
        db.query(Printer)
        .filter(
            Printer.owner_id == owner_id
        )
        .order_by(
            Printer.printer_name
        )
        .all()
    )


# ==========================================================
# Get Single Printer
# ==========================================================

@router.get(
    "/{printer_id}",
    response_model=PrinterResponse
)
def get_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:

        raise HTTPException(
            status_code=404,
            detail="Printer not found."
        )

    return printer


# ==========================================================
# Update Printer
# ==========================================================

@router.put(
    "/{printer_id}"
)
def update_printer(
    printer_id: UUID,
    data: PrinterUpdate,
    db: Session = Depends(get_db)
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:

        raise HTTPException(
            status_code=404,
            detail="Printer not found."
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():

        setattr(
            printer,
            field,
            value
        )

    printer.updated_at = datetime.utcnow()

    db.commit()

    db.refresh(printer)

    return {

        "success": True,

        "printer_id":
            str(printer.printer_id),

        "printer_name":
            printer.printer_name,

        "message":
            "Printer updated successfully."

    }


# ==========================================================
# Update Printer Status
# ==========================================================

@router.put(
    "/{printer_id}/status"
)
def update_printer_status(
    printer_id: UUID,
    data: PrinterStatusUpdate,
    db: Session = Depends(get_db)
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:

        raise HTTPException(
            status_code=404,
            detail="Printer not found."
        )

    printer.status = data.status

    printer.current_queue = data.current_queue

    printer.last_seen = datetime.utcnow()

    # ------------------------------------------------------
    # Availability follows actual status
    # ------------------------------------------------------

    printer.is_available = (
        data.status == PrinterStatus.ONLINE
        or data.status == PrinterStatus.BUSY
    )

    db.commit()

    db.refresh(printer)

    return {

        "success": True,

        "printer_id":
            str(printer.printer_id),

        "status":
            printer.status.value,

        "is_available":
            printer.is_available,

        "current_queue":
            printer.current_queue,

        "message":
            "Printer status updated successfully."

    }


# ==========================================================
# Set Default Printer
# ==========================================================

@router.put(
    "/{printer_id}/default"
)
def set_default_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:

        raise HTTPException(
            status_code=404,
            detail="Printer not found."
        )

    db.query(Printer).filter(
        Printer.owner_id == printer.owner_id
    ).update(
        {
            "is_default": False
        }
    )

    printer.is_default = True

    printer.updated_at = datetime.utcnow()

    db.commit()

    db.refresh(printer)

    return {

        "success": True,

        "printer_id":
            str(printer.printer_id),

        "printer_name":
            printer.printer_name,

        "message":
            "Default printer updated successfully."

    }


# ==========================================================
# Delete Printer
# ==========================================================

@router.delete(
    "/{printer_id}"
)
def delete_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:

        raise HTTPException(
            status_code=404,
            detail="Printer not found."
        )

    # ------------------------------------------------------
    # Prevent deletion if jobs are assigned
    # ------------------------------------------------------

    if len(printer.jobs) > 0:

        raise HTTPException(
            status_code=400,
            detail="Printer has active jobs."
        )

    db.delete(printer)

    db.commit()

    return {

        "success": True,

        "printer_id":
            str(printer_id),

        "message":
            "Printer deleted successfully."

    }


# ==========================================================
# Printer Health
# ==========================================================

@router.get(
    "/health"
)
def printer_health():

    return {

        "service": "Printer API",

        "status": "Healthy",

        "version": "1.0.0",

        "message":
            "Printer service is running successfully."

    }


# ==========================================================
# Ping Printer
# ==========================================================

@router.get(
    "/ping/{printer_id}"
)
def ping_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):

    printer = (
        db.query(Printer)
        .filter(
            Printer.printer_id == printer_id
        )
        .first()
    )

    if not printer:

        raise HTTPException(
            status_code=404,
            detail="Printer not found."
        )

    return {

        "printer_id":
            str(printer.printer_id),

        "printer_name":
            printer.printer_name,

        "status":
            printer.status.value,

        "is_available":
            printer.is_available,

        "is_physical":
            printer.is_physical,

        "is_virtual":
            printer.is_virtual,

        "last_seen":
            printer.last_seen,

        "queue":
            printer.current_queue

    }