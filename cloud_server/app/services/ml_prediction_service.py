import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import MODEL_PATH, ML_MIN_TRAINING_RECORDS
from app.database.models import (
    ActiveJob,
    JobFile,
    Printer,
    JobStatus,
    PrintType,
    PaperSize
)
from app.utils.logger import logger

# ==========================================================
# Deterministic Fallback Baseline Constants
# ==========================================================
BASE_SECONDS_PER_PAGE = 4.0
COLOR_MULTIPLIER = 1.35
DUPLEX_MULTIPLIER = 1.15
COPIES_SETUP_SECONDS = 3.0

# In-memory cached model
_LOADED_MODEL = None
_MODEL_LOAD_TIME = 0


# ==========================================================
# Feature Extraction Pipeline
# ==========================================================

def extract_job_file_features(file: JobFile) -> Dict[str, float]:
    """
    Extract structured numerical features for a single file.
    """
    pages = float(max(file.page_count or 1, 1))
    copies = float(max(file.copies or 1, 1))
    is_color = 1.0 if file.print_type in (PrintType.COLOR, PrintType.MIXED) else 0.0
    is_duplex = 1.0 if file.duplex else 0.0
    is_a3 = 1.0 if file.paper_size == PaperSize.A3 else 0.0
    is_legal = 1.0 if file.paper_size == PaperSize.LEGAL else 0.0

    return {
        "total_pages": pages,
        "copies": copies,
        "is_color": is_color,
        "is_duplex": is_duplex,
        "is_a3": is_a3,
        "is_legal": is_legal,
        "total_sheet_impressions": pages * copies,
    }


def extract_prediction_features(
    job: ActiveJob,
    printer: Printer,
    db: Session
) -> np.ndarray:
    """
    Build complete feature vector for ML model inference.
    Features:
    [
        total_pages,
        total_copies,
        color_page_ratio,
        duplex_ratio,
        is_a3,
        is_legal,
        printer_completed_jobs,
        printer_current_queue,
        estimated_queue_wait_seconds
    ]
    """
    files = job.files or []
    if not files:
        files = db.query(JobFile).filter(JobFile.job_id == job.job_id).all()

    total_pages = sum(f.page_count or 1 for f in files) or 1
    total_copies = max(sum(f.copies or 1 for f in files), 1)

    color_pages = sum(
        (f.page_count or 1)
        for f in files
        if f.print_type in (PrintType.COLOR, PrintType.MIXED)
    )
    color_ratio = float(color_pages) / float(total_pages)

    duplex_pages = sum((f.page_count or 1) for f in files if f.duplex)
    duplex_ratio = float(duplex_pages) / float(total_pages)

    has_a3 = 1.0 if any(f.paper_size == PaperSize.A3 for f in files) else 0.0
    has_legal = 1.0 if any(f.paper_size == PaperSize.LEGAL for f in files) else 0.0

    printer_jobs = float(printer.total_jobs_printed or 0)
    current_queue = float(printer.current_queue or 0)

    queue_wait = estimate_printer_queue_seconds(printer, db)

    features = [
        float(total_pages),
        float(total_copies),
        float(color_ratio),
        float(duplex_ratio),
        float(has_a3),
        float(has_legal),
        float(printer_jobs),
        float(current_queue),
        float(queue_wait)
    ]

    return np.array(features, dtype=np.float64).reshape(1, -1)


# ==========================================================
# Deterministic Fallback Predictor
# ==========================================================

def estimate_file_seconds_deterministic(file: JobFile, printer: Printer) -> float:
    pages = max(file.page_count or 1, 1)
    copies = max(file.copies or 1, 1)
    seconds_per_page = BASE_SECONDS_PER_PAGE

    if file.print_type in (PrintType.COLOR, PrintType.MIXED):
        seconds_per_page *= COLOR_MULTIPLIER

    if file.duplex:
        seconds_per_page *= DUPLEX_MULTIPLIER

    if file.paper_size == PaperSize.A3:
        seconds_per_page *= 1.4
    elif file.paper_size == PaperSize.LEGAL:
        seconds_per_page *= 1.1

    completed_jobs = printer.total_jobs_printed or 0
    if completed_jobs >= 100:
        seconds_per_page *= 0.90
    elif completed_jobs >= 50:
        seconds_per_page *= 0.95

    printing_time = pages * copies * seconds_per_page
    setup_time = max(copies - 1, 0) * COPIES_SETUP_SECONDS
    return printing_time + setup_time


def estimate_job_seconds_deterministic(job: ActiveJob, printer: Printer, db: Optional[Session] = None) -> float:
    files = job.files
    if not files and db:
        files = db.query(JobFile).filter(JobFile.job_id == job.job_id).all()
    if not files:
        return 10.0

    total = 0.0
    for file in files:
        total += estimate_file_seconds_deterministic(file, printer)
    return total


