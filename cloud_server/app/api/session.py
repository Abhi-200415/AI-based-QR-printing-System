import os
import uuid

import qrcode

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ShopOwner, ActiveJob


router = APIRouter(
    tags=["QR Session"]
)

templates = Jinja2Templates(
    directory="templates"
)


# ==========================================================
# Create / Get Owner QR
# ==========================================================

@router.get(
    "/owner/{owner_id}/qr",
    response_class=HTMLResponse
)
async def owner_qr(
    request: Request,
    owner_id: str,
    db: Session = Depends(get_db)
):

    owner = (
        db.query(ShopOwner)
        .filter(
            ShopOwner.owner_id == owner_id
        )
        .first()
    )

    if not owner:

        raise HTTPException(
            status_code=404,
            detail="Owner not found."
        )

    # ------------------------------------------------------
    # Create permanent QR token only once
    # ------------------------------------------------------

    if not owner.qr_token:

        owner.qr_token = uuid.uuid4().hex

        db.commit()
        db.refresh(owner)

    # ------------------------------------------------------
    # QR destination
    # ------------------------------------------------------

    base_url = str(
        request.base_url
    ).rstrip("/")

    upload_url = (
        f"{base_url}/qr/{owner.qr_token}"
    )

    # ------------------------------------------------------
    # Generate QR image
    # ------------------------------------------------------

    os.makedirs(
        "static",
        exist_ok=True
    )

    qr_filename = (
        f"{owner.qr_token}.png"
    )

    qr_path = os.path.join(
        "static",
        qr_filename
    )

    if not os.path.exists(qr_path):

        qr = qrcode.make(
            upload_url
        )

        qr.save(
            qr_path
        )

    # ------------------------------------------------------
    # Save QR path
    # ------------------------------------------------------

    if owner.qr_path != f"/static/{qr_filename}":

        owner.qr_path = (
            f"/static/{qr_filename}"
        )

        db.commit()

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "owner": owner,
            "qr_path": owner.qr_path,
            "upload_url": upload_url
        }
    )


# ==========================================================
# Customer Scans Owner QR
# ==========================================================

@router.get(
    "/qr/{qr_token}",
    response_class=HTMLResponse
)
async def qr_scan(
    request: Request,
    qr_token: str,
    db: Session = Depends(get_db)
):

    owner = (
        db.query(ShopOwner)
        .filter(
            ShopOwner.qr_token == qr_token,
            ShopOwner.is_active == True
        )
        .first()
    )

    if not owner:

        raise HTTPException(
            status_code=404,
            detail="Invalid or inactive shop QR code."
        )

    # ------------------------------------------------------
    # Create a new print job for this shop
    # ------------------------------------------------------

    job = ActiveJob(
        owner_id=owner.owner_id
    )

    db.add(job)

    db.commit()
    db.refresh(job)

    # ------------------------------------------------------
    # Redirect customer to upload page
    # ------------------------------------------------------

    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url=f"/upload/{job.job_id}",
        status_code=303
    )
