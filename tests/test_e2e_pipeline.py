import os
import sys
import uuid
import unittest
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    Base,
    ShopOwner,
    ShopSettings,
    Printer,
    ActiveJob,
    JobFile,
    PricingRule,
    Payment,
    JobStatus,
    PaymentStatus,
    PrintType,
    PaperSize,
    Orientation,
    PricingBasis
)
from app.services.pricing_engine import calculate_job_cost
from app.services.payment_service import PaymentService
from app.services.assignment_service import assign_printer
from app.services.queue_service import add_job_to_queue, complete_queue_job
from app.services.analytics_service import record_job_completion_analytics, get_dashboard_statistics


class TestE2EPipeline(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_complete_end_to_end_pipeline(self):
        owner_id = uuid.uuid4()
        owner = ShopOwner(
            owner_id=owner_id,
            shop_name="Central Print Hub",
            owner_name="David",
            email="david@hub.com",
            phone="9876543210",
            password_hash="hash",
            is_active=True
        )
        settings = ShopSettings(
            owner_id=owner_id,
            pricing_basis=PricingBasis.PER_SIDE,
            tax_percentage=5.0
        )
        rule_bw = PricingRule(
            owner_id=owner_id,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            price_per_page=Decimal("2.00"),
            is_active=True
        )
        rule_color = PricingRule(
            owner_id=owner_id,
            paper_size=PaperSize.A4,
            print_type=PrintType.COLOR,
            price_per_page=Decimal("10.00"),
            is_active=True
        )

        p1 = Printer(
            printer_id=uuid.uuid4(),
            owner_id=owner_id,
            agent_id="agent_001",
            printer_name="Canon Color Pro",
            status="Online",
            is_available=True,
            supports_bw=True,
            supports_color=True,
            supports_duplex=True
        )
        p2 = Printer(
            printer_id=uuid.uuid4(),
            owner_id=owner_id,
            agent_id="agent_001",
            printer_name="Brother Mono Fast",
            status="Online",
            is_available=True,
            supports_bw=True,
            supports_color=False,
            supports_duplex=True
        )
        self.db.add_all([owner, settings, rule_bw, rule_color, p1, p2])
        self.db.commit()

        # Step 1: QR scan creates job
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)
        self.db.commit()

        # Step 2: Upload 2 files (File 1: B/W 5 pages, File 2: Color 2 pages)
        f1 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="thesis_intro.pdf",
            stored_filename=f"{uuid.uuid4()}.pdf",
            page_count=5,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        f2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="thesis_cover.pdf",
            stored_filename=f"{uuid.uuid4()}.pdf",
            page_count=2,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.COLOR,
            duplex=False
        )
        self.db.add_all([f1, f2])
        self.db.commit()

        # Step 3 & 4: Price calculation
        total_amount = calculate_job_cost(job.job_id, self.db)
        self.assertEqual(total_amount, Decimal("31.50"))
        self.assertEqual(job.total_files, 2)
        self.assertEqual(job.total_pages, 7)

        # Step 5: Payment creation & verification
        payment = PaymentService.create_payment_order(job, db=self.db)
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        
        PaymentService.process_successful_payment(
            payment,
            transaction_id="TXN_UPI_9988",
            provider_payment_id="ORDER_9988",
            db=self.db
        )
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(job.payment_status, PaymentStatus.PAID)

        # Step 6: AI Printer Selection
        assigned_printer = assign_printer(job, self.db)
        self.assertEqual(assigned_printer.printer_id, p1.printer_id)
        self.assertEqual(job.assigned_printer_id, p1.printer_id)

        # Step 7: Queue job
        queued_job = add_job_to_queue(job.job_id, self.db)
        self.assertEqual(queued_job.status, JobStatus.QUEUED)
        self.assertEqual(queued_job.queue_position, 1)
        self.assertGreater(queued_job.estimated_seconds, 0)

        # Step 8: Multi-file verification
        self.assertEqual(len(job.files), 2)

        # Step 9: Agent execution simulation
        job.status = JobStatus.PRINTING
        job.started_at = datetime.utcnow()
        self.db.commit()

        job.completed_at = datetime.utcnow()
        complete_queue_job(job.job_id, self.db)
        self.assertEqual(job.status, JobStatus.COMPLETED)

        # Step 10: Record Analytics
        record_job_completion_analytics(job, self.db)
        stats = get_dashboard_statistics(owner_id, self.db)

        self.assertEqual(stats["completed_jobs"], 1)
        self.assertEqual(stats["total_pages"], 7)
        self.assertEqual(stats["total_revenue"], 31.50)


if __name__ == "__main__":
    unittest.main()
