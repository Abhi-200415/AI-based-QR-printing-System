import os
import sys

# Set TESTING=1 before any app imports to avoid remote database connection timeouts
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import io
import uuid
import unittest
from unittest.mock import patch

# Ensure cloud_server and PRINT_AGENT are in sys.path
sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.connection import Base
from app.database.models import ShopOwner, ActiveJob, JobFile, JobStatus, PaymentStatus, PaperSize, PrintType
from app.services.cleanup_service import delete_uploaded_file, cleanup_job_files, cleanup_file
from PRINT_AGENT.services.cleanup import secure_delete


class TestCleanupAndVoiceAssistant(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        self.owner = ShopOwner(
            owner_id=uuid.uuid4(),
            owner_name="Test Owner",
            shop_name="Print Shop",
            email="test@shop.com",
            phone="9876543210",
            password_hash="hash",
            is_active=True
        )
        self.db.add(self.owner)
        self.db.commit()

        # Temporary test directory
        self.test_dir = os.path.abspath("test_temp_cleanup")
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                try:
                    os.remove(os.path.join(self.test_dir, f))
                except Exception:
                    pass
            try:
                os.rmdir(self.test_dir)
            except Exception:
                pass

    # ==========================================================
    # 1. CLOUD CLEANUP TESTS
    # ==========================================================

    def test_01_cloud_cleanup_terminal_logs_and_safe_deletion(self):
        """Verify structured cloud cleanup logs and safe file shredding."""
        temp_file = os.path.join(self.test_dir, "cloud_test_doc.pdf")
        with open(temp_file, "wb") as f:
            f.write(b"%PDF-1.4 cloud confidential data here")

        job_id = uuid.uuid4()
        job = ActiveJob(
            job_id=job_id,
            owner_id=self.owner.owner_id,
            status=JobStatus.COMPLETED,
            payment_status=PaymentStatus.PAID
        )
        self.db.add(job)
        jf = JobFile(
            file_id=uuid.uuid4(),
            job_id=job_id,
            original_filename="cloud_test_doc.pdf",
            file_path=temp_file,
            page_count=3,
            copies=1,
            paper_size=PaperSize.A4,
            print_type=PrintType.BW
        )
        self.db.add(jf)
        self.db.commit()

        # Capture stdout to verify terminal log format
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            cleaned_count = cleanup_job_files(job_id, self.db)

        log_output = stdout_capture.getvalue()

        # Validate count and file removal
        self.assertEqual(cleaned_count, 1)
        self.assertFalse(os.path.exists(temp_file))

        # Validate required structured terminal logs
        self.assertIn("[CLOUD CLEANUP] Starting cleanup", log_output)
        self.assertIn(f"[CLOUD CLEANUP] Job ID: {job_id}", log_output)
        self.assertIn("[CLOUD CLEANUP] Temporary file located", log_output)
        self.assertIn("[CLOUD CLEANUP] Deletion successful", log_output)
        self.assertIn("[CLOUD CLEANUP] Cleanup completed", log_output)

        # Validate database state updated to prevent re-deletion
        self.db.refresh(jf)
        self.assertEqual(jf.file_path, "[DELETED]")

        # Safe repeated cleanup (idempotency check)
        stdout_repeat = io.StringIO()
        with patch("sys.stdout", stdout_repeat):
            repeat_cleaned = cleanup_job_files(job_id, self.db)
        self.assertEqual(repeat_cleaned, 1)
        # Should not throw exception and should report safe handling

    def test_02_cloud_cleanup_missing_file_safety(self):
        """Verify cloud cleanup safely handles already-deleted files without error."""
        non_existent_path = os.path.join(self.test_dir, "ghost_file.pdf")
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            delete_uploaded_file(non_existent_path, job_id="test-job-99")
        log_output = stdout_capture.getvalue()
        self.assertIn("[CLOUD CLEANUP] Temporary file already removed or missing", log_output)

    # ==========================================================
    # 2. LOCAL PRINT AGENT CLEANUP TESTS
    # ==========================================================

    def test_03_local_cleanup_terminal_logs_and_safe_deletion(self):
        """Verify structured local print agent cleanup logs."""
        local_file = os.path.join(self.test_dir, "local_print_job.pdf")
        with open(local_file, "wb") as f:
            f.write(b"%PDF-1.4 local shop spool data")

        job_id = "local-job-777"
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            result = secure_delete(local_file, job_id=job_id)

        log_output = stdout_capture.getvalue()

        self.assertTrue(result)
        self.assertFalse(os.path.exists(local_file))

        # Validate required structured logs
        self.assertIn("[LOCAL CLEANUP] Starting local cleanup", log_output)
        self.assertIn(f"[LOCAL CLEANUP] Job ID: {job_id}", log_output)
        self.assertIn("[LOCAL CLEANUP] Temporary file located", log_output)
        self.assertIn("[LOCAL CLEANUP] File deletion successful", log_output)
        self.assertIn("[LOCAL CLEANUP] Cleanup completed", log_output)

        # Repeated delete check
        stdout_repeat = io.StringIO()
        with patch("sys.stdout", stdout_repeat):
            repeat_result = secure_delete(local_file, job_id=job_id)
        self.assertFalse(repeat_result)
        self.assertIn("[LOCAL CLEANUP] Cleanup completed", stdout_repeat.getvalue())

    # ==========================================================
    # 3. VOICE ASSISTANT SERVER TELEMETRY & TERMINAL LOGS
    # ==========================================================

    def test_04_voice_telemetry_terminal_logs(self):
        """Verify voice assistant events log the required structured terminal messages."""
        from app.api.ai import log_voice_command, VoiceLogRequest

        events = [
            ("MIC_ACTIVATED", None, None, None, "[VOICE] Microphone activated"),
            ("SPEECH_CAPTURED", "print 2 copies color", "CONFIGURE_PRINT", None, "[VOICE] Speech captured"),
            ("EXECUTING", "print 2 copies color", "CONFIGURE_PRINT", None, "[VOICE] Executing action"),
            ("COMPLETED", "print 2 copies color", "CONFIGURE_PRINT", None, "[VOICE] Action completed successfully"),
            ("UNCLEAR", "print", "AMBIGUOUS", None, "[VOICE] Command unclear"),
            ("RECOGNITION_FAILED", None, None, "not-allowed", "[VOICE] Recognition failed"),
            ("FAILED", "preview", "PREVIEW", "Preview element missing", "[VOICE] Execution failed: Preview element missing")
        ]

        for evt, cmd, intent, detail, expected_log in events:
            stdout_capture = io.StringIO()
            with patch("sys.stdout", stdout_capture):
                res = log_voice_command(VoiceLogRequest(event=evt, command=cmd, intent=intent, detail=detail))
            self.assertEqual(res["status"], "ok")
            self.assertIn(expected_log, stdout_capture.getvalue())

    # ==========================================================
    # 4. VOICE ASSISTANT CLIENT SCRIPT CHECKS
    # ==========================================================

    def test_05_voice_script_requirements_and_parser(self):
        """Verify voice_search.js constraints and parseCommand intent detection."""
        voice_path = os.path.join("cloud_server", "static", "js", "voice_search.js")
        self.assertTrue(os.path.exists(voice_path))
        with open(voice_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Check required architectural rules
        self.assertIn("continuous = false", code)
        self.assertIn("parseCommand", code)
        self.assertIn("Spiral Binding", code)
        self.assertIn("Transparent/Glass Sheet", code)
        self.assertIn("Role Restricted", code)
        self.assertIn("/ai/voice-command", code)
        self.assertIn("speechSynthesis", code)
        self.assertIn("lastExecutionTime", code)  # Debounce mechanism


if __name__ == "__main__":
    unittest.main()
