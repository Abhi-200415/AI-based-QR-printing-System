from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Printer,
    PrinterStatus,
    ActiveJob,
    JobStatus
)
from app.schemas.printer import (
    PrinterRegister,
    PrinterResponse,
    PrinterStatusUpdate
)
from app.utils.logger import logger

router = APIRouter(
    prefix="/printer",
    tags=["Printer"]
)


# ==========================================================
# 1. Static Routes First (Prevent Route Shadowing)
# ==========================================================

@router.get("/health")
def printer_health():
    """
    Health check for Printer API. Declared before /{printer_id} to prevent path shadowing.
    """
    return {
        "service": "Printer API",
        "status": "Healthy",
        "version": "1.0.0",
        "message": "Printer service is running successfully."
    }


# ==========================================================
# Register Printer
# ==========================================================

@router.post("/register")
def register_printer(
    data: PrinterRegister,
    db: Session = Depends(get_db)
):
    # Find existing printer by owner_id and printer_name
    printer = (
        db.query(Printer)
        .filter(
            Printer.owner_id == data.owner_id,
            Printer.printer_name == data.printer_name
        )
        .first()
    )

    now = datetime.utcnow()

    if printer:
        # Update existing printer
        printer.printer_model = data.printer_model or printer.printer_model
        printer.printer_type = data.printer_type or printer.printer_type
        printer.is_physical = data.is_physical
        printer.is_virtual = data.is_virtual
        printer.status = PrinterStatus(data.status) if data.status else PrinterStatus.ONLINE
        printer.is_available = data.is_available
        printer.supports_bw = data.supports_bw
        printer.supports_color = data.supports_color
        printer.supports_duplex = data.supports_duplex
        printer.supports_legal = data.supports_legal
        printer.supports_a3 = data.supports_a3
        printer.agent_id = data.agent_id or printer.agent_id
        printer.last_seen = now
    else:
        # Create new printer
        printer = Printer(
            printer_id=uuid4(),
            owner_id=data.owner_id,
            agent_id=data.agent_id,
            printer_name=data.printer_name,
            printer_model=data.printer_model,
            printer_type=data.printer_type or "PHYSICAL",
            is_physical=data.is_physical,
            is_virtual=data.is_virtual,
            status=PrinterStatus(data.status) if data.status else PrinterStatus.ONLINE,
            is_available=data.is_available,
            supports_bw=data.supports_bw,
            supports_color=data.supports_color,
            supports_duplex=data.supports_duplex,
            supports_legal=data.supports_legal,
            supports_a3=data.supports_a3,
            is_default=data.is_default,
            last_seen=now
        )
        db.add(printer)

    db.commit()
    db.refresh(printer)

    return {
        "success": True,
        "printer_id": str(printer.printer_id),
        "printer_name": printer.printer_name,
        "status": printer.status.value,
        "message": "Printer registered/synchronized successfully."
    }


# ==========================================================
# Get All Printers For Owner
# ==========================================================

@router.get("/owner/{owner_id}", response_model=List[PrinterResponse])
def get_printers(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    return (
        db.query(Printer)
        .filter(Printer.owner_id == owner_id)
        .order_by(Printer.printer_name)
        .all()
    )


# ==========================================================
# Get Single Printer / Status Updates
# ==========================================================

@router.get("/{printer_id}", response_model=PrinterResponse)
def get_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):
    printer = db.query(Printer).filter(Printer.printer_id == printer_id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found.")
    return printer


@router.put("/{printer_id}/status")
def update_printer_status(
    printer_id: UUID,
    data: PrinterStatusUpdate,
    db: Session = Depends(get_db)
):
    printer = db.query(Printer).filter(Printer.printer_id == printer_id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found.")

    if data.status:
        printer.status = data.status
    if data.is_available is not None:
        printer.is_available = data.is_available
    if data.current_queue is not None:
        printer.current_queue = data.current_queue

    printer.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(printer)

    return {
        "success": True,
        "printer_id": str(printer.printer_id),
        "status": printer.status.value,
        "is_available": printer.is_available,
        "current_queue": printer.current_queue
    }


@router.delete("/{printer_id}")
def delete_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):
    printer = db.query(Printer).filter(Printer.printer_id == printer_id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found.")

    # Inefficient printer delete guard fixed using SQL count on active jobs
    active_jobs_count = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == printer_id,
            ActiveJob.status.in_([JobStatus.QUEUED, JobStatus.ASSIGNED, JobStatus.PRINTING])
        )
        .count()
    )

    if active_jobs_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete printer with {active_jobs_count} active print jobs."
        )

    db.delete(printer)
    db.commit()

    return {
        "success": True,
        "printer_id": str(printer_id),
        "message": "Printer deleted successfully."
    }


@router.get("/ping/{printer_id}")
def ping_printer(
    printer_id: UUID,
    db: Session = Depends(get_db)
):
    printer = db.query(Printer).filter(Printer.printer_id == printer_id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found.")

    return {
        "printer_id": str(printer.printer_id),
        "printer_name": printer.printer_name,
        "status": printer.status.value,
        "is_available": printer.is_available,
        "is_physical": printer.is_physical,
        "is_virtual": printer.is_virtual,
        "last_seen": printer.last_seen,
        "queue": printer.current_queue or 0
    }