from collections import Counter
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    Printer,
    JobStatus
)


# ==========================================================
# Dashboard Statistics
# ==========================================================

def get_dashboard_statistics(
    owner_id,
    db: Session
):

    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.owner_id == owner_id
        )
        .all()
    )

    printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == owner_id
        )
        .all()
    )

    total_jobs = len(jobs)

    completed_jobs = sum(
        job.status == JobStatus.COMPLETED
        for job in jobs
    )

    pending_jobs = sum(
        job.status == JobStatus.PENDING
        for job in jobs
    )

    failed_jobs = sum(
        job.status == JobStatus.FAILED
        for job in jobs
    )

    revenue = sum(
        Decimal(job.total_amount)
        for job in jobs
    )

    pages = sum(
        job.total_pages
        for job in jobs
    )

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "pending_jobs": pending_jobs,
        "failed_jobs": failed_jobs,
        "total_pages": pages,
        "total_revenue": revenue,
        "total_printers": len(printers)
    }


# ==========================================================
# Printer Utilization
# ==========================================================

def printer_utilization(
    owner_id,
    db: Session
):

    printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == owner_id
        )
        .all()
    )

    result = []

    for printer in printers:

        result.append({
            "printer_name": printer.printer_name,
            "jobs_printed": printer.total_jobs_printed,
            "current_queue": printer.current_queue,
            "status": printer.status.value
        })

    return result


# ==========================================================
# AI Revenue Prediction
# ==========================================================

def predict_revenue(
    owner_id,
    db: Session
):

    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.owner_id == owner_id,
            ActiveJob.status == JobStatus.COMPLETED
        )
        .all()
    )

    if not jobs:
        return Decimal("0.00")

    revenue = sum(
        Decimal(job.total_amount)
        for job in jobs
    )

    average = revenue / len(jobs)

    prediction = average * Decimal("30")

    return prediction


# ==========================================================
# AI Busy Hour Prediction
# ==========================================================

def predict_busy_hour(
    owner_id,
    db: Session
):

    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.owner_id == owner_id
        )
        .all()
    )

    hours = []

    for job in jobs:

        if job.created_at:
            hours.append(
                job.created_at.hour
            )

    if not hours:
        return None

    return Counter(hours).most_common(1)[0][0]


# ==========================================================
# AI Business Recommendation
# ==========================================================

def get_ai_recommendation(
    owner_id,
    db: Session
):

    stats = get_dashboard_statistics(
        owner_id,
        db
    )

    recommendation = []

    if stats["failed_jobs"] > 5:
        recommendation.append(
            "Investigate printer failures."
        )

    if stats["pending_jobs"] > 20:
        recommendation.append(
            "Queue is busy. Consider adding another printer."
        )

    if stats["total_pages"] > 5000:
        recommendation.append(
            "High print volume detected."
        )

    if not recommendation:
        recommendation.append(
            "Printing performance is healthy."
        )

    return recommendation


# ==========================================================
# AI Analytics Dashboard
# ==========================================================

def analytics_dashboard(
    owner_id,
    db: Session
):

    return {

        "statistics":
            get_dashboard_statistics(
                owner_id,
                db
            ),

        "printer_utilization":
            printer_utilization(
                owner_id,
                db
            ),

        "predicted_monthly_revenue":
            predict_revenue(
                owner_id,
                db
            ),

        "predicted_busy_hour":
            predict_busy_hour(
                owner_id,
                db
            ),

        "ai_recommendation":
            get_ai_recommendation(
                owner_id,
                db
            )
    }