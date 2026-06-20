from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import JobFile

router = APIRouter(
    prefix="/preview",
    tags=["Preview"]
)


@router.get("/{file_id}")
def preview_file(
    file_id: str,
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

    return FileResponse(
        path=file.file_path,
        filename=file.original_file_name
    )