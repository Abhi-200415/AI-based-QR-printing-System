# 01 — Complete Project File Inventory

This inventory accounts for every file in the **AI-Based QR Printing System** repository, categorized by module and operational tier.

---

## 1. Cloud Server Core & Application Layer (`cloud_server/app/`)

| Relative File Path | Type | Size | Module / Subsystem | Purpose & Responsibilities | Key Dependencies | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `cloud_server/app/main.py` | Python | 7.19 KB | Core Application | FastAPI root app initialization, CORS middleware, security headers middleware, static file mounting, router registration, DB table check | `fastapi`, `starlette`, `app.api.*`, `app.core.config` | **Active / Production Entry Point** |
| `cloud_server/app/core/config.py` | Python | 1.77 KB | Configuration | Environment variable parsing, settings model (`pydantic_settings`), secret configuration | `pydantic_settings`, `os` | **Active** |
| `cloud_server/app/core/crypto.py` | Python | 5.23 KB | Cryptography | AES-256-GCM envelope encryption/decryption for uploaded documents, master key derivation | `cryptography.hazmat.primitives.ciphers.aead.AESGCM` | **Active** |
| `cloud_server/app/core/security.py` | Python | 4.88 KB | Security & Auth | Argon2id & bcrypt password hashing, JWT creation/validation, HTTP Bearer security schemes | `passlib`, `jose`, `fastapi.security`, `argon2` | **Active** |
| `cloud_server/app/core/job_store.py` | Python | 75 B | State Storage | Global ephemeral in-memory state dictionary fallback | Python built-ins | **Active (Legacy Helper)** |
| `cloud_server/app/core/cleanup.py` | Python | 0 B | Core Maintenance | Empty placeholder module superseded by `app/services/cleanup_service.py` | None | **Empty / Deprecated** |
| `cloud_server/app/database/connection.py` | Python | 4.41 KB | Database Engine | SQLAlchemy engine configuration, connection pooling (`pool_size=10`), session factory, DB health check | `sqlalchemy`, `psycopg2` / `sqlite3` | **Active** |
| `cloud_server/app/database/models.py` | Python | 28.69 KB | ORM Models | Declarative SQLAlchemy models for `ShopOwner`, `ShopSettings`, `Printer`, `ActiveJob`, `JobFile`, `PricingRule`, `Payment`, `AnalyticsDaily`, `FinishingService`, `JobFinishingService` | `sqlalchemy.orm`, `uuid`, `enum` | **Active** |
| `cloud_server/app/utils/logger.py` | Python | 278 B | Logging | Central standard library logger configuration for cloud server | `logging` | **Active** |

---

## 2. Cloud Server API Routers (`cloud_server/app/api/`)

