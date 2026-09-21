import os
import uuid
import qrcode

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ShopOwner, ActiveJob

from app.core.config import TEMPLATES_DIR, STATIC_DIR, resolve_public_base_url

router = APIRouter(
    tags=["QR Session"]
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ==========================================================
from uuid import UUID

# ==========================================================
# Create / Get Owner QR Page
# ==========================================================

@router.get(
    "/owner/{owner_id}/qr",
    response_class=HTMLResponse
)
async def owner_qr(
    request: Request,
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    owner = (
        db.query(ShopOwner)
        .filter(ShopOwner.owner_id == owner_id)
        .first()
    )

    if not owner:
        raise HTTPException(
            status_code=404,
            detail="Owner not found."
        )

    if not owner.qr_token:
        owner.qr_token = uuid.uuid4().hex
        db.commit()
        db.refresh(owner)

    # Determine public base URL dynamically (Render HTTPS / Domain / Forwarded Host)
    base_url = resolve_public_base_url(request)
    upload_url = f"{base_url}/qr/{owner.qr_token}"

    os.makedirs(STATIC_DIR, exist_ok=True)
    qr_filename = f"{owner.qr_token}.png"
    qr_path = os.path.join(STATIC_DIR, qr_filename)

    # Always generate/update QR code image with current public upload URL
    qr = qrcode.make(upload_url)
    qr.save(qr_path)

    if owner.qr_path != f"/static/{qr_filename}":
        owner.qr_path = f"/static/{qr_filename}"
        db.commit()

    return templates.TemplateResponse(
        request=request,
        name="session.html",
        context={
            "owner": owner,
            "qr_path": f"/static/{qr_filename}",
            "upload_url": upload_url
        }
    )


# ==========================================================
# Owner Dashboard HTML View
# ==========================================================

@router.get(
    "/owner/{owner_id}/dashboard",
    response_class=HTMLResponse
)
async def owner_dashboard_view(
    request: Request,
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    owner = db.query(ShopOwner).filter(ShopOwner.owner_id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found.")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "owner_id": str(owner.owner_id),
            "shop_name": owner.shop_name,
            "owner_name": owner.owner_name
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

    job = ActiveJob(
        owner_id=owner.owner_id
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return RedirectResponse(
        url=f"/upload/{job.job_id}",
        status_code=303
    )


# ==========================================================
# Customer Live Job Tracker HTML View
# ==========================================================

@router.get(
    "/job/tracker/{job_id}",
    response_class=HTMLResponse
)
async def job_tracker_view(
    request: Request,
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return templates.TemplateResponse(
        request=request,
        name="job_status.html",
        context={
            "job_id": str(job.job_id)
        }
    )
