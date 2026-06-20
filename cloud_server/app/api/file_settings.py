from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import JobFile

from app.schemas.file_settings import (
    FileSettingsUpdate
)
from app.services.pricing_engine import (
    calculate_job_cost
)

router = APIRouter(
    prefix="/file",
    tags=["File Settings"]
)


@router.put("/{file_id}/settings")
def update_file_settings(
    file_id: str,
    data: FileSettingsUpdate,
    db: Session = Depends(get_db)
):

    file = (
        db.query(JobFile)
        .filter(
            JobFile.file_id == file_id
        )
        .first()
    )

    if not file:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    file.copies = data.copies
    file.print_mode = data.print_mode
    file.duplex = data.duplex

    # Future Mixed Mode
    if hasattr(file, "color_page_ranges"):
        file.color_page_ranges = data.color_page_ranges

  calculate_job_cost(
    file.job_id,
    db
)

    return {
        "message": "File settings updated",
        "file_id": str(file.file_id),
        "copies": file.copies,
        "print_mode": file.print_mode,
        "duplex": file.duplex,
        "color_page_ranges": data.color_page_ranges
    }