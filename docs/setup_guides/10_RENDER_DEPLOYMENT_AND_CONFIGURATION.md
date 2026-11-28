# 10 — Render Deployment, Configuration & Infrastructure

This document details the deployment topology, container specifications, and environment configuration for hosting the cloud backend on **Render.com**.

---

## 1. Cloud Architecture on Render

```mermaid
graph TD
    A["Internet / Customers / Shop Owners"] -->|"HTTPS / TLS (Port 443)"| B["Render Cloud Edge / Reverse Proxy"]
    B -->|"Internal HTTP Proxy (Port $PORT)"| C["Uvicorn ASGI Server (cloud_server)"]
    C --> D["FastAPI Core Application (app.main:app)"]
    D --> E["PostgreSQL Cloud Database (Render Managed PostgreSQL)"]
    D --> F["Encrypted Cloud Storage (uploads/ directory)"]
    G["Edge Print Agent (Shop Windows PC)"] -->|"WSS / TLS Persistent Socket"| B
```

---

## 2. Infrastructure Configuration Files

### 2.1 `render.yaml` (Infrastructure-as-Code)
```yaml
services:
  - type: web
    name: ai-qr-printing-cloud
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir cloud_server
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: DEBUG
        value: "false"
      - key: DATABASE_URL
        fromDatabase:
          name: ai_qr_printing_db
          property: connectionString
      - key: JWT_SECRET
        generateValue: true
      - key: PAYMENT_GATEWAY_PROVIDER
        value: RAZORPAY
```

### 2.2 `Procfile`
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir cloud_server
```

### 2.3 `runtime.txt`
```
python-3.11.8
```

---

## 3. Environment Variables Reference

| Variable Name | Required? | Purpose in Production | Example / Format |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Yes | Controls logging verbosity and error display | `production` / `development` |
| `DEBUG` | Yes | Disables OpenAPI docs / debug traceback in prod | `false` |
| `BASE_URL` | Yes | Base public domain used in QR code generation | `https://ai-qr-printing.onrender.com` |
| `DATABASE_URL` | Yes | PostgreSQL connection URI | `postgresql://user:pass@ep-host.render.com/dbname` |
| `JWT_SECRET` | Yes | 256-bit secret used for owner JWTs & AES key derivation | 64-char Hex or High-entropy string |
| `PAYMENT_GATEWAY_KEY_ID` | Yes | Razorpay API Public Key ID | `rzp_live_xxxxxxxx` or `rzp_test_xxxxxxxx` |
| `PAYMENT_GATEWAY_KEY_SECRET` | Yes | Razorpay Secret Key for HMAC-SHA256 signature verification | 24-32 char secure secret |
| `PAYMENT_WEBHOOK_SECRET` | Optional | Webhook verification secret from Razorpay dashboard | Webhook secret string |
| `UPLOAD_DIR` | Optional | Storage location for encrypted uploads | `uploads` (Default) |
| `MAX_UPLOAD_SIZE_MB` | Optional | Maximum allowed upload payload per document | `50` |
| `CORS_ORIGINS` | Optional | Allowed Cross-Origin domains | `*` or specific domains |

---

## 4. Production Deployment Verification Checklist

- [x] Python 3.11 runtime verified via `runtime.txt`.
- [x] Uvicorn bound to dynamic Render port `$PORT` via `--app-dir cloud_server`.
- [x] Static files mounted safely at `/static` (`app.mount("/static", StaticFiles(...))`).
- [x] PostgreSQL connection pooling configured with `pool_size=10, max_overflow=20, pool_pre_ping=True`.
- [x] Security headers middleware active (`nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin`).
- [x] Database tables auto-created and verified on boot via `lifespan` handler.