def estimate_printer_queue_seconds(printer: Printer, db: Session) -> float:
    queued_jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.assigned_printer_id == printer.printer_id,
            ActiveJob.status == JobStatus.QUEUED
        )
        .order_by(ActiveJob.queue_position.asc())
        .all()
    )

    total = 0.0
    for queued_job in queued_jobs:
        total += estimate_job_seconds_deterministic(queued_job, printer, db)
    return total


# ==========================================================
# ML Model Loading & Inference
# ==========================================================

def get_ml_model():
    """
    Safely load trained ML model if available.
    """
    global _LOADED_MODEL, _MODEL_LOAD_TIME
    model_file = Path(MODEL_PATH)
    if not model_file.exists():
        return None

    try:
        mtime = model_file.stat().st_mtime
        if _LOADED_MODEL is None or mtime > _MODEL_LOAD_TIME:
            import joblib
            _LOADED_MODEL = joblib.load(model_file)
            _MODEL_LOAD_TIME = mtime
            logger.info(f"Loaded trained ML print prediction model from {MODEL_PATH}")
        return _LOADED_MODEL
    except Exception as e:
        logger.warning(f"Could not load ML model from {MODEL_PATH}: {e}. Using deterministic predictor.")
        return None


def predict_job_completion_time(
    job: ActiveJob,
    printer: Printer,
    db: Session
) -> Tuple[float, str]:
    """
    Predict expected completion time (in seconds) for a job on a printer.
    Returns: (predicted_seconds, prediction_source: 'ML' | 'DETERMINISTIC_FALLBACK')
    """
    queue_wait = estimate_printer_queue_seconds(printer, db)
    model = get_ml_model()

    if model is not None:
        try:
            features = extract_prediction_features(job, printer, db)
            predicted_job_seconds = float(model.predict(features)[0])
            # Enforce reasonable lower bound
            predicted_job_seconds = max(predicted_job_seconds, 2.0)
            total_predicted = queue_wait + predicted_job_seconds
            return (round(total_predicted, 2), "ML")
        except Exception as e:
            logger.warning(f"ML inference error: {e}. Falling back to deterministic estimation.")

    # Deterministic fallback
    job_seconds = estimate_job_seconds_deterministic(job, printer, db)
    total_predicted = queue_wait + job_seconds
    return (round(total_predicted, 2), "DETERMINISTIC_FALLBACK")


# ==========================================================
# Model Training Pipeline (When Sufficient Real Data Exists)
# ==========================================================

def train_ml_model_from_db(db: Session) -> Dict[str, Any]:
    """
    Extract real historical completed jobs, build dataset, train and evaluate regression model.
    Only trains if historical records >= ML_MIN_TRAINING_RECORDS.
    Never fabricates data.
    """
    completed_jobs = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.status == JobStatus.COMPLETED,
            ActiveJob.started_at.isnot(None),
            ActiveJob.completed_at.isnot(None),
            ActiveJob.assigned_printer_id.isnot(None)
        )
        .all()
    )

    count = len(completed_jobs)
    if count < ML_MIN_TRAINING_RECORDS:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"Only {count} real completed records found (minimum required: {ML_MIN_TRAINING_RECORDS}). Deterministic fallback remains active.",
            "records_count": count,
            "threshold": ML_MIN_TRAINING_RECORDS
        }

    try:
        from sklearn.linear_model import Ridge
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        import joblib

        X_list = []
        y_list = []

        for j in completed_jobs:
            duration = (j.completed_at - j.started_at).total_seconds()
            if duration <= 0 or duration > 3600:  # ignore invalid outliers
                continue

            printer = j.assigned_printer
            if not printer:
                continue

            feats = extract_prediction_features(j, printer, db).flatten()
            X_list.append(feats)
            y_list.append(duration)

        if len(X_list) < ML_MIN_TRAINING_RECORDS:
            return {
                "status": "INSUFFICIENT_VALID_DATA",
                "message": f"Only {len(X_list)} valid timing records after filtering.",
                "records_count": len(X_list)
            }

        X = np.array(X_list)
        y = np.array(y_list)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = Ridge(alpha=1.0)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        # Save model artifact
        out_path = Path(MODEL_PATH)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, out_path)

        global _LOADED_MODEL, _MODEL_LOAD_TIME
        _LOADED_MODEL = model
        _MODEL_LOAD_TIME = time.time()

        return {
            "status": "TRAINED",
            "model": "Ridge Regression",
            "training_records": len(X_train),
            "test_records": len(X_test),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "saved_to": str(out_path)
        }

    except Exception as e:
        logger.error(f"Failed to train ML model: {e}")
        return {
            "status": "ERROR",
            "error": str(e)
        }
