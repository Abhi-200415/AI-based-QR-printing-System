# 14 — Academic Viva Questions, Answers & Code Grounding

This guide provides technical answers to frequent project defense questions, linked directly to source code lines.

---

## 1. System Architecture & Flow Questions

### Q1: How does a customer initiate a print session without creating an account?
- **Technical Answer**: The system implements dynamic QR session tokens. Each shop has a unique `qr_token` embedded in its standee URL (`https://<domain>/qr/<token>`). When scanned, the endpoint `GET /qr/{qr_token}` ([`cloud_server/app/api/session.py:L25-L65`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/session.py#L25-L65)) retrieves the `ShopOwner`, creates a new `ActiveJob` record with status `PENDING`, and returns an HTTP `303 See Other` redirecting the customer's browser directly to `/upload/{job_id}`.
- **Code Evidence**: [`cloud_server/app/api/session.py:L25-L65`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/session.py#L25-L65)

---

### Q2: How does the cloud server communicate with local physical printers behind NAT / Firewalls?
- **Technical Answer**: Because local shop PCs are behind private NAT firewalls without public IP addresses, the cloud cannot directly push HTTP requests to the shop. Instead, the **Local Print Agent** ([`PRINT_AGENT/agent.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PRINT_AGENT/agent.py)) establishes an outbound persistent WebSocket connection (`/ws/printer`) to the cloud server. The cloud WebSocket hub maintains an active connection map and broadcasts `JOB_DISPATCH` payloads over this open duplex tunnel.
- **Code Evidence**: [`cloud_server/app/websocket/manager.py:L20-L80`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/websocket/manager.py#L20-L80) and [`PRINT_AGENT/websocket/client.py:L30-L90`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PRINT_AGENT/websocket/client.py#L30-L90).

---

## 2. Security, Cryptography & Privacy Questions

### Q3: How do you guarantee the privacy of sensitive documents uploaded to the cloud?
- **Technical Answer**: Uploaded documents are encrypted using **AES-256-GCM** envelope encryption at rest before being written to disk in [`cloud_server/app/api/upload.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/upload.py#L110-L135) via `encrypt_document()` ([`cloud_server/app/core/crypto.py:L45-L75`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/crypto.py#L45-L75)). The database stores only metadata and file paths; it contains zero document plaintext. Decryption occurs only in RAM upon authenticated fetch by the Edge Print Agent once the job is verified as `PAID`.
- **Code Evidence**: [`cloud_server/app/core/crypto.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/crypto.py) and [`tests/test_security.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/tests/test_security.py).

---

### Q4: How is local file cleanup handled on the shop owner's physical computer?
- **Technical Answer**: Rather than simple OS deletion (which leaves recoverable blocks), the agent implements **DoD 5220.22-M compliant multi-pass secure file shredding** in [`PRINT_AGENT/services/cleanup.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PRINT_AGENT/services/cleanup.py). The file is overwritten with random bytes (Pass 1), overwritten with zero bytes (Pass 2), truncated to zero length, flushed with `os.fsync()`, and unlinked.
- **Code Evidence**: [`PRINT_AGENT/services/cleanup.py:L20-L65`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PRINT_AGENT/services/cleanup.py#L20-L65).

---

## 3. Payment & Financial Verification Questions

### Q5: How do you prevent payment tampering or unpaid jobs from printing?
- **Technical Answer**:
  1. **Cryptographic Verification**: On Razorpay checkout completion, `POST /payment/verify` recomputes the HMAC-SHA256 signature using `PAYMENT_GATEWAY_KEY_SECRET` and `hmac.compare_digest()`.
  2. **Payment Gating**: The file streaming download route (`GET /download/job/{job_id}/file/{file_id}`) strictly enforces `ActiveJob.payment_status == PaymentStatus.PAID`. If unpaid, it returns HTTP `403 Forbidden` and never decrypts the document.
- **Code Evidence**: [`cloud_server/app/api/payment.py:L130-L200`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L130-L200) and [`cloud_server/app/api/download.py:L40-L70`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/download.py#L40-L70).

---

## 4. AI / ML & Data Science Questions

### Q6: What machine learning algorithms are implemented in your project?
- **Technical Answer**:
  1. **Revenue & Volume Forecasting**: Implemented via Scikit-Learn **Ordinary Least Squares (OLS) Linear Regression** (`LinearRegression`) in [`cloud_server/app/services/analytics_service.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/analytics_service.py#L280-L360) predicting 7-day future demand from historical `AnalyticsDaily` records.
  2. **Print Duration Estimation**: Multi-variable regression predicting print duration based on total pages, copies, color mode, duplex mode, and queue depth in [`cloud_server/app/services/ml_prediction_service.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/ml_prediction_service.py#L60-L120).
  3. **Multi-Attribute Decision Heuristics**: Heuristic scoring engine for smart printer allocation in [`cloud_server/app/services/assignment_service.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/assignment_service.py#L30-L100).
