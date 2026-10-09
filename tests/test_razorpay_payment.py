import os
import sys
import hmac
import hashlib
import uuid
import unittest
from decimal import Decimal

# Ensure cloud_server is in Python path
sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import Base, get_db
from app.database.models import (
    ShopOwner,
    ActiveJob,
    JobFile,
    Payment,
    PaymentStatus,
    PaymentProvider,
    PaymentMethod,
    JobStatus,
    PaperSize,
    PrintType
)
from app.services.payment_service import PaymentService

# Test in-memory DB fixture
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestRazorpayPaymentFlow(unittest.TestCase):
    """
    Comprehensive regression test suite for Razorpay payment flow:
    - HMAC-SHA256 signature verification (valid, invalid, whitespace-tolerant)
    - Order ID tampering & mismatch prevention
    - Razorpay SDK field names (razorpay_*) and legacy field names (provider_*)
    - Payment order creation payload structure (key_id, amount_paise)
    - Webhook vs Checkout signature separation
    """

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        self.db = TestingSessionLocal()
        self.client = TestClient(app)

        unique_suffix = uuid.uuid4().hex[:6]
        self.owner_id = uuid.uuid4()
        self.owner = ShopOwner(
            owner_id=self.owner_id,
            shop_name="Razorpay Test Print Shop",
            owner_name="Test Merchant",
            email=f"rzp_{unique_suffix}@shop.local",
            phone=f"987{unique_suffix[:7]}",
            password_hash="testhash123",
            is_active=True
        )
        self.db.add(self.owner)
        self.db.commit()

        self.job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal("45.00"),
            total_files=1,
            total_pages=5,
            customer_name="Alice Customer",
            customer_phone="9998887776"
        )
        self.db.add(self.job)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        # Clean test records
        self.db.query(Payment).delete()
        self.db.query(JobFile).delete()
        self.db.query(ActiveJob).delete()
        self.db.query(ShopOwner).delete()
        self.db.commit()
        self.db.close()
        app.dependency_overrides.clear()

    # ==========================================================
    # 1. Cryptographic HMAC-SHA256 Signature Verification Tests
    # ==========================================================

    def test_valid_hmac_sha256_signature_verification(self):
        secret = "rzp_test_secret_key_12345"
        order_id = "order_DBJOWzybf0sJbb"
        payment_id = "pay_29QQoUBi66xm2f"

        message = f"{order_id}|{payment_id}".encode("utf-8")
        valid_signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

        is_valid = PaymentService.verify_gateway_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=valid_signature,
            secret=secret
        )
        self.assertTrue(is_valid, "Valid Razorpay HMAC signature must verify successfully.")

    def test_invalid_signature_rejection(self):
        secret = "rzp_test_secret_key_12345"
        order_id = "order_DBJOWzybf0sJbb"
        payment_id = "pay_29QQoUBi66xm2f"
        tampered_sig = "a" * 64

        is_valid = PaymentService.verify_gateway_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=tampered_sig,
            secret=secret
        )
        self.assertFalse(is_valid, "Tampered signature must be rejected.")

    def test_mismatched_secret_fails_verification(self):
        correct_secret = "rzp_test_secret_key_12345"
        wrong_secret = "rzp_test_wrong_secret_67890"
        order_id = "order_DBJOWzybf0sJbb"
        payment_id = "pay_29QQoUBi66xm2f"

        message = f"{order_id}|{payment_id}".encode("utf-8")
        signature_generated_with_wrong_key = hmac.new(wrong_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

        is_valid = PaymentService.verify_gateway_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature_generated_with_wrong_key,
            secret=correct_secret
        )
        self.assertFalse(is_valid, "Signature generated with mismatched secret must fail.")

    def test_signature_verification_whitespace_tolerance(self):
        secret = "  rzp_test_secret_key_12345  \n"
        order_id = "  order_DBJOWzybf0sJbb "
        payment_id = "pay_29QQoUBi66xm2f\t"

        clean_secret = secret.strip()
        clean_order_id = order_id.strip()
        clean_payment_id = payment_id.strip()

        message = f"{clean_order_id}|{clean_payment_id}".encode("utf-8")
        valid_sig = hmac.new(clean_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

        is_valid = PaymentService.verify_gateway_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=f"  {valid_sig}  ",
            secret=secret
        )
        self.assertTrue(is_valid, "Leading/trailing whitespace in keys or inputs must be trimmed safely.")

    # ==========================================================
    # 2. End-to-End API Verification Endpoint Tests
    # ==========================================================

    def test_api_verify_payment_with_razorpay_fields(self):
        secret = "rzp_test_secret_abc"
        # Temporarily mock the payment gateway secret in config
        import app.services.payment_service as ps
        original_secret = ps.PAYMENT_GATEWAY_KEY_SECRET
        ps.PAYMENT_GATEWAY_KEY_SECRET = secret

        try:
            # Create payment record
            payment = Payment(
                job_id=self.job.job_id,
                provider=PaymentProvider.RAZORPAY,
                payment_method=PaymentMethod.UPI,
                amount=self.job.total_amount,
                status=PaymentStatus.PENDING,
                provider_payment_id="order_TEST123456"
            )
            self.db.add(payment)
            self.db.commit()

            order_id = "order_TEST123456"
            payment_id = "pay_TEST987654"
            message = f"{order_id}|{payment_id}".encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

            # Call /payment/verify with standard Razorpay field names
            res = self.client.post("/payment/verify", json={
                "payment_id": str(payment.payment_id),
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["payment_status"], "Paid")

            # Verify in DB
            self.db.refresh(payment)
            self.assertEqual(payment.status, PaymentStatus.PAID)
            self.assertTrue(payment.verified)
        finally:
            ps.PAYMENT_GATEWAY_KEY_SECRET = original_secret

    def test_api_verify_payment_rejects_tampered_signature(self):
        secret = "rzp_test_secret_abc"
        import app.services.payment_service as ps
        original_secret = ps.PAYMENT_GATEWAY_KEY_SECRET
        ps.PAYMENT_GATEWAY_KEY_SECRET = secret

        try:
            payment = Payment(
                job_id=self.job.job_id,
                provider=PaymentProvider.RAZORPAY,
                payment_method=PaymentMethod.UPI,
                amount=self.job.total_amount,
                status=PaymentStatus.PENDING,
                provider_payment_id="order_TEST123456"
            )
            self.db.add(payment)
            self.db.commit()

            res = self.client.post("/payment/verify", json={
                "payment_id": str(payment.payment_id),
                "razorpay_order_id": "order_TEST123456",
                "razorpay_payment_id": "pay_TEST987654",
                "razorpay_signature": "SIG_MOCK_INVALID_SIGNATURE"
            })

            self.assertEqual(res.status_code, 400)
            self.assertIn("Invalid signature", res.json()["detail"])

            self.db.refresh(payment)
            self.assertEqual(payment.status, PaymentStatus.FAILED)
        finally:
            ps.PAYMENT_GATEWAY_KEY_SECRET = original_secret

    def test_api_verify_payment_rejects_mismatched_order_id(self):
        secret = "rzp_test_secret_abc"
        import app.services.payment_service as ps
        original_secret = ps.PAYMENT_GATEWAY_KEY_SECRET
        ps.PAYMENT_GATEWAY_KEY_SECRET = secret

        try:
            # Payment recorded with order_ORIGINAL
            payment = Payment(
                job_id=self.job.job_id,
                provider=PaymentProvider.RAZORPAY,
                payment_method=PaymentMethod.UPI,
                amount=self.job.total_amount,
                status=PaymentStatus.PENDING,
                provider_payment_id="order_ORIGINAL_123"
            )
            self.db.add(payment)
            self.db.commit()

            # Attacker presents order_SPOOFED with a valid signature for order_SPOOFED
            spoofed_order = "order_SPOOFED_999"
            payment_id = "pay_TEST987654"
            message = f"{spoofed_order}|{payment_id}".encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

            res = self.client.post("/payment/verify", json={
                "payment_id": str(payment.payment_id),
                "razorpay_order_id": spoofed_order,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })

            self.assertEqual(res.status_code, 400)
            self.assertIn("Mismatched order ID", res.json()["detail"])
        finally:
            ps.PAYMENT_GATEWAY_KEY_SECRET = original_secret

    # ==========================================================
    # 3. Create Payment API Response Structure Test
    # ==========================================================

    def test_create_payment_response_contains_checkout_parameters(self):
        res = self.client.post(f"/payment/create/{self.job.job_id}", json={
            "payment_method": "UPI"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("payment_id", data)
        self.assertIn("job_id", data)
        self.assertIn("amount", data)
        self.assertIn("amount_paise", data)
        self.assertEqual(data["amount_paise"], 4500)
        self.assertIn("currency", data)
        self.assertIn("provider", data)
        self.assertIn("shop_name", data)
        self.assertEqual(data["shop_name"], "Razorpay Test Print Shop")
        self.assertIn("customer_name", data)
        self.assertEqual(data["customer_name"], "Alice Customer")

    # ==========================================================
    # 4. Webhook vs Checkout Signature Separation Test
    # ==========================================================

    def test_webhook_signature_uses_raw_body(self):
        webhook_secret = "whsec_test_secret_999"
        raw_payload = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_123"}}}}'

        expected_webhook_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256
        ).hexdigest()

        is_valid = PaymentService.verify_webhook_signature(
            raw_body=raw_payload,
            received_signature=expected_webhook_sig,
            webhook_secret=webhook_secret
        )
        self.assertTrue(is_valid, "Webhook signature verification must verify raw body against secret.")

        # Tampered body should fail
        tampered_payload = b'{"event":"payment.failed"}'
        is_tampered_valid = PaymentService.verify_webhook_signature(
            raw_body=tampered_payload,
            received_signature=expected_webhook_sig,
            webhook_secret=webhook_secret
        )
        self.assertFalse(is_tampered_valid, "Tampered webhook payload must fail verification.")


if __name__ == "__main__":
    unittest.main()
