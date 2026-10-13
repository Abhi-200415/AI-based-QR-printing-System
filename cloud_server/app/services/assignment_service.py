from sqlalchemy.orm import Session
from typing import Optional, List, Tuple

from app.database.models import (
    ActiveJob,
    Printer,
    PrinterStatus,
    PrintType,
    PaperSize,
)
from app.services.ml_prediction_service import (
    predict_job_completion_time,
    predict_job_time_breakdown,
    format_duration_friendly
)
from app.utils.logger import logger


# ==========================================================
# Eligibility Filter
# ==========================================================

def is_printer_eligible(
    printer: Printer,
    job: ActiveJob
) -> bool:
    """
    Strict capability & eligibility check.
    A printer must satisfy ALL requirements of ALL files in the job.
    """
    if printer.owner_id != job.owner_id:
        return False

    if printer.status != PrinterStatus.ONLINE:
        return False

    if not printer.is_available:
        return False

    files = job.files or []
    if not files:
        return False

    for file in files:
        # Color mode check
        if file.print_type == PrintType.BW:
            if not printer.supports_bw:
                return False
        elif file.print_type in (PrintType.COLOR, PrintType.MIXED):
            if not printer.supports_color:
                return False

        # Duplex check
        if file.duplex and not printer.supports_duplex:
            return False

        # Paper size check
        if file.paper_size == PaperSize.A3 and not printer.supports_a3:
            return False
        elif file.paper_size == PaperSize.LEGAL and not printer.supports_legal:
            return False

    return True


def has_eligible_online_printer(
    job: ActiveJob,
    db: Session
) -> bool:
    """
    Checks whether at least one eligible printer exists for the shop owner that is ONLINE and available.
    """
    candidate_printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == job.owner_id,
            Printer.status == PrinterStatus.ONLINE,
            Printer.is_available == True
        )
        .all()
    )
    if not candidate_printers:
        return False

    files = job.files or []
    if not files:
        return True

    for printer in candidate_printers:
        if is_printer_eligible(printer, job):
            return True

    return False


# ==========================================================
# Compatibility Scoring
# ==========================================================

def calculate_printer_score(
    printer: Printer,
    job: ActiveJob
) -> int:
    """
    Score printer compatibility (legacy / ranking helper).
    Returns -1 if incompatible.
    """
    if not is_printer_eligible(printer, job):
        return -1

    score = 100

    # Queue load penalty
    queue = printer.current_queue or 0
    score -= queue * 10

    # Default printer preference bonus
    if printer.is_default:
        score += 5

    # Reliability bonus from historical completed jobs
    total_jobs = printer.total_jobs_printed or 0
    score += min(total_jobs // 100, 10)

    return max(score, 1)


# ==========================================================
# Assign Best Printer (AI / ML Selection)
# ==========================================================

def assign_printer(
    job: ActiveJob,
    db: Session
) -> Optional[Printer]:
    """
    Selects the optimal printer for the job using AI/ML prediction
    over filtered eligible printers, with deterministic tie-breaking.
    """
    # ------------------------------------------------------
    # If already assigned, return existing printer
    # ------------------------------------------------------
    if job.assigned_printer_id:
        return (
            db.query(Printer)
            .filter(Printer.printer_id == job.assigned_printer_id)
            .first()
        )

    # ------------------------------------------------------
    # Find all online printers for this shop owner
    # ------------------------------------------------------
    candidate_printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == job.owner_id,
            Printer.status == PrinterStatus.ONLINE,
            Printer.is_available == True
        )
        .all()
    )

    if not candidate_printers:
        logger.warning(f"No online printers available for owner {job.owner_id}")
        return None

    # ------------------------------------------------------
    # Step 1: Capability & Eligibility Filtering
    # ------------------------------------------------------
    eligible_printers = [
        p for p in candidate_printers
        if is_printer_eligible(p, job)
    ]

    if not eligible_printers:
        logger.warning(f"No eligible printers match requirements for job {job.job_id}")
        return None

    # ------------------------------------------------------
    # Step 2: AI/ML Prediction & Deterministic Tie-Breaking
    # ------------------------------------------------------
    evaluated_printers: List[Tuple[float, int, str, Printer, str]] = []

    for printer in eligible_printers:
        predicted_seconds, source = predict_job_completion_time(job, printer, db)
        queue_count = printer.current_queue or 0
        printer_key = str(printer.printer_id)

        # Tuple for sorting: (lowest completion time, lowest queue count, tie-breaker key)
        evaluated_printers.append(
            (predicted_seconds, queue_count, printer_key, printer, source)
        )

    # Sort ascending: lowest predicted completion time first
    evaluated_printers.sort(key=lambda x: (x[0], x[1], x[2]))

    best_pred_seconds, _, _, best_printer, pred_source = evaluated_printers[0]

    # ------------------------------------------------------
    # Step 3: Assign Printer to Job
    # ------------------------------------------------------
    job.assigned_printer_id = best_printer.printer_id
    job.estimated_seconds = int(best_pred_seconds)

    db.commit()
    db.refresh(job)

    logger.info(
        f"Assigned Job {job.job_id} -> Printer '{best_printer.printer_name}' "
        f"({best_printer.printer_id}) via {pred_source} (ETA: {best_pred_seconds}s)"
    )

    return best_printer