| Relative File Path | Type | Size | Module / Subsystem | Purpose & Responsibilities | Key Dependencies | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `cloud_server/app/api/agent.py` | Python | 4.74 KB | Agent REST API | Edge Print Agent registration (`/agent/register`), periodic heartbeat reporting (`/agent/heartbeat`), agent status retrieval | `fastapi`, `sqlalchemy`, `app.database.models` | **Active** |
| `cloud_server/app/api/ai.py` | Python | 3.14 KB | AI & ML API | ML model status, retraining triggers (`/ai/train-model`), intelligent printer recommendation endpoint (`/ai/printer/{job_id}`) | `fastapi`, `app.services.ml_prediction_service`, `app.services.assignment_service` | **Active** |
| `cloud_server/app/api/ai_document_search.py` | Python | 1.55 KB | Search API | Document keyword search across uploaded and decrypted document text | `fastapi`, `app.services.document_search_service` | **Active** |
| `cloud_server/app/api/analytics.py` | Python | 4.08 KB | Business Intelligence | Owner dashboard analytics, revenue charts, forecasting data, busy-hour predictions | `fastapi`, `app.services.analytics_service` | **Active** |
| `cloud_server/app/api/download.py` | Python | 5.83 KB | Secure Ingestion | Payment-gated file download endpoint for Edge Print Agent (`/download/job/{job_id}/file/{file_id}`) | `fastapi`, `app.core.crypto`, `app.database.models` | **Active** |
| `cloud_server/app/api/file_settings.py` | Python | 7.55 KB | Print Settings | Per-file print configuration (copies, color mode, duplex, paper size, page ranges), price re-calculation | `fastapi`, `app.services.pricing_engine` | **Active** |
| `cloud_server/app/api/jobs.py` | Python | 11.14 KB | Job Management | Job creation, single-job queries, status updates, job cancellation, dispatch-next trigger | `fastapi`, `app.services.job_service`, `app.services.dispatch_service` | **Active** |
| `cloud_server/app/api/owner.py` | Python | 9.70 KB | Owner Auth & Shop | Owner registration, login (JWT token return), password reset, profile query, dashboard data API | `fastapi`, `app.core.security`, `app.database.models` | **Active** |
| `cloud_server/app/api/payment.py` | Python | 15.83 KB | Razorpay & Cash API | Razorpay order creation (`/payment/create/{job_id}`), HMAC-SHA256 signature verification (`/payment/verify`), webhook processing, cash approval/rejection | `fastapi`, `razorpay`, `app.services.payment_service` | **Active** |
| `cloud_server/app/api/preview.py` | Python | 4.02 KB | Document Preview | Thumbnail and first-page image preview generation for uploaded customer documents | `fastapi`, `app.services.preview_service` | **Active** |
| `cloud_server/app/api/pricing.py` | Python | 7.32 KB | Pricing Rules | Tiered pricing rule creation, rule updates, quick-update batch API, job cost calculation | `fastapi`, `app.services.pricing_engine` | **Active** |
| `cloud_server/app/api/printer.py` | Python | 6.99 KB | Printer Management | Printer registration, status toggles (online/offline/maintenance), owner printer inventory, ping health | `fastapi`, `app.database.models` | **Active** |
| `cloud_server/app/api/queue.py` | Python | 4.48 KB | Queue API | Queue insertion (`/queue/{job_id}`), queue position query, printer queue inspection, queue summary statistics | `fastapi`, `app.services.queue_service` | **Active** |
| `cloud_server/app/api/receipt.py` | Python | 5.95 KB | Receipt API | Authoritative receipt data generation (JSON), HTML formatted receipt view, and printable HTML receipt download | `fastapi`, `app.database.models`, `fastapi.responses.HTMLResponse` | **Active** |
| `cloud_server/app/api/services.py` | Python | 8.64 KB | Finishing Services | Value-added services (lamination, binding, stapling), shop service configuration, job service attachment, operator completion | `fastapi`, `app.database.models`, `app.services.pricing_engine` | **Active** |
| `cloud_server/app/api/session.py` | Python | 4.42 KB | Dynamic QR & Web UI | QR token scanning (`/qr/{qr_token}`), QR image generation (`/owner/{owner_id}/qr`), job tracker page, dashboard view | `fastapi`, `qrcode`, `jinja2` | **Active** |
| `cloud_server/app/api/settings.py` | Python | 3.46 KB | Shop Settings | Shop global print policy configuration (allowed duplex, allowed color, max file size) | `fastapi`, `app.database.models` | **Active** |
| `cloud_server/app/api/status.py` | Python | 2.25 KB | System Status | High-level system health and database connectivity probe | `fastapi` | **Active** |
| `cloud_server/app/api/upload.py` | Python | 6.01 KB | File Upload UI & API | Customer file upload endpoint (`/upload/{job_id}`), PDF/DOCX page count extraction, AES-256 encryption on write | `fastapi`, `app.services.page_counter`, `app.core.crypto` | **Active** |

---

## 3. Cloud Server Schemas & Services (`cloud_server/app/schemas/` & `services/`)

