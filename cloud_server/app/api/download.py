from uuid import UUID
import os

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.database.models import (
    ActiveJob,
    JobFile,
    PaymentStatus
)

router = APIRouter(

    prefix="/download",

    tags=["Download"]

)
# ==========================================================
# Download Print File
# ==========================================================

@router.get(

    "/job/{job_id}/file/{file_id}"

)
def download_file(

    job_id: UUID,

    file_id: UUID,

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

    file = (

        db.query(JobFile)

        .filter(

            JobFile.file_id == file_id,

            JobFile.job_id == job_id

        )

        .first()

    )

    if not file:

        raise HTTPException(

            status_code=404,

            detail="File not found."

        )
        # -----------------------------------------
    # Payment Verification
    # -----------------------------------------

    if job.payment_status != PaymentStatus.PAID:

        raise HTTPException(

            status_code=403,

            detail="Payment not completed."

        )

    # -----------------------------------------
    # File Exists
    # -----------------------------------------

    if not os.path.exists(

        file.file_path

    ):

        raise HTTPException(

            status_code=404,

            detail="Stored file missing."

        )

    # -----------------------------------------
    # Return File
    # -----------------------------------------

    return FileResponse(

        path=file.file_path,

        filename=file.stored_filename,

        media_type="application/octet-stream"

    )
# ==========================================================
# Download Health
# ==========================================================

@router.get(

    "/health"

)
def download_health():

    return {

        "service": "Download API",

        "status": "Healthy",

        "message": "Download service is running."

    }