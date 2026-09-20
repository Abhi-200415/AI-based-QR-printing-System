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


if __name__ == "__main__":
    unittest.main()
