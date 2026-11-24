from sqlalchemy.orm import Session
from typing import Optional, List, Tuple

from app.database.models import (
    ActiveJob,
    JobFile,
    Printer,
    PrinterStatus,
    PrintType,
    PaperSize,
    JobStatus
)
from app.services.ml_prediction_service import (
    predict_job_completion_time,
    predict_job_time_breakdown,
    format_duration_friendly
)
from app.utils.logger import logger


# ==========================================================
# Eligibility Filter (Per-File & Per-Job)
# ==========================================================

def is_printer_eligible_for_file(
    printer: Printer,
    file: JobFile
) -> bool:
    """
    Strict capability check for an individual document.
    Ensures printer is online, available, and supports document color, duplex, and paper size.
    Hard gate: faster or default printers must NEVER bypass capability requirements.
    """
    if printer.status != PrinterStatus.ONLINE or not printer.is_available:
        return False

    p_type = file.print_type
    if isinstance(p_type, str):
        try:
            p_type = PrintType(p_type.strip().upper())
        except Exception:
            p_type = PrintType.BW

    # Color mode check: Hard gate
    if p_type in (PrintType.COLOR, PrintType.MIXED):
        if not printer.supports_color:
            return False
    elif p_type == PrintType.BW:
        # Printer must support black-and-white printing
        if not printer.supports_bw:
            return False

    # Duplex check: Hard gate
    if file.duplex and not printer.supports_duplex:
        return False

    # Paper size check: Hard gate
    p_size = file.paper_size
    if isinstance(p_size, str):
        try:
            p_size = PaperSize(p_size.strip().upper())
        except Exception:
            p_size = PaperSize.A4

    if p_size == PaperSize.A3 and not printer.supports_a3:
        return False
    elif p_size == PaperSize.LEGAL and not printer.supports_legal:
        return False

    return True


def is_printer_eligible(
    printer: Printer,
    job: ActiveJob
) -> bool:
    """
    Strict capability check for an entire job on a single printer.
    A printer must satisfy ALL requirements of ALL files in the job.
    """
    if printer.owner_id != job.owner_id:
        return False

    if printer.status != PrinterStatus.ONLINE or not printer.is_available:
        return False

    files = job.files or []
    if not files:
        return False

    for file in files:
        if not is_printer_eligible_for_file(printer, file):
            return False

    return True


