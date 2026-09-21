import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from app.main import app
from app.api.printer import printer_health
from app.api.queue import queue_statistics
from app.api.ai import model_status
from app.api.agent import agent_health
from app.api.download import download_health
from app.core.config import resolve_public_base_url

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.connection import Base, get_db
from app.database.models import ShopOwner, ActiveJob

from sqlalchemy.pool import StaticPool

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

app.dependency_overrides[get_db] = override_get_db


class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        db = TestingSessionLocal()
        owner = db.query(ShopOwner).filter(ShopOwner.is_active == True).first()
        if not owner:
            from uuid import uuid4
            from app.core.security import hash_password
            owner = ShopOwner(
                owner_id=uuid4(),
                shop_name="Auto Test Shop",
                owner_name="Test Owner",
                email="test_owner@shop.local",
                phone="9988776655",
                password_hash=hash_password("admin123"),
                is_active=True
            )
            db.add(owner)
            db.commit()
        db.close()

    def test_routes_registered_without_shadowing(self):
        # Inspect all registered route paths in FastAPI app
        route_paths = [route.path for route in app.routes if hasattr(route, "path")]

        # Verify essential routes exist
        self.assertIn("/health", route_paths)
        self.assertIn("/queue/statistics/summary", route_paths)
        self.assertIn("/printer/health", route_paths)
        self.assertIn("/agent/health", route_paths)
        self.assertIn("/download/health", route_paths)
        self.assertIn("/ai/model-status", route_paths)

        # Verify route ordering: /printer/health must appear before /printer/{printer_id}
        printer_routes = [r.path for r in app.routes if hasattr(r, "path") and r.path.startswith("/printer")]
        idx_health = printer_routes.index("/printer/health")
        idx_id = printer_routes.index("/printer/{printer_id}")
        self.assertLess(idx_health, idx_id, "Route /printer/health MUST be declared before /printer/{printer_id} to prevent path shadowing")

        # Verify route ordering: /queue/statistics/summary must appear before /queue/{job_id}
        queue_routes = [r.path for r in app.routes if hasattr(r, "path") and r.path.startswith("/queue")]
        idx_q_stats = queue_routes.index("/queue/statistics/summary")
        idx_q_id = queue_routes.index("/queue/{job_id}")
        self.assertLess(idx_q_stats, idx_q_id, "Route /queue/statistics/summary MUST be declared before /queue/{job_id} to prevent path shadowing")

    def test_printer_health_function(self):
        data = printer_health()
        self.assertEqual(data["status"], "Healthy")
        self.assertEqual(data["service"], "Printer API")

    def test_agent_health_function(self):
        data = agent_health()
        self.assertEqual(data["status"], "Healthy")

    def test_download_health_function(self):
        data = download_health()
        self.assertEqual(data["status"], "Healthy")

    def test_ai_model_status_function(self):
        data = model_status()
        self.assertIn("fallback_status", data)
        self.assertIn("feature_set", data)

    def test_root_endpoint_serves_owner_portal(self):
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Smart Printing", response.text)
        self.assertIn("Owner Login", response.text)
        self.assertIn("Register Shop", response.text)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_owner_login_and_dashboard_flow(self):
        client = TestClient(app)
        # 1. Login with test owner credentials
        login_res = client.post("/owner/login", json={
            "email": "test_owner@shop.local",
            "password": "admin123"
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.json()
        self.assertIn("access_token", login_data)
        owner_id = login_data["owner_id"]

        # 2. View owner dashboard
        dash_res = client.get(f"/owner/{owner_id}/dashboard")
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn("Shop Operations & Analytics Dashboard", dash_res.text)

    def test_owner_qr_and_customer_scan(self):
        client = TestClient(app)
        db = TestingSessionLocal()
        owner = db.query(ShopOwner).filter(ShopOwner.is_active == True).first()
        
        # 1. Owner views QR page
        qr_page_res = client.get(
            f"/owner/{owner.owner_id}/qr",
            headers={"x-forwarded-proto": "https", "x-forwarded-host": "qr-printing-system.onrender.com"}
        )
        self.assertEqual(qr_page_res.status_code, 200)
        self.assertIn("Smart QR Printing Standee", qr_page_res.text)
        self.assertIn("https://qr-printing-system.onrender.com/qr/", qr_page_res.text)
        
        db.refresh(owner)
        self.assertIsNotNone(owner.qr_token)

        # 2. Customer scans QR code
        res_scan = client.get(f"/qr/{owner.qr_token}", follow_redirects=True)
        self.assertEqual(res_scan.status_code, 200)
        self.assertIn("Upload Your Documents", res_scan.text)
        self.assertIn("text/html", res_scan.headers.get("content-type", ""))
        db.close()

    def test_health_and_status_endpoints(self):
        client = TestClient(app)
        res_health = client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "Healthy")

        res_status = client.get("/api/status")
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(res_status.json()["status"], "Running")

        # Verify HEAD / health check support
        res_head = client.head("/")
        self.assertEqual(res_head.status_code, 200)


if __name__ == "__main__":
    unittest.main()
