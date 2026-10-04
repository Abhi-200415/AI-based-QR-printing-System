from uuid import UUID
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ActiveJob, JobFinishingService, PaymentStatus
from app.core.config import TEMPLATES_DIR
from app.utils.logger import logger

router = APIRouter(
    prefix="/receipt",
    tags=["Receipt"]
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


def _build_receipt_data(job: ActiveJob, db: Session) -> dict:
    shop = job.owner
    shop_name = shop.shop_name if shop else "AI Smart Printing Shop"
    shop_address = shop.address if shop else ""

    # Group finishing services: per-file vs order-level
    all_services = db.query(JobFinishingService).filter(JobFinishingService.job_id == job.job_id).all()
    file_srv_map = {}
    order_srvs = []

    for s in all_services:
        if s.file_id:
            fid_str = str(s.file_id)
            if fid_str not in file_srv_map:
                file_srv_map[fid_str] = []
            file_srv_map[fid_str].append({
                "id": str(s.id),
                "service_name": s.service_name,
                "unit_price": float(s.unit_price or 0),
                "quantity": s.quantity or 1,
                "total_price": float(s.total_price or 0)
            })
        else:
            order_srvs.append({
                "id": str(s.id),
                "service_name": s.service_name,
                "unit_price": float(s.unit_price or 0),
                "quantity": s.quantity or 1,
                "total_price": float(s.total_price or 0)
            })

    items = []
    printing_subtotal = Decimal("0.00")
    for f in (job.files or []):
        file_cost = Decimal(str(f.estimated_cost or "0.00"))
        printing_subtotal += file_cost
        f_srvs = file_srv_map.get(str(f.file_id), [])

        items.append({
            "file_id": str(f.file_id),
            "filename": f.original_filename or "document.pdf",
            "page_count": f.page_count or 1,
            "copies": f.copies or 1,
            "paper_size": f.paper_size.value if f.paper_size else "A4",
            "orientation": f.orientation.value if f.orientation else "Portrait",
            "print_type": f.print_type.value if f.print_type else "BW",
            "duplex": bool(f.duplex),
            "page_ranges": f.page_ranges,
            "printing_cost": float(file_cost),
            "finishing_services": f_srvs
        })

    finishing_subtotal = sum(Decimal(str(s.total_price or "0.00")) for s in all_services)
    tax_amt = Decimal(str(job.tax or "0.00"))
    grand_total = Decimal(str(job.total_amount or "0.00"))

    # If job has no recorded total yet, calculate from parts
    if grand_total <= Decimal("0.00"):
        grand_total = printing_subtotal + finishing_subtotal + tax_amt

    # Payment details
    pmt = job.payment
    pmt_method = pmt.payment_method.value if (pmt and pmt.payment_method) else "ONLINE"
    pmt_status = pmt.status.value if pmt else job.payment_status.value
    txn_id = pmt.transaction_id or pmt.provider_payment_id if pmt else None

    date_str = job.created_at.strftime("%d %b %Y, %I:%M %p") if job.created_at else datetime.utcnow().strftime("%d %b %Y, %I:%M %p")

    return {
        "order_id": str(job.job_id),
        "date_time": date_str,
        "shop_name": shop_name,
        "shop_address": shop_address,
        "customer_reference": job.customer_reference,
        "items": items,
        "file_items": items,
        "order_finishing_services": order_srvs,
        "printing_subtotal": float(printing_subtotal),
        "finishing_subtotal": float(finishing_subtotal),
        "tax": float(tax_amt),
        "grand_total": float(grand_total),
        "payment_method": pmt_method,
        "payment_status": pmt_status,
        "transaction_id": txn_id
    }


@router.get("/job/{job_id}")
def get_receipt_json(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Returns authoritative receipt breakdown data in JSON format.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Order not found.")

    return _build_receipt_data(job, db)


@router.get("/job/{job_id}/view", response_class=HTMLResponse)
def view_receipt_html(
    request: Request,
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Renders receipt view for display in browser or modal.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Order not found.")

    receipt_data = _build_receipt_data(job, db)
    return templates.TemplateResponse(
        request=request,
        name="receipt.html",
        context={
            "receipt": receipt_data
        }
    )


@router.get("/job/{job_id}/download")
def download_receipt_html(
    request: Request,
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Secure receipt download endpoint (allowed separate from document verification).
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Order not found.")

    receipt_data = _build_receipt_data(job, db)
    rendered_content = templates.get_template("receipt.html").render({
        "request": request,
        "receipt": receipt_data
    })

    clean_order_id = str(job.job_id)[:8]
    return Response(
        content=rendered_content.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="Receipt_Order_{clean_order_id}.html"',
            "Cache-Control": "no-cache"
        }
    )