| Relative File Path | Type | Size | Module / Subsystem | Purpose & Responsibilities | Key Dependencies | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `cloud_server/app/schemas/analytics.py` | Python | 1.02 KB | Pydantic Schemas | Data validation schemas for analytics responses and forecasts | `pydantic` | **Active** |
| `cloud_server/app/schemas/file_settings.py` | Python | 1.88 KB | Pydantic Schemas | Schemas for per-file print configuration requests/responses | `pydantic` | **Active** |
| `cloud_server/app/schemas/job.py` | Python | 1.92 KB | Pydantic Schemas | Schemas for job creation, job status, and job list responses | `pydantic` | **Active** |
| `cloud_server/app/schemas/owner.py` | Python | 1.41 KB | Pydantic Schemas | Schemas for owner registration, login, token responses, and profiles | `pydantic` | **Active** |
| `cloud_server/app/schemas/payment.py` | Python | 1.61 KB | Pydantic Schemas | Schemas for Razorpay order creation, payment verification, cash workflow | `pydantic` | **Active** |
| `cloud_server/app/schemas/pricing.py` | Python | 1.99 KB | Pydantic Schemas | Schemas for pricing rule definitions, rule updates, pricing breakdown | `pydantic` | **Active** |
| `cloud_server/app/schemas/printer.py` | Python | 4.96 KB | Pydantic Schemas | Schemas for printer registration, capabilities, telemetry, status updates | `pydantic` | **Active** |
| `cloud_server/app/schemas/queue.py` | Python | 948 B | Pydantic Schemas | Schemas for queue status, queue entry, and priority payloads | `pydantic` | **Active** |
| `cloud_server/app/schemas/service.py` | Python | 2.33 KB | Pydantic Schemas | Schemas for finishing service management and job attachments | `pydantic` | **Active** |
| `cloud_server/app/schemas/settings.py` | Python | 2.24 KB | Pydantic Schemas | Schemas for shop configuration and operational flags | `pydantic` | **Active** |
| `cloud_server/app/services/analytics_service.py` | Python | 22.54 KB | Data Science & Analytics | Daily analytics aggregation, 7-day revenue forecasting via linear regression, busy-hour clustering, rule-based business insights | `scikit-learn`, `numpy`, `sqlalchemy` | **Active** |
| `cloud_server/app/services/assignment_service.py` | Python | 6.14 KB | Smart Scheduling | Multi-attribute scoring algorithm for optimal printer selection (capability match, queue depth, speed) | `sqlalchemy`, `app.database.models` | **Active** |
| `cloud_server/app/services/cleanup_service.py` | Python | 2.75 KB | Maintenance | Automated background cleanup of abandoned pending jobs (>2h) and orphaned upload files | `sqlalchemy`, `os`, `shutil` | **Active** |
| `cloud_server/app/services/dispatch_service.py` | Python | 3.15 KB | Dispatch Engine | Core job dispatcher that pulls the next paid job and broadcasts over WebSockets to local agent | `app.websocket.manager`, `sqlalchemy` | **Active** |
| `cloud_server/app/services/document_search_service.py` | Python | 3.14 KB | Document Search | In-memory text extraction and keyword matching for uploaded PDF/DOCX documents | `pypdf`, `python-docx` | **Active** |
| `cloud_server/app/services/job_service.py` | Python | 5.65 KB | Job Core Logic | Job lifecycle management, status transitions, estimation recalculation | `sqlalchemy`, `app.database.models` | **Active** |
| `cloud_server/app/services/ml_prediction_service.py` | Python | 10.50 KB | Machine Learning | Scikit-Learn linear regression model for print completion time estimation, daily revenue predictions | `sklearn.linear_model.LinearRegression`, `numpy` | **Active** |
| `cloud_server/app/services/page_counter.py` | Python | 3.02 KB | Document Analysis | Binary header and DOM inspection for exact page count extraction (PDF, DOCX, Images) | `pypdf`, `docx`, `PIL` | **Active** |
| `cloud_server/app/services/payment_service.py` | Python | 6.56 KB | Payment Logic | Razorpay API client integration, order signature validation, transaction recording | `razorpay`, `hmac`, `hashlib` | **Active** |
| `cloud_server/app/services/physical_printer_service.py` | Python | 467 B | Hardware Service | Helper bridge for physical printer status inquiries | `sqlalchemy` | **Active** |
| `cloud_server/app/services/preview_service.py` | Python | 2.80 KB | Thumbnail Generation | Decrypts encrypted document in RAM and generates PNG thumbnail previews via `pdf2image` | `pdf2image`, `PIL`, `app.core.crypto` | **Active** |
| `cloud_server/app/services/pricing_engine.py` | Python | 13.14 KB | Cost Calculation | Multi-tier price calculation engine taking into account page count, color mode, duplex, paper size, finishing services | `sqlalchemy`, `decimal` | **Active** |
| `cloud_server/app/services/print_prediction.py` | Python | 909 B | Heuristic Estimation | Quick mathematical heuristic estimation of print execution time | Built-in math | **Active** |
| `cloud_server/app/services/printer_capability_service.py` | Python | 5.42 KB | Hardware Matcher | Validates job requirements (e.g. A3 color duplex) against registered printer hardware features | `app.database.models` | **Active** |
| `cloud_server/app/services/printer_scheduler.py` | Python | 2.96 KB | Load Balancing | Evaluates printer workloads and balances incoming job assignments | `sqlalchemy` | **Active** |
| `cloud_server/app/services/queue_service.py` | Python | 6.73 KB | Queue Manager | Enqueues jobs, manages queue position integers, recalculates queue wait times | `sqlalchemy` | **Active** |
| `cloud_server/app/websocket/manager.py` | Python | 4.45 KB | WebSocket Hub | Maintains active WebSocket client connections for local print agents, tracks agent-to-shop mapping | `fastapi.WebSocket` | **Active** |
| `cloud_server/app/websocket/printer_socket.py` | Python | 2.77 KB | WebSocket Endpoint | WebSocket handler endpoint (`/ws/printer`) for live agent communication and telemetry stream | `fastapi`, `app.websocket.manager` | **Active** |

