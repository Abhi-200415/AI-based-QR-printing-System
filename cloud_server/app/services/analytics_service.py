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
    Payment,
    PaymentStatus,
    PaymentMethod,
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
# Comprehensive Revenue & Financial Analytics
# ==========================================================

def get_revenue_breakdown(
    owner_id,
    db: Session
) -> Dict[str, Any]:
    """
    Computes fine-grained revenue breakdown by payment method, time period, and print category.
    """
    now = datetime.utcnow()
    today_date = date.today()
    current_year = now.year
    current_month = now.month

    jobs = (
        db.query(ActiveJob)
        .filter(ActiveJob.owner_id == owner_id)
        .all()
    )

    total_revenue = Decimal("0.00")
    cash_revenue = Decimal("0.00")
    online_revenue = Decimal("0.00")
    today_revenue = Decimal("0.00")
    month_revenue = Decimal("0.00")
    bw_revenue = Decimal("0.00")
    color_revenue = Decimal("0.00")

    paid_jobs_count = 0
    pending_cash_count = 0
    pending_cash_amount = Decimal("0.00")

    for j in jobs:
        pmt = j.payment
        amt = Decimal(str(j.total_amount or (pmt.amount if pmt else 0) or 0))

        # Check for pending cash approval requests
        if j.status == JobStatus.PENDING and pmt and pmt.payment_method == PaymentMethod.CASH and pmt.status == PaymentStatus.PENDING:
            pending_cash_count += 1
            pending_cash_amount += amt

        # Only process paid jobs for realized revenue
        if j.payment_status == PaymentStatus.PAID:
            paid_jobs_count += 1
            total_revenue += amt

            # By payment method
            if pmt and pmt.payment_method == PaymentMethod.CASH:
                cash_revenue += amt
            else:
                online_revenue += amt

            # By date/time
            job_time = (pmt.paid_at if pmt and pmt.paid_at else j.created_at)
            if job_time:
                if job_time.date() == today_date:
                    today_revenue += amt
                if job_time.year == current_year and job_time.month == current_month:
                    month_revenue += amt

            # By print category (B/W vs Color)
            has_color = False
            for f in (j.files or []):
                if f.print_type in (PrintType.COLOR, PrintType.MIXED) or f.color_pages > 0:
                    has_color = True
                    break
            if has_color:
                color_revenue += amt
            else:
                bw_revenue += amt

    aov = (total_revenue / Decimal(str(paid_jobs_count))) if paid_jobs_count > 0 else Decimal("0.00")

    return {
        "total_revenue": float(round(total_revenue, 2)),
        "cash_revenue": float(round(cash_revenue, 2)),
        "online_revenue": float(round(online_revenue, 2)),
        "today_revenue": float(round(today_revenue, 2)),
        "month_revenue": float(round(month_revenue, 2)),
        "bw_revenue": float(round(bw_revenue, 2)),
        "color_revenue": float(round(color_revenue, 2)),
        "paid_orders_count": paid_jobs_count,
        "pending_cash_count": pending_cash_count,
        "pending_cash_amount": float(round(pending_cash_amount, 2)),
        "average_order_value": float(round(aov, 2))
    }


def get_recent_transactions(
    owner_id,
    db: Session,
    limit: int = 15
) -> List[Dict[str, Any]]:
    """
    Returns recent transaction activity for the shop operator dashboard.
    """
    jobs = (
        db.query(ActiveJob)
        .filter(ActiveJob.owner_id == owner_id)
        .order_by(ActiveJob.created_at.desc())
        .limit(limit)
        .all()
    )

    transactions = []
    for j in jobs:
        pmt = j.payment
        filenames = [f.original_filename for f in (j.files or [])]
        transactions.append({
            "job_id": str(j.job_id),
            "customer_name": j.customer_name or "Walk-in Customer",
            "customer_phone": j.customer_phone or "-",
            "amount": float(j.total_amount or (pmt.amount if pmt else 0) or 0.0),
            "payment_method": pmt.payment_method.value if pmt else "UPI",
            "payment_status": j.payment_status.value,
            "job_status": j.status.value,
            "total_pages": j.total_pages or 0,
            "total_files": len(filenames),
            "files": filenames,
            "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S") if j.created_at else "-",
            "paid_at": pmt.paid_at.strftime("%Y-%m-%d %H:%M:%S") if pmt and pmt.paid_at else None
        })

    return transactions


def get_pending_cash_approvals(
    owner_id,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Returns active cash orders requiring operator confirmation.
    """
    jobs = (
        db.query(ActiveJob)
        .join(Payment, ActiveJob.job_id == Payment.job_id)
        .filter(
            ActiveJob.owner_id == owner_id,
            ActiveJob.status == JobStatus.PENDING,
            Payment.payment_method == PaymentMethod.CASH,
            Payment.status == PaymentStatus.PENDING
        )
        .order_by(ActiveJob.created_at.desc())
        .all()
    )

    approvals = []
    for j in jobs:
        filenames = [f.original_filename for f in (j.files or [])]
        approvals.append({
            "job_id": str(j.job_id),
            "customer_name": j.customer_name or "Walk-in Customer",
            "customer_phone": j.customer_phone or "-",
            "total_amount": float(j.total_amount or j.payment.amount or 0.0),
            "total_pages": j.total_pages or 0,
            "total_copies": j.total_copies or 1,
            "total_files": len(filenames),
            "files": filenames,
            "created_at": j.created_at.strftime("%H:%M:%S") if j.created_at else "-"
        })

    return approvals


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

    revenue_data = get_revenue_breakdown(owner_id, db)

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
        "total_revenue": revenue_data["total_revenue"],
        "cash_revenue": revenue_data["cash_revenue"],
        "online_revenue": revenue_data["online_revenue"],
        "today_revenue": revenue_data["today_revenue"],
        "month_revenue": revenue_data["month_revenue"],
        "bw_revenue": revenue_data["bw_revenue"],
        "color_revenue": revenue_data["color_revenue"],
        "pending_cash_count": revenue_data["pending_cash_count"],
        "pending_cash_amount": revenue_data["pending_cash_amount"],
        "average_order_value": revenue_data["average_order_value"],
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
        caps = []
        if printer.supports_bw:
            caps.append("B/W")
        if printer.supports_color:
            caps.append("Color")
        if printer.supports_duplex:
            caps.append("Duplex")
        if printer.supports_a3:
            caps.append("A3")

        result.append({
            "printer_id": str(printer.printer_id),
            "printer_name": printer.printer_name,
            "printer_model": printer.printer_model or "Standard",
            "jobs_printed": printer.total_jobs_printed or 0,
            "current_queue": printer.current_queue or 0,
            "status": printer.status.value,
            "is_available": printer.is_available,
            "is_physical": printer.is_physical,
            "is_virtual": printer.is_virtual,
            "capabilities": ", ".join(caps) if caps else "B/W"
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
    stats = get_dashboard_statistics(owner_id, db)
    revenue = get_revenue_breakdown(owner_id, db)
    pending_cash = get_pending_cash_approvals(owner_id, db)
    recent_txns = get_recent_transactions(owner_id, db, limit=15)

    return {
        "statistics": stats,
        "revenue_breakdown": revenue,
        "pending_cash_approvals": pending_cash,
        "recent_transactions": recent_txns,
        "printer_utilization": printer_utilization(owner_id, db),
        "predicted_monthly_revenue": float(predict_revenue(owner_id, db)),
        "predicted_busy_hour": predict_busy_hour(owner_id, db),
        "ai_recommendations": get_ai_recommendation(owner_id, db)
    }