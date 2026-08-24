from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    Printer,
    PrinterStatus,
    PrintType,
    PaperSize,
)

from app.services.print_prediction import (
    predict_completion_seconds
)

from app.services.physical_printer_service import (
    check_printer_available
)

# ==========================================================
# AI Printer Scoring
# ==========================================================

def calculate_printer_score(
    printer: Printer,
    job: ActiveJob
) -> int:

    """
    Intelligent printer scoring.

    The printer must satisfy ALL file requirements
    before it can receive a positive score.

    Higher score = better printer.
    """

    # ------------------------------------------------------
    # Basic printer availability
    # ------------------------------------------------------

    if printer.status != PrinterStatus.ONLINE:

        return -1

    if not job.files:

        return -1

    score = 100

    # ------------------------------------------------------
    # Evaluate every file in the job
    # ------------------------------------------------------

    for file in job.files:

        # ----------------------------------------------
        # B/W requirement
        # ----------------------------------------------

        if file.print_type == PrintType.BW:

            if not printer.supports_bw:

                return -1

            score += 10

        # ----------------------------------------------
        # Color requirement
        # ----------------------------------------------

        elif file.print_type == PrintType.COLOR:

            if not printer.supports_color:

                return -1

            score += 20

        # ----------------------------------------------
        # Mixed requirement
        # ----------------------------------------------

        elif file.print_type == PrintType.MIXED:

            if not printer.supports_color:

                return -1

            score += 20

        # ----------------------------------------------
        # Duplex
        # ----------------------------------------------

        if file.duplex:

            if not printer.supports_duplex:

                return -1

            score += 10

        # ----------------------------------------------
        # A3
        # ----------------------------------------------

        if file.paper_size == PaperSize.A3:

            if not printer.supports_a3:

                return -1

            score += 10

        # ----------------------------------------------
        # Legal
        # ----------------------------------------------

        if file.paper_size == PaperSize.LEGAL:

            if not printer.supports_legal:

                return -1

            score += 10

    # ------------------------------------------------------
    # Queue Load
    # ------------------------------------------------------

    queue = printer.current_queue or 0

    # Stronger penalty as queue grows
    score -= queue * 12

    # ------------------------------------------------------
    # Default printer
    # ------------------------------------------------------

    if printer.is_default:

        score += 5

    # ------------------------------------------------------
    # Reliability
    # ------------------------------------------------------

    total_jobs = printer.total_jobs_printed or 0

    reliability_bonus = min(
        total_jobs // 100,
        10
    )

    score += reliability_bonus

    return score

# ==========================================================
# Assign Best Printer
# ==========================================================

def assign_printer(
    job: ActiveJob,
    db: Session
):

    # ------------------------------------------------------
    # Prevent duplicate printer assignment
    # ------------------------------------------------------

    if job.assigned_printer_id:

        return (
            db.query(Printer)
            .filter(
                Printer.printer_id ==
                job.assigned_printer_id
            )
            .first()
        )
    # ------------------------------------------------------
    # Find online printers belonging to this owner
    # ------------------------------------------------------

    printers = (
    db.query(Printer)
    .filter(
        Printer.owner_id == job.owner_id,
        Printer.status == PrinterStatus.ONLINE,
        Printer.is_physical == True,
        Printer.is_available == True
    )
    .all()
)

    if not printers:

        return None

    # ------------------------------------------------------
    # Find best printer
    # ------------------------------------------------------

    best_printer = None
    best_score = -1
    best_eta = None

    for printer in printers:

        # ----------------------------------------------
        # Capability / compatibility score
        # ----------------------------------------------

        # ----------------------------------------------
        # Physical printer availability
        # ----------------------------------------------

        if printer.is_physical:

            if not check_printer_available(
                printer.printer_name,
                printer.printer_type
            ):

                continue

        score = calculate_printer_score(
            printer,
            job
        )

        if score < 0:

            continue

        # ----------------------------------------------
        # Predict completion time
        # ----------------------------------------------

        predicted_seconds = (
            predict_completion_seconds(
                job,
                printer,
                db
            )
        )

        # ----------------------------------------------
        # Intelligent selection
        #
        # Primary objective:
        #     lower predicted completion time
        #
        # Secondary objective:
        #     higher capability score
        # ----------------------------------------------

        if best_printer is None:

            best_printer = printer
            best_score = score
            best_eta = predicted_seconds

            continue

        if predicted_seconds < best_eta:

            best_printer = printer
            best_score = score
            best_eta = predicted_seconds

        elif (
            predicted_seconds == best_eta
            and score > best_score
        ):

            best_printer = printer
            best_score = score
            best_eta = predicted_seconds

    # ------------------------------------------------------
    # No compatible printer
    # ------------------------------------------------------

    if best_printer is None:

        return None

    # ------------------------------------------------------
    # Assign printer
    # ------------------------------------------------------

    job.assigned_printer_id = (
        best_printer.printer_id
    )

    db.commit()

    db.refresh(job)

    return best_printer

# ==========================================================
# AI Best Printer Assignment
# ==========================================================
#
# This function is used by the AI API.
# It internally uses the existing printer-scoring algorithm.
#
# ==========================================================

def assign_best_printer(
    job: ActiveJob,
    db: Session
):

    return assign_printer(
        job,
        db
    )

