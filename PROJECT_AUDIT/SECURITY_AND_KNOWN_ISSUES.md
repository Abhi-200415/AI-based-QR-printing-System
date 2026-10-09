# Security & Known Issues Audit Report

This report provides a prioritized security evaluation, vulnerability assessment, and risk remediation roadmap for the **AI-Based QR Printing System**.

---

## 1. Security Architecture & Threat Model Evaluation

```
+----------------------------------------------------------------------------------------------------+
|                                    SECURITY POSTURE SCORECARD                                      |
+------------------------------------+----------------------------------+----------------------------+
| 1. DATA ENCRYPTION AT REST         | 2. PAYMENT GATING ENCLAVE        | 3. AUTHENTICATION & ACCESS |
| Status: EXCELLENT (Grade A)        | Status: EXCELLENT (Grade A)      | Status: ROBUST (Grade A-)  |
| - AES-256-GCM Envelope Encryption  | - Unpaid = Never Decrypted / 403 | - Argon2id Password Hash   |
| - Random per-file DEKs & Nonces    | - HMAC-SHA256 Signature Check    | - JWT Bearer (24h Expiry)  |
| - Zero Plaintext Stored on Disk    | - Offline Printer Hardware Guard | - Multi-Tenant Isolation   |
+------------------------------------+----------------------------------+----------------------------+
| 4. TRANSPORT SECURITY              | 5. INPUT & UPLOAD SANITIZATION   | 6. EDGE DATA ERASURE       |
| Status: ROBUST (Grade A)           | Status: ROBUST (Grade A)         | Status: STRONG (Grade A-)  |
| - Enforced HTTPS / TLS 1.3         | - Binary Magic Byte Inspection   | - DoD 5220.22-M Shredding  |
| - Authenticated WSS WebSockets     | - Path Traversal (../) Stripping | - Random + Zero Overwrite  |
| - Security Headers Active          | - Max File Size Clamping (50MB)  | - In-Memory RAM Streaming  |
+------------------------------------+----------------------------------+----------------------------+
```

---

## 2. Prioritized Security Findings & Remediation Plan

### Finding SEC-01 (Medium Priority): Explicit JWT Authorization on Cash Confirmation
- **Severity**: **MEDIUM** (CVSS: 4.3)
- **Component**: [`cloud_server/app/api/payment.py:L285-L335`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L285-L335)
- **Observed Behavior**: The endpoint `POST /payment/cash-confirm/{job_id}` accepts a path parameter `job_id: UUID` and dependency `db: Session = Depends(get_db)`. It does not explicitly declare `current_owner: ShopOwner = Depends(get_current_owner)`.
- **Impact Assessment**: While UUIDv4 identifiers have 122 bits of cryptographic entropy (making brute-force guessing computationally infeasible), an unauthenticated attacker who somehow intercepts an active customer `job_id` could theoretically trigger cash confirmation.
- **Remediation Recommendation**:
  ```python
  @router.post("/cash-confirm/{job_id}")
  async def confirm_cash_payment(
      job_id: UUID,
      current_owner: ShopOwner = Depends(get_current_owner),
      db: Session = Depends(get_db)
  ):
      job = db.query(ActiveJob).filter(
          ActiveJob.job_id == job_id,
          ActiveJob.owner_id == current_owner.owner_id
      ).first()
      if not job:
          raise HTTPException(status_code=404, detail="Job not found or access denied.")
  ```

---

### Finding SEC-02 (Low Priority / Quality of Life): Agent In-Memory Concurrency Set
- **Severity**: **LOW** (Reliability concern rather than security breach)
- **Component**: [`PRINT_AGENT/services/job_handler.py:L30-L51`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PRINT_AGENT/services/job_handler.py#L30-L51)
- **Observed Behavior**: `CURRENT_PROCESSING_JOBS = set()` is maintained purely in process memory.
- **Impact Assessment**: If the local PC suffers an abrupt power cut while SumatraPDF is spooling, the in-memory set resets upon restart. The cloud job remains marked `PRINTING`, requiring manual operator status reset from the dashboard.
- **Remediation Recommendation**: Maintain a local lightweight SQLite journal `local_spool_history.db` storing active job UUIDs across agent restarts.

---

### Finding SEC-03 (Informational): SSD Flash Storage Secure Deletion Realities
- **Severity**: **INFORMATIONAL / ACADEMIC HONESTY**
- **Component**: [`PRINT_AGENT/services/cleanup.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PRINT_AGENT/services/cleanup.py)
- **Observed Behavior**: The agent executes DoD 5220.22-M multi-pass overwriting (`os.write(b'\\x00')` + `os.fsync()`).
- **Academic Context**: On Solid State Drives (SSDs) and NVMe storage, hardware-level Flash Translation Layers (FTL) and wear-leveling algorithms may remap write operations to new physical NAND blocks rather than overwriting original flash cells directly.
- **Mitigation Active**: Because files are already encrypted with AES-256-GCM before transport and downloaded over TLS, residual flash blocks without the transient RAM key cannot be deciphered.

---

## 3. Verified Security Strengths (Audit Pass)

1. **Password Security**: Argon2id + Bcrypt multi-hash context in [`cloud_server/app/core/security.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/security.py) completely eliminates the historical 72-byte string limitation. Tested successfully with 128-character complex passwords.
2. **Strict Payment Gating**: The file download route ([`download.py:L35-L140`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/download.py#L35-L140)) strictly checks `ActiveJob.payment_status == PaymentStatus.PAID`. Unpaid jobs are returned HTTP `403 Forbidden` and decrypted content is never generated.
3. **Multi-Tenant Isolation (IDOR Defense)**: Verified via automated tests (`test_security.py::test_cross_owner_file_isolation`). Owner A cannot access or decrypt documents belonging to Owner B.
4. **Security Headers**: FastAPI root application injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `X-XSS-Protection: 1; mode=block` across all responses.
