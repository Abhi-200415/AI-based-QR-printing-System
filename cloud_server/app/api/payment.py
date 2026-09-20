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
# Cash Payment (Operator / Counter Confirmation)
# ==========================================================

@router.post("/cash/{job_id}")
async def cash_payment(
    job_id: UUID,
    db: Session = Depends(get_db)
):
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

    # Assign printer and queue
    prepared_job = assign_paid_job(job.job_id, db)
    if prepared_job and prepared_job.assigned_printer_id and prepared_job.queue_position == 1:
        await dispatch_job_to_agent(prepared_job)

    return {
        "success": True,
        "payment_id": str(payment.payment_id),
        "job_id": str(job.job_id),
        "payment_status": payment.status.value,
        "job_status": prepared_job.status.value if prepared_job else job.status.value,
        "queue_position": prepared_job.queue_position if prepared_job else None,
        "message": "Cash payment recorded. Job added to queue."
    }


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
