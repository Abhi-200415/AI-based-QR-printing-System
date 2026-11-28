# Prioritized Action Plan & Next Steps

This roadmap outlines the prioritized engineering, deployment, and academic actions required for the **AI-Based QR Printing System**.

---

## 1. Priority 1 — Production Credentials & Cloud Launch (Immediate)

1. **Configure Live Razorpay API Keys on Render**:
   - In the Render dashboard, populate `PAYMENT_GATEWAY_KEY_ID` and `PAYMENT_GATEWAY_KEY_SECRET` with the live merchant credentials.
   - This immediately activates online UPI (GPay, PhonePe, Paytm), Credit/Debit Cards, and Netbanking for customers.
2. **Verify Public Render Domain Binding**:
   - Ensure `BASE_URL` in Render environment matches the custom or Render domain (e.g. `https://ai-qr-printing.onrender.com`).
   - This ensures all generated shop QR standees link directly to the production cloud endpoint.

---

## 2. Priority 2 — Physical Edge Print Agent Deployment (Shop PC)

1. **Setup Windows Print Agent on Physical PC**:
   - Clone or copy the `PRINT_AGENT/` folder to the Windows PC physically connected to the shop printers.
   - Install required dependencies: `pip install -r PRINT_AGENT/requirements.txt`.
   - Configure `PRINT_AGENT/.env` with `CLOUD_API_URL`, `WEBSOCKET_URL`, `SHOP_ID`, and `AGENT_ID`.
2. **Launch Agent Daemon**:
   - Run `python agent.py`.
   - Verify that the agent auto-discovers connected USB/Network printers and registers them with status `ONLINE` on the Cloud Server.
3. **Perform Physical Print Smoke Test**:
   - Send a 1-page test job from the mobile QR interface and verify physical paper ejection.

---

## 3. Priority 3 — Minor Security & Reliability Hardening

1. **Add Explicit JWT Dependency to Cash Confirmation**:
   - In [`cloud_server/app/api/payment.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L285-L335), inject `current_owner: ShopOwner = Depends(get_current_owner)` on `/cash-confirm/{job_id}` for defense-in-depth authorization.
2. **Implement Local Spool Journal on Agent**:
   - Add a lightweight SQLite table `PRINT_AGENT/spool_journal.db` to persist active print job UUIDs across unexpected PC reboots.

---

## 4. Priority 4 — Academic Defense & Machine Learning Model Training

1. **Accumulate 30+ Production Jobs**:
   - As real print jobs are completed and `started_at` / `completed_at` timestamps are logged, call `POST /ai/train-model`.
   - This transitions the print duration estimator from parametric fallback to a trained Scikit-Learn **Ridge Regression** model.
2. **Viva Defense Preparation**:
   - Review [PROJECT_DOCUMENTATION/14_VIVA_QUESTIONS_AND_CODE_LOCATIONS.md](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/PROJECT_DOCUMENTATION/14_VIVA_QUESTIONS_AND_CODE_LOCATIONS.md) for direct line references and examiner answers.
