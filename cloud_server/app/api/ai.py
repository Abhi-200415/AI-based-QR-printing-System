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
    assign_best_printer
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
        .filter(
            ShopOwner.owner_id == owner_id
        )
        .first()
    )

    if not owner:
        raise HTTPException(
            status_code=404,
            detail="Owner not found."
        )

    return analytics_dashboard(
        owner_id,
        db
    )


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
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    printer = assign_best_printer(
        job,
        db
    )

    if not printer:
        raise HTTPException(
            status_code=404,
            detail="No suitable printer found."
        )

    return {

        "recommended_printer": printer.printer_name,

        "printer_id": str(printer.printer_id),

        "supports_color": printer.supports_color,

        "supports_duplex": printer.supports_duplex,

        "current_queue": printer.current_queue
    }


# ==========================================================
# AI Revenue Prediction
# ==========================================================

@router.get("/prediction/revenue/{owner_id}")
def revenue_prediction(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return {

        "predicted_monthly_revenue":

        predict_revenue(
            owner_id,
            db
        )
    }


# ==========================================================
# AI Busy Hour Prediction
# ==========================================================

@router.get("/prediction/busy-hour/{owner_id}")
def busy_hour_prediction(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return {

        "predicted_busy_hour":

        predict_busy_hour(
            owner_id,
            db
        )
    }


# ==========================================================
# AI Business Recommendation
# ==========================================================

@router.get("/recommendation/{owner_id}")
def recommendation(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return {

        "recommendation":

        get_ai_recommendation(
            owner_id,
            db
        )
    }


# ==========================================================
# Future AI Features
# ==========================================================

@router.get("/future")
def future_ai():

    return {

        "planned_features": [

            "AI Color Detection",

            "AI OCR",

            "Semantic Document Search",

            "AI Print Cost Optimization",

            "AI Queue Optimization"
        ]
    }