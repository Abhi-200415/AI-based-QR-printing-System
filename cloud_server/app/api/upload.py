import os
import uuid
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Request
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ActiveJob,
    JobFile,
    PrintType,
    PaperSize,
    Orientation
)
from app.services.preview_service import analyze_uploaded_file
from app.core.config import UPLOAD_DIR, MAX_UPLOAD_SIZE_MB, ALLOWED_EXTENSIONS, TEMPLATES_DIR
from app.utils.logger import logger

router = APIRouter(
    tags=["Upload"]
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ==========================================================
# Upload Page
# ==========================================================

@router.get("/upload/{job_id}", response_class=HTMLResponse)
def upload_page(
    request: Request,
    job_id: str,
    db: Session = Depends(get_db)
):
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Print session not found."
        )

    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "job_id": job_id
        }
    )


# ==========================================================
# Upload Files
# ==========================================================

@router.post("/upload/{job_id}")
async def upload_files(
    job_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files uploaded."
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    uploaded_files = []

    for upload in files:
        # Sanitize filename
        safe_original_name = os.path.basename(upload.filename or "document")
        extension = Path(safe_original_name).suffix.lower()

        # Validate extension
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{extension}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        unique_name = f"{uuid.uuid4()}{extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        # Read content and enforce file size limit
        contents = await upload.read()
        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File '{safe_original_name}' exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB}MB."
            )

        if len(contents) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{safe_original_name}' is empty."
            )

        # Save to disk
        try:
            with open(file_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

        # Analyze file (page counting + format check) with exception handling
        try:
            analysis = analyze_uploaded_file(file_path)
            page_count = max(analysis.get("page_count", 1), 1)
        except Exception as e:
            logger.warning(f"Error analyzing uploaded file {file_path}: {e}")
            # If corrupted or unsupported, cleanup file and return HTTP 400
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail=f"Unable to process file '{safe_original_name}': {str(e)}"
            )

        # Create JobFile record in DB
        job_file = JobFile(
            job_id=job.job_id,
            original_filename=safe_original_name,
            stored_filename=unique_name,
            file_path=file_path,
            file_type=extension.replace(".", "").upper(),
            file_size_bytes=len(contents),
            page_count=page_count,
            copies=1,
            paper_size=PaperSize.A4,
            orientation=Orientation.PORTRAIT,
            duplex=False,
            print_type=PrintType.BW,
            color_mode="AUTO"
        )

        db.add(job_file)
        db.commit()
        db.refresh(job_file)

        uploaded_files.append({
            "file_id": str(job_file.file_id),
            "filename": job_file.original_filename,
            "page_count": job_file.page_count,
            "file_type": job_file.file_type
        })

    # Update total files count on job
    job.total_files = len(job.files or [])
    db.commit()

    return {
        "message": "Files uploaded and analyzed successfully.",
        "job_id": str(job.job_id),
        "uploaded_files": uploaded_files
    }