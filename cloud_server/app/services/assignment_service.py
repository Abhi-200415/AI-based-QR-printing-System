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
    predict_job_completion_time
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
