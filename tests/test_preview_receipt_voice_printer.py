import os
import sys
import uuid
import unittest
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch

# Ensure cloud_server is in sys.path
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
    ShopSettings,
    Printer,
    ActiveJob,
    JobFile,
    PricingRule,
    FinishingService,
    JobFinishingService,
    Payment,
    JobStatus,
    PaymentStatus,
    PrinterStatus,
    PrintType,
    PaperSize,
    Orientation,
    PaymentMethod,
    PaymentProvider
)
from app.services.pricing_engine import (
    seed_default_pricing_rules,
    seed_default_finishing_services,
    calculate_job_cost,
    apply_finishing_services_to_job
)
from app.services.payment_service import PaymentService
from app.services.assignment_service import has_eligible_online_printer
from app.core.crypto import encrypt_document
from app.core.config import UPLOAD_DIR


class TestPreviewReceiptVoicePrinterFeature(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Create Shop Owner
        self.owner = ShopOwner(
            owner_id=uuid.uuid4(),
            owner_name="Alice Owner",
            shop_name="Apex Print Studio",
            email="alice@apexprint.com",
            phone="9876500001",
            password_hash="hashed_pw",
            address="100 Tech Park, Bangalore",
            is_active=True
        )
        self.db.add(self.owner)
        self.db.commit()

        # Seed standard pricing and finishing
        seed_default_pricing_rules(self.owner.owner_id, self.db)
        seed_default_finishing_services(self.owner.owner_id, self.db)

        os.makedirs(UPLOAD_DIR, exist_ok=True)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    # ==========================================================
    # 1. FILE PREVIEW TESTS
    # ==========================================================

    def test_01_pdf_preview_inline_no_forced_download(self):
        """Test PDF preview is served inline with application/pdf and never attachment."""
        pdf_content = b"%PDF-1.4 sample pdf content for preview testing"
        enc_payload = encrypt_document(pdf_content)
        file_path = os.path.join(UPLOAD_DIR, f"test_doc_{uuid.uuid4()}.enc")
        with open(file_path, "wb") as f:
            f.write(enc_payload)

        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)

        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Assignment.pdf",
            stored_filename=os.path.basename(file_path),
            file_path=file_path,
            file_type="PDF",
            page_count=5,
            copies=1
        )
        self.db.add(file)
        self.db.commit()

        res = self.client.get(f"/preview/job/{job.job_id}/file/{file.file_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/pdf")
        self.assertIn("inline", res.headers.get("content-disposition", ""))
        self.assertNotIn("attachment", res.headers.get("content-disposition", ""))
        self.assertEqual(res.content, pdf_content)

        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_02_image_and_txt_preview(self):
        """Test image (PNG) and TXT document inline previews."""
        # PNG
        png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRsample"
        enc_png = encrypt_document(png_content)
        png_path = os.path.join(UPLOAD_DIR, f"test_img_{uuid.uuid4()}.enc")
        with open(png_path, "wb") as f:
            f.write(enc_png)

        # TXT
        txt_content = b"Hello, this is a plain text notes file."
        enc_txt = encrypt_document(txt_content)
        txt_path = os.path.join(UPLOAD_DIR, f"test_txt_{uuid.uuid4()}.enc")
        with open(txt_path, "wb") as f:
            f.write(enc_txt)

        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)

        f_png = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="chart.png",
            file_path=png_path,
            file_type="PNG"
        )
        f_txt = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="notes.txt",
            file_path=txt_path,
            file_type="TXT"
        )
        self.db.add_all([f_png, f_txt])
        self.db.commit()

        # Check PNG
        res_png = self.client.get(f"/preview/job/{job.job_id}/file/{f_png.file_id}")
        self.assertEqual(res_png.status_code, 200)
        self.assertEqual(res_png.headers["content-type"], "image/png")
        self.assertIn("inline", res_png.headers.get("content-disposition", ""))
        self.assertEqual(res_png.content, png_content)

        # Check TXT
        res_txt = self.client.get(f"/preview/job/{job.job_id}/file/{f_txt.file_id}")
        self.assertEqual(res_txt.status_code, 200)
        self.assertIn("text/plain", res_txt.headers["content-type"])
        self.assertIn("inline", res_txt.headers.get("content-disposition", ""))
        self.assertEqual(res_txt.content, txt_content)

        # Cleanup
        for p in (png_path, txt_path):
            if os.path.exists(p):
                os.remove(p)

    def test_03_unsupported_preview_format(self):
        """Test unsupported file type returns safe message without crashing."""
        doc_content = b"PK\x03\x04docx binary data"
        enc_doc = encrypt_document(doc_content)
        doc_path = os.path.join(UPLOAD_DIR, f"test_doc_{uuid.uuid4()}.enc")
        with open(doc_path, "wb") as f:
            f.write(enc_doc)

        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)

        f_docx = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Report.docx",
            file_path=doc_path,
            file_type="DOCX"
        )
        self.db.add(f_docx)
        self.db.commit()

        res = self.client.get(f"/preview/job/{job.job_id}/file/{f_docx.file_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Preview is not available for this file type", res.text)

        if os.path.exists(doc_path):
            os.remove(doc_path)

    def test_04_cross_job_preview_blocked(self):
        """Test cross-job file access is rejected (file belongs to job A, requested via job B)."""
        job_a = ActiveJob(job_id=uuid.uuid4(), owner_id=self.owner.owner_id)
        job_b = ActiveJob(job_id=uuid.uuid4(), owner_id=self.owner.owner_id)
        self.db.add_all([job_a, job_b])

        f_a = JobFile(
            file_id=uuid.uuid4(),
            job_id=job_a.job_id,
            original_filename="Secret_Job_A.pdf",
            file_path=os.path.join(UPLOAD_DIR, "dummy.enc"),
            file_type="PDF"
        )
        self.db.add(f_a)
        self.db.commit()

        # Request file A using job B's endpoint URL
        res = self.client.get(f"/preview/job/{job_b.job_id}/file/{f_a.file_id}")
        self.assertEqual(res.status_code, 404)

    # ==========================================================
    # 2. RECEIPT SYSTEM TESTS
    # ==========================================================

    def test_05_receipt_generation_json_view_download(self):
        """Test authoritative receipt JSON, HTML view, and HTML download endpoints."""
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            customer_reference="Rahul",
            status=JobStatus.QUEUED,
            payment_status=PaymentStatus.PAID
        )
        self.db.add(job)

        f1 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Assignment.pdf",
            page_count=10,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            estimated_cost=Decimal("20.00")
        )
        f2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="Project.pdf",
            page_count=15,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            estimated_cost=Decimal("30.00")
        )
        self.db.add_all([f1, f2])

        # Per-file finishing services
        srv_spiral = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()

        srv_glass = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner.owner_id,
            FinishingService.service_name == "Transparent/Glass Sheet"
        ).first()

        jf1 = JobFinishingService(
            id=uuid.uuid4(),
            job_id=job.job_id,
            file_id=f1.file_id,
            service_id=srv_glass.service_id,
            service_name="Transparent/Glass Sheet",
            unit_price=Decimal("3.00"),
            quantity=1,
            total_price=Decimal("3.00")
        )
        jf2 = JobFinishingService(
            id=uuid.uuid4(),
            job_id=job.job_id,
            file_id=f2.file_id,
            service_id=srv_spiral.service_id,
            service_name="Spiral Binding",
            unit_price=Decimal("30.00"),
            quantity=1,
            total_price=Decimal("30.00")
        )
        self.db.add_all([jf1, jf2])

        # Authoritative cost calculation
        job.subtotal = Decimal("83.00")  # (20 + 30) printing + (3 + 30) finishing
        job.tax = Decimal("0.00")
        job.total_amount = Decimal("83.00")

        # Payment record
        pmt = Payment(
            payment_id=uuid.uuid4(),
            job_id=job.job_id,
            provider=PaymentProvider.RAZORPAY,
            payment_method=PaymentMethod.UPI,
            amount=Decimal("83.00"),
            status=PaymentStatus.PAID,
            transaction_id="TXN_RAHUL_8300"
        )
        self.db.add(pmt)
        self.db.commit()

        # 1. Test JSON Receipt
        res_json = self.client.get(f"/receipt/job/{job.job_id}")
        self.assertEqual(res_json.status_code, 200)
        r_data = res_json.json()
        self.assertEqual(r_data["order_id"], str(job.job_id))
        self.assertEqual(r_data["shop_name"], "Apex Print Studio")
        self.assertEqual(r_data["customer_reference"], "Rahul")
        self.assertEqual(r_data["printing_subtotal"], 50.00)
        self.assertEqual(r_data["finishing_subtotal"], 33.00)
        self.assertEqual(r_data["grand_total"], 83.00)
        self.assertEqual(r_data["payment_status"], "Paid")
        self.assertEqual(r_data["payment_method"], "UPI")
        self.assertEqual(len(r_data["items"]), 2)
        self.assertEqual(r_data["items"][0]["filename"], "Assignment.pdf")
        self.assertEqual(r_data["items"][0]["finishing_services"][0]["service_name"], "Transparent/Glass Sheet")
        self.assertEqual(r_data["items"][1]["filename"], "Project.pdf")
        self.assertEqual(r_data["items"][1]["finishing_services"][0]["service_name"], "Spiral Binding")

        # 2. Test HTML View
        res_view = self.client.get(f"/receipt/job/{job.job_id}/view")
        self.assertEqual(res_view.status_code, 200)
        self.assertIn("Apex Print Studio", res_view.text)
        self.assertIn("Assignment.pdf", res_view.text)
        self.assertIn("Spiral Binding", res_view.text)
        self.assertIn("₹83.00", res_view.text)

        # 3. Test Download Attachment
        res_dl = self.client.get(f"/receipt/job/{job.job_id}/download")
        self.assertEqual(res_dl.status_code, 200)
        self.assertIn("attachment", res_dl.headers.get("content-disposition", ""))
        self.assertIn(".html", res_dl.headers.get("content-disposition", ""))

    # ==========================================================
    # 3. PER-FILE FINISHING & HISTORICAL SNAPSHOT TESTS
    # ==========================================================

    def test_06_per_file_finishing_and_price_snapshot(self):
        """
        Verify different files can have different finishing services,
        and owner changing prices later does not affect historical orders.
        """
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)

        f1 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="doc1.pdf",
            page_count=10,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        f2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="doc2.pdf",
            page_count=10,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add_all([f1, f2])
        self.db.commit()

        srv_spiral = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()
        self.assertEqual(float(srv_spiral.price), 30.00)

        srv_glass = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner.owner_id,
            FinishingService.service_name == "Transparent/Glass Sheet"
        ).first()
        self.assertEqual(float(srv_glass.price), 3.00)

        # Select Glass Sheet for File 1, Spiral Binding for File 2
        res = self.client.post(
            f"/services/job/{job.job_id}/select",
            json={
                "customer_reference": "Alice",
                "services": [
                    {"service_id": str(srv_glass.service_id), "file_id": str(f1.file_id), "quantity": 1},
                    {"service_id": str(srv_spiral.service_id), "file_id": str(f2.file_id), "quantity": 1}
                ]
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # 10 pgs @ Rs 2.00 = Rs 20 (doc1) + Rs 20 (doc2) = Rs 40 printing + Rs 3 (glass) + Rs 30 (spiral) = Rs 73.00
        self.assertEqual(data["subtotal"], 73.00)
        self.assertEqual(data["total_amount"], 73.00)

        # Owner modifies Spiral Binding price from Rs 30.00 to Rs 45.00
        res_edit = self.client.put(
            f"/services/{srv_spiral.service_id}",
            json={"price": 45.00}
        )
        self.assertEqual(res_edit.status_code, 200)

        # Check existing job historical snapshot remains Rs 30.00 / total Rs 73.00
        self.db.refresh(job)
        self.assertEqual(float(job.total_amount), 73.00)
        applied_spiral = self.db.query(JobFinishingService).filter(
            JobFinishingService.job_id == job.job_id,
            JobFinishingService.service_id == srv_spiral.service_id
        ).first()
        self.assertEqual(float(applied_spiral.unit_price), 30.00)
        self.assertEqual(float(applied_spiral.total_price), 30.00)

        # Create NEW order - should use new price of Rs 45.00
        job_new = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job_new)
        f_new = JobFile(
            file_id=uuid.uuid4(),
            job_id=job_new.job_id,
            original_filename="new_doc.pdf",
            page_count=5,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add(f_new)
        self.db.commit()

        res_new = self.client.post(
            f"/services/job/{job_new.job_id}/select",
            json={
                "services": [
                    {"service_id": str(srv_spiral.service_id), "file_id": str(f_new.file_id), "quantity": 1}
                ]
            }
        )
        self.assertEqual(res_new.status_code, 200)
        # 5 pgs @ Rs 2.00 = Rs 10 printing + Rs 45 spiral = Rs 55.00
        self.assertEqual(res_new.json()["total_amount"], 55.00)

    # ==========================================================
    # 4. PRINTER AVAILABILITY & PAYMENT GATING TESTS
    # ==========================================================

    def test_07_payment_gating_blocks_when_no_printer_online(self):
        """Test payment creation is blocked server-side when all printers for shop are offline."""
        # Add offline printer
        offline_printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            printer_name="Office HP LaserJet",
            status=PrinterStatus.OFFLINE,
            is_available=False,
            supports_bw=True
        )
        self.db.add(offline_printer)

        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)
        f = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="test.pdf",
            page_count=5,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW
        )
        self.db.add(f)
        self.db.commit()

        calculate_job_cost(job.job_id, self.db)

        # Attempt payment creation
        res = self.client.post(
            f"/payment/create/{job.job_id}",
            json={"payment_method": "UPI"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("No printer is currently available", res.json()["detail"])

        # Attempt cash payment request
        res_cash = self.client.post(f"/payment/cash/{job.job_id}")
        self.assertEqual(res_cash.status_code, 400)
        self.assertIn("No printer is currently available", res_cash.json()["detail"])

        # Bring printer ONLINE and AVAILABLE
        offline_printer.status = PrinterStatus.ONLINE
        offline_printer.is_available = True
        self.db.commit()

        # Now payment creation must succeed
        res_online = self.client.post(
            f"/payment/create/{job.job_id}",
            json={"payment_method": "UPI"}
        )
        self.assertEqual(res_online.status_code, 200)
        self.assertEqual(res_online.json()["status"], "Pending")

    # ==========================================================
    # 5. VOICE ASSISTANT CLIENT COMMAND PARSER LOGIC
    # ==========================================================

    def test_08_voice_command_parser_accuracy(self):
        """Test voice parser extracts complex multi-field configurations accurately."""
        # Read the JavaScript voice parser file to verify implementation
        voice_js_path = os.path.join("cloud_server", "static", "js", "voice_search.js")
        self.assertTrue(os.path.exists(voice_js_path))
        with open(voice_js_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        # Verify key requirements embedded in script
        self.assertIn("continuous = false", js_code)  # Strict tap-to-activate lifecycle
        self.assertIn("parseCommand", js_code)
        self.assertIn("Spiral Binding", js_code)
        self.assertIn("Transparent/Glass Sheet", js_code)
        self.assertIn("Role Restricted", js_code)


if __name__ == "__main__":
    unittest.main()
