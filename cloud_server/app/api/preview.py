import os
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ActiveJob, JobFile
from app.core.crypto import decrypt_document, is_encrypted_envelope, CryptoSecurityException
from app.core.config import UPLOAD_DIR
from app.utils.logger import logger

router = APIRouter(
    prefix="/preview",
    tags=["Preview"]
)

# Supported inline preview MIME types
INLINE_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".txt": "text/plain; charset=utf-8"
}


@router.get("/job/{job_id}/file/{file_id}")
def preview_file(
    job_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Secure Inline File Preview Endpoint.
    - Authoritative verification: file must belong to the requested job_id.
    - Decrypts AES-256-GCM envelope on-the-fly into memory.
    - Serves inline with Content-Disposition: inline (NEVER attachment).
    - Prevents cross-customer access and path traversal.
    - Returns 'Preview is not available for this file type' for unsupported extensions.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job session not found.")

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
            detail="File not found or does not belong to this print order."
        )

    # Path traversal protection
    if not file.file_path:
        raise HTTPException(status_code=404, detail="File path not recorded.")

    norm_upload_dir = os.path.abspath(UPLOAD_DIR)
    norm_file_path = os.path.abspath(file.file_path)

    if not norm_file_path.startswith(norm_upload_dir):
        logger.security_warning(f"Path traversal blocked for preview attempt: {norm_file_path}")
        raise HTTPException(status_code=403, detail="Access to the requested resource is denied.")

    if not os.path.exists(norm_file_path):
        raise HTTPException(status_code=404, detail="Document content has expired or is missing.")

    # Extension check
    orig_ext = Path(file.original_filename or "").suffix.lower()
    if orig_ext not in INLINE_MIME_TYPES:
        return Response(
            content=b"Preview is not available for this file type.",
            media_type="text/plain; charset=utf-8",
            status_code=200,
            headers={
                "Content-Disposition": "inline",
                "X-Preview-Supported": "false"
            }
        )

    # Read and decrypt in memory
    try:
        with open(norm_file_path, "rb") as f:
            raw_data = f.read()
    except Exception as e:
        logger.error(f"Failed to read file for preview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error reading document.")

    if is_encrypted_envelope(raw_data):
        try:
            plaintext = decrypt_document(raw_data)
        except CryptoSecurityException as e:
            logger.error(f"Integrity check failed during preview of file {file_id}: {e}")
            raise HTTPException(status_code=500, detail="Document decryption integrity check failed.")
    else:
        plaintext = raw_data

    mime_type = INLINE_MIME_TYPES[orig_ext]
    safe_filename = os.path.basename(file.original_filename or f"preview_{file_id}{orig_ext}")

    return Response(
        content=plaintext,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff"
        }
    )
