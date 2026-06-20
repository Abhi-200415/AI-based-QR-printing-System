import os
import uuid
from app.services.page_counter import count_pages
from typing import List

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Request,
    Depends,
    HTTPException
)

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ActiveJob,
    JobFile
)

from app.websocket.manager import broadcast_job

router = APIRouter(
    tags=["Upload"]
)

templates = Jinja2Templates(
    directory="templates"
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==========================================
# UPLOAD PAGE
# ==========================================

@router.get(
    "/upload/{job_id}",
    response_class=HTMLResponse
)
async def upload_page(
    request: Request,
    job_id: str
):
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "job_id": job_id
        }
    )


# ==========================================
# MULTI FILE UPLOAD
# ==========================================

@router.post("/upload/{job_id}")
async def handle_upload(
    job_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    uploaded_files = []

    for file in files:

        file_uuid = str(uuid.uuid4())

        stored_file_name = (
            f"{file_uuid}_{file.filename}"
        )

        file_path = os.path.join(
            UPLOAD_DIR,
            stored_file_name
        )

        with open(file_path, "wb") as buffer:
            buffer.write(
                await file.read()
            )

        extension = (
            file.filename
            .split(".")[-1]
            .lower()
        )
        page_count = count_pages(file_path)
        new_file = JobFile(
            job_id=job.job_id,
            stored_file_name=stored_file_name,
            original_file_name=file.filename,
            file_type=extension,
            file_path=file_path,
            page_count=page_count,
            copies=1,
            print_mode="bw",
            duplex=False,
            ai_color_detected=False,
            detected_color_pages=0,
            estimated_print_cost=0
        )

        db.add(new_file)
        db.flush()

        uploaded_files.append(
            {
                "file_id": str(new_file.file_id),
                "filename": file.filename,
                "file_type": extension
            }
        )

    job.total_files += len(files)

    db.commit()

    await broadcast_job(
        {
            "job_id": str(job.job_id),
            "files": uploaded_files
        }
    )

    return {
        "message": "Files uploaded successfully",
        "job_id": str(job.job_id),
        "total_files": len(files),
        "uploaded_files": uploaded_files
    }