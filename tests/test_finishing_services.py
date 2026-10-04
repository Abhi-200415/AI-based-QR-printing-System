import os
import sys
import uuid
import unittest
from decimal import Decimal
from datetime import datetime

# Ensure cloud_server is in Python path
sys.path.insert(0, os.path.abspath("cloud_server"))

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
from app.services.queue_service import complete_queue_job


class TestFinishingServicesFeature(unittest.TestCase):

    def setUp(self):
        # Create an isolated in-memory SQLite database
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Override get_db dependency for FastAPI TestClient
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Setup Shop A
        self.owner_a = ShopOwner(
            owner_id=uuid.uuid4(),
            owner_name="Owner Alice",
            shop_name="Shop A Express Print",
            email="alice@shopa.com",
            phone="9876543210",
            password_hash="hash",
            is_active=True
        )
        self.db.add(self.owner_a)

        # Setup Shop B
        self.owner_b = ShopOwner(
            owner_id=uuid.uuid4(),
            owner_name="Owner Bob",
            shop_name="Shop B Premium Graphics",
            email="bob@shopb.com",
            phone="9876543211",
            password_hash="hash",
            is_active=True
        )
        self.db.add(self.owner_b)
        self.db.commit()

        # Seed defaults for Shop A & Shop B
        seed_default_pricing_rules(self.owner_a.owner_id, self.db)
        seed_default_finishing_services(self.owner_a.owner_id, self.db)
        seed_default_pricing_rules(self.owner_b.owner_id, self.db)
        seed_default_finishing_services(self.owner_b.owner_id, self.db)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # ------------------------------------------------------------------
    # 1. Create Finishing Service
    # ------------------------------------------------------------------
    def test_01_create_finishing_service(self):
        res = self.client.post(
            f"/services/owner/{self.owner_a.owner_id}",
            json={
                "service_name": "Hardcover Binding",
                "description": "Hardboard premium rexine binding with golden embossed title",
                "price": 150.00,
                "charge_type": "PER_ORDER",
                "is_enabled": True
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["service_name"], "Hardcover Binding")
        self.assertEqual(float(data["price"]), 150.00)
        self.assertTrue(data["is_enabled"])

    # ------------------------------------------------------------------
    # 2. Edit Service Price
    # ------------------------------------------------------------------
    def test_02_edit_service_price(self):
        service = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()
        self.assertIsNotNone(service)
        self.assertEqual(float(service.price), 30.00)

        # Update price to 35.00
        res = self.client.put(
            f"/services/{service.service_id}",
            json={"price": 35.00}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(float(res.json()["price"]), 35.00)

        # Check DB
        self.db.refresh(service)
        self.assertEqual(float(service.price), 35.00)

    # ------------------------------------------------------------------
    # 3 & 4. Enable / Disable Service
    # ------------------------------------------------------------------
    def test_03_enable_disable_service(self):
        service = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Lamination"
        ).first()

        # Disable
        res = self.client.put(
            f"/services/{service.service_id}",
            json={"is_enabled": False}
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["is_enabled"])

        # Enable
        res = self.client.put(
            f"/services/{service.service_id}",
            json={"is_enabled": True}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["is_enabled"])

    # ------------------------------------------------------------------
    # 5. Delete Service
    # ------------------------------------------------------------------
    def test_04_delete_service(self):
        s = FinishingService(
            service_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            service_name="Temporary Service",
            price=Decimal("12.00"),
            is_enabled=True
        )
        self.db.add(s)
        self.db.commit()

        res = self.client.delete(f"/services/{s.service_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        # Confirm not in DB
        found = self.db.query(FinishingService).filter(FinishingService.service_id == s.service_id).first()
        self.assertIsNone(found)

    # ------------------------------------------------------------------
    # 6. Shop-Specific Isolation (Shop A vs Shop B)
    # ------------------------------------------------------------------
    def test_05_shop_specific_pricing_isolation(self):
        # In Shop A, set Spiral Binding = 30.00
        # In Shop B, set Spiral Binding = 40.00
        srv_a = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()
        srv_b = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_b.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()

        srv_a.price = Decimal("30.00")
        srv_b.price = Decimal("40.00")
        self.db.commit()

        # Fetch available services for Shop A
        res_a = self.client.get(f"/services/shop/{self.owner_a.owner_id}/available")
        self.assertEqual(res_a.status_code, 200)
        items_a = {item["service_name"]: float(item["price"]) for item in res_a.json()}
        self.assertEqual(items_a["Spiral Binding"], 30.00)

        # Fetch available services for Shop B
        res_b = self.client.get(f"/services/shop/{self.owner_b.owner_id}/available")
        self.assertEqual(res_b.status_code, 200)
        items_b = {item["service_name"]: float(item["price"]) for item in res_b.json()}
        self.assertEqual(items_b["Spiral Binding"], 40.00)

    # ------------------------------------------------------------------
    # 7 & 8. Customer Cannot Use Disabled Service
    # ------------------------------------------------------------------
    def test_06_customer_cannot_use_disabled_service(self):
        srv = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Envelope"
        ).first()
        srv.is_enabled = False
        self.db.commit()

        # Create active job
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)
        self.db.commit()

        # Customer attempts to select disabled envelope service
        res = self.client.post(
            f"/services/job/{job.job_id}/select",
            json={
                "customer_reference": "Rahul",
                "services": [{"service_id": str(srv.service_id), "quantity": 1}]
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not available for this shop or is disabled", res.json()["detail"])

    # ------------------------------------------------------------------
    # 9. Customer Cannot Use Cross-Shop Service
    # ------------------------------------------------------------------
    def test_07_cross_shop_access_blocked(self):
        # Service belongs to Shop B
        srv_b = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_b.owner_id
        ).first()

        # Job belongs to Shop A
        job_a = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job_a)
        self.db.commit()

        # Customer in Shop A tries to pass Shop B's service ID
        res = self.client.post(
            f"/services/job/{job_a.job_id}/select",
            json={
                "customer_reference": "Rahul",
                "services": [{"service_id": str(srv_b.service_id), "quantity": 1}]
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not available for this shop", res.json()["detail"])

    # ------------------------------------------------------------------
    # 10, 11, 12, 13. End-to-End Pricing, Snapshots, and Updates
    # ------------------------------------------------------------------
    def test_08_authoritative_calculation_and_price_snapshot(self):
        """
        Tests the authoritative calculation:
        1 Document: 20 pages, B&W, 2 copies -> 20 * 2 = 40 billable sides @ Rs 2.00 = Rs 80 (or 20 pgs 1 copy = Rs 40)
        Let's test: 15 pages, 2 copies @ Rs 2.00 = Rs 60.
        Spiral Binding @ Rs 30.00
        Total = Rs 90.00
        """
        # 1. Create Job for Shop A
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)

        # 15 pages x 2 copies = 30 sides @ Rs 2.00/pg = Rs 60.00 printing
        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="thesis_final.pdf",
            page_count=15,
            copies=2,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add(file)
        self.db.commit()

        # Find Spiral Binding for Shop A (Rs 30.00)
        binding_srv = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()
        self.assertEqual(float(binding_srv.price), 30.00)

        # 2. Customer selects Spiral Binding and provides reference "Rahul"
        res = self.client.post(
            f"/services/job/{job.job_id}/select",
            json={
                "customer_reference": "Rahul",
                "services": [{"service_id": str(binding_srv.service_id), "quantity": 1}]
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["customer_reference"], "Rahul")
        self.assertEqual(data["finishing_status"], "PENDING")
        self.assertEqual(data["subtotal"], 90.00)  # Rs 60 print + Rs 30 binding
        self.assertEqual(data["total_amount"], 90.00)
        self.assertEqual(len(data["services"]), 1)
        self.assertEqual(data["services"][0]["service_name"], "Spiral Binding")
        self.assertEqual(data["services"][0]["unit_price"], 30.00)
        self.assertEqual(data["services"][0]["total_price"], 30.00)

        # 3. Customer pays Rs 90.00 online
        pay_res = self.client.post(
            f"/payment/create/{job.job_id}",
            json={"payment_method": "UPI"}
        )
        self.assertEqual(pay_res.status_code, 200)
        pay_data = pay_res.json()
        self.assertEqual(pay_data["amount"], 90.00)

        # Verify payment using gateway mock
        from unittest.mock import patch
        with patch.object(PaymentService, "verify_gateway_signature", return_value=True):
            verify_res = self.client.post(
                "/payment/verify",
                json={
                    "payment_id": pay_data["payment_id"],
                    "provider_payment_id": "PAY_UPI_9999",
                    "provider_order_id": "ORDER_1042",
                    "signature": "SIG_VALID"
                }
            )
            self.assertEqual(verify_res.status_code, 200)

        self.db.refresh(job)
        self.assertEqual(job.payment_status, PaymentStatus.PAID)
        self.assertEqual(job.finishing_status, "PENDING")

        # 4. Physical printing finishes (Queue marks printing complete)
        complete_queue_job(job.job_id, self.db)
        self.db.refresh(job)
        # Because finishing is pending, finishing_status is PENDING
        self.assertEqual(job.finishing_status, "PENDING")

        # 5. Operator clicks Complete Finishing
        finish_res = self.client.post(f"/services/job/{job.job_id}/complete-finishing")
        self.assertEqual(finish_res.status_code, 200)
        self.db.refresh(job)
        self.assertEqual(job.finishing_status, "COMPLETED")
        self.assertEqual(job.status, JobStatus.COMPLETED)

        # 6. Later, Shop Owner increases Spiral Binding price from Rs 30 to Rs 35
        upd_res = self.client.put(
            f"/services/{binding_srv.service_id}",
            json={"price": 35.00}
        )
        self.assertEqual(upd_res.status_code, 200)

        # 7. Verify OLD order snapshot remains strictly Rs 30.00 / Rs 90.00 total
        old_snapshot = self.db.query(JobFinishingService).filter(
            JobFinishingService.job_id == job.job_id
        ).first()
        self.assertEqual(float(old_snapshot.unit_price), 30.00)
        self.assertEqual(float(old_snapshot.total_price), 30.00)
        self.db.refresh(job)
        self.assertEqual(float(job.total_amount), 90.00)

        # 8. Create NEW order: Verify it receives the updated Rs 35.00 price
        job2 = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job2)
        file2 = JobFile(
            file_id=uuid.uuid4(),
            job_id=job2.job_id,
            original_filename="new_doc.pdf",
            page_count=15,
            copies=2,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add(file2)
        self.db.commit()

        res2 = self.client.post(
            f"/services/job/{job2.job_id}/select",
            json={
                "customer_reference": "Priya",
                "services": [{"service_id": str(binding_srv.service_id), "quantity": 1}]
            }
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["services"][0]["unit_price"], 35.00)
        self.assertEqual(data2["subtotal"], 95.00)  # Rs 60 print + Rs 35 binding
        self.assertEqual(data2["total_amount"], 95.00)

    # ------------------------------------------------------------------
    # 14. Multiple Finishing Services on a Single Order
    # ------------------------------------------------------------------
    def test_09_multiple_finishing_services(self):
        # Spiral Binding (Rs 30) + Lamination (Rs 20) + Glass Sheet (Rs 3)
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)
        # 10 pages x 1 copy @ Rs 2.00 = Rs 20.00
        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="report.pdf",
            page_count=10,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add(file)
        self.db.commit()

        s_binding = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Spiral Binding"
        ).first()
        s_lamination = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Lamination"
        ).first()
        s_glass = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Transparent/Glass Sheet"
        ).first()

        res = self.client.post(
            f"/services/job/{job.job_id}/select",
            json={
                "customer_reference": "Anil",
                "services": [
                    {"service_id": str(s_binding.service_id), "quantity": 1},
                    {"service_id": str(s_lamination.service_id), "quantity": 1},
                    {"service_id": str(s_glass.service_id), "quantity": 2}
                ]
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Print = Rs 20.00
        # Binding = Rs 30.00
        # Lamination = Rs 20.00
        # Glass Sheet = Rs 3.00 * 2 = Rs 6.00
        # Total = 20 + 30 + 20 + 6 = Rs 76.00
        self.assertEqual(data["subtotal"], 76.00)
        self.assertEqual(data["total_amount"], 76.00)
        self.assertEqual(len(data["services"]), 3)

    # ------------------------------------------------------------------
    # 15. Cash Payment Workflow with Finishing Services
    # ------------------------------------------------------------------
    def test_10_cash_payment_with_finishing_services(self):
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=self.owner_a.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING
        )
        self.db.add(job)
        file = JobFile(
            file_id=uuid.uuid4(),
            job_id=job.job_id,
            original_filename="docs.pdf",
            page_count=5,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW,
            duplex=False
        )
        self.db.add(file)
        self.db.commit()

        s_stapling = self.db.query(FinishingService).filter(
            FinishingService.owner_id == self.owner_a.owner_id,
            FinishingService.service_name == "Stapling"
        ).first()

        self.client.post(
            f"/services/job/{job.job_id}/select",
            json={
                "customer_reference": "Kiran",
                "services": [{"service_id": str(s_stapling.service_id), "quantity": 1}]
            }
        )

        # Request Cash Payment (Print: 5 * 2 = 10 + Stapling: 5 = Rs 15)
        res_cash = self.client.post(f"/payment/cash/{job.job_id}")
        self.assertEqual(res_cash.status_code, 200)
        self.db.refresh(job)
        self.assertEqual(float(job.total_amount), 15.00)

        # Operator confirms cash at counter
        res_confirm = self.client.post(f"/payment/cash-confirm/{job.job_id}")
        self.assertEqual(res_confirm.status_code, 200)
        self.db.refresh(job)
        self.assertEqual(job.payment_status, PaymentStatus.PAID)
        self.assertEqual(job.finishing_status, "PENDING")


if __name__ == "__main__":
    unittest.main()
