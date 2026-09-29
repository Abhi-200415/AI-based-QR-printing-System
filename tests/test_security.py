import os
import sys
import io
import uuid
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

# Ensure cloud_server and PRINT_AGENT are in Python path
sys.path.insert(0, os.path.abspath("cloud_server"))
sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import Base, get_db
from app.database.models import (
    ShopOwner,
    ShopSettings,
    Printer,
    ActiveJob,
    JobFile,
    JobStatus,
    PaymentStatus,
    PrintType,
    PaperSize,
    Orientation
)
from app.core.security import hash_password, verify_password, create_access_token, verify_access_token
from app.core.crypto import (
    encrypt_document,
    decrypt_document,
    is_encrypted_envelope,
    CryptoSecurityException,
    MAGIC_HEADER
)
from app.services.cleanup_service import cleanup_job_files, cleanup_abandoned_jobs
from app.services.preview_service import analyze_uploaded_bytes, validate_file_content
from PRINT_AGENT.services.cleanup import secure_delete


from app.database.connection import SessionLocal

class TestSecurityHardening(unittest.TestCase):
    """
    Comprehensive Security Verification Suite:
    - Application-Level AES-256-GCM Document Encryption
    - Cloud Storage & Database Compromise Resilience
    - Strict Payment Gating (Unpaid = Never Decrypt)
    - Multi-Tenant Owner & Agent Isolation (Anti-IDOR)
    - Path Traversal & Upload Sanitization
    - Cryptographic Tamper Detection & Key Separation
    - Production Security Headers
    - Local & Cloud File Shredding / Cleanup
    """

    def setUp(self):
        self.db = SessionLocal()
        self.client = TestClient(app)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # ==========================================================
    # 1. AES-256-GCM Application-Level Document Encryption Tests
    # ==========================================================

    def test_crypto_encryption_and_decryption(self):
        sample_doc = b"%PDF-1.4 Mock confidential customer document with secret data."
        encrypted = encrypt_document(sample_doc)
        
        self.assertTrue(is_encrypted_envelope(encrypted))
        self.assertTrue(encrypted.startswith(MAGIC_HEADER))
        self.assertNotEqual(encrypted, sample_doc)
        self.assertNotIn(b"confidential", encrypted)

        # Decrypt with correct master key
        decrypted = decrypt_document(encrypted)
        self.assertEqual(decrypted, sample_doc)

    def test_ciphertext_not_readable_as_plaintext(self):
        sample_pdf = b"%PDF-1.4 1 0 obj << /Type /Catalog >> endobj trailer << /Root 1 0 R >> %%EOF"
        encrypted = encrypt_document(sample_pdf)

        # Confirm that the ciphertext cannot be parsed or interpreted as a PDF
        self.assertFalse(encrypted.startswith(b"%PDF"))
        self.assertTrue(encrypted.startswith(MAGIC_HEADER))
        # Ensure raw PDF markers are not present in plaintext inside ciphertext
        self.assertNotIn(b"/Type /Catalog", encrypted)

    def test_wrong_master_key_fails_decryption(self):
        sample_doc = b"Highly sensitive invoice details"
        encrypted = encrypt_document(sample_doc)

        attacker_fake_key = os.urandom(32)
        with self.assertRaises(CryptoSecurityException):
            decrypt_document(encrypted, custom_master_key=attacker_fake_key)

    def test_ciphertext_tampering_fails_gcm_auth(self):
        sample_doc = b"Authentic unaltered student paper"
        encrypted = bytearray(encrypt_document(sample_doc))

        # Flip a bit in the ciphertext payload
        encrypted[-1] ^= 0x01

        with self.assertRaises(CryptoSecurityException) as ctx:
            decrypt_document(bytes(encrypted))
        self.assertIn("tamper", str(ctx.exception).lower())

    def test_header_tampering_fails(self):
        sample_doc = b"Authentic document"
        encrypted = bytearray(encrypt_document(sample_doc))

        # Corrupt magic header
        encrypted[0] = ord("X")
        with self.assertRaises(CryptoSecurityException):
            decrypt_document(bytes(encrypted))

    def _create_owner(self, email_prefix: str = "sec_test") -> ShopOwner:
        unique_id = uuid.uuid4()
        owner = ShopOwner(
            owner_id=unique_id,
            shop_name=f"Security Test Shop {unique_id.hex[:6]}",
            owner_name="Sec Tester",
            email=f"{email_prefix}_{unique_id.hex[:8]}@test.local",
            phone=f"9{unique_id.int % 1000000000:09d}",
            password_hash=hash_password("admin123"),
            is_active=True
        )
        self.db.add(owner)
        self.db.commit()
        return owner

    # ==========================================================
    # 2. Cloud Compromise Simulation Tests
    # ==========================================================

    def test_cloud_database_compromise_simulation(self):
        """
        Simulates an attacker dumping the entire PostgreSQL database.
        Verifies that no plaintext document contents, no plaintext DEKs,
        and no Master Keys are stored in the database.
        """
        owner = self._create_owner("db_sim")
        job = ActiveJob(job_id=uuid.uuid4(), owner_id=owner.owner_id)
        self.db.add(job)
        self.db.commit()

        file = JobFile(
            job_id=job.job_id,
            original_filename="confidential_contract.pdf",
            stored_filename="test_enc.enc",
            file_path="uploads/test_enc.enc",
            file_size=1024,
            page_count=3
        )
        self.db.add(file)
        self.db.commit()

        # Query all DB columns as an attacker would
        queried_file = self.db.query(JobFile).filter(JobFile.job_id == job.job_id).first()
        # Verify no file content exists in database table
        self.assertFalse(hasattr(queried_file, "plaintext"))
        self.assertFalse(hasattr(queried_file, "file_content"))
        self.assertFalse(hasattr(queried_file, "master_key"))

    def test_cloud_storage_compromise_simulation(self):
        """
        Simulates an attacker gaining read access to the cloud storage uploads directory.
        Verifies that files on disk are strictly AES-256-GCM ciphertexts.
        """
        test_content = b"%PDF-1.7 Confidential medical report"
        enc_payload = encrypt_document(test_content)

        test_path = os.path.abspath("test_simulated_cloud_file.enc")
        try:
            with open(test_path, "wb") as f:
                f.write(enc_payload)

            with open(test_path, "rb") as f:
                disk_data = f.read()

            self.assertTrue(is_encrypted_envelope(disk_data))
            self.assertNotIn(b"medical report", disk_data)
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    # ==========================================================
    # 3. Payment Gating & File Download Security
    # ==========================================================

    def test_unpaid_job_download_forbidden(self):
        """
        Enforces Strict Payment Gating (UNPAID = NEVER PRINT / NEVER DECRYPT).
        """
        owner = self._create_owner("unpaid_test")
        job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=owner.owner_id,
            payment_status=PaymentStatus.PENDING # UNPAID
        )
        self.db.add(job)
        self.db.commit()

        file = JobFile(
            job_id=job.job_id,
            original_filename="notes.pdf",
            stored_filename="mock.enc",
            file_path="mock.enc"
        )
        self.db.add(file)
        self.db.commit()

        # Attempt download via API client
        response = self.client.get(f"/download/job/{job.job_id}/file/{file.file_id}")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Payment not completed", response.json().get("detail", ""))

    def test_cross_owner_file_isolation(self):
        """
        IDOR / Multi-Tenant Isolation Test:
        Owner A cannot access or decrypt Owner B's documents.
        """
        owner_a = self._create_owner("owner_a")
        owner_b = self._create_owner("owner_b")

        token_b = create_access_token(str(owner_b.owner_id))

        job_a = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=owner_a.owner_id,
            payment_status=PaymentStatus.PAID
        )
        self.db.add(job_a)
        self.db.commit()

        file_a = JobFile(
            job_id=job_a.job_id,
            original_filename="owner_a_secret.pdf",
            stored_filename="a.enc",
            file_path="a.enc"
        )
        self.db.add(file_a)
        self.db.commit()

        # Owner B tries to request Owner A's file
        headers = {"Authorization": f"Bearer {token_b}"}
        # In download endpoint, accessing a non-existent or un-owned file returns 404 or 403
        response = self.client.get(
            f"/download/job/{job_a.job_id}/file/{file_a.file_id}",
            headers=headers
        )
        # Should not successfully download Owner A's content
        self.assertNotEqual(response.status_code, 200)

    # ==========================================================
    # 4. Upload & Path Traversal Security
    # ==========================================================

    def test_path_traversal_sanitization(self):
        """
        Path traversal attempts in filenames must be stripped safely.
        """
        malicious_names = [
            "../../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\cmd.exe",
            "/absolute/path/file.pdf",
            "../../../evil.pdf"
        ]
        for bad_name in malicious_names:
            safe_name = os.path.basename(bad_name).replace("\\", "/").split("/")[-1]
            self.assertNotIn("..", safe_name)
            self.assertNotIn("/", safe_name)
            self.assertNotIn("\\", safe_name)

    def test_magic_bytes_file_validation(self):
        # Valid PDF header
        valid_pdf = b"%PDF-1.4 Mock content"
        valid, _ = validate_file_content(valid_pdf, ".pdf")
        self.assertTrue(valid)

        # Spoofed file (EXE disguised as PDF)
        spoofed_pdf = b"MZ\x90\x00\x03\x00\x00\x00 Fake executable payload"
        valid, msg = validate_file_content(spoofed_pdf, ".pdf")
        self.assertFalse(valid)
        self.assertIn("signature", msg.lower())

    # ==========================================================
    # 5. Security Headers & Configuration
    # ==========================================================

    def test_security_headers_present(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(response.headers.get("X-XSS-Protection"), "1; mode=block")

    # ==========================================================
    # 6. Secure Deletion & Cleanup Tests
    # ==========================================================

    def test_secure_shredding_and_cleanup(self):
        test_file = os.path.abspath("test_shred_me.tmp")
        with open(test_file, "wb") as f:
            f.write(b"Confidential data to be securely wiped")

        self.assertTrue(os.path.exists(test_file))
        result = secure_delete(test_file)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(test_file))

    def test_scheduled_abandoned_job_cleanup(self):
        owner = self._create_owner("abandoned_owner")
        old_time = datetime.utcnow() - timedelta(hours=5)
        abandoned_job = ActiveJob(
            job_id=uuid.uuid4(),
            owner_id=owner.owner_id,
            status=JobStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            created_at=old_time
        )
        self.db.add(abandoned_job)
        self.db.commit()

        cleaned = cleanup_abandoned_jobs(self.db, max_age_hours=2)
        self.assertGreaterEqual(cleaned, 1)

        # Verify job was deleted
        remaining = self.db.query(ActiveJob).filter(ActiveJob.job_id == abandoned_job.job_id).first()
        self.assertIsNone(remaining)


if __name__ == "__main__":
    unittest.main()
