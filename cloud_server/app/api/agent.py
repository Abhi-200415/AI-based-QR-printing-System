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

from app.services.physical_printer_service import (
    check_printer_available
)


router = APIRouter(
    prefix="/agent",
    tags=["Print Agent"]
)


# ==========================================================
# Check All Printers
# ==========================================================

def synchronize_printers(
    printers
):

    available_count = 0

    for printer in printers:

        # --------------------------------------------------
        # Physical / Windows availability
        # --------------------------------------------------

        available = check_printer_available(
            printer.printer_name,
            printer.printer_type
        )

        printer.is_available = available

        # --------------------------------------------------
        # Update status
        # --------------------------------------------------

        if available:

            # Do not overwrite BUSY
            # when a job is currently printing.

            if printer.status != PrinterStatus.BUSY:

                printer.status = PrinterStatus.ONLINE

            available_count += 1

        else:

            # Do not leave a disconnected printer ONLINE.

            if printer.status != PrinterStatus.BUSY:

                printer.status = PrinterStatus.OFFLINE

    return available_count


# ==========================================================
# Synchronize Printer Capabilities
# ==========================================================

def synchronize_printer_capabilities(printers):

    updated = 0

    for printer in printers:

        try:

            from app.services.printer_capability_service import (
                get_printer_capabilities
            )

            result = get_printer_capabilities(
                printer.printer_name
            )

        except Exception:

            continue

        # ----------------------------------------------
        # Never overwrite existing values when the
        # Windows capability query fails or times out.
        # ----------------------------------------------

        if not result.get("success"):

            continue

        # ----------------------------------------------
        # B&W
        # ----------------------------------------------

        printer.supports_bw = True

        # ----------------------------------------------
        # Color
        # ----------------------------------------------

        if result.get("color") is True:

            printer.supports_color = True

        else:

            printer.supports_color = False

        # ----------------------------------------------
        # Duplex
        # ----------------------------------------------

        if result.get("duplex") is True:

            printer.supports_duplex = True

        else:

            printer.supports_duplex = False

        # ----------------------------------------------
        # Legal
        # ----------------------------------------------

        paper_sizes = [
            str(x).lower()
            for x in result.get(
                "paper_sizes",
                []
            )
        ]

        printer.supports_legal = any(
            "legal" in paper
            for paper in paper_sizes
        )

        # ----------------------------------------------
        # A3
        # ----------------------------------------------

        printer.supports_a3 = any(
            "a3" in paper
            for paper in paper_sizes
        )

        updated += 1

    return updated

# ==========================================================
# Register Agent
# ==========================================================

@router.post("/register")
def register_agent(

    owner_id: UUID,

    agent_id: str,

    db: Session = Depends(get_db)

):

    printers = (

        db.query(Printer)

        .filter(

            Printer.owner_id == owner_id,

            Printer.agent_id == agent_id

        )

        .all()

    )

    if not printers:

        raise HTTPException(

            status_code=404,

            detail="Agent not registered."

        )

    available_count = synchronize_printers(
        printers
    )

    capability_count = synchronize_printer_capabilities(
        printers
    )

    now = datetime.utcnow()

    for printer in printers:

        printer.last_seen = now

    db.commit()

    return {

        "success": True,

        "message": "Agent connected.",

        "printers": len(printers),

        "available_printers":
            available_count,

        "capabilities_updated":
            capability_count

    }


# ==========================================================
# Agent Heartbeat
# ==========================================================

@router.post("/heartbeat")
def heartbeat(

    owner_id: UUID,

    agent_id: str,

    db: Session = Depends(get_db)

):

    printers = (

        db.query(Printer)

        .filter(

            Printer.owner_id == owner_id,

            Printer.agent_id == agent_id

        )

        .all()

    )

    if not printers:

        raise HTTPException(

            status_code=404,

            detail="Agent not found."

        )

    available_count = synchronize_printers(
        printers
    )

    now = datetime.utcnow()

    for printer in printers:

        printer.last_seen = now

    db.commit()

    return {

        "success": True,

        "message": "Heartbeat received.",

        "printers": len(printers),

        "available_printers":
            available_count

    }


# ==========================================================
# Agent Status
# ==========================================================

@router.get("/status/{agent_id}")
def agent_status(

    agent_id: str,

    db: Session = Depends(get_db)

):

    printers = (

        db.query(Printer)

        .filter(

            Printer.agent_id == agent_id

        )

        .all()

    )

    if not printers:

        raise HTTPException(

            status_code=404,

            detail="Agent not found."

        )

    # Synchronize before reporting status

    synchronize_printers(
        printers
    )

    db.commit()

    return {

        "agent_id": agent_id,

        "online": True,

        "printers": [

            {

                "printer_id":
                    str(printer.printer_id),

                "printer_name":
                    printer.printer_name,

                "status":
                    printer.status.value,

                "is_available":
                    printer.is_available,

                "queue":
                    printer.current_queue,

                "last_seen":
                    printer.last_seen

            }

            for printer in printers

        ]

    }


# ==========================================================
# Agent Health
# ==========================================================

@router.get("/health")
def health():

    return {

        "service": "Print Agent API",

        "status": "Healthy",

        "message":
            "Agent service is running."

    }



