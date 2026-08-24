from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    JobFile,
    PrintType,
    PaperSize,
    Orientation,
)

from app.schemas.file_settings import FileSettingsUpdate
from app.services.pricing_engine import calculate_job_cost


router = APIRouter(
    prefix="/file",
    tags=["File Settings"]
)

templates = Jinja2Templates(
    directory="templates"
)


# ==========================================================
# Print Settings Page
# ==========================================================

@router.get("/settings-page/{file_id}")
async def settings_page(
    request: Request,
    file_id: str,
    db: Session = Depends(get_db)
):

    job_file = (
        db.query(JobFile)
        .filter(JobFile.file_id == file_id)
        .first()
    )

    if job_file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    return templates.TemplateResponse(
        "file_settings.html",
        {
            "request": request,
            "file_id": str(job_file.file_id),
            "job_id": str(job_file.job_id),
            "file_name": job_file.original_filename,
            "page_count": job_file.page_count
        }
    )


# ==========================================================
# Update File Settings
# ==========================================================

@router.put("/{file_id}/settings")
def update_file_settings(
    file_id: str,
    data: FileSettingsUpdate,
    db: Session = Depends(get_db)
):

    job_file = (
        db.query(JobFile)
        .filter(JobFile.file_id == file_id)
        .first()
    )

    if job_file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    job_file.copies = data.copies

    job_file.duplex = data.duplex

    job_file.print_type = PrintType(
        data.print_type.upper()
    )

    if data.paper_size:

        job_file.paper_size = PaperSize(
            data.paper_size.upper()
        )

    if data.orientation:

        job_file.orientation = Orientation(
            data.orientation
        )

    job_file.page_ranges = data.page_ranges

    if job_file.print_type == PrintType.MIXED:

        job_file.color_page_ranges = (
            data.color_page_ranges
        )

    else:

        job_file.color_page_ranges = None

    db.commit()

    db.refresh(job_file)

    calculate_job_cost(
        job_file.job_id,
        db
    )

    return {

        "success": True,

        "message":
            "File settings updated successfully.",

        "file_id":
            str(job_file.file_id),

        "settings": {

            "copies":
                job_file.copies,

            "paper_size":
                job_file.paper_size.value
                if job_file.paper_size
                else None,

            "orientation":
                job_file.orientation.value
                if job_file.orientation
                else None,

            "print_type":
                job_file.print_type.value,

            "duplex":
                job_file.duplex,

            "page_ranges":
                job_file.page_ranges,

            "color_page_ranges":
                job_file.color_page_ranges,

        },

    }


# ==========================================================
# Price Summary Page
# ==========================================================

@router.get("/summary/{file_id}")
async def price_summary(
    request: Request,
    file_id: str,
    db: Session = Depends(get_db)
):

    job_file = (
        db.query(JobFile)
        .filter(JobFile.file_id == file_id)
        .first()
    )

    if job_file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    job = job_file.job

    return templates.TemplateResponse(
        "price_summary.html",
        {
            "request": request,
            "file_id": str(job_file.file_id),
            "job_id": str(job_file.job_id),
            "file_name": job_file.original_filename,
            "page_count": job_file.page_count,
            "copies": job_file.copies,
            "paper_size": (
                job_file.paper_size.value
                if job_file.paper_size
                else None
            ),
            "orientation": (
                job_file.orientation.value
                if job_file.orientation
                else None
            ),
            "print_type": (
                job_file.print_type.value
                if job_file.print_type
                else None
            ),
            "duplex": job_file.duplex,
            "total_amount": (
                job.total_amount
                if job and job.total_amount is not None
                else "0.00"
            )
        }
    )


