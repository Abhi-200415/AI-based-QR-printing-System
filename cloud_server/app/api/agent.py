from uuid import UUID
from datetime import datetime
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Body
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Printer,
    PrinterStatus
)
from app.utils.logger import logger

router = APIRouter(
    prefix="/agent",
    tags=["Print Agent"]
)


# ==========================================================
# Request Schemas
# ==========================================================

class AgentRegisterPayload(BaseModel):
    owner_id: UUID
    agent_id: str
    printer_names: Optional[List[str]] = []


class AgentHeartbeatPayload(BaseModel):
    owner_id: UUID
    agent_id: str


# ==========================================================
# 1. Static Routes First
# ==========================================================

@router.get("/health")
def agent_health():
    return {
        "service": "Print Agent API",
        "status": "Healthy",
        "message": "Agent service is running."
    }


# ==========================================================
# Register Agent
# ==========================================================

@router.post("/register")
def register_agent(
    payload: Optional[AgentRegisterPayload] = None,
    owner_id: Optional[UUID] = None,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    final_owner_id = payload.owner_id if payload else owner_id
    final_agent_id = payload.agent_id if payload else agent_id

    if not final_owner_id or not final_agent_id:
        raise HTTPException(
            status_code=400,
            detail="owner_id and agent_id are required for agent registration."
        )

    printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == final_owner_id,
            Printer.agent_id == final_agent_id
        )
        .all()
    )

    now = datetime.utcnow()
    for printer in printers:
        printer.last_seen = now
        # Keep existing offline printers offline unless explicitly re-registered
        if printer.status != PrinterStatus.OFFLINE:
            printer.status = PrinterStatus.ONLINE
            printer.is_available = True

    db.commit()

    logger.info(f"Registered Agent {final_agent_id} for Owner {final_owner_id} with {len(printers)} printers.")

    return {
        "success": True,
        "message": "Agent registered and printers synchronized.",
        "agent_id": final_agent_id,
        "printers_count": len(printers),
        "available_printers": sum(1 for p in printers if p.is_available)
    }


# ==========================================================
# Agent Heartbeat
# ==========================================================

@router.post("/heartbeat")
def heartbeat(
    payload: Optional[AgentHeartbeatPayload] = None,
    owner_id: Optional[UUID] = None,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    final_owner_id = payload.owner_id if payload else owner_id
    final_agent_id = payload.agent_id if payload else agent_id

    if not final_owner_id or not final_agent_id:
        raise HTTPException(
            status_code=400,
            detail="owner_id and agent_id are required for heartbeat."
        )

    printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == final_owner_id,
            Printer.agent_id == final_agent_id
        )
        .all()
    )

    now = datetime.utcnow()
    for printer in printers:
        printer.last_seen = now
        # Do not force offline printers to online during periodic heartbeat
        if printer.status == PrinterStatus.OFFLINE:
            printer.is_available = False
            continue
        if printer.status != PrinterStatus.BUSY:
            printer.status = PrinterStatus.ONLINE
            printer.is_available = True

    db.commit()

    return {
        "success": True,
        "message": "Heartbeat received.",
        "agent_id": final_agent_id,
        "printers_count": len(printers)
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
        .filter(Printer.agent_id == agent_id)
        .all()
    )

    if not printers:
        return {
            "agent_id": agent_id,
            "online": False,
            "printers": []
        }

    return {
        "agent_id": agent_id,
        "online": True,
        "printers": [
            {
                "printer_id": str(printer.printer_id),
                "printer_name": printer.printer_name,
                "status": printer.status.value,
                "is_available": printer.is_available,
                "queue": printer.current_queue or 0,
                "last_seen": printer.last_seen
            }
            for printer in printers
        ]
    }
