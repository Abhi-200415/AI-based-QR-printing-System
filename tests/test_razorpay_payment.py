import os
os.environ["TESTING"] = "true"
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
    Printer,
    PrinterStatus,
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

    # ==========================================================
    # 5. Environment Resolution & Alias Precedence Tests
    # ==========================================================

    def test_live_mode_selected_when_explicitly_configured(self):
        from app.core.config import resolve_payment_settings
        env = {
            "PAYMENT_MODE": "live",
            "RAZORPAY_LIVE_KEY_ID": "rzp_live_my_key_123",
            "RAZORPAY_LIVE_KEY_SECRET": "sec_live_999"
        }
        cfg = resolve_payment_settings(env)
        self.assertEqual(cfg["mode"], "live")
        self.assertEqual(cfg["key_id"], "rzp_live_my_key_123")
        self.assertEqual(cfg["key_secret"], "sec_live_999")
        self.assertEqual(cfg["provider"], "RAZORPAY")

    def test_test_mode_selected_when_explicitly_configured(self):
        from app.core.config import resolve_payment_settings
        env = {
            "PAYMENT_MODE": "test",
            "RAZORPAY_TEST_KEY_ID": "rzp_test_abc_789",
            "RAZORPAY_TEST_KEY_SECRET": "sec_test_111"
        }
        cfg = resolve_payment_settings(env)
        self.assertEqual(cfg["mode"], "test")
        self.assertEqual(cfg["key_id"], "rzp_test_abc_789")
        self.assertEqual(cfg["key_secret"], "sec_test_111")
        self.assertEqual(cfg["provider"], "RAZORPAY")

    def test_deterministic_alias_precedence_live_over_stale_test_keys(self):
        """
        Exact Render Scenario: User updated RAZORPAY_KEY_ID with LIVE key,
        but PAYMENT_GATEWAY_KEY_ID still contained the old TEST key.
        The system must deterministically select the LIVE credentials.
        """
        from app.core.config import resolve_payment_settings
        env = {
            "PAYMENT_GATEWAY_KEY_ID": "rzp_test_stale_key_111",
            "PAYMENT_GATEWAY_KEY_SECRET": "sec_test_stale_secret_222",
            "RAZORPAY_KEY_ID": "rzp_live_fresh_key_333",
            "RAZORPAY_KEY_SECRET": "sec_live_fresh_secret_444"
        }
        cfg = resolve_payment_settings(env)
        self.assertEqual(cfg["mode"], "live", "Presence of rzp_live_ key must infer live mode.")
        self.assertEqual(cfg["key_id"], "rzp_live_fresh_key_333", "Live key must take precedence over stale test key.")
        self.assertEqual(cfg["key_secret"], "sec_live_fresh_secret_444", "Matching live secret must be paired with live key.")
        self.assertEqual(cfg["provider"], "RAZORPAY")

    def test_provider_auto_detected_when_keys_present_without_explicit_provider(self):
        from app.core.config import resolve_payment_settings
        env = {
            "RAZORPAY_KEY_ID": "rzp_live_test_auto_detect",
            "RAZORPAY_KEY_SECRET": "sec_auto_detect"
        }
        cfg = resolve_payment_settings(env)
        self.assertEqual(cfg["provider"], "RAZORPAY", "Provider must auto-detect as RAZORPAY when credentials exist.")

    def test_secret_masking_and_no_leak_in_diagnostics(self):
        from app.core.config import mask_key_id, get_payment_diagnostics
        masked = mask_key_id("rzp_live_1234567890abcdef")
        self.assertTrue(masked.startswith("rzp_live_****"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertNotIn("1234567890", masked)

        # Check diagnostics endpoint
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("payment", data)
        p_diag = data["payment"]
        self.assertIn("provider", p_diag)
        self.assertIn("mode", p_diag)
        self.assertIn("key_id_masked", p_diag)
        self.assertIn("key_secret_configured", p_diag)
        # Ensure no secret strings leaked anywhere in response body
        self.assertNotIn("sec_", res.text)
        self.assertNotIn("key_secret", p_diag.get("key_id_masked", ""))

    def test_missing_credentials_fails_signature_safely(self):
        # Empty secret
        is_valid = PaymentService.verify_gateway_signature(
            order_id="order_123",
            payment_id="pay_456",
            signature="sig_789",
            secret=""
        )
        self.assertFalse(is_valid, "Signature check with missing secret must return False safely.")

    # ==========================================================
    # 6. Mocked Remote Order Creation & Gateway Error Handling
    # ==========================================================

    def test_mocked_gateway_order_creation_success(self):
        from unittest.mock import patch, MagicMock
        from app.core.config import resolve_payment_settings

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "order_MOCK_RZP_998877"}

        with patch("os.environ", {
            "PAYMENT_MODE": "live",
            "RAZORPAY_KEY_ID": "rzp_live_mock_test_key",
            "RAZORPAY_KEY_SECRET": "sec_live_mock_secret"
        }):
            with patch("requests.post", return_value=mock_resp):
                payment = PaymentService.create_payment_order(
                    job=self.job,
                    payment_method=PaymentMethod.UPI,
                    db=self.db
                )
                self.assertEqual(payment.provider_payment_id, "order_MOCK_RZP_998877")
                self.assertEqual(payment.provider, PaymentProvider.RAZORPAY)

    def test_mocked_gateway_order_creation_failure_raises_502(self):
        from unittest.mock import patch, MagicMock
        from fastapi import HTTPException

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"description": "Invalid key or secret."}}

        with patch("os.environ", {
            "PAYMENT_MODE": "live",
            "RAZORPAY_KEY_ID": "rzp_live_mock_test_key",
            "RAZORPAY_KEY_SECRET": "sec_live_mock_secret"
        }):
            with patch("requests.post", return_value=mock_resp):
                with self.assertRaises(HTTPException) as ctx:
                    PaymentService.create_payment_order(
                        job=self.job,
                        payment_method=PaymentMethod.UPI,
                        db=self.db
                    )
                self.assertEqual(ctx.exception.status_code, 502)
                self.assertIn("Invalid key or secret", ctx.exception.detail)

    # ==========================================================
    # 7. Price Summary Frontend & Time Estimate Tests
    # ==========================================================

    def test_price_summary_page_renders_payment_button_with_exact_amount(self):
        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=self.job.job_id,
            original_filename="TestDocument.pdf",
            file_path="test_doc.pdf",
            file_type="application/pdf",
            file_size=1024,
            page_count=5,
            copies=1,
            print_type=PrintType.BW,
            paper_size=PaperSize.A4,
            duplex=False,
            estimated_cost=Decimal("45.00")
        )
        self.db.add(file)
        self.db.commit()

        res = self.client.get(f"/file/summary/{file.file_id}")
        self.assertEqual(res.status_code, 200)
        # Verify the Confirm Order & Pay button text and amount
        self.assertIn("Confirm Order & Pay", res.text)
        self.assertIn("45.00", res.text)
        # Verify the presence of the estimated waiting & printing time section
        self.assertIn("Estimated Waiting & Printing Time", res.text)
        self.assertIn("Note:", res.text)

    def test_time_estimates_calculation_with_eligible_online_printer(self):
        from app.services.assignment_service import get_job_time_estimates

        # Add file to job
        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=self.job.job_id,
            original_filename="Brochure.pdf",
            file_path="brochure.pdf",
            file_type="application/pdf",
            file_size=2048,
            page_count=10,
            copies=1,
            print_type=PrintType.BW,
            paper_size=PaperSize.A4,
            duplex=False,
            estimated_cost=Decimal("45.00")
        )
        self.db.add(file)

        printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner_id,
            printer_name="Main Canon Laser",
            printer_model="Canon LBP2900",
            status=PrinterStatus.ONLINE,
            is_physical=True,
            is_virtual=False,
            is_available=True,
            supports_bw=True,
            supports_color=False,
            supports_duplex=False,
            current_queue=0
        )
        self.db.add(printer)
        self.db.commit()

        est = get_job_time_estimates(self.job, self.db)
        self.assertTrue(est["available"])
        self.assertEqual(est["queue_wait_seconds"], 0.0)
        self.assertEqual(est["queue_wait_display"], "0 sec")
        self.assertGreater(est["print_duration_seconds"], 0.0)
        self.assertEqual(est["total_seconds"], est["queue_wait_seconds"] + est["print_duration_seconds"])
        self.assertEqual(est["printer_name"], "Main Canon Laser")
        self.assertEqual(est["printer_status"], "Eligible & Ready")
        self.assertIn("Estimates are calculated in real time", est["disclaimer"])

    def test_time_estimates_missing_data_fallback_when_printers_offline(self):
        from app.services.assignment_service import get_job_time_estimates

        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=self.job.job_id,
            original_filename="OfflineDoc.pdf",
            file_path="offline_doc.pdf",
            file_type="application/pdf",
            file_size=1024,
            page_count=2,
            copies=1,
            print_type=PrintType.BW,
            paper_size=PaperSize.A4,
            duplex=False,
            estimated_cost=Decimal("45.00")
        )
        self.db.add(file)
        self.db.commit()

        # No printer added for this owner
        est = get_job_time_estimates(self.job, self.db)
        self.assertFalse(est["available"])
        self.assertEqual(est["total_display"], "Estimate unavailable")
        self.assertIn("No compatible printers", est["disclaimer"])

        # Also verify rendering on the summary page displays the defensive fallback
        res = self.client.get(f"/file/summary/{file.file_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Estimate Unavailable", res.text)

    def test_queue_waiting_time_dynamically_includes_jobs_ahead(self):
        from app.services.assignment_service import get_job_time_estimates

        printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner_id,
            printer_name="Queue Test Printer",
            printer_model="HP LaserJet M404",
            status=PrinterStatus.ONLINE,
            is_physical=True,
            is_virtual=False,
            is_available=True,
            supports_bw=True,
            supports_color=True,
            supports_duplex=True,
            current_queue=0
        )
        self.db.add(printer)

        # Job 1 (already paid and in queue)
        job1 = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.QUEUED,
            payment_status=PaymentStatus.PAID,
            total_amount=Decimal("30.00"),
            assigned_printer_id=printer.printer_id,
            queue_position=1
        )
        self.db.add(job1)
        file1 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job1.job_id,
            original_filename="Job1.pdf",
            file_path="job1.pdf",
            file_type="application/pdf",
            file_size=1024,
            page_count=10,
            copies=1,
            print_type=PrintType.BW,
            paper_size=PaperSize.A4,
            duplex=False,
            estimated_cost=Decimal("30.00")
        )
        self.db.add(file1)

        # Job 2 (unassigned, prospective customer at checkout)
        file2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=self.job.job_id,
            original_filename="Job2.pdf",
            file_path="job2.pdf",
            file_type="application/pdf",
            file_size=1024,
            page_count=5,
            copies=1,
            print_type=PrintType.BW,
            paper_size=PaperSize.A4,
            duplex=False,
            estimated_cost=Decimal("45.00")
        )
        self.db.add(file2)
        self.db.commit()

        # Job 2's queue wait should include Job 1's duration
        est = get_job_time_estimates(self.job, self.db)
        self.assertTrue(est["available"])
        self.assertGreater(est["queue_wait_seconds"], 0.0, "Queue wait must count Job 1 ahead in queue.")
        self.assertGreater(est["total_seconds"], est["print_duration_seconds"])

    def test_amount_integrity_and_server_side_enforcement(self):
        # Verify creating payment fails if total_amount is 0 or negative
        zero_job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal("0.00")
        )
        self.db.add(zero_job)
        self.db.commit()

        res = self.client.post(f"/payment/create/{zero_job.job_id}", json={"payment_method": "UPI"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("price could not be calculated", res.json()["detail"])

    def test_duplicate_order_creation_and_idempotency_prevention(self):
        # First call creates the payment
        res1 = self.client.post(f"/payment/create/{self.job.job_id}", json={"payment_method": "UPI"})
        self.assertEqual(res1.status_code, 200)
        p1 = res1.json()

        # Second call for the same job should return the exact same payment_id without re-creating
        res2 = self.client.post(f"/payment/create/{self.job.job_id}", json={"payment_method": "UPI"})
        self.assertEqual(res2.status_code, 200)
        p2 = res2.json()

        self.assertEqual(p1["payment_id"], p2["payment_id"])
        self.assertEqual(p1["amount"], p2["amount"])

        # Count in database must remain exactly 1 payment record
        count = self.db.query(Payment).filter(Payment.job_id == self.job.job_id).count()
        self.assertEqual(count, 1)

    def test_job_status_api_returns_timing_estimates_without_leaking_others(self):
        res = self.client.get(f"/jobs/{self.job.job_id}/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("job_id", data)
        self.assertIn("estimated_queue_wait_display", data)
        self.assertIn("estimated_print_duration_display", data)
        self.assertIn("estimated_total_display", data)
        self.assertIn("timing_disclaimer", data)
        self.assertNotIn("Alice Customer", str(data.get("other_customers", "")))


if __name__ == "__main__":
    unittest.main()
