from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from collections import Counter
from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    JobFile,
    Printer,
    JobStatus,
    PaymentStatus,
    PrintType,
    AnalyticsDaily
)
from app.utils.logger import logger


# ==========================================================
# Record Daily Analytics
# ==========================================================

def record_job_completion_analytics(
    job: ActiveJob,
    db: Session
):
    """
    Update or create AnalyticsDaily record for this owner and date when a job completes.
    """
    today = date.today()
    owner_id = job.owner_id

    daily = (
        db.query(AnalyticsDaily)
        .filter(
            AnalyticsDaily.owner_id == owner_id,
            AnalyticsDaily.analytics_date == today
        )
        .first()
    )

    if not daily:
        daily = AnalyticsDaily(
            owner_id=owner_id,
            analytics_date=today,
            total_jobs=0,
            completed_jobs=0,
            failed_jobs=0,
            cancelled_jobs=0,
            total_files=0,
            total_pages=0,
            total_copies=0,
            bw_pages=0,
            color_pages=0,
            total_revenue=Decimal("0.00")
        )
        db.add(daily)

    daily.total_jobs = (daily.total_jobs or 0) + 1
    if job.status == JobStatus.COMPLETED:
        daily.completed_jobs = (daily.completed_jobs or 0) + 1
        daily.total_files = (daily.total_files or 0) + (job.total_files or len(job.files or []))
        daily.total_pages = (daily.total_pages or 0) + (job.total_pages or 0)
        daily.total_copies = (daily.total_copies or 0) + (job.total_copies or 1)

        # Count color vs bw
        files = job.files or []
        for f in files:
            pcount = (f.page_count or 1) * (f.copies or 1)
            if f.print_type in (PrintType.COLOR, PrintType.MIXED):
                daily.color_pages = (daily.color_pages or 0) + pcount
            else:
                daily.bw_pages = (daily.bw_pages or 0) + pcount

        if job.payment_status == PaymentStatus.PAID and job.total_amount:
            daily.total_revenue = (daily.total_revenue or Decimal("0.00")) + Decimal(str(job.total_amount))

    elif job.status == JobStatus.FAILED:
        daily.failed_jobs = (daily.failed_jobs or 0) + 1
    elif job.status == JobStatus.CANCELLED:
        daily.cancelled_jobs = (daily.cancelled_jobs or 0) + 1

    db.commit()


# ==========================================================
# Dashboard Statistics
# ==========================================================

def get_dashboard_statistics(
    owner_id,
    db: Session
) -> Dict[str, Any]:
    jobs = (
        db.query(ActiveJob)
        .filter(ActiveJob.owner_id == owner_id)
        .all()
    )

    printers = (
        db.query(Printer)
        .filter(Printer.owner_id == owner_id)
        .all()
    )

    total_jobs = len(jobs)
    completed_jobs = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
    pending_jobs = sum(1 for j in jobs if j.status in (JobStatus.PENDING, JobStatus.QUEUED, JobStatus.ASSIGNED))
    printing_jobs = sum(1 for j in jobs if j.status == JobStatus.PRINTING)
    failed_jobs = sum(1 for j in jobs if j.status == JobStatus.FAILED)
    cancelled_jobs = sum(1 for j in jobs if j.status == JobStatus.CANCELLED)

    total_pages = sum((j.total_pages or 0) for j in jobs if j.status == JobStatus.COMPLETED)
    total_revenue = sum(
        Decimal(str(j.total_amount or 0))
        for j in jobs
        if j.payment_status == PaymentStatus.PAID
    )

    # Average completion time in seconds for completed jobs
    durations = []
    for j in jobs:
        if j.status == JobStatus.COMPLETED and j.started_at and j.completed_at:
            dur = (j.completed_at - j.started_at).total_seconds()
            if 0 < dur < 3600:
                durations.append(dur)

    avg_completion_time = round(sum(durations) / len(durations), 1) if durations else 0.0

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "pending_jobs": pending_jobs,
        "printing_jobs": printing_jobs,
        "failed_jobs": failed_jobs,
        "cancelled_jobs": cancelled_jobs,
        "total_pages": total_pages,
        "total_revenue": float(total_revenue),
        "average_completion_seconds": avg_completion_time,
        "total_printers": len(printers),
        "online_printers": sum(1 for p in printers if p.status.value.lower() == "online")
    }


# ==========================================================
# Printer Utilization
# ==========================================================

def printer_utilization(
    owner_id,
    db: Session
) -> List[Dict[str, Any]]:
    printers = (
        db.query(Printer)
        .filter(Printer.owner_id == owner_id)
        .all()
    )

    result = []
    for printer in printers:
        result.append({
            "printer_id": str(printer.printer_id),
            "printer_name": printer.printer_name,
            "jobs_printed": printer.total_jobs_printed or 0,
            "current_queue": printer.current_queue or 0,
            "status": printer.status.value,
            "is_available": printer.is_available
        })

    return result


# ==========================================================
# AI Revenue Prediction
# ==========================================================

def predict_revenue(
    owner_id,
    db: Session
) -> Decimal:
    jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.owner_id == owner_id,
            ActiveJob.status == JobStatus.COMPLETED,
            ActiveJob.payment_status == PaymentStatus.PAID
        )
        .all()
    )

    if not jobs:
        return Decimal("0.00")

    revenue = sum(
        Decimal(str(job.total_amount or 0))
        for job in jobs
    )

    average = revenue / Decimal(str(len(jobs)))
    # Estimate 30-day projection based on average daily rate
    return round(average * Decimal("30"), 2)


# ==========================================================
# AI Busy Hour Prediction
# ==========================================================

def predict_busy_hour(
    owner_id,
    db: Session
) -> Optional[int]:
    jobs = (
        db.query(ActiveJob)
        .filter(ActiveJob.owner_id == owner_id)
        .all()
    )

    hours = [j.created_at.hour for j in jobs if j.created_at]
    if not hours:
        return None

    return Counter(hours).most_common(1)[0][0]


# ==========================================================
# AI Business Recommendation
# ==========================================================

def get_ai_recommendation(
    owner_id,
    db: Session
) -> List[str]:
    stats = get_dashboard_statistics(owner_id, db)
    recommendations = []

    if stats["failed_jobs"] > 0:
        recommendations.append(f"Investigate {stats['failed_jobs']} failed jobs to resolve paper jams or driver issues.")

    if stats["pending_jobs"] > 10:
        recommendations.append("High queue backlog detected. Ensure all print agents are online.")

    if stats["total_pages"] > 500:
        recommendations.append("High printing volume: schedule preventive maintenance and ink checks.")

    if not recommendations:
        recommendations.append("System is operating smoothly with healthy queue and completion rates.")

    return recommendations


# ==========================================================
# Full Analytics Dashboard Data
# ==========================================================

def analytics_dashboard(
    owner_id,
    db: Session
) -> Dict[str, Any]:
    return {
        "statistics": get_dashboard_statistics(owner_id, db),
        "printer_utilization": printer_utilization(owner_id, db),
        "predicted_monthly_revenue": float(predict_revenue(owner_id, db)),
        "predicted_busy_hour": predict_busy_hour(owner_id, db),
        "ai_recommendations": get_ai_recommendation(owner_id, db)
    }