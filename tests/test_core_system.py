import os
import sys
import uuid
import unittest
from decimal import Decimal
from datetime import datetime

# Ensure cloud_server and PRINT_AGENT are in Python path
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
    AnalyticsDaily,
    JobStatus,
    PaymentStatus,
    PrintType,
    PaperSize,
    Orientation,
    PricingBasis,
    PaymentProvider
)
from app.services.queue_service import (
    add_job_to_queue,
    get_all_queue_jobs,
    get_queue,
    cancel_queue_job,
    complete_queue_job
)
from app.services.pricing_engine import (
    calculate_file_cost,
    calculate_job_cost
)
from app.services.payment_service import (
    PaymentService
)
from app.services.assignment_service import (
    is_printer_eligible,
    assign_printer
)
from app.services.ml_prediction_service import (
    predict_job_completion_time
)
from app.services.analytics_service import (
    record_job_completion_analytics,
    get_dashboard_statistics
)


class TestCoreSystem(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_models_and_relationships(self):
        owner = ShopOwner(
            owner_id=uuid.uuid4(),
            shop_name="Test Fast Print",
            owner_name="Alice Owner",
            email="alice@test.com",
            phone="9999999999",
            password_hash="hashed_pw",
            is_active=True
        )
        self.db.add(owner)
        self.db.commit()

        printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=owner.owner_id,
            printer_name="HP LaserJet Pro",
            status="Online",
            is_available=True,
            supports_bw=True,
            supports_color=False,
            supports_duplex=True
        )
        self.db.add(printer)

        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            estimated_seconds=0
        )
        self.db.add(job)
        self.db.commit()

        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="doc.pdf",
            stored_filename="stored_doc.pdf",
            page_count=5,
            copies=2,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=True
        )
        self.db.add(file)
        self.db.commit()

        self.db.refresh(job)
        self.assertEqual(len(job.files), 1)
        self.assertEqual(job.files[0].page_count, 5)
        self.assertEqual(job.owner.shop_name, "Test Fast Print")

    def test_pricing_engine_calculation(self):
        owner_id = uuid.uuid4()
        owner = ShopOwner(
            owner_id=owner_id,
            shop_name="Print Hub",
            owner_name="Bob",
            email="bob@test.com",
            phone="8888888888",
            password_hash="pw",
            is_active=True
        )
        settings = ShopSettings(
            owner_id=owner_id,
            pricing_basis=PricingBasis.PER_SIDE,
            tax_percentage=10.0
        )
        rule_bw = PricingRule(
            owner_id=owner_id,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False,
            price_per_page=Decimal("2.00"),
            page_from=1,
            page_to=100,
            is_active=True
        )
        self.db.add_all([owner, settings, rule_bw])
        self.db.commit()

        job = ActiveJob(owner_id=owner_id)
        self.db.add(job)
        self.db.commit()

        file = JobFile(
            job_id=job.job_id,
            original_filename="assignment.pdf",
            stored_filename="stored_assignment.pdf",
            page_count=10,
            copies=2,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add(file)
        self.db.commit()

        total_cost = calculate_job_cost(job.job_id, self.db)
        # Subtotal: 10 pages * 2 copies * ₹2.00 = ₹40.00
        # Tax: 10% of ₹40 = ₹4.00
        # Total: ₹44.00
        self.assertEqual(total_cost, Decimal("44.00"))
        self.assertEqual(job.subtotal, Decimal("40.00"))
        self.assertEqual(job.tax, Decimal("4.00"))

    def test_queue_system_transitions(self):
        owner_id = uuid.uuid4()
        printer_id = uuid.uuid4()
        printer = Printer(
            printer_id=printer_id,
            owner_id=owner_id,
            printer_name="Canon iR",
            status="Online",
            is_available=True
        )
        self.db.add(printer)

        job1 = ActiveJob(
            owner_id=owner_id,
            assigned_printer_id=printer_id,
            status=JobStatus.ASSIGNED
        )
        job2 = ActiveJob(
            owner_id=owner_id,
            assigned_printer_id=printer_id,
            status=JobStatus.ASSIGNED
        )
        self.db.add_all([job1, job2])
        self.db.commit()

        q1 = add_job_to_queue(job1.job_id, self.db)
        self.assertEqual(q1.queue_position, 1)
        self.assertEqual(q1.status, JobStatus.QUEUED)
        self.assertGreater(q1.estimated_seconds, 0)

        q2 = add_job_to_queue(job2.job_id, self.db)
        self.assertEqual(q2.queue_position, 2)
        self.assertEqual(q2.status, JobStatus.QUEUED)

        all_queued = get_all_queue_jobs(self.db)
        self.assertEqual(len(all_queued), 2)

        # Complete Job 1
        comp1 = complete_queue_job(job1.job_id, self.db)
        self.assertEqual(comp1.status, JobStatus.COMPLETED)

        # Remaining in queue
        p_queue = get_queue(printer_id, self.db)
        self.assertEqual(len(p_queue), 1)
        self.assertEqual(p_queue[0].job_id, job2.job_id)
        self.assertEqual(p_queue[0].queue_position, 1)

    def test_ai_printer_selection_and_fallback(self):
        owner_id = uuid.uuid4()
        p_bw = Printer(
            printer_id=uuid.uuid4(),
            owner_id=owner_id,
            printer_name="Mono Laser",
            status="Online",
            is_available=True,
            supports_bw=True,
            supports_color=False,
            supports_duplex=True
        )
        p_color = Printer(
            printer_id=uuid.uuid4(),
            owner_id=owner_id,
            printer_name="Color Laser",
            status="Online",
            is_available=True,
            supports_bw=True,
            supports_color=True,
            supports_duplex=True
        )
        self.db.add_all([p_bw, p_color])
        self.db.commit()

        job = ActiveJob(owner_id=owner_id)
        self.db.add(job)
        self.db.commit()

        file_color = JobFile(
            job_id=job.job_id,
            original_filename="chart.pdf",
            stored_filename="stored_chart.pdf",
            page_count=4,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.COLOR
        )
        self.db.add(file_color)
        self.db.commit()
        self.db.refresh(job)

        self.assertFalse(is_printer_eligible(p_bw, job))
        self.assertTrue(is_printer_eligible(p_color, job))

        assigned = assign_printer(job, self.db)
        self.assertEqual(assigned.printer_id, p_color.printer_id)
        self.assertEqual(job.assigned_printer_id, p_color.printer_id)
        self.assertGreater(job.estimated_seconds, 0)

    def test_payment_service_and_idempotency(self):
        job = ActiveJob(
            owner_id=uuid.uuid4(),
            total_amount=Decimal("50.00")
        )
        self.db.add(job)
        self.db.commit()

        payment = PaymentService.create_payment_order(job, db=self.db)
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.amount, Decimal("50.00"))

        PaymentService.process_successful_payment(
            payment,
            transaction_id="TXN_12345",
            db=self.db
        )
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertTrue(payment.verified)
        self.assertEqual(job.payment_status, PaymentStatus.PAID)

        # Idempotency
        PaymentService.process_successful_payment(payment, db=self.db)
        self.assertEqual(payment.status, PaymentStatus.PAID)

    def test_analytics_recording(self):
        owner_id = uuid.uuid4()
        job = ActiveJob(
            owner_id=owner_id,
            status=JobStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_amount=Decimal("120.00"),
            total_pages=30,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()

        record_job_completion_analytics(job, self.db)
        stats = get_dashboard_statistics(owner_id, self.db)
        self.assertEqual(stats["completed_jobs"], 1)
        self.assertEqual(stats["total_revenue"], 120.0)


if __name__ == "__main__":
    unittest.main()
