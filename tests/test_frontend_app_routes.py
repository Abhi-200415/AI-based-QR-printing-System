import os
import sys
import uuid
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

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
    JobStatus,
    PaymentStatus,
    PrintType,
    PaperSize,
    Orientation
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

class TestFrontendAppRoutes(unittest.TestCase):

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

        # Create a test shop owner
        self.owner_id = uuid.uuid4()
        self.owner = ShopOwner(
            owner_id=self.owner_id,
            shop_name="Apex Print Studio",
            owner_name="John Doe",
            email="apex@test.com",
            phone="9876543210",
            password_hash="test_pw_hash",
            upi_id="apex@upi",
            qr_token="apex_token_123",
            is_active=True
        )
        self.db.add(self.owner)

        self.settings = ShopSettings(
            owner_id=self.owner_id,
            max_file_size_mb=50,
            max_files_per_job=20,
            tax_percentage=0.0
        )
        self.db.add(self.settings)

        self.printer = Printer(
            printer_id=uuid.uuid4(),
            owner_id=self.owner_id,
            printer_name="Office HP LaserJet",
            printer_model="LaserJet Pro M404n",
            status="Online",
            is_physical=True,
            is_virtual=False,
            is_available=True,
            supports_bw=True,
            supports_color=True,
            supports_duplex=True
        )
        self.db.add(self.printer)

        self.job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_id,
            customer_name="Bob Customer",
            customer_phone="9988776655",
            status=JobStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_amount=Decimal("25.00"),
            total_pages=5,
            total_copies=1,
            assigned_printer_id=self.printer.printer_id
        )
        self.db.add(self.job)

        self.file = JobFile(
            file_id=uuid.uuid4(),
            job_id=self.job.job_id,
            original_filename="thesis_chapter1.pdf",
            stored_filename="file_1.enc",
            file_type="PDF",
            page_count=5,
            copies=1,
            paper_size=PaperSize.A4,
            orientation=Orientation.PORTRAIT,
            print_type=PrintType.BW,
            duplex=False,
            estimated_cost=Decimal("25.00")
        )
        self.db.add(self.file)

        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_static_css(self):
        res = self.client.get("/static/style.css")
        self.assertEqual(res.status_code, 200)
        self.assertIn("--bg-primary", res.text)
        self.assertIn(".app-sidebar", res.text)

    def test_login_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Owner Login", res.text)

    def test_owner_dashboard_view_all_sections(self):
        res = self.client.get(f"/owner/{self.owner_id}/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify app-like navigation and all 10 view sections exist
        self.assertIn('id="view-dashboard"', html)
        self.assertIn('id="view-jobs"', html)
        self.assertIn('id="view-queue"', html)
        self.assertIn('id="view-printers"', html)
        self.assertIn('id="view-payments"', html)
        self.assertIn('id="view-analytics"', html)
        self.assertIn('id="view-qr-code"', html)
        self.assertIn('id="view-pricing"', html)
        self.assertIn('id="view-settings"', html)
        self.assertIn('id="view-profile"', html)

        # Verify sidebar and navigation items
        self.assertIn('data-view="dashboard"', html)
        self.assertIn('data-view="jobs"', html)
        self.assertIn('data-view="queue"', html)
        self.assertIn('data-view="printers"', html)
        self.assertIn('data-view="payments"', html)
        self.assertIn('data-view="analytics"', html)
        self.assertIn('data-view="qr-code"', html)
        self.assertIn('data-view="pricing"', html)
        self.assertIn('data-view="settings"', html)
        self.assertIn('data-view="profile"', html)

    def test_jobs_owner_api(self):
        res = self.client.get(f"/jobs/owner/{self.owner_id}")
        self.assertEqual(res.status_code, 200)
        jobs = res.json()
        self.assertIsInstance(jobs, list)
        self.assertGreaterEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["customer_name"], "Bob Customer")
        self.assertEqual(jobs[0]["files"][0]["filename"], "thesis_chapter1.pdf")

    def test_analytics_dashboard_api(self):
        res = self.client.get(f"/analytics/dashboard/{self.owner_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("statistics", data)
        self.assertIn("revenue_breakdown", data)
        self.assertIn("charts", data)

    def test_analytics_charts_api(self):
        res = self.client.get(f"/analytics/charts/{self.owner_id}")
        self.assertEqual(res.status_code, 200)
        charts = res.json()
        self.assertIn("revenue_timeline", charts)
        self.assertIn("hourly_traffic", charts)
        self.assertIn("print_types", charts)
        self.assertIn("payment_methods", charts)

    def test_printers_owner_api(self):
        res = self.client.get(f"/printer/owner/{self.owner_id}")
        self.assertEqual(res.status_code, 200)
        printers = res.json()
        self.assertEqual(len(printers), 1)
        self.assertEqual(printers[0]["printer_name"], "Office HP LaserJet")

    def test_pricing_rules_api(self):
        res = self.client.get(f"/pricing/owner/{self.owner_id}")
        self.assertEqual(res.status_code, 200)
        rules = res.json()
        self.assertIsInstance(rules, list)

    def test_shop_settings_api(self):
        res = self.client.get(f"/settings/owner/{self.owner_id}")
        self.assertEqual(res.status_code, 200)
        settings = res.json()
        self.assertEqual(settings["max_file_size_mb"], 50)

    def test_qr_standee_view(self):
        res = self.client.get(f"/owner/{self.owner_id}/qr")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Apex Print Studio", res.text)

    def test_customer_workflow(self):
        # 1. Customer scans QR
        res = self.client.get(f"/qr/{self.owner.qr_token}", follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        redirect_url = res.headers["location"]
        self.assertTrue(redirect_url.startswith("/upload/"))

        # 2. Customer sees upload page
        res = self.client.get(redirect_url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Upload Print Documents", res.text)

        # 3. Settings page
        res = self.client.get(f"/file/settings-page/{self.file.file_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Configure Print Options", res.text)

        # 4. Price summary page
        res = self.client.get(f"/file/summary/{self.file.file_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Print Order Summary", res.text)

        # 5. Live tracker view
        res = self.client.get(f"/job/tracker/{self.job.job_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Live Print Order Tracker", res.text)

if __name__ == "__main__":
    unittest.main()
