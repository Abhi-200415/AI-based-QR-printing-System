# 08 — Razorpay Payment Flow & Financial Security Enclave

This document provides a comprehensive security and implementation audit of the **Razorpay Payment Gateway Integration** and cash workflows in the system.

---

## 1. Razorpay End-to-End Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer Browser
    participant Cloud as Cloud Server (/payment)
    participant DB as PostgreSQL Database
    participant RZ as Razorpay REST API
    participant WS as WebSocket Dispatcher

    %% Order Creation
    Customer->>Cloud: POST /payment/create/{job_id}
    Note over Cloud: Validates job total & checks printer online status
    Cloud->>RZ: razorpay_client.order.create({amount: in_paise, currency: "INR"})
    RZ-->>Cloud: Returns order_id (e.g. "order_Oxx123456")
    Cloud->>DB: INSERT into payments (status="PENDING", transaction_id=order_id)
    Cloud-->>Customer: JSON {order_id, amount, key_id, currency}

    %% Client Checkout
    Customer->>RZ: Opens Razorpay Standard Checkout Modal
    Customer->>RZ: Completes UPI (GPay/PhonePe) or Credit/Debit Card
    RZ-->>Customer: Returns {razorpay_order_id, razorpay_payment_id, razorpay_signature}

    %% Server Signature Verification
    Customer->>Cloud: POST /payment/verify (Includes Razorpay payload)
    Note over Cloud: HMAC-SHA256 Verification (secret + order_id|payment_id)
    alt Valid Signature
        Cloud->>DB: UPDATE payments SET status="SUCCESS", verified=True
        Cloud->>DB: UPDATE active_jobs SET payment_status="PAID", status="QUEUED"
        Cloud->>WS: Trigger dispatch_next_queued_job()
        Cloud-->>Customer: JSON {status: "PAID", redirect_url: "/job/tracker/{job_id}"}
    else Invalid Signature / Tampering
        Cloud->>DB: UPDATE payments SET status="FAILED"
        Cloud-->>Customer: HTTP 400 Bad Request ("Invalid payment signature")
    end
```

---

## 2. Server-Side Signature Verification & Cryptographic Integrity

### 2.1 HMAC-SHA256 Verification Implementation
- **Source Location**: `cloud_server/app/api/payment.py` ([L130-L220](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L130-L220))
- **Mathematical Principle**:
  $$\text{Expected Signature} = \text{HMAC-SHA256}(\text{key}=\text{PAYMENT\_GATEWAY\_KEY\_SECRET}, \text{msg}=\text{order\_id} \parallel \text{"|"} \parallel \text{payment\_id})$$
- **Code Logic**:
  ```python
  generated_signature = hmac.new(
      settings.PAYMENT_GATEWAY_KEY_SECRET.encode("utf-8"),
      f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8"),
      hashlib.sha256
  ).hexdigest()

  if not hmac.compare_digest(generated_signature, payload.razorpay_signature):
      raise HTTPException(status_code=400, detail="Invalid payment signature.")
  ```
- **Security Guarantee**: `hmac.compare_digest()` is used to eliminate timing attack vulnerabilities.

---

## 3. Strict Payment-Gated Security Rules

1. **Zero Unpaid Decryption Policy**:
   - The file download route (`GET /download/job/{job_id}/file/{file_id}`) rejects any download request with HTTP `403 Forbidden` if `ActiveJob.payment_status != PaymentStatus.PAID`.
   - Files remain encrypted on disk with AES-256-GCM until verified payment occurs.
2. **Offline Hardware Guard**:
   - `POST /payment/create/{job_id}` verifies that at least one printer registered to the target shop has `status == "ONLINE"`. If all printers are offline, the payment creation request is blocked with HTTP `400 Bad Request` to prevent taking customer funds when printing is impossible.
3. **Idempotency & Duplicate Webhook Handling**:
   - `POST /payment/webhook` checks if the payment record is already marked `SUCCESS`. If already verified, subsequent duplicate webhook payloads return HTTP `200 OK` without triggering duplicate queue entries or double prints.

---

## 4. Cash Payment Confirmation Workflow

For customers who prefer cash or lack digital payment access:
1. Customer clicks "Pay Cash at Counter" -> Calls `POST /payment/cash/{job_id}`.
2. Job is marked `payment_status = "PENDING_CASH_APPROVAL"`.
3. Job is **NOT** sent to the printer queue.
4. Shop owner's dashboard displays a real-time cashier banner with customer name, job ID, and amount due.
5. Once the shop owner collects the cash, the owner clicks "Confirm Cash Payment" (`POST /payment/cash-confirm/{job_id}`).
6. Server marks `payment_status = "PAID"` and pushes the job to the print queue.
