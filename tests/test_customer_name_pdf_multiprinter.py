import os
os.environ["TESTING"] = "true"
import sys
import uuid
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import HTTPException

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
    JobStatus,
    PaperSize,
    PrintType
)
from app.services.customer_service import validate_customer_name, clear_customer_name_after_completion
from app.services.receipt_pdf_service import generate_receipt_pdf, build_receipt_dict_for_job, get_receipt_pdf_bytes
from app.services.assignment_service import is_printer_eligible_for_file, assign_printer, get_job_time_estimates

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

app.dependency_overrides[get_db] = override_get_db


class TestCustomerNamePdfMultiPrinter(unittest.TestCase):
    """
    Comprehensive integration test suite covering:
    - Customer name validation & sanitization (Objective 2.1)
    - Authentic ReportLab PDF receipt generation & download (Objective 3)
    - Temporary customer name retention & transactional cleanup upon child jobs completion (Objective 2.3 & 2.4)
    - Mixed-document multi-printer assignment & parallel completion estimates (Objective 5 & 8)
    - Safe job retry without duplicate printing (Objective 6.3)
    """

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        self.db = TestingSessionLocal()
        self.client = TestClient(app)

        self.owner_id = uuid.uuid4()
        self.owner = ShopOwner(
            owner_id=self.owner_id,
            shop_name="Print Hub Express",
            owner_name="Shop Manager",
            email=f"hub_{uuid.uuid4().hex[:6]}@printhub.local",
            phone="9876543210",
            password_hash="hashed_pw_123",
            is_active=True
        )
        self.db.add(self.owner)
        self.db.commit()

        # Standard online printer for owner
        self.default_printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner_id,
            printer_name="Standard Shop Printer",
            supports_bw=True,
            supports_color=True,
            supports_duplex=True,
            supports_a3=True,
            supports_legal=True,
            status=PrinterStatus.ONLINE,
            is_available=True,
            current_queue=0,
            total_jobs_printed=100
        )
        self.db.add(self.default_printer)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(JobFile).delete()
        self.db.query(Payment).delete()
        self.db.query(ActiveJob).delete()
        self.db.query(Printer).delete()
        self.db.query(ShopOwner).delete()
        self.db.commit()
        self.db.close()

    def test_customer_name_validation(self):
        # Valid names
        valid_cases = ["John Doe", "  O'Connor-Smith  ", "José María 123", "P. K. Sharma"]
        for raw in valid_cases:
            sanitized = validate_customer_name(raw)
            self.assertEqual(sanitized, raw.strip())

        # Invalid: empty / whitespace
        for invalid in ["", "   ", "\t\n  "]:
            with self.assertRaises(HTTPException) as cm:
                validate_customer_name(invalid)
            self.assertEqual(cm.exception.status_code, 400)

        # Invalid: HTML / script tags
        for attack in ["<script>alert(1)</script>", "John <b>Doe</b>", "Name <style>"]:
            with self.assertRaises(HTTPException) as cm:
                validate_customer_name(attack)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertIn("invalid", cm.exception.detail.lower())

        # Invalid: too short
        with self.assertRaises(HTTPException) as cm:
            validate_customer_name("A")
        self.assertEqual(cm.exception.status_code, 400)

    def test_authentic_pdf_receipt_generation(self):
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_amount=Decimal("65.00"),
            total_files=1,
            total_pages=10,
            customer_name="Dr. Evelyn Stone"
        )
        self.db.add(job)
        self.db.commit()

        file_item = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Research_Paper.pdf",
            paper_size=PaperSize.A4,
            print_type=PrintType.COLOR,
            duplex=True,
            page_count=10,
            copies=1,
            estimated_cost=Decimal("65.00")
        )
        self.db.add(file_item)
        self.db.commit()

        # Generate PDF directly
        receipt_data = build_receipt_dict_for_job(job, self.db)
        self.assertEqual(receipt_data["customer_name"], "Dr. Evelyn Stone")
        pdf_bytes = generate_receipt_pdf(receipt_data)
        self.assertIsNotNone(pdf_bytes)
        self.assertGreater(len(pdf_bytes), 500)
        # Check standard binary PDF header magic bytes %PDF-
        self.assertEqual(pdf_bytes[:5], b"%PDF-")

        # Test download endpoint via FastAPI client
        response = self.client.get(f"/receipt/job/{job.job_id}/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        expected_short_id = str(job.job_id)[:8]
        self.assertIn(f"Receipt_Order_{expected_short_id}.pdf", response.headers["content-disposition"])
        self.assertEqual(response.content[:5], b"%PDF-")

    def test_customer_name_temporary_retention_and_cleanup(self):
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.PRINTING,
            payment_status=PaymentStatus.PAID,
            total_amount=Decimal("40.00"),
            total_files=2,
            total_pages=15,
            customer_name="Alice Smith"
        )
        self.db.add(job)
        self.db.commit()

        f1 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Part1.pdf",
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False,
            page_count=10,
            copies=1,
            status=JobStatus.PRINTING
        )
        f2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Part2.pdf",
            paper_size=PaperSize.A4,
            print_type=PrintType.COLOR,
            duplex=False,
            page_count=5,
            copies=1,
            status=JobStatus.PENDING
        )
        self.db.add_all([f1, f2])
        self.db.commit()

        # Step 1: Pre-generate PDF receipt while customer name is present
        pdf_bytes, filename = get_receipt_pdf_bytes(job, self.db)
        self.assertEqual(pdf_bytes[:5], b"%PDF-")
        self.assertGreater(len(pdf_bytes), 500)

        # Step 2: Try clearing when only f1 is complete - should NOT clear
        f1.status = JobStatus.COMPLETED
        f1.print_completed = True
        self.db.commit()

        cleared = clear_customer_name_after_completion(job.job_id, self.db)
        self.assertFalse(cleared)
        self.db.refresh(job)
        self.assertEqual(job.customer_name, "Alice Smith")

        # Step 3: Complete f2 and parent job -> now all child jobs are completed
        f2.status = JobStatus.COMPLETED
        f2.print_completed = True
        job.status = JobStatus.COMPLETED
        self.db.commit()

        cleared = clear_customer_name_after_completion(job.job_id, self.db)
        self.assertTrue(cleared)
        self.db.refresh(job)
        # Verify customer_name is now scrubbed from database
        self.assertIsNone(job.customer_name)

        # Step 4: Verify cached PDF receipt remains accessible and intact for customer
        response = self.client.get(f"/receipt/job/{job.job_id}/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.content[:5], b"%PDF-")

    def test_mixed_document_multi_printer_assignment(self):
        # Remove the all-in-one default printer so we can test true multi-printer splitting
        self.db.delete(self.default_printer)
        self.db.commit()

        # Create Mono-only and Color-only printers
        mono_printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner_id,
            printer_name="HP Mono Laser 100",
            supports_bw=True,
            supports_color=False,
            supports_duplex=True,
            supports_a3=False,
            supports_legal=False,
            status=PrinterStatus.ONLINE,
            is_available=True,
            current_queue=0,
            total_jobs_printed=50
        )
        color_printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner_id,
            printer_name="Epson Color 500",
            supports_bw=False,
            supports_color=True,
            supports_duplex=True,
            supports_a3=True,
            supports_legal=True,
            status=PrinterStatus.ONLINE,
            is_available=True,
            current_queue=0,
            total_jobs_printed=20
        )
        self.db.add_all([mono_printer, color_printer])
        self.db.commit()

        # Color file eligibility
        color_file = JobFile(
            file_id=uuid.uuid4(),
            original_filename="Poster.pdf",
            print_type=PrintType.COLOR,
            paper_size=PaperSize.A4,
            duplex=False
        )
        self.assertFalse(is_printer_eligible_for_file(mono_printer, color_file))
        self.assertTrue(is_printer_eligible_for_file(color_printer, color_file))

        # Mono file eligibility
        mono_file = JobFile(
            file_id=uuid.uuid4(),
            original_filename="Invoice.pdf",
            print_type=PrintType.BW,
            paper_size=PaperSize.A4,
            duplex=False
        )
        self.assertTrue(is_printer_eligible_for_file(mono_printer, mono_file))
        self.assertFalse(is_printer_eligible_for_file(color_printer, mono_file))

        # Create mixed order
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PAID,
            total_files=2,
            total_pages=6,
            customer_name="Bob Brown"
        )
        self.db.add(job)
        self.db.commit()

        color_file.job_id = job.job_id
        mono_file.job_id = job.job_id
        self.db.add_all([color_file, mono_file])
        self.db.commit()

        assigned_p = assign_printer(job, self.db)
        self.assertIsNotNone(assigned_p)

        self.db.refresh(color_file)
        self.db.refresh(mono_file)

        # Check that color file was routed to color printer
        self.assertEqual(color_file.assigned_printer_id, color_printer.printer_id)
        # Check that mono file was routed to mono printer
        self.assertEqual(mono_file.assigned_printer_id, mono_printer.printer_id)

        # Test timing estimates for the multi-printer assigned job
        estimates = get_job_time_estimates(job, self.db)
        self.assertTrue(estimates["available"])
        self.assertIn("queue_wait_seconds", estimates)
        self.assertIn("print_duration_seconds", estimates)
        self.assertIn("total_seconds", estimates)
        self.assertIn("Multi-Printer", estimates["printer_name"])

    def test_safe_retry_mechanism(self):
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            status=JobStatus.FAILED,
            payment_status=PaymentStatus.PAID,
            total_files=2,
            total_pages=10,
            customer_name="Carol Danvers"
        )
        self.db.add(job)
        self.db.commit()

        # Child file 1 succeeded, child file 2 failed
        f1 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="DocA.pdf",
            status=JobStatus.COMPLETED,
            print_completed=True
        )
        f2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="DocB.pdf",
            status=JobStatus.FAILED,
            print_completed=False
        )
        self.db.add_all([f1, f2])
        self.db.commit()

        # Execute retry endpoint
        response = self.client.post(f"/jobs/{job.job_id}/retry")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success", False))

        self.db.refresh(job)
        self.db.refresh(f1)
        self.db.refresh(f2)

        # Parent job should be reset to QUEUED or PENDING
        self.assertIn(job.status, [JobStatus.PENDING, JobStatus.QUEUED])
        # File 1 must NOT be re-printed (retains COMPLETED status)
        self.assertEqual(f1.status, JobStatus.COMPLETED)
        # File 2 must be reset to PENDING / QUEUED
        self.assertIn(f2.status, [JobStatus.PENDING, JobStatus.QUEUED])


if __name__ == "__main__":
    unittest.main()