# ==========================================================
# Real-Time Job Timing Estimates & Printer Readiness
# ==========================================================

def get_job_time_estimates(
    job: ActiveJob,
    db: Session
) -> dict:
    """
    Computes queue waiting time, print duration, total estimated completion time,
    and printer status for the customer frontend without mutating the database.
    If no printer is eligible or online, returns a structured unavailable state.
    """
    # 1. If job is already assigned to a printer:
    if job.assigned_printer_id:
        printer = (
            db.query(Printer)
            .filter(Printer.printer_id == job.assigned_printer_id)
            .first()
        )
        if printer:
            breakdown = predict_job_time_breakdown(job, printer, db, exclude_job_id=job.job_id)
            return {
                "available": True,
                "queue_wait_seconds": breakdown["queue_wait_seconds"],
                "queue_wait_display": format_duration_friendly(breakdown["queue_wait_seconds"]),
                "print_duration_seconds": breakdown["print_duration_seconds"],
                "print_duration_display": format_duration_friendly(breakdown["print_duration_seconds"]),
                "total_seconds": breakdown["total_seconds"],
                "total_display": format_duration_friendly(breakdown["total_seconds"]),
                "printer_name": printer.printer_name,
                "printer_status": "Assigned & Active",
                "source": breakdown["source"],
                "source_display": "AI Print Model" if breakdown["source"] == "ML" else "Standard Engine",
                "disclaimer": "Estimates are calculated in real time based on active queue conditions and document size. Live completion times may adjust as queue conditions change."
            }

    # 2. If unassigned (e.g., in pre-payment price summary):
    candidate_printers = (
        db.query(Printer)
        .filter(
            Printer.owner_id == job.owner_id,
            Printer.status == PrinterStatus.ONLINE,
            Printer.is_available == True
        )
        .all()
    )

    if not candidate_printers:
        return {
            "available": False,
            "queue_wait_seconds": None,
            "queue_wait_display": "Unavailable",
            "print_duration_seconds": None,
            "print_duration_display": "Unavailable",
            "total_seconds": None,
            "total_display": "Estimate unavailable",
            "printer_name": "No Printer Online",
            "printer_status": "Offline / Unavailable",
            "source": "NONE",
            "source_display": "Unavailable",
            "disclaimer": "No compatible printers are currently online. Estimates will appear when a printer connects."
        }

    eligible_printers = [
        p for p in candidate_printers
        if is_printer_eligible(p, job)
    ]

    if not eligible_printers:
        return {
            "available": False,
            "queue_wait_seconds": None,
            "queue_wait_display": "Unavailable",
            "print_duration_seconds": None,
            "print_duration_display": "Unavailable",
            "total_seconds": None,
            "total_display": "Estimate unavailable",
            "printer_name": "None Compatible",
            "printer_status": "Requirements Exceed Printer Capabilities",
            "source": "NONE",
            "source_display": "Unavailable",
            "disclaimer": "None of the online printers match your print specifications (e.g., color, duplex, or paper size)."
        }

    # Rank eligible printers by total completion time
    evaluated: List[Tuple[float, int, str, Printer, dict]] = []
    for p in eligible_printers:
        breakdown = predict_job_time_breakdown(job, p, db)
        evaluated.append((
            breakdown["total_seconds"],
            p.current_queue or 0,
            str(p.printer_id),
            p,
            breakdown
        ))

    evaluated.sort(key=lambda x: (x[0], x[1], x[2]))
    best_printer = evaluated[0][3]
    best_breakdown = evaluated[0][4]

    return {
        "available": True,
        "queue_wait_seconds": best_breakdown["queue_wait_seconds"],
        "queue_wait_display": format_duration_friendly(best_breakdown["queue_wait_seconds"]),
        "print_duration_seconds": best_breakdown["print_duration_seconds"],
        "print_duration_display": format_duration_friendly(best_breakdown["print_duration_seconds"]),
        "total_seconds": best_breakdown["total_seconds"],
        "total_display": format_duration_friendly(best_breakdown["total_seconds"]),
        "printer_name": best_printer.printer_name,
        "printer_status": "Eligible & Ready",
        "source": best_breakdown["source"],
        "source_display": "AI Print Model" if best_breakdown["source"] == "ML" else "Standard Engine",
        "disclaimer": "Estimates are calculated in real time based on active queue conditions and document size. Live completion times may adjust as queue conditions change."
    }
