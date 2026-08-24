from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import JobFile

from app.services.document_search_service import (
    search_document,
    pages_to_range
)

router = APIRouter(
    prefix="/ai-search",
    tags=["AI Document Search"]
)


# ==========================================================
# Search Request
# ==========================================================

class SearchRequest(BaseModel):
    search_text: str


# ==========================================================
# Search Document
# ==========================================================

@router.post("/search/{file_id}")
def search_file(

    file_id: UUID,

    request: SearchRequest,

    db: Session = Depends(get_db)

):

    job_file = (

        db.query(JobFile)

        .filter(
            JobFile.file_id == file_id
        )

        .first()

    )

    if not job_file:

        raise HTTPException(

            status_code=404,

            detail="File not found."

        )

    pages = search_document(

        job_file.file_path,

        request.search_text

    )

    return {

        "success": True,

        "search_text": request.search_text,

        "matched_pages": pages,

        "page_ranges": pages_to_range(pages),

        "total_matches": len(pages)
    }