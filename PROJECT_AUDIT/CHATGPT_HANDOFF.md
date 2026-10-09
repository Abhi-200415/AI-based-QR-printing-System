# AI-Based QR Printing System — ChatGPT Context Handoff Guide

> **To ChatGPT**: Read this document to understand the full project context, architecture, database schemas, code locations, and operational status without needing the user to re-explain.

---

## 1. Project Context & Purpose

The **AI-Based QR Printing System** is an end-to-end print shop automation platform designed for university copy centers and print shops. It allows walk-in customers to scan a shop-specific QR code, upload documents (PDF, DOCX, Images), select per-file print configurations (copies, duplex, color, finishing), pay via Razorpay (UPI/Card) or Cash, and have documents automatically dispatched to a local Windows computer running a background Print Agent that prints to physical hardware.

---

## 2. Core Technology Stack & Architecture

- **Backend**: **FastAPI** (Python 3.11) with Uvicorn ASGI server deployed on Render.
- **Database**: **SQLAlchemy 2.0 ORM** with **PostgreSQL** (Production on Render) and SQLite fallback.
- **Security & Cryptography**:
  - Documents encrypted at rest via **AES-256-GCM** envelope encryption (`app/core/crypto.py`).
  - Passwords hashed using **Argon2id** (`app/core/security.py`).
  - Auth via **JWT Bearer tokens** with 24-hour expiration.
  - Payment gating: `GET /download/...` strictly returns `403 Forbidden` for unpaid jobs.
- **Payment Gateway**: **Razorpay** SDK with server-side HMAC-SHA256 signature verification + walk-in **Cash Payment confirmation** on owner dashboard.
- **Frontend**: **Jinja2 templates** with vanilla CSS3 (dark glassmorphism theme), JavaScript ES6+, and Web Speech API voice assistant (`static/js/voice_search.js`).
- **Edge Print Agent (`PRINT_AGENT/`)**: Python daemon on Windows PC using `win32print` for hardware discovery, `DEVMODEW` manipulation for driver-less print settings, bundled headless `SumatraPDF.exe` for silent PDF printing, and DoD 5220.22-M multi-pass secure file shredding.
- **AI/ML Models**:
  - **7-day revenue & volume forecast**: Scikit-Learn **LinearRegression** (`app/services/analytics_service.py`).
  - **Print duration estimation**: Scikit-Learn **Ridge Regression** (`app/services/ml_prediction_service.py`) with parametric deterministic fallback ($4.0\text{s/page} \times \text{multipliers}$).
  - **Smart printer selection**: Heuristic scoring engine (`app/services/assignment_service.py`).

---

## 3. Key Source File Locations

| Subsystem | Source File Path | Key Functions / Responsibilities |
| :--- | :--- | :--- |
| **App Entry** | `cloud_server/app/main.py` | FastAPI app, CORS, security middleware, lifespan DB init |
| **Crypto Enclave** | `cloud_server/app/core/crypto.py` | `encrypt_document`, `decrypt_document` (AES-256-GCM) |
| **Auth & Security** | `cloud_server/app/core/security.py`| `hash_password`, `verify_password`, `create_access_token` |
| **Database Models** | `cloud_server/app/database/models.py` | `ShopOwner`, `ActiveJob`, `JobFile`, `Printer`, `Payment` |
| **Dynamic QR** | `cloud_server/app/api/session.py` | `GET /qr/{qr_token}` -> `303 Redirect` to `/upload/{job_id}` |
| **File Upload** | `cloud_server/app/api/upload.py` | `POST /upload/{job_id}` (Magic bytes, page count, AES encrypt) |
| **Settings & Voice**| `cloud_server/app/api/file_settings.py`| `PUT /file/{file_id}/settings` (Color/BW splits, duplex) |
| **Pricing Engine** | `cloud_server/app/services/pricing_engine.py`| `calculate_job_price` (Tiered page rates + finishing) |
| **Payment API** | `cloud_server/app/api/payment.py` | `create_payment`, `verify_payment`, `confirm_cash_payment` |
| **File Download** | `cloud_server/app/api/download.py` | `GET /download/job/...` (Gated: Unpaid = HTTP 403) |
| **Dispatcher** | `cloud_server/app/services/dispatch_service.py`| `dispatch_job_to_agent` (Broadcasts WebSocket event) |
| **WebSocket Hub** | `cloud_server/app/websocket/manager.py`| `printer_socket`, tracks agent connections |
| **Print Agent** | `PRINT_AGENT/agent.py` | Main edge daemon, connects to cloud WSS |
| **Agent Spooler** | `PRINT_AGENT/printers/advanced_executor.py`| SumatraPDF silent execution + Win32 DevMode |
| **DoD Shredder** | `PRINT_AGENT/services/cleanup.py` | `secure_delete` (Multi-pass random + zero overwrite) |

---

## 4. Current Verification & Test Status

- **Automated Tests**: **63 / 63 Tests Passed (100%)** running `python -m unittest discover -s tests -p "test_*.py" -v`.
- **10-Job Performance Benchmark**: Average upload duration: $3.05\text{s}$, Average request-to-start: $17.31\text{s}$ (~83% faster than manual USB printing).
- **Production Status**: Cloud server is configured for deployment on Render (`render.yaml`, `Procfile`, `runtime.txt`).
- **Immediate Next Action**: Add live Razorpay credentials to Render environment, launch `PRINT_AGENT/agent.py` on shop PC, and print QR standees.