def has_eligible_online_printer(
    job: ActiveJob,
    db: Session
) -> bool:
    """
    Checks whether the shop has online printer capacity to fulfill the order:
    1. Either a single printer can handle ALL documents in the order, OR
    2. Across the available online printers, EVERY document has at least one compatible printer.
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

    # 1. Check if any single printer handles everything
    for printer in candidate_printers:
        if is_printer_eligible(printer, job):
            return True

    # 2. Check if every individual file can be satisfied by at least one online printer
    for file in files:
        has_compat = any(is_printer_eligible_for_file(p, file) for p in candidate_printers)
        if not has_compat:
            return False

    return True


# ==========================================================
# Capability Affinity & Transparent Scoring
# ==========================================================

def calculate_printer_affinity_tier(
    printer: Printer,
    job_or_file
) -> int:
    """
    Capability-based affinity tier calculation.
    Hard compatibility must be verified before calling this ranking function.
    
    Tier 0: Ideal specialization match.
      - Dedicated Monochrome printer (supports_bw=True, supports_color=False) for B/W jobs.
      - Colour printer (supports_color=True) for Colour/Mixed jobs.
    Tier 1: Acceptable fallback.
      - Colour printer (supports_color=True) used for B/W jobs when no dedicated monochrome
        printer is available or when monochrome queue is heavily backlogged.
    """
    needs_color = False
    if isinstance(job_or_file, JobFile):
        p_type = job_or_file.print_type
        if isinstance(p_type, str):
            needs_color = p_type.strip().upper() in ("COLOR", "MIXED")
        else:
            needs_color = p_type in (PrintType.COLOR, PrintType.MIXED)
    elif hasattr(job_or_file, "files") and job_or_file.files:
        needs_color = any(
            (f.print_type in (PrintType.COLOR, PrintType.MIXED) if not isinstance(f.print_type, str)
             else f.print_type.strip().upper() in ("COLOR", "MIXED"))
            for f in job_or_file.files
        )
    elif hasattr(job_or_file, "print_type") and job_or_file.print_type:
        p_type = job_or_file.print_type
        if isinstance(p_type, str):
            needs_color = p_type.strip().upper() in ("COLOR", "MIXED")
        else:
            needs_color = p_type in (PrintType.COLOR, PrintType.MIXED)

    if needs_color:
        return 0
    else:
        # B/W job: dedicated monochrome printers get Tier 0; color printers get Tier 1 fallback
        if printer.supports_bw and not printer.supports_color:
            return 0
        return 1


def calculate_printer_selection_score(
    printer: Printer,
    job_or_file,
    predicted_seconds: float
) -> float:
    """
    Transparent scoring mechanism for compatible printers:
    - Affinity tier penalty (0 for ideal match, +1000.0 for color fallback on B/W)
    - Estimated completion time in seconds (predicted_seconds)
    - Queue backlog wait penalty (15.0s per queued job)
    - Default printer preference bonus (-5.0s)
    Lowest score represents the best printer.
    """
    tier = calculate_printer_affinity_tier(printer, job_or_file)
    queue_count = printer.current_queue or 0
    queue_wait_penalty = queue_count * 15.0
    default_bonus = 5.0 if printer.is_default else 0.0

    return (tier * 1000.0) + predicted_seconds + queue_wait_penalty - default_bonus


def calculate_printer_score(
    printer: Printer,
    job: ActiveJob
) -> int:
    """
    Legacy integer score compatibility helper (0-100 scale).
    Higher is better for legacy callers.
    """
    if not is_printer_eligible(printer, job):
        return -1

    tier = calculate_printer_affinity_tier(printer, job)
    score = 100 - (tier * 40)

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
# Assign Best Printer (Single or Multi-Printer Distribution)
# ==========================================================

def assign_printer(
    job: ActiveJob,
    db: Session
) -> Optional[Printer]:
    """
    Selects the optimal printer(s) for the job using capability matching and AI/ML prediction.
    - If customer selected BLACK AND WHITE, prefers a compatible monochrome printer over color.
    - If customer selected COLOUR, only selects a printer supporting colour.
    - If mixed files require different printers, distributes each child file to its optimal compatible printer.
    - If no compatible printer is available, keeps job safely pending and returns None.
    """
    # If already assigned, return existing printer
    if job.assigned_printer_id:
        existing = (
            db.query(Printer)
            .filter(Printer.printer_id == job.assigned_printer_id)
            .first()
        )
        if existing and existing.status == PrinterStatus.ONLINE and existing.is_available:
            return existing

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

    files = job.files or []

    # Strategy 1: Check if any single printer can handle all files (preferred)
    eligible_printers = [
        p for p in candidate_printers
        if is_printer_eligible(p, job)
    ]

    if eligible_printers:
        evaluated_printers: List[Tuple[float, int, int, str, Printer, str, float]] = []
        for printer in eligible_printers:
            predicted_seconds, source = predict_job_completion_time(job, printer, db)
            score = calculate_printer_selection_score(printer, job, predicted_seconds)
            queue_count = printer.current_queue or 0
            printer_key = str(printer.printer_id)
            evaluated_printers.append(
                (score, queue_count, -(printer.total_jobs_printed or 0), printer_key, printer, source, predicted_seconds)
            )

        evaluated_printers.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        best_score, _, _, _, best_printer, pred_source, best_pred_seconds = evaluated_printers[0]

        job.assigned_printer_id = best_printer.printer_id
        job.estimated_seconds = int(best_pred_seconds)

        # Set each unfinished file to this printer (preserve already completed files)
        for f in files:
            if not f.print_completed and f.status != JobStatus.COMPLETED:
                f.assigned_printer_id = best_printer.printer_id
                f.status = JobStatus.QUEUED

        db.commit()
        db.refresh(job)
        logger.info(
            f"Assigned Job {job.job_id} -> Single Printer '{best_printer.printer_name}' "
            f"via {pred_source} (Score: {best_score:.1f}, ETA: {best_pred_seconds}s)"
        )
        return best_printer

    # Strategy 2: Multi-Printer Distribution for mixed documents
    # Assign each file to its best compatible online printer
    assigned_printers_map = {}
    max_eta = 0.0

    for file in files:
        if file.print_completed or file.status == JobStatus.COMPLETED:
            continue
        eligible_for_file = [
            p for p in candidate_printers
            if is_printer_eligible_for_file(p, file)
        ]
        if not eligible_for_file:
            logger.warning(f"File {file.original_filename} in job {job.job_id} has no compatible online printer.")
            return None

        # Score and rank eligible printers for this file using capability affinity
        scored_for_file = []
        for p in eligible_for_file:
            pred_sec, _ = predict_job_completion_time(job, p, db)
            file_score = calculate_printer_selection_score(p, file, pred_sec)
            scored_for_file.append((file_score, p.current_queue or 0, -(p.total_jobs_printed or 0), p, pred_sec))

        scored_for_file.sort(key=lambda x: (x[0], x[1], x[2]))
        best_for_file = scored_for_file[0][3]
        file_eta = scored_for_file[0][4]
        max_eta = max(max_eta, file_eta)

        file.assigned_printer_id = best_for_file.printer_id
        file.status = JobStatus.QUEUED
        assigned_printers_map[str(file.file_id)] = best_for_file

    primary_printer = list(assigned_printers_map.values())[0] if assigned_printers_map else candidate_printers[0]
    job.assigned_printer_id = primary_printer.printer_id
    job.estimated_seconds = int(max_eta) if max_eta > 0 else 60

    db.commit()
    db.refresh(job)

    printer_names = {p.printer_name for p in assigned_printers_map.values()}
    logger.info(
        f"Assigned Multi-Printer Job {job.job_id} ({len(files)} files) across {len(printer_names)} printers: "
        f"{', '.join(printer_names)}"
    )
    return primary_printer


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
    Handles single-printer and multi-printer parallel execution models correctly.
    """
    files = job.files or []

    # 1. If job is already assigned to a printer:
    if job.assigned_printer_id:
        printer = (
            db.query(Printer)
            .filter(Printer.printer_id == job.assigned_printer_id)
            .first()
        )
        if printer:
            # Check if files are distributed across multiple printers
            distinct_printer_ids = {f.assigned_printer_id for f in files if f.assigned_printer_id}
            if len(distinct_printer_ids) > 1:
                # Multi-printer parallel execution model:
                # Total completion time is the maximum of parallel printer queues
                p_objs = db.query(Printer).filter(Printer.printer_id.in_(distinct_printer_ids)).all()
                p_names = [p.printer_name for p in p_objs]
                max_total = 0.0
                max_wait = 0.0
                total_duration = 0.0

                for p in p_objs:
                    bd = predict_job_time_breakdown(job, p, db, exclude_job_id=job.job_id)
                    max_total = max(max_total, bd["total_seconds"])
                    max_wait = max(max_wait, bd["queue_wait_seconds"])
                    total_duration += bd["print_duration_seconds"]

                return {
                    "available": True,
                    "queue_wait_seconds": max_wait,
                    "queue_wait_display": format_duration_friendly(max_wait),
                    "print_duration_seconds": total_duration,
                    "print_duration_display": format_duration_friendly(total_duration),
                    "total_seconds": max_total,
                    "total_display": format_duration_friendly(max_total),
                    "printer_name": f"Multi-Printer ({', '.join(p_names)})",
                    "printer_status": "Assigned (Parallel Print)",
                    "source": "MULTI_PRINTER_SCHEDULER",
                    "source_display": "Intelligent Multi-Printer Scheduler",
                    "disclaimer": "Documents distributed across multiple compatible printers in parallel for fastest completion."
                }

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

    # Strategy 1: Single printer eligibility
    eligible_printers = [
        p for p in candidate_printers
        if is_printer_eligible(p, job)
    ]

    if eligible_printers:
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

    # Strategy 2: Multi-printer check
    all_files_have_printers = True
    assigned_printers = []
    for f in files:
        compat = [p for p in candidate_printers if is_printer_eligible_for_file(p, f)]
        if not compat:
            all_files_have_printers = False
            break
        compat.sort(key=lambda p: p.current_queue or 0)
        assigned_printers.append(compat[0])

    if all_files_have_printers and assigned_printers:
        unique_printers = list({p.printer_id: p for p in assigned_printers}.values())
        names = [p.printer_name for p in unique_printers]
        max_eta = 0.0
        max_wait = 0.0
        sum_duration = 0.0
        for p in unique_printers:
            bd = predict_job_time_breakdown(job, p, db)
            max_eta = max(max_eta, bd["total_seconds"])
            max_wait = max(max_wait, bd["queue_wait_seconds"])
            sum_duration += bd["print_duration_seconds"]

        return {
            "available": True,
            "queue_wait_seconds": max_wait,
            "queue_wait_display": format_duration_friendly(max_wait),
            "print_duration_seconds": sum_duration,
            "print_duration_display": format_duration_friendly(sum_duration),
            "total_seconds": max_eta,
            "total_display": format_duration_friendly(max_eta),
            "printer_name": f"Multi-Printer ({', '.join(names)})",
            "printer_status": "Compatible Multi-Printer Route",
            "source": "MULTI_PRINTER_SCHEDULER",
            "source_display": "Intelligent Multi-Printer Scheduler",
            "disclaimer": "Mixed documents will be distributed across suitable printers for parallel printing."
        }

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
