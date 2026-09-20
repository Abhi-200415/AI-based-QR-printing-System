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

class TestAPIEndpoints(unittest.TestCase):

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

    def test_root_endpoint_leads_to_owner_dashboard(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Shop Operations & Analytics Dashboard", response.text)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_customer_qr_scan_leads_to_customer_upload(self):
        from fastapi.testclient import TestClient
        from app.database.connection import SessionLocal
        from app.database.models import ShopOwner
        client = TestClient(app)
        db = SessionLocal()
        owner = db.query(ShopOwner).filter(ShopOwner.is_active == True).first()
        if not owner:
            owner = ShopOwner(shop_name="Auto Shop", owner_name="Owner", email="auto@shop.com", phone="9998887776", is_active=True)
            db.add(owner)
            db.commit()
            db.refresh(owner)
        
        # Ensure owner has QR token
        client.get(f"/owner/{owner.owner_id}/qr")
        db.refresh(owner)

        # Customer scans QR
        res_scan = client.get(f"/qr/{owner.qr_token}", follow_redirects=True)
        self.assertEqual(res_scan.status_code, 200)
        self.assertIn("Upload Documents for Printing", res_scan.text)
        self.assertIn("text/html", res_scan.headers.get("content-type", ""))
        db.close()

    def test_health_and_status_endpoints(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)
        res_health = client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "Healthy")

        res_status = client.get("/api/status")
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(res_status.json()["status"], "Running")


if __name__ == "__main__":
    unittest.main()
