import os
import uuid
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    Request
)

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ActiveJob,
    JobFile,
    PaperSize,
    Orientation,
    PrintType
)

from app.services.page_counter import count_pages
from app.services.job_service import update_job_summary
from app.services.preview_service import get_file_preview
from app.websocket.manager import broadcast_job

router = APIRouter(
    tags=["Upload"]
)

templates = Jinja2Templates(
    directory="templates"
)

UPLOAD_DIR = "uploads"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


# ==========================================================
# AI File Analysis (Future Ready)
# ==========================================================

def analyze_uploaded_file(file_path: str):

    page_count = count_pages(file_path)

    return {

        "page_count": page_count,

        # Future AI Module
        "ai_color_detected": False,

        "bw_pages": page_count,

        "color_pages": 0,

        "recommended_print_type": PrintType.BW,

        "recommended_orientation": Orientation.PORTRAIT,

        "recommended_duplex": False,

        "document_type": "Unknown"
    }


# ==========================================================
# Upload Page
# ==========================================================

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
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    uploaded_files = []

    for upload in files:

        extension = Path(
            upload.filename
        ).suffix.lower()

        unique_name = (
            f"{uuid.uuid4()}{extension}"
        )

        file_path = os.path.join(
            UPLOAD_DIR,
            unique_name
        )

        contents = await upload.read()

        with open(file_path, "wb") as file:
            file.write(contents)

        analysis = analyze_uploaded_file(
            file_path
        )

        job_file = JobFile(

            job_id=job.job_id,

            original_filename=upload.filename,

            stored_filename=unique_name,

            file_path=file_path,

            file_type=extension,

            file_size=len(contents),

            page_count=analysis["page_count"],

            copies=1,

            paper_size=PaperSize.A4,

            orientation=analysis["recommended_orientation"],

            duplex=analysis["recommended_duplex"],

            print_type=analysis["recommended_print_type"],

            color_mode="AUTO",

            page_ranges=None,

            color_page_ranges=None,

            bw_pages=analysis["bw_pages"],

            color_pages=analysis["color_pages"],

            ai_color_detected=analysis["ai_color_detected"],

            estimated_cost=0,

            print_completed=False
        )

        db.add(job_file)

        db.flush()

        preview = get_file_preview(
            file_path
        )

        uploaded_files.append({

            "file_id": str(job_file.file_id),

            "file_name": upload.filename,

            "preview": preview,

            "page_count": analysis["page_count"],

            "document_type": analysis["document_type"],

            "recommended_print": analysis["recommended_print_type"].value,

            "recommended_orientation": analysis["recommended_orientation"].value,

            "recommended_duplex": analysis["recommended_duplex"]
        })

    db.commit()

    update_job_summary(
        job.job_id,
        db
    )

    await broadcast_job({

        "event": "FILES_UPLOADED",

        "job_id": str(job.job_id),

        "files": uploaded_files
    })

    return {

        "success": True,

        "message": "Files uploaded successfully.",

        "job_id": str(job.job_id),

        "uploaded_files": uploaded_files
    }