---

## 4. Frontend Templates & Static Assets (`cloud_server/templates/` & `static/`)

| Relative File Path | Type | Size | Module / Subsystem | Purpose & Responsibilities | Key Dependencies | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `cloud_server/templates/dashboard.html` | HTML5/Jinja2 | 117.66 KB | Owner Portal | Full-featured responsive owner dashboard: live queue table, printer management, price rules, finishing services, cash confirmation modal, analytics charts | Vanilla JS, Chart.js, HTML5 | **Active** |
| `cloud_server/templates/file_settings.html` | HTML5/Jinja2 | 25.76 KB | Customer UI | Per-file print configuration interface: page range selector, color/BW toggle, duplex switch, finishing service checkboxes, live cost preview | Vanilla JS, Voice API | **Active** |
| `cloud_server/templates/job_status.html` | HTML5/Jinja2 | 14.68 KB | Customer UI | Live job tracker page: shows queue position, payment status, completion progress bar, auto-refresh polling | Vanilla JS | **Active** |
| `cloud_server/templates/owner_login.html` | HTML5/Jinja2 | 23.02 KB | Authentication UI | Owner login and registration modal tab interface with client-side form validation and password strength meter | Vanilla JS, CSS3 | **Active** |
| `cloud_server/templates/price_summary.html` | HTML5/Jinja2 | 17.35 KB | Customer UI | Final checkout summary: itemized per-file cost, finishing costs, tax breakdown, Razorpay online checkout button, cash payment button | Razorpay Checkout JS | **Active** |
| `cloud_server/templates/receipt.html` | HTML5/Jinja2 | 10.34 KB | Customer / Shop | Digital thermal-style invoice receipt with print formatting, shop branding, breakdown, and transaction ID | CSS print media | **Active** |
| `cloud_server/templates/session.html` | HTML5/Jinja2 | 5.91 KB | QR Landing | QR landing session page: creates or retrieves active job session and redirects to upload view | Vanilla JS | **Active** |
| `cloud_server/templates/upload.html` | HTML5/Jinja2 | 7.83 KB | Customer UI | Drag-and-drop multi-file document upload interface with file validation, progress bars, and document list | HTML5 File API | **Active** |
| `cloud_server/static/style.css` | CSS3 | 18.43 KB | Styling | Complete unified design system: dark mode palette, glassmorphism cards, responsive grids, buttons, badges | CSS3 variables | **Active** |
| `cloud_server/static/js/voice_search.js` | JavaScript | 9.86 KB | AI Voice Assistant | Web Speech API integration for natural language voice configuration of print settings (e.g. "print 3 copies in color duplex") | Web Speech API | **Active** |

---

## 5. Local Print Agent (`PRINT_AGENT/`)

