from uuid import UUID
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.database.models import (
    ActiveJob,
    Payment,
    PaymentStatus,
    PaymentProvider,
    PaymentMethod
)

from app.services.job_service import (
    prepare_job,
    assign_paid_job
)

from app.services.dispatch_service import (
    dispatch_job_to_agent
)

router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)
# ==========================================================
# Create Payment
# ==========================================================

@router.post("/create/{job_id}")
def create_payment(
    job_id: UUID,
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

    # ------------------------------------------------------
    # Payment already exists
    # ------------------------------------------------------

    if job.payment:

        return {

            "payment_id":
                str(job.payment.payment_id),

            "status":
                job.payment.status.value,

            "amount":
                float(job.payment.amount),

            "currency":
                job.payment.currency

        }

    # ------------------------------------------------------
    # Calculate pricing before creating payment
    # ------------------------------------------------------

    if not job.total_amount or job.total_amount <= 0:

        prepared_job = prepare_job(
            job.job_id,
            db
        )

        if not prepared_job:

            raise HTTPException(
                status_code=500,
                detail="Unable to prepare job pricing."
            )

        db.refresh(job)

    # ------------------------------------------------------
    # Verify price
    # ------------------------------------------------------

    if not job.total_amount or job.total_amount <= 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Job price could not be calculated."
            )
        )

    # ------------------------------------------------------
    # Create pending payment
    # ------------------------------------------------------

    payment = Payment(

        job_id=job.job_id,

        provider=PaymentProvider.MANUAL,

        payment_method=PaymentMethod.UPI,

        amount=job.total_amount,

        status=PaymentStatus.PENDING,

        currency="INR",

        verified=False

    )

    db.add(payment)

    db.commit()

    db.refresh(payment)

    return {

        "payment_id":
            str(payment.payment_id),

        "job_id":
            str(job.job_id),

        "amount":
            float(payment.amount),

        "currency":
            payment.currency,

        "status":
            payment.status.value,

        "message":
            "Payment created and waiting for verification."

    }


# ==========================================================
# Get Payment Status
# ==========================================================

@router.get("/{payment_id}")
def payment_status(
    payment_id: UUID,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.payment_id == payment_id
        )
        .first()
    )

    if not payment:

        raise HTTPException(
            status_code=404,
            detail="Payment not found."
        )

    return {

        "payment_id":
            str(payment.payment_id),

        "job_id":
            str(payment.job_id),

        "provider":
            payment.provider.value,

        "payment_method":
            payment.payment_method.value,

        "amount":
            float(payment.amount),

        "currency":
            payment.currency,

        "status":
            payment.status.value,

        "verified":
            payment.verified,

        "transaction_id":
            payment.transaction_id,

        "provider_payment_id":
            payment.provider_payment_id,

        "verified_at":
            payment.verified_at,

        "paid_at":
            payment.paid_at,

        "failure_reason":
            payment.failure_reason

    }


# ==========================================================
# Payment Verification Callback
# ==========================================================

