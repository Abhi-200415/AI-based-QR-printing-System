from uuid import UUID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ShopOwner,
    ActiveJob
)
from app.services.analytics_service import (
    analytics_dashboard,
    predict_revenue,
    predict_busy_hour,
    get_ai_recommendation
)
from app.services.assignment_service import (
    assign_printer
)
from app.services.ml_prediction_service import (
    train_ml_model_from_db,
    get_ml_model
)

router = APIRouter(
    prefix="/ai",
    tags=["Artificial Intelligence"]
)


# ==========================================================
# AI Dashboard
# ==========================================================

@router.get("/dashboard/{owner_id}")
def ai_dashboard(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    owner = (
        db.query(ShopOwner)
        .filter(ShopOwner.owner_id == owner_id)
        .first()
    )

    if not owner:
        raise HTTPException(
            status_code=404,
            detail="Owner not found."
        )

    return analytics_dashboard(owner_id, db)


# ==========================================================
# AI Printer Recommendation
# ==========================================================

@router.post("/printer/{job_id}")
def recommend_printer(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    printer = assign_printer(job, db)

    if not printer:
        raise HTTPException(
            status_code=404,
            detail="No suitable eligible printer found."
        )

    return {
        "job_id": str(job.job_id),
        "assigned_printer_id": str(printer.printer_id),
        "printer_name": printer.printer_name,
        "estimated_seconds": job.estimated_seconds or 0
    }


# ==========================================================
# ML Model Status & Training Endpoints
# ==========================================================

@router.get("/model-status")
def model_status():
    """
    Check the current AI/ML print time prediction model status.
    """
    model = get_ml_model()
    return {
        "model_loaded": model is not None,
        "model_type": type(model).__name__ if model else "None",
        "fallback_status": "Active (Deterministic domain predictor)",
        "feature_set": [
            "total_pages",
            "total_copies",
            "color_ratio",
            "duplex_ratio",
            "is_a3",
            "is_legal",
            "printer_historical_jobs",
            "printer_queue_length",
            "queue_wait_seconds"
        ],
        "target": "actual_completion_seconds"
    }


@router.post("/train-model")
def train_model(
    db: Session = Depends(get_db)
):
    """
    Trigger training of ML print time prediction model using real completed jobs.
    """
    result = train_ml_model_from_db(db)
    return result


# ==========================================================
# Voice Assistant Telemetry & Command Audit
# ==========================================================

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.utils.logger import logger


class VoiceLogRequest(BaseModel):
    event: str
    command: Optional[str] = None
    intent: Optional[str] = None
    detail: Optional[str] = None


@router.post("/voice-command")
def log_voice_command(payload: VoiceLogRequest):
    """
    Structured server-side terminal logging for voice assistant interactions.
    Streams formatted logs to cloud container stdout/logs.
    """
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    evt = payload.event
    safe_cmd = (payload.command or "").strip()[:100]
    safe_intent = (payload.intent or "UNKNOWN").strip()
    safe_detail = (payload.detail or "").strip()[:150]

    if evt == "MIC_ACTIVATED":
        print(f"[{ts}] [VOICE] Microphone activated", flush=True)
        logger.info("[VOICE] Microphone activated")
    elif evt == "SPEECH_CAPTURED":
        print(f"[{ts}] [VOICE] Speech captured", flush=True)
        print(f"[{ts}] [VOICE] Recognized command: {safe_cmd}", flush=True)
        print(f"[{ts}] [VOICE] Intent identified: {safe_intent}", flush=True)
        logger.info(f"[VOICE] Speech captured: {safe_cmd} (Intent: {safe_intent})")
    elif evt == "EXECUTING":
        print(f"[{ts}] [VOICE] Executing action", flush=True)
        logger.info(f"[VOICE] Executing action: {safe_intent}")
    elif evt == "COMPLETED":
        print(f"[{ts}] [VOICE] Action completed successfully", flush=True)
        logger.info(f"[VOICE] Action completed successfully: {safe_intent}")
    elif evt == "UNCLEAR":
        print(f"[{ts}] [VOICE] Command unclear", flush=True)
        logger.warning(f"[VOICE] Command unclear: {safe_cmd}")
    elif evt == "FAILED":
        print(f"[{ts}] [VOICE] Execution failed: {safe_detail}", flush=True)
        logger.error(f"[VOICE] Execution failed: {safe_detail}")
    elif evt == "RECOGNITION_FAILED":
        print(f"[{ts}] [VOICE] Recognition failed", flush=True)
        logger.warning(f"[VOICE] Recognition failed: {safe_detail}")

    return {"status": "ok", "event": evt}