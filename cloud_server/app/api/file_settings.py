import uuid
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    JobFile,
    PrintType,
    PaperSize,
    Orientation,
    FinishingService,
    JobFinishingService
)

from app.schemas.file_settings import FileSettingsUpdate
from app.services.pricing_engine import calculate_job_cost, seed_default_finishing_services


from app.core.config import TEMPLATES_DIR

router = APIRouter(
    prefix="/file",
    tags=["File Settings"]
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


def _parse_uuid(val) -> UUID:
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid UUID format")


# ==========================================================
# Print Settings Page
# ==========================================================

@router.get("/settings-page/{file_id}")
async def settings_page(
    request: Request,
    file_id: UUID,
    db: Session = Depends(get_db)
):

    parsed_id = _parse_uuid(file_id)
    job_file = (
        db.query(JobFile)
        .filter(JobFile.file_id == parsed_id)
        .first()
    )

    if job_file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    owner_id = job_file.job.owner_id
    seed_default_finishing_services(owner_id, db)
    services = (
        db.query(FinishingService)
        .filter(
            FinishingService.owner_id == owner_id,
            FinishingService.is_enabled == True
        )
        .order_by(FinishingService.created_at.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="file_settings.html",
        context={
            "file_id": str(job_file.file_id),
            "job_id": str(job_file.job_id),
            "owner_id": str(owner_id),
            "file_name": job_file.original_filename,
            "page_count": job_file.page_count,
            "finishing_services": services
        }
    )


# ==========================================================
# Update File Settings
# ==========================================================

@router.put("/{file_id}/settings")
def update_file_settings(
    file_id: UUID,
    data: FileSettingsUpdate,
    db: Session = Depends(get_db)
):

    parsed_id = _parse_uuid(file_id)
    job_file = (
        db.query(JobFile)
        .filter(JobFile.file_id == parsed_id)
        .first()
    )

    if job_file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    job_file.copies = max(data.copies or 1, 1)
    job_file.duplex = bool(data.duplex)

    if isinstance(data.print_type, PrintType):
        job_file.print_type = data.print_type
    elif isinstance(data.print_type, str):
        job_file.print_type = PrintType(data.print_type.strip().upper())

    if data.paper_size:
        if isinstance(data.paper_size, PaperSize):
            job_file.paper_size = data.paper_size
        elif isinstance(data.paper_size, str):
            job_file.paper_size = PaperSize(data.paper_size.strip().upper())

    if data.orientation:
        if isinstance(data.orientation, Orientation):
            job_file.orientation = data.orientation
        elif isinstance(data.orientation, str):
            val = data.orientation.strip().capitalize()
            if val in ("Portrait", "Landscape"):
                job_file.orientation = Orientation(val)
            else:
                job_file.orientation = Orientation.PORTRAIT

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
    file_id: UUID,
    db: Session = Depends(get_db)
):

    parsed_id = _parse_uuid(file_id)
    job_file = (
        db.query(JobFile)
        .filter(JobFile.file_id == parsed_id)
        .first()
    )

    if job_file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    job = job_file.job
    all_files = db.query(JobFile).filter(JobFile.job_id == job.job_id).all()
    applied_services = (
        db.query(JobFinishingService)
        .filter(JobFinishingService.job_id == job.job_id)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="price_summary.html",
        context={
            "file_id": str(job_file.file_id),
            "job_id": str(job.job_id),
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
            "files": all_files,
            "subtotal": (
                job.subtotal
                if job and job.subtotal is not None
                else "0.00"
            ),
            "tax": (
                job.tax
                if job and job.tax is not None
                else "0.00"
            ),
            "total_amount": (
                job.total_amount
                if job and job.total_amount is not None
                else "0.00"
            ),
            "customer_reference": job.customer_reference if job else None,
            "finishing_status": job.finishing_status if job else "NONE",
            "applied_finishing_services": applied_services
        }
    )


