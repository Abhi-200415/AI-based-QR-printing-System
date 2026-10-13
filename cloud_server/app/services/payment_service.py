import os
import hmac
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import (
    PAYMENT_GATEWAY_PROVIDER,
    PAYMENT_GATEWAY_KEY_ID,
    PAYMENT_GATEWAY_KEY_SECRET,
    PAYMENT_WEBHOOK_SECRET
)
from app.database.models import (
    ActiveJob,
    Payment,
    PaymentStatus,
    PaymentProvider,
    PaymentMethod
)
from app.utils.logger import logger


class PaymentService:
    """
    Production Payment Service supporting multiple gateways (Razorpay, Cashfree, Stripe, Manual/Cash).
    Implements secure cryptographic signature verification and idempotent state transitions.
    """

    @staticmethod
    def get_configured_provider() -> PaymentProvider:
        from app.core.config import get_payment_diagnostics
        diag = get_payment_diagnostics()
        provider_name = diag["provider"].upper()
        if provider_name == "RAZORPAY":
            return PaymentProvider.RAZORPAY
        elif provider_name == "CASHFREE":
            return PaymentProvider.CASHFREE
        elif provider_name == "UROPAY":
            return PaymentProvider.UROPAY
        return PaymentProvider.MANUAL

    @staticmethod
    def create_payment_order(
        job: ActiveJob,
        payment_method: PaymentMethod = PaymentMethod.UPI,
        db: Optional[Session] = None
    ) -> Payment:
        """
        Creates or retrieves a pending payment record for the active job.
        If a live payment gateway is configured, prepares gateway order parameters.
        """
        from app.core.config import resolve_payment_settings
        cfg = resolve_payment_settings()
        provider = PaymentService.get_configured_provider()
        key_id = cfg["key_id"].strip()
        key_secret = cfg["key_secret"].strip()

        amount = Decimal(str(job.total_amount or 0))
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Cannot create payment for job with amount 0.")

        # If job already has a payment:
        if job.payment:
            # If already paid or failed, return as-is
            if job.payment.status != PaymentStatus.PENDING:
                return job.payment

            # If pending, check if provider or order ID needs updating
            # (e.g. was previously MANUAL/CASH, or gateway has been reconfigured with live keys)
            needs_order_refresh = (
                provider == PaymentProvider.RAZORPAY
                and key_id
                and key_secret
                and (
                    job.payment.provider != PaymentProvider.RAZORPAY
                    or not job.payment.provider_payment_id
                    or not job.payment.provider_payment_id.startswith("order_")
                    or len(job.payment.provider_payment_id) < 18
                )
            )
            if not needs_order_refresh:
                return job.payment

        qr_reference = None
        provider_payment_id = None

        # When Razorpay credentials are provided, create the remote gateway order reference
        if provider == PaymentProvider.RAZORPAY and key_id and key_secret:
            try:
                # Razorpay amounts are in paise (INR * 100)
                amount_in_paise = int(amount * 100)

                import requests
                resp = requests.post(
                    "https://api.razorpay.com/v1/orders",
                    auth=(key_id, key_secret),
                    json={
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "receipt": f"job_{job.job_id.hex[:14]}",
                        "notes": {
                            "job_id": str(job.job_id),
                            "owner_id": str(job.owner_id)
                        }
                    },
                    timeout=10
                )
                if resp.status_code in (200, 201):
                    order_data = resp.json()
                    provider_payment_id = order_data.get("id")
                    logger.info(f"Created Razorpay order: {provider_payment_id} for job {job.job_id}")
                else:
                    err_msg = "Unknown gateway error"
                    try:
                        err_data = resp.json()
                        err_msg = err_data.get("error", {}).get("description") or str(err_data)
                    except Exception:
                        err_msg = resp.text[:200]
                    logger.error(f"Razorpay order API returned status {resp.status_code}: {err_msg}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Payment gateway error ({resp.status_code}): {err_msg}"
                    )

                # Razorpay Standard Checkout handles UPI QR codes and mobile app intents natively
                qr_reference = None
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error creating Razorpay order: {e}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Payment gateway order creation failed: {str(e)}"
                )

        if job.payment:
            # Update existing pending payment record
            job.payment.provider = provider
            job.payment.payment_method = payment_method
            job.payment.amount = amount
            job.payment.provider_payment_id = provider_payment_id
            job.payment.qr_reference = qr_reference
            payment = job.payment
        else:
            payment = Payment(
                job_id=job.job_id,
                provider=provider,
                payment_method=payment_method,
                amount=amount,
                status=PaymentStatus.PENDING,
                currency="INR",
                provider_payment_id=provider_payment_id,
                qr_reference=qr_reference,
                verified=False
            )
            if db:
                db.add(payment)

        if db:
            db.commit()
            db.refresh(payment)

        return payment

    @staticmethod
    def verify_gateway_signature(
        order_id: str,
        payment_id: str,
        signature: str,
        secret: Optional[str] = None
    ) -> bool:
        """
        Cryptographic HMAC-SHA256 verification of payment gateway signatures.
        """
        from app.core.config import resolve_payment_settings
        cfg = resolve_payment_settings()
        import app.services.payment_service as ps
        module_secret = getattr(ps, "PAYMENT_GATEWAY_KEY_SECRET", "")
        key = (secret or module_secret or cfg["key_secret"] or cfg["webhook_secret"] or "").strip()
        if not key:
            logger.warning("No payment secret configured. Rejecting gateway signature verification.")
            return False

        order_id = (order_id or "").strip()
        payment_id = (payment_id or "").strip()
        signature = (signature or "").strip()

        if not order_id or not payment_id or not signature:
            logger.warning("Incomplete parameters for gateway signature verification.")
            return False

        try:
            message = f"{order_id}|{payment_id}".encode("utf-8")
            expected_signature = hmac.new(
                key.encode("utf-8"),
                message,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes,
        received_signature: str,
        webhook_secret: Optional[str] = None
    ) -> bool:
        """
        Verify incoming webhook payload signature.
        """
        from app.core.config import resolve_payment_settings
        cfg = resolve_payment_settings()
        import app.services.payment_service as ps
        module_secret = getattr(ps, "PAYMENT_GATEWAY_KEY_SECRET", "")
        module_webhook = getattr(ps, "PAYMENT_WEBHOOK_SECRET", "")
        secret = (webhook_secret or module_webhook or cfg["webhook_secret"] or module_secret or cfg["key_secret"] or "").strip()
        if not secret:
            return False

        try:
            expected_sig = hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_sig, received_signature)
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    @staticmethod
    def process_successful_payment(
        payment: Payment,
        transaction_id: Optional[str] = None,
        provider_payment_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> bool:
        """
        Idempotent payment confirmation. Marks payment as PAID, updates job status.
        """
        if payment.status == PaymentStatus.PAID:
            logger.info(f"Payment {payment.payment_id} was already marked PAID.")
            return True

        now = datetime.utcnow()
        payment.status = PaymentStatus.PAID
        payment.verified = True
        payment.verified_at = now
        payment.paid_at = now
        if transaction_id:
            payment.transaction_id = transaction_id
        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id
        payment.failure_reason = None

        if payment.job:
            payment.job.payment_status = PaymentStatus.PAID

        if db:
            db.commit()
            db.refresh(payment)

        logger.info(f"Payment {payment.payment_id} successfully processed and marked PAID.")
        return True

    @staticmethod
    def process_failed_payment(
        payment: Payment,
        failure_reason: str,
        db: Optional[Session] = None
    ):
        payment.status = PaymentStatus.FAILED
        payment.verified = True
        payment.verified_at = datetime.utcnow()
        payment.failure_reason = failure_reason

        if payment.job:
            payment.job.payment_status = PaymentStatus.FAILED

        if db:
            db.commit()
            db.refresh(payment)

        logger.info(f"Payment {payment.payment_id} marked FAILED: {failure_reason}")
