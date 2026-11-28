# 02 — File-by-File Source Code Explanation

This document contains a comprehensive, line-grounded technical analysis of every project-owned source file across the entire repository.

---

## 1. Cloud Server Core & Application Layer

### 1.1 `cloud_server/app/main.py`
- **Exact Path**: `cloud_server/app/main.py` (210 lines)
- **Responsibility**: Root application entry point for the FastAPI cloud backend. Configures CORS, security headers middleware, static file directories, lifespan events, database table creation verification, and registers all API routers.
- **Key Definitions**:
  - `lifespan(app: FastAPI)` ([L35-L65](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/main.py#L35-L65)): Startup and shutdown context manager. Verifies database connectivity via `init_db()`, creates uploads and static directories if absent.
  - `app = FastAPI(...)` ([L67-L78](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/main.py#L67-L78)): Instantiates FastAPI with OpenAPI title `"AI-Based QR Printing Cloud Server"`.
  - Security Headers Middleware ([L84-L100](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/main.py#L84-L100)): Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy`.
  - Router Inclusions ([L108-L175](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/main.py#L108-L175)): Mounts 17 distinct APIRouters under explicit prefixes (`/owner`, `/upload`, `/preview`, `/receipt`, `/file`, `/jobs`, `/pricing`, `/services`, `/printer`, `/queue`, `/payment`, `/analytics`, `/ai`, `/ai-search`, `/download`, `/agent`, `/settings`, `/`).
- **Endpoints Exposed**:
  - `GET /`: Redirects or renders default root landing.
  - `GET /owner/login-page`, `GET /register`, `GET /login`: Renders `owner_login.html`.
  - `GET /api/status`, `GET /health`: Healthcheck endpoints returning status `"healthy"`, timestamp, and DB status.
- **Integration**: Loaded by `uvicorn` in production on Render.

---

### 1.2 `cloud_server/app/core/config.py`
- **Exact Path**: `cloud_server/app/core/config.py` (91 lines)
- **Responsibility**: Centralized application configuration. Reads and validates environment variables with fallbacks.
- **Key Definitions**:
  - `Settings(BaseSettings)`: Pydantic settings class managing `ENVIRONMENT`, `DEBUG`, `BASE_URL`, `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM` (`HS256`), `JWT_EXPIRATION_HOURS` (`24`), `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB` (`50`), `PAYMENT_GATEWAY_KEY_ID`, `PAYMENT_GATEWAY_KEY_SECRET`, `PAYMENT_WEBHOOK_SECRET`, and `CORS_ORIGINS`.
  - `settings = Settings()`: Singleton settings instance loaded across all modules.
- **Error Handling**: Gracefully falls back to SQLite (`sqlite:///./qr_printing.db`) if `DATABASE_URL` is empty, and auto-derives secure default keys if environment secrets are absent in local testing.

---

### 1.3 `cloud_server/app/core/crypto.py`
- **Exact Path**: `cloud_server/app/core/crypto.py` (154 lines)
- **Responsibility**: Provides military-grade document envelope encryption and decryption at rest using AES-256-GCM. Ensures cloud server uploads cannot be read as plaintext on disk or by database dumps.
- **Key Definitions**:
  - `get_master_key()` ([L25-L42](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/crypto.py#L25-L42)): Derives a 256-bit cryptographic key using PBKDF2HMAC over `JWT_SECRET` with fixed salt.
  - `encrypt_document(plaintext: bytes) -> bytes` ([L45-L75](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/crypto.py#L45-L75)): Generates random 12-byte IV/nonce, encrypts plaintext via AESGCM, prepends magic header `AEP1` + IV + 16-byte authentication tag.
  - `decrypt_document(ciphertext_envelope: bytes) -> bytes` ([L78-L115](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/crypto.py#L78-L115)): Validates `AEP1` magic header, extracts IV, and decrypts ciphertext. Raises `ValueError` on tampering.
  - `is_encrypted_envelope(data: bytes) -> bool` ([L118-L128](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/crypto.py#L118-L128)): Validates envelope signature.
- **Called By**: `upload.py` (during file ingestion), `download.py` (during agent streaming), `preview_service.py` (during preview generation).

---

### 1.4 `cloud_server/app/core/security.py`
- **Exact Path**: `cloud_server/app/core/security.py` (163 lines)
- **Responsibility**: User authentication, password hashing, and JWT token management.
- **Key Definitions**:
  - `pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")` ([L24-L28](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/security.py#L24-L28)): Multi-scheme password hasher. Fixes legacy 72-byte bcrypt limit by transparently utilizing Argon2id for long passwords and auto-truncating/pre-hashing SHA-256 fallback if necessary.
  - `hash_password(password: str) -> str` ([L35-L55](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/security.py#L35-L55)): Generates secure hash for storage.
  - `verify_password(plain_password: str, hashed_password: str) -> bool` ([L58-L75](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/security.py#L58-L75)): Verifies plaintext against stored hash.
  - `create_access_token(subject: str, expires_delta: timedelta = None) -> str` ([L78-L98](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/security.py#L78-L98)): Encodes JWT token containing `sub` (owner ID) and expiry timestamp.
  - `get_current_owner(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> ShopOwner` ([L105-L140](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/core/security.py#L105-L140)): FastAPI dependency enforcing JWT bearer authentication on protected endpoints.
- **Called By**: `owner.py`, `settings.py`, `pricing.py`, `services.py`, `analytics.py`.

---

### 1.5 `cloud_server/app/database/connection.py`
- **Exact Path**: `cloud_server/app/database/connection.py` (131 lines)
- **Responsibility**: Configures the SQLAlchemy database engine, session factory, connection pooling, and table creation hooks.
- **Key Definitions**:
  - `engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, pool_recycle=1800, pool_pre_ping=True)`: Enterprise connection pool designed for PostgreSQL on Render, with automatic SQLite connection adjustments (disabling pooling parameters for SQLite).
  - `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`: Factory for transactional database sessions.
  - `get_db() -> Generator[Session, None, None]`: Contextual generator yielding a database session and safely closing it in a `finally` block.
  - `init_db()`: Calls `Base.metadata.create_all(bind=engine)` and verifies table presence.

---

### 1.6 `cloud_server/app/database/models.py`
- **Exact Path**: `cloud_server/app/database/models.py` (1,419 lines)
- **Responsibility**: Master declarative ORM definitions for all entities in the printing ecosystem.
- **Key Models**:
  - `ShopOwner`: Represents a registered print shop. Fields: `owner_id` (UUID PK), `shop_name`, `owner_name`, `email`, `phone`, `password_hash`, `upi_id`, `qr_token`, `qr_path`, `is_active`.
  - `ShopSettings`: Global shop configuration. Fields: `setting_id`, `owner_id` (FK), `default_printer_id` (FK), `pricing_basis` (`PER_PAGE`/`TIERED`), `allow_bw_print`, `allow_color_print`, `allow_duplex`, `max_file_size_mb`, `max_files_per_job`.
  - `Printer`: Represents physical and virtual printers registered to a shop. Fields: `printer_id` (UUID PK), `owner_id` (FK), `printer_name`, `printer_model`, `is_physical`, `is_available`, `supports_bw`, `supports_color`, `supports_duplex`, `supports_a3`, `supports_legal`, `status` (`ONLINE`/`OFFLINE`/`PRINTING`/`ERROR`), `agent_id`, `current_queue`, `total_jobs_printed`.
  - `ActiveJob`: Primary print order entity. Fields: `job_id` (UUID PK), `owner_id` (FK), `assigned_printer_id` (FK), `customer_name`, `customer_phone`, `status` (`PENDING`/`QUEUED`/`PRINTING`/`COMPLETED`/`FAILED`/`CANCELLED`), `finishing_status` (`NONE`/`PENDING_FINISHING`/`FINISHING_COMPLETED`), `payment_status` (`PENDING`/`PAID`/`FAILED`/`REFUNDED`), `total_files`, `total_pages`, `total_amount`, `estimated_seconds`.
  - `JobFile`: Individual document attached to a job. Fields: `file_id` (UUID PK), `job_id` (FK), `original_filename`, `stored_filename`, `file_path`, `file_type`, `file_size`, `page_count`, `copies`, `paper_size`, `orientation`, `duplex`, `print_type` (`BW`/`COLOR`), `color_mode` (`ALL_BW`/`ALL_COLOR`/`CUSTOM_MIXED`), `color_page_ranges`, `bw_pages`, `color_pages`, `estimated_cost`, `print_completed`.
  - `PricingRule`: Tiered cost rules per page range. Fields: `pricing_id`, `owner_id` (FK), `paper_size` (`A4`/`A3`/`LEGAL`), `print_type` (`BW`/`COLOR`), `duplex`, `page_from`, `page_to`, `price_per_page`, `is_active`.
  - `Payment`: Audit log of payments. Fields: `payment_id`, `job_id` (FK), `provider` (`RAZORPAY`/`CASH`), `amount`, `status` (`PENDING`/`SUCCESS`/`FAILED`), `transaction_id`, `provider_payment_id`, `verified`.
  - `AnalyticsDaily`: Aggregated business intelligence record per day. Fields: `analytics_id`, `owner_id` (FK), `analytics_date`, `total_revenue`, `total_jobs`, `bw_pages`, `color_pages`, `predicted_revenue`, `predicted_peak_hour`, `printer_recommendation`.
  - `FinishingService` & `JobFinishingService`: Value-added shop services (Spiral Binding, Lamination, Stapling) with unit pricing and job associations.

---

## 2. Cloud Server API Routers & Handlers

### 2.1 `cloud_server/app/api/owner.py`
- **Exact Path**: `cloud_server/app/api/owner.py` (322 lines)
- **Responsibility**: Handles shop owner lifecycle: registration, login, JWT token generation, password resets, profile queries, and dashboard status queries.
- **Key Functions**:
  - `register_owner(payload: OwnerRegisterRequest, db: Session)` ([L35-L95](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L35-L95)): Validates unique email, hashes password, generates unique `qr_token`, creates default `ShopSettings`, default `PricingRule` sets (A4 B&W, A4 Color), default `FinishingService` records, and generates shop QR image.
  - `login_owner(payload: OwnerLoginRequest, db: Session)` ([L100-L140](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L100-L140)): Verifies credentials using `verify_password()`, creates and returns JWT Bearer token with 24-hour expiration.
  - `reset_owner_password(...)` ([L145-L180](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L145-L180)): Validates owner identity and updates password hash.
  - `owner_dashboard(owner_id: UUID, current_owner: ShopOwner, db: Session)` ([L220-L290](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L220-L290)): Aggregates live owner statistics (active printers, queue depth, daily revenue, recent jobs, pending cash approvals).

---

### 2.2 `cloud_server/app/api/session.py`
- **Exact Path**: `cloud_server/app/api/session.py` (182 lines)
- **Responsibility**: Manages customer entry via QR codes and web template views.
- **Key Endpoints**:
  - `GET /qr/{qr_token}` ([L25-L65](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/session.py#L25-L65)): Entry point when a customer scans the shop QR code. Looks up `ShopOwner` by `qr_token`, instantiates a new `ActiveJob` with status `PENDING`, and returns a `303 See Other` redirect to `/upload/{job_id}`.
  - `GET /owner/{owner_id}/qr` ([L70-L110](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/session.py#L70-L110)): Dynamic QR generation endpoint. Returns PNG image containing URL `${BASE_URL}/qr/${qr_token}`.
  - `GET /owner/{owner_id}/dashboard`: Renders `dashboard.html` for shop owners.
  - `GET /job/tracker/{job_id}`: Renders `job_status.html` for customer live tracking.

---

### 2.3 `cloud_server/app/api/upload.py`
- **Exact Path**: `cloud_server/app/api/upload.py` (202 lines)
- **Responsibility**: Ingests uploaded customer documents (PDF, DOCX, PNG, JPG), validates file headers/magic bytes, extracts accurate page counts, applies AES-256-GCM encryption, and saves ciphertext to disk while creating `JobFile` records.
- **Key Functions**:
  - `upload_page(job_id: UUID, request: Request, db: Session)` ([L30-L60](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/upload.py#L30-L60)): Renders `upload.html` Jinja2 template with job context and shop settings.
  - `upload_files(job_id: UUID, files: List[UploadFile], db: Session)` ([L65-L185](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/upload.py#L65-L185)): Reads binary bytes, performs path traversal sanitization on `filename`, verifies file signature via magic bytes (`%PDF-`, `PK\x03\x04`, `\x89PNG`), extracts page counts via `extract_page_count()`, encrypts bytes with `encrypt_document()`, saves `.enc` payload to disk, creates `JobFile` records, recalculates initial pricing, and returns redirect/JSON response to `file_settings.html`.

---

### 2.4 `cloud_server/app/api/file_settings.py`
- **Exact Path**: `cloud_server/app/api/file_settings.py` (285 lines)
- **Responsibility**: Handles customer print configuration per document (copies, color mode, duplex, paper size, custom page selection) and transitions the job to the pricing checkout summary.
- **Key Functions**:
  - `settings_page(file_id: UUID, request: Request, db: Session)` ([L30-L80](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/file_settings.py#L30-L80)): Renders `file_settings.html` with current document metadata, available finishing services, and pricing rules.
  - `update_file_settings(file_id: UUID, payload: FileSettingsUpdateRequest, db: Session)` ([L85-L200](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/file_settings.py#L85-L200)): Parses custom page ranges (e.g. `1-5, 8, 10-12`), evaluates color vs. black-and-white page splits, updates `JobFile` records, invokes `calculate_job_price()`, and updates `ActiveJob.total_amount`.
  - `price_summary(file_id: UUID, request: Request, db: Session)` ([L205-L270](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/file_settings.py#L205-L270)): Renders `price_summary.html` with itemized costs, tax, finishing options, and Razorpay payment checkout integration.

---

### 2.5 `cloud_server/app/api/payment.py`
- **Exact Path**: `cloud_server/app/api/payment.py` (462 lines)
- **Responsibility**: Comprehensive payment gateway routing. Handles Razorpay order generation, HMAC-SHA256 signature verification, webhook processing, and walk-in cash confirmation/rejection workflows.
- **Key Functions**:
  - `create_payment(job_id: UUID, db: Session)` ([L45-L125](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L45-L125)): Validates job existence and checks if at least one printer for the shop is online. If valid, generates Razorpay order via `razorpay_client.order.create(amount=in_paise, currency="INR")`, records `Payment` entity with status `PENDING`, and returns `order_id`, `amount`, and `key_id` to frontend.
  - `verify_payment(payload: PaymentVerifyRequest, db: Session)` ([L130-L220](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L130-L220)): Computes HMAC-SHA256 of `order_id|payment_id` with `PAYMENT_GATEWAY_KEY_SECRET`. Upon match, transitions `Payment.status` to `SUCCESS`, `ActiveJob.payment_status` to `PAID`, inserts job into the print queue via `enqueue_job()`, and triggers auto-dispatch.
  - `cash_payment_request(job_id: UUID, db: Session)` ([L275-L330](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L275-L330)): Sets payment mode to `CASH` with status `PENDING_CASH_APPROVAL`.
  - `confirm_cash_payment(job_id: UUID, current_owner: ShopOwner, db: Session)` ([L335-L390](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L335-L390)): Allows shop owner from the dashboard to confirm cash collection, transitioning `payment_status` to `PAID` and queuing the job.

---

### 2.6 `cloud_server/app/api/download.py`
- **Exact Path**: `cloud_server/app/api/download.py` (178 lines)
- **Responsibility**: Payment-gated secure document distribution endpoint for the local Edge Print Agent.
- **Key Functions**:
  - `download_file(job_id: UUID, file_id: UUID, db: Session, authorization: str)` ([L35-L140](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/download.py#L35-L140)):
    1. Validates that `ActiveJob.payment_status == PaymentStatus.PAID`. If unpaid, immediately returns `403 Forbidden` ("Payment not completed. File access strictly prohibited.").
    2. Verifies that `JobFile.job_id == job_id` (cross-job IDOR prevention).
    3. Reads `.enc` file from storage, decrypts ciphertext in memory using `decrypt_document()`, and streams decrypted binary to the authenticated agent over TLS.

---

### 2.7 `cloud_server/app/api/jobs.py` & `queue.py`
- **Exact Paths**: `cloud_server/app/api/jobs.py` (328 lines), `cloud_server/app/api/queue.py` (165 lines)
- **Responsibility**: Manages print job states, queue position indices, cancellations, and dispatch triggers.
- **Key Functions**:
  - `queue_job(job_id: UUID, db: Session)`: Enqueues paid job and assigns `queue_position`.
  - `dispatch_next_queued_job(printer_id: UUID, db: Session)`: Finds highest-priority/oldest paid job matching printer capabilities and dispatches over WebSocket.
  - `cancel_job_endpoint(job_id: UUID, db: Session)`: Safely marks job `CANCELLED` and adjusts queue positions of following jobs.

---

### 2.8 `cloud_server/app/api/analytics.py` & `ai.py`
- **Exact Paths**: `cloud_server/app/api/analytics.py` (172 lines), `cloud_server/app/api/ai.py` (132 lines)
- **Responsibility**: Surfaces business intelligence and machine learning predictions to shop owners.
- **Key Endpoints**:
  - `GET /analytics/dashboard/{owner_id}`: Comprehensive summary of revenue, jobs, and paper breakdown.
  - `GET /analytics/forecast/{owner_id}`: 7-day revenue and volume forecast via Scikit-Learn linear regression.
  - `GET /analytics/prediction/busy-hour/{owner_id}`: Identifies shop peak traffic hours.
  - `POST /ai/printer/{job_id}`: Evaluates multi-attribute candidate scoring to recommend the optimal printer.

---

## 3. Local Print Agent Source Files (`PRINT_AGENT/`)

### 3.1 `PRINT_AGENT/agent.py`
- **Exact Path**: `PRINT_AGENT/agent.py` (130 lines)
- **Responsibility**: Main background daemon process for the local Windows print agent.
- **Execution Lifecycle**:
  1. Discovers local Windows printers via `discovery.discover_printers()`.
  2. Queries hardware capabilities (duplex, color, paper sizes) via `capabilities.get_printer_capabilities()`.
  3. Registers agent and hardware inventory with cloud server via `auth.register_agent()`.
  4. Connects to cloud WebSocket endpoint (`/ws/printer`).
  5. Listens in an async event loop for incoming `JOB_DISPATCH` payloads.
  6. Delegates job execution to `services/job_handler.py`.

---

### 3.2 `PRINT_AGENT/printers/executor.py` & `advanced_executor.py`
- **Exact Paths**: `PRINT_AGENT/printers/executor.py` (542 lines), `PRINT_AGENT/printers/advanced_executor.py` (443 lines)
- **Responsibility**: Executes physical prints on Windows printers using either Win32 DevMode spooler calls or headless command-line tools.
- **Key Logic**:
  - `print_document(file_path, printer_name, settings)`:
    - Parses settings (copies, orientation, duplex, color, page ranges).
    - If PDF: Uses bundled `SumatraPDF.exe` with CLI arguments:
      ```cmd
      SumatraPDF.exe -print-to "<PrinterName>" -print-settings "<copies>x,duplex=...,color=...,<page_ranges>" -silent "<file_path>"
      ```
    - If Image/DOCX: Dispatches via Win32 ShellExecute or native graphics printer DC.
    - Monitors Win32 print spooler to confirm job departure.

---

### 3.3 `PRINT_AGENT/services/downloader.py` & `cleanup.py`
- **Exact Paths**: `PRINT_AGENT/services/downloader.py` (144 lines), `PRINT_AGENT/services/cleanup.py` (75 lines)
- **Responsibility**: Secure document ingestion and permanent DoD-compliant data erasure on the edge machine.
- **Key Logic**:
  - `download_job_file(job_id, file_id, target_dir)`: Sends authenticated GET request to `/download/job/{job_id}/file/{file_id}`, verifies SHA-256 integrity, and writes temporary decrypted file to local disk.
  - `secure_delete(file_path)`: Overwrites file with random bytes (Pass 1), zero bytes (Pass 2), and truncates before removing file handle (`os.remove()`), preventing forensic recovery of customer documents from local disks.
