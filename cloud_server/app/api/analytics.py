from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ShopOwner

from app.services.analytics_service import (
    get_dashboard_statistics,
    printer_utilization,
    predict_revenue,
    predict_busy_hour,
    get_ai_recommendation,
    analytics_dashboard
)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# ==========================================================
# Dashboard
# ==========================================================

@router.get("/dashboard/{owner_id}")
def dashboard(
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
# Statistics
# ==========================================================

@router.get("/statistics/{owner_id}")
def statistics(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return get_dashboard_statistics(
        owner_id,
        db
    )


# ==========================================================
# Printer Utilization
# ==========================================================

@router.get("/printers/{owner_id}")
def printers(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return printer_utilization(
        owner_id,
        db
    )


# ==========================================================
# Revenue Prediction
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
# Busy Hour Prediction
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
# AI Recommendation
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