@router.post("/callback/{payment_id}")
async def payment_callback(
    payment_id: UUID,
    success: bool,
    transaction_id: str = None,
    provider_payment_id: str = None,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.payment_id == payment_id
        )
        .first()
    )

    if not payment:

        raise HTTPException(
            status_code=404,
            detail="Payment not found."
        )

    job = payment.job

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job associated with payment not found."
        )

    # ------------------------------------------------------
    # Prevent duplicate successful processing
    # ------------------------------------------------------

    if payment.status == PaymentStatus.PAID:

        return {

            "success": True,

            "payment_id":
                str(payment.payment_id),

            "status":
                payment.status.value,

            "message":
                "Payment was already verified."

        }

    # ======================================================
    # SUCCESS
    # ======================================================

    if success:

        payment.status = PaymentStatus.PAID

        payment.verified = True

        payment.verified_at = datetime.utcnow()

        payment.paid_at = datetime.utcnow()

        payment.transaction_id = (
            transaction_id
        )

        payment.provider_payment_id = (
            provider_payment_id
        )

        payment.failure_reason = None

        # --------------------------------------------------
        # Synchronize job payment status
        # --------------------------------------------------

        job.payment_status = (
            PaymentStatus.PAID
        )

        db.commit()

        # --------------------------------------------------
        # Assign printer AFTER payment
        # --------------------------------------------------

        prepared_job = assign_paid_job(
            job.job_id,
            db
        )


        if (
            prepared_job
            and prepared_job.assigned_printer_id
            and prepared_job.queue_position == 1
        ):
            await dispatch_job_to_agent(
                prepared_job
            )

        if not prepared_job:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Payment succeeded, "
                    "but job assignment failed."
                )
            )

        # --------------------------------------------------
        # No compatible printer available
        # --------------------------------------------------

        if not prepared_job.assigned_printer_id:

            db.refresh(payment)

            return {

                "success": True,

                "payment_id":
                    str(payment.payment_id),

                "job_id":
                    str(job.job_id),

                "payment_status":
                    payment.status.value,

                "assigned_printer":
                    None,

                "queue_position":
                    None,

                "message":
                    (
                        "Payment verified, "
                        "but no compatible printer "
                        "is currently available."
                    )

            }

        db.refresh(payment)

        return {

            "success": True,

            "payment_id":
                str(payment.payment_id),

            "job_id":
                str(job.job_id),

            "payment_status":
                payment.status.value,

            "job_status":
                prepared_job.status.value,

            "assigned_printer":
                str(
                    prepared_job.assigned_printer_id
                ),

            "queue_position":
                prepared_job.queue_position,

            "message":
                (
                    "Payment verified successfully. "
                    "Job assigned and added to queue."
                )

        }

    # ======================================================
    # FAILURE
    # ======================================================

    payment.status = PaymentStatus.FAILED

    payment.verified = True

    payment.verified_at = datetime.utcnow()

    payment.failure_reason = (
        "Payment verification failed."
    )

    job.payment_status = (
        PaymentStatus.FAILED
    )

    db.commit()

    return {

        "success": False,

        "payment_id":
            str(payment.payment_id),

        "job_id":
            str(job.job_id),

        "payment_status":
            payment.status.value,

        "message":
            "Payment verification failed."

    }


# ==========================================================
# Cash Payment
# ==========================================================

@router.post("/cash/{job_id}")
async def cash_payment(
    job_id: UUID,
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

    # ------------------------------------------------------
    # Calculate pricing if necessary
    # ------------------------------------------------------

    if not job.total_amount or job.total_amount <= 0:

        prepared_job = prepare_job(
            job.job_id,
            db
        )

        if not prepared_job:

            raise HTTPException(
                status_code=500,
                detail="Unable to prepare job pricing."
            )

        db.refresh(job)

    # ------------------------------------------------------
    # Verify price
    # ------------------------------------------------------

    if not job.total_amount or job.total_amount <= 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Job price could not be calculated."
            )
        )

    # ------------------------------------------------------
    # Create or update payment
    # ------------------------------------------------------

    payment = job.payment

    if not payment:

        payment = Payment(

            job_id=job.job_id,

            provider=PaymentProvider.MANUAL,

            payment_method=PaymentMethod.CASH,

            amount=job.total_amount,

            currency="INR",

            status=PaymentStatus.PAID,

            verified=True,

            verified_at=datetime.utcnow(),

            paid_at=datetime.utcnow()

        )

        db.add(payment)

    else:

        payment.status = PaymentStatus.PAID

        payment.payment_method = PaymentMethod.CASH

        payment.verified = True

        payment.verified_at = datetime.utcnow()

        payment.paid_at = datetime.utcnow()

        payment.failure_reason = None

    # ------------------------------------------------------
    # Synchronize job payment status
    # ------------------------------------------------------

    job.payment_status = PaymentStatus.PAID

    db.commit()

    # ------------------------------------------------------
    # Assign printer AFTER payment
    # ------------------------------------------------------

    prepared_job = assign_paid_job(
        job.job_id,
        db
    )

    if prepared_job and prepared_job.assigned_printer_id:
        await dispatch_job_to_agent(
            prepared_job
        )

    if not prepared_job:

        raise HTTPException(
            status_code=500,
            detail=(
                "Payment recorded, "
                "but job assignment failed."
            )
        )

    # ------------------------------------------------------
    # No printer available
    # ------------------------------------------------------

    if not prepared_job.assigned_printer_id:

        return {

            "success": True,

            "job_id":
                str(job.job_id),

            "payment_status":
                PaymentStatus.PAID.value,

            "job_status":
                prepared_job.status.value,

            "assigned_printer":
                None,

            "queue_position":
                None,

            "message":
                (
                    "Cash payment recorded, "
                    "but no compatible printer "
                    "is currently available."
                )

        }

    return {

        "success": True,

        "job_id":
            str(job.job_id),

        "payment_status":
            PaymentStatus.PAID.value,

        "job_status":
            prepared_job.status.value,

        "assigned_printer":
            str(
                prepared_job.assigned_printer_id
            ),

        "queue_position":
            prepared_job.queue_position,

        "message":
            "Cash payment recorded and job processed."

    }





