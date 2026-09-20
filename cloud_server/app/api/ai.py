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