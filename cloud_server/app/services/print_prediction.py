from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    JobFile,
    Printer
)
from app.services.ml_prediction_service import (
    predict_job_completion_time,
    estimate_file_seconds_deterministic,
    estimate_job_seconds_deterministic,
    estimate_printer_queue_seconds
)

# Compatibility functions for existing modules
def estimate_file_seconds(file: JobFile, printer: Printer) -> float:
    return estimate_file_seconds_deterministic(file, printer)


def estimate_job_seconds(job: ActiveJob, printer: Printer) -> float:
    return estimate_job_seconds_deterministic(job, printer)


def predict_completion_seconds(
    job: ActiveJob,
    printer: Printer,
    db: Session
) -> float:
    """
    Predict completion time using AI/ML prediction with deterministic fallback.
    """
    seconds, _source = predict_job_completion_time(job, printer, db)
    return seconds