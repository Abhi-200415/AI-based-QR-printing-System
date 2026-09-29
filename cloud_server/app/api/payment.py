from uuid import UUID
from datetime import datetime
from typing import Optional
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Header
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    ActiveJob,
    Payment,
    PaymentStatus,
    PaymentProvider,
    PaymentMethod,
    JobStatus
)
from app.services.job_service import (
    prepare_job,
    assign_paid_job
)
from app.services.dispatch_service import (
    dispatch_job_to_agent
)
from app.services.payment_service import PaymentService
from app.utils.logger import logger

router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)


# ==========================================================
# Request Schemas
# ==========================================================

class PaymentCreateRequest(BaseModel):
    payment_method: Optional[PaymentMethod] = PaymentMethod.UPI


class PaymentVerifyRequest(BaseModel):
    payment_id: UUID
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    signature: Optional[str] = None


# ==========================================================
# Create Payment
# ==========================================================

@router.post("/create/{job_id}")
def create_payment(
    job_id: UUID,
    payload: Optional[PaymentCreateRequest] = None,
    db: Session = Depends(get_db)
):
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Return existing payment if already created
    if job.payment:
        return {
            "payment_id": str(job.payment.payment_id),
            "job_id": str(job.job_id),
            "status": job.payment.status.value,
            "amount": float(job.payment.amount),
            "currency": job.payment.currency,
            "provider": job.payment.provider.value,
            "qr_reference": job.payment.qr_reference,
            "provider_payment_id": job.payment.provider_payment_id
        }

    # Ensure pricing is calculated
    if not job.total_amount or job.total_amount <= 0:
        prepared_job = prepare_job(job.job_id, db)
        if not prepared_job:
            raise HTTPException(status_code=500, detail="Unable to calculate job pricing.")
        db.refresh(job)

    if not job.total_amount or job.total_amount <= 0:
        raise HTTPException(status_code=400, detail="Job price could not be calculated.")

    method = payload.payment_method if payload else PaymentMethod.UPI
    payment = PaymentService.create_payment_order(job, payment_method=method, db=db)

    return {
        "payment_id": str(payment.payment_id),
        "job_id": str(job.job_id),
        "status": payment.status.value,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "provider": payment.provider.value,
        "qr_reference": payment.qr_reference,
        "provider_payment_id": payment.provider_payment_id
    }


# ==========================================================
# Verify Payment (Secure HMAC-SHA256 or Provider Check)
# ==========================================================

@router.post("/verify")
async def verify_payment(
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db)
):
    payment = db.query(Payment).filter(Payment.payment_id == payload.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")

    job = payment.job
    if not job:
        raise HTTPException(status_code=404, detail="Job not found for this payment.")

    # Idempotency check: if already paid, return status
    if payment.status == PaymentStatus.PAID:
        return {
            "success": True,
            "payment_id": str(payment.payment_id),
            "job_id": str(job.job_id),
            "status": payment.status.value,
            "message": "Payment was already verified."
        }

    # Secure verification
    verified = False
    if payload.signature and payload.provider_order_id and payload.provider_payment_id:
        verified = PaymentService.verify_gateway_signature(
            order_id=payload.provider_order_id,
            payment_id=payload.provider_payment_id,
            signature=payload.signature
        )
    elif payment.provider == PaymentProvider.MANUAL:
        # For manual payment in local/demo environment
        verified = True

    if not verified:
        PaymentService.process_failed_payment(payment, failure_reason="Invalid payment signature.", db=db)
        raise HTTPException(status_code=400, detail="Payment verification failed. Invalid signature.")

    # Process successful payment
    PaymentService.process_successful_payment(
        payment,
        transaction_id=payload.provider_payment_id or "TXN_MANUAL",
        provider_payment_id=payload.provider_order_id,
        db=db
    )

    # Assign printer and add to queue
    prepared_job = assign_paid_job(job.job_id, db)
    if prepared_job and prepared_job.assigned_printer_id and prepared_job.queue_position == 1:
        await dispatch_job_to_agent(prepared_job)

    db.refresh(payment)
    return {
        "success": True,
        "payment_id": str(payment.payment_id),
        "job_id": str(job.job_id),
        "payment_status": payment.status.value,
        "job_status": prepared_job.status.value if prepared_job else job.status.value,
        "assigned_printer": str(prepared_job.assigned_printer_id) if prepared_job and prepared_job.assigned_printer_id else None,
        "queue_position": prepared_job.queue_position if prepared_job else None,
        "message": "Payment verified successfully. Job queued for printing."
    }


# ==========================================================
# Webhook Endpoint (For Gateway Asynchronous Notifications)
# ==========================================================

@router.post("/webhook")
async def payment_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    db: Session = Depends(get_db)
):
    body = await request.body()
    if x_signature:
        is_valid = PaymentService.verify_webhook_signature(body, x_signature)
        if not is_valid:
            logger.warning("Rejected payment webhook with invalid signature.")
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    try:
        data = json.loads(body.decode("utf-8"))
        logger.info(f"Received valid payment webhook: {data.get('event')}")
        # Process webhook payload event
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error parsing payment webhook: {e}")
        return {"status": "error", "message": str(e)}


# ==========================================================
# Cash Payment Request (Customer requests Cash at counter)
# ==========================================================

@router.post("/cash/{job_id}")
async def cash_payment_request(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Customer selects 'Pay Cash at Counter'.
    Creates a pending cash payment waiting for operator dashboard confirmation.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if not job.total_amount or job.total_amount <= 0:
        prepare_job(job.job_id, db)
        db.refresh(job)

    payment = job.payment
    if not payment:
        payment = Payment(
            job_id=job.job_id,
            provider=PaymentProvider.MANUAL,
            payment_method=PaymentMethod.CASH,
            amount=job.total_amount or Decimal("0.00"),
            status=PaymentStatus.PENDING,
            currency="INR",
            verified=False
        )
        db.add(payment)
    else:
        payment.provider = PaymentProvider.MANUAL
        payment.payment_method = PaymentMethod.CASH
        payment.amount = job.total_amount or Decimal("0.00")
        payment.status = PaymentStatus.PENDING
        payment.verified = False

    job.payment_status = PaymentStatus.PENDING
    job.status = JobStatus.PENDING

    db.commit()
    db.refresh(payment)
    db.refresh(job)

    return {
        "success": True,
        "payment_id": str(payment.payment_id),
        "job_id": str(job.job_id),
        "payment_status": payment.status.value,
        "job_status": job.status.value,
        "amount": float(payment.amount),
        "message": "Cash payment requested. Please pay at counter. Waiting for operator confirmation."
    }


# ==========================================================
# Operator Confirm Cash Payment & Queue Job
# ==========================================================

@router.post("/cash-confirm/{job_id}")
async def confirm_cash_payment(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Operator confirms cash receipt on Dashboard.
    Marks payment as PAID, assigns printer, and queues job for printing.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    payment = job.payment
    if not payment:
        payment = Payment(
            job_id=job.job_id,
            provider=PaymentProvider.MANUAL,
            payment_method=PaymentMethod.CASH,
            amount=job.total_amount or Decimal("0.00"),
            status=PaymentStatus.PENDING,
            currency="INR"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

    PaymentService.process_successful_payment(
        payment,
        transaction_id=f"CASH_{job.job_id.hex[:8]}",
        db=db
    )

    # Assign printer and queue job
    prepared_job = assign_paid_job(job.job_id, db)
    if prepared_job and prepared_job.assigned_printer_id and prepared_job.queue_position == 1:
        await dispatch_job_to_agent(prepared_job)

    return {
        "success": True,
        "payment_id": str(payment.payment_id),
        "job_id": str(job.job_id),
        "payment_status": payment.status.value,
        "job_status": prepared_job.status.value if prepared_job else job.status.value,
        "assigned_printer": str(prepared_job.assigned_printer_id) if prepared_job and prepared_job.assigned_printer_id else None,
        "queue_position": prepared_job.queue_position if prepared_job else None,
        "message": "Cash payment confirmed. Job queued for printing."
    }


# ==========================================================
# Operator Reject Cash Payment / Cancel Request
# ==========================================================

@router.post("/cash-reject/{job_id}")
def reject_cash_payment(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Operator rejects cash request or cancels invalid order.
    """
    job = db.query(ActiveJob).filter(ActiveJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.payment:
        PaymentService.process_failed_payment(
            job.payment,
            failure_reason="Cash payment rejected or cancelled by shop operator.",
            db=db
        )

    job.status = JobStatus.CANCELLED
    db.commit()

    return {
        "success": True,
        "job_id": str(job.job_id),
        "message": "Cash payment request rejected and job cancelled."
    }


# ==========================================================
# Pending Cash Payments for Shop Owner
# ==========================================================

@router.get("/pending-cash/{owner_id}")
def get_pending_cash_jobs(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Returns list of jobs waiting for counter cash confirmation.
    """
    jobs = (
        db.query(ActiveJob)
        .join(Payment, ActiveJob.job_id == Payment.job_id)
        .filter(
            ActiveJob.owner_id == owner_id,
            ActiveJob.status == JobStatus.PENDING,
            Payment.payment_method == PaymentMethod.CASH,
            Payment.status == PaymentStatus.PENDING
        )
        .order_by(ActiveJob.created_at.desc())
        .all()
    )

    results = []
    for j in jobs:
        filenames = [f.original_filename for f in (j.files or [])]
        results.append({
            "job_id": str(j.job_id),
            "customer_name": j.customer_name or "Walk-in Customer",
            "customer_phone": j.customer_phone or "-",
            "total_files": j.total_files or len(filenames),
            "total_pages": j.total_pages or 0,
            "total_copies": j.total_copies or 1,
            "total_amount": float(j.total_amount or 0.0),
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "files": filenames
        })

    return results


# ==========================================================
# Get Payment Details
# ==========================================================

@router.get("/{payment_id}")
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db)
):
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")

    return {
        "payment_id": str(payment.payment_id),
        "job_id": str(payment.job_id),
        "provider": payment.provider.value,
        "payment_method": payment.payment_method.value,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "status": payment.status.value,
        "verified": payment.verified,
        "transaction_id": payment.transaction_id,
        "provider_payment_id": payment.provider_payment_id,
        "verified_at": payment.verified_at,
        "paid_at": payment.paid_at
    }


# ==========================================================
# Get Payment by Job ID
# ==========================================================

@router.get("/job/{job_id}")
def get_payment_by_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    payment = db.query(Payment).filter(Payment.job_id == job_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found for this job.")

    return {
        "payment_id": str(payment.payment_id),
        "job_id": str(payment.job_id),
        "status": payment.status.value,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "provider": payment.provider.value,
        "paid_at": payment.paid_at
    }