| Relative File Path | Type | Size | Module / Subsystem | Purpose & Responsibilities | Key Dependencies | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PRINT_AGENT/agent.py` | Python | 3.85 KB | Agent Daemon | Main agent daemon entry point: discovers printers, establishes WebSocket link, handles incoming job events, coordinates print execution | `websockets`, `asyncio`, `PRINT_AGENT.printers.*` | **Active / Edge Entry Point** |
| `PRINT_AGENT/core/auth.py` | Python | 4.95 KB | Agent Auth | Handles agent registration with cloud server, authentication headers, API token caching | `requests`, `PRINT_AGENT.core.config` | **Active** |
| `PRINT_AGENT/core/config.py` | Python | 1.77 KB | Agent Config | Loads environment variables (`CLOUD_API_URL`, `AGENT_ID`, `SHOP_ID`, `DOWNLOAD_FOLDER`) | `dotenv`, `os` | **Active** |
| `PRINT_AGENT/core/constants.py` | Python | 1.61 KB | Agent Constants | Defines hardware status codes, message types, paper sizes, and error enumerations | Built-in | **Active** |
| `PRINT_AGENT/core/logger.py` | Python | 1.17 KB | Agent Logging | Rotating file logger for local agent diagnostic logs (`PRINT_AGENT/logs/agent.log`) | `logging.handlers.RotatingFileHandler` | **Active** |
| `PRINT_AGENT/printers/discovery.py` | Python | 2.16 KB | Win32 Discovery | Discovers installed Windows printers using `win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)` | `win32print` | **Active** |
| `PRINT_AGENT/printers/capabilities.py` | Python | 11.01 KB | Capability Detector | Queries Win32 DeviceCapabilities (`DC_BINS`, `DC_PAPERS`, `DC_DUPLEX`, `DC_COLOR`, `DC_RESOLUTIONS`) | `win32print`, `ctypes` | **Active** |
| `PRINT_AGENT/printers/devmode.py` | Python | 7.01 KB | Win32 DevMode | Modifies Windows printer DevMode structure for exact duplex (DM_DUPLEX), color (DM_COLOR), paper size, orientation | `win32print`, `ctypes` | **Active** |
| `PRINT_AGENT/printers/executor.py` | Python | 9.65 KB | Print Executor | Standard print execution engine using Win32 API and ShellExecute / SumatraPDF silent printing CLI | `subprocess`, `win32api`, `win32print` | **Active** |
| `PRINT_AGENT/printers/advanced_executor.py` | Python | 10.09 KB | Advanced Executor | High-precision print execution engine with DevMode lock, page range parsing, and spooler verification | `win32print`, `subprocess` | **Active** |
| `PRINT_AGENT/printers/manager.py` | Python | 10.26 KB | Hardware Manager | Aggregates discovered printers, monitors availability, selects target printer matching job specs | `win32print` | **Active** |
| `PRINT_AGENT/printers/print_monitor.py` | Python | 282 B | Spooler Monitor | Legacy spooler helper module | Built-in | **Active** |
| `PRINT_AGENT/printers/print_monitors.py` | Python | 2.33 KB | Spooler Telemetry | Win32 print spooler job status polling (monitors `JOB_STATUS_PRINTING`, `JOB_STATUS_ERROR`, `JOB_STATUS_DELETING`) | `win32print` | **Active** |
| `PRINT_AGENT/services/downloader.py` | Python | 4.36 KB | Secure Downloader | Authenticated streaming downloader that fetches encrypted file from cloud API, decrypts payload in memory, writes to temporary local path | `requests`, `app.core.crypto` | **Active** |
| `PRINT_AGENT/services/file_validator.py` | Python | 1.60 KB | Local Validator | Verifies downloaded file integrity via magic bytes and size limits before sending to spooler | Python built-ins | **Active** |
| `PRINT_AGENT/services/job_handler.py` | Python | 5.67 KB | Agent Job Pipeline | Coordinates download, validation, printing execution, and status callback for a single print job | `PRINT_AGENT.services.*` | **Active** |
| `PRINT_AGENT/services/printer_availability.py` | Python | 5.60 KB | Availability Monitor | Periodically checks printer online status and hardware error flags (paper out, door open, offline) | `win32print` | **Active** |
| `PRINT_AGENT/services/status_reporter.py` | Python | 3.77 KB | Status Reporter | Sends REST and WebSocket status updates back to cloud server (`PRINTING`, `COMPLETED`, `FAILED`) | `requests`, `websockets` | **Active** |
| `PRINT_AGENT/services/cleanup.py` | Python | 1.45 KB | Secure Shredder | Multi-pass DoD compliant secure file shredding and deletion of downloaded temporary print files | `os`, `random` | **Active** |
| `PRINT_AGENT/websocket/client.py` | Python | 5.17 KB | Agent WS Client | Reconnecting WebSocket client that handles bidirectional message exchange with cloud `/ws/printer` | `websockets`, `asyncio`, `json` | **Active** |
| `PRINT_AGENT/tools/SumatraPDF.exe` | Binary / Executable | 19.35 MB | PDF Silent Print Tool | Lightweight, standalone PDF reader used for headless, silent, scriptable PDF printing on Windows | External tool | **Active Executable Asset** |
| `PRINT_AGENT/tools/SumatraPDF-settings.txt` | Configuration | 2.20 KB | PDF Tool Settings | Default preferences for SumatraPDF CLI execution | SumatraPDF config | **Active** |

---

## 6. Test Suite & Quality Assurance (`tests/`)

| Relative File Path | Type | Size | Test Count | Key Test Targets Covered | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tests/test_api_endpoints.py` | Python | 8.13 KB | 13 Tests | Owner registration, login, JWT verification, QR scanning, upload session, job creation, pricing endpoints | **Passed (63/63 Suite)** |
| `tests/test_core_system.py` | Python | 9.57 KB | 8 Tests | End-to-end database transactions, multi-file upload, page count calculation, rule-based pricing | **Passed (63/63 Suite)** |
| `tests/test_e2e_pipeline.py` | Python | 6.13 KB | 3 Tests | Full lifecycle: Owner -> QR -> Upload -> Pricing -> Payment Verification -> Queue -> Dispatch | **Passed (63/63 Suite)** |
| `tests/test_finishing_services.py` | Python | 20.82 KB | 13 Tests | Finishing service CRUD, per-file and per-job service attachment, pricing calculations, operator completion | **Passed (63/63 Suite)** |
| `tests/test_frontend_app_routes.py` | Python | 8.50 KB | 14 Tests | Jinja2 template rendering for upload, settings, summary, tracker, login, and dashboard pages | **Passed (63/63 Suite)** |
| `tests/test_preview_receipt_voice_printer.py` | Python | 21.04 KB | 11 Tests | PDF preview generation, digital receipt view/download, voice command parser, offline printer payment gating | **Passed (63/63 Suite)** |
| `tests/test_print_agent.py` | Python | 1.27 KB | 3 Tests | Print agent configuration loading, file validator logic, graceful printer discovery fallback | **Passed (63/63 Suite)** |
| `tests/test_security.py` | Python | 12.57 KB | 17 Tests | AES-256-GCM crypto envelope, DB compromise simulation, storage compromise simulation, IDOR multi-tenant isolation, path traversal sanitization, magic bytes spoofing check | **Passed (63/63 Suite)** |

---

## 7. Migration Scripts & Root Deployment Files

| Relative File Path | Type | Size | Purpose | Key Content |
| :--- | :--- | :--- | :--- | :--- |
| `Procfile` | Configuration | 70 B | Render / Heroku process definition | `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir cloud_server` |
| `render.yaml` | YAML | 682 B | Infrastructure-as-Code for Render deployment | Web service definition, Python environment, environment variable mappings |
| `requirements.txt` | Dependencies | 846 B | Root Python package dependencies | `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `cryptography`, `razorpay`, `pypdf`, `scikit-learn` |
| `runtime.txt` | Configuration | 14 B | Python runtime specification | `python-3.11.8` |
| `cloud_server/requirements.txt` | Dependencies | 835 B | Cloud server specific Python packages | Synchronized with root `requirements.txt` |
| `PRINT_AGENT/requirements.txt` | Dependencies | 251 B | Windows Print Agent dependencies | `pywin32`, `websockets`, `requests`, `python-dotenv`, `cryptography` |
| `cloud_server/add_pricing_basis_column.py` | Python Script | 90 lines | Database schema migration helper | Adds `pricing_basis` column to `shop_settings` table |
| `cloud_server/add_a4_pricing_rules.py` | Python Script | 72 lines | Database seeding script | Seeds standard A4/A3 pricing rules for shops |
| `cloud_server/add_ai_column.py` | Python Script | 23 lines | Database schema migration helper | Adds AI analytics and anomaly detection columns |
| `cloud_server/add_printer_columns.py` | Python Script | 58 lines | Database schema migration helper | Adds hardware capability columns to `printers` table |
| `cloud_server/add_qr_columns.py` | Python Script | 24 lines | Database schema migration helper | Adds `qr_token` and `qr_path` columns to `shop_owners` table |
