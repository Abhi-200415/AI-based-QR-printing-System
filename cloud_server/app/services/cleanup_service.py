import os

from sqlalchemy.orm import Session

from app.database.models import JobFile


# ==========================================================
# Delete Physical File
# ==========================================================

def delete_uploaded_file(file_path: str):

    if file_path and os.path.exists(file_path):
        os.remove(file_path)


# ==========================================================
# Cleanup Single File
# ==========================================================

def cleanup_file(
    job_file: JobFile,
    db: Session
):

    delete_uploaded_file(
        job_file.file_path
    )

    # Remove sensitive information
    job_file.file_path = None
    job_file.stored_filename = None

    db.commit()

    db.refresh(job_file)

    return job_file


# ==========================================================
# Cleanup Entire Job
# ==========================================================

def cleanup_job_files(
    job_id,
    db: Session
):

    files = (
        db.query(JobFile)
        .filter(
            JobFile.job_id == job_id
        )
        .all()
    )

    cleaned = 0

    for file in files:

        cleanup_file(
            file,
            db
        )

        cleaned += 1

    return cleaned


# ==========================================================
# Check Whether Cleanup Needed
# ==========================================================

def cleanup_required(
    job_file: JobFile
):

    return (
        job_file.file_path is not None
    )