# AI-Based QR Printing System — Complete Project Analysis

> **ANALYSIS-ONLY REPORT** — No files were modified, created, deleted, or moved.

---

## A. Complete Project Structure

```
AI-based-QR-printing-System/
├── .gitignore                          ← root ignore rules
├── README.md
├── combined_project.txt                ← developer-generated dump (ignored)
├── aab.txt                             ← untracked/ignored test file
├── test_print.pdf / test_print.docx    ← ignored test files
├── downloads/                          ← root-level (unused at runtime?)
├── logs/                               ← root-level (unused at runtime?)
│
├── cloud_server/                       ← FastAPI Cloud Server
│   ├── .env                            ← ⚠️ COMMITTED SECRET (DB credentials)
│   ├── .gitignore                      ← only covers .env locally in this folder
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── add_*.py                        ← one-off DB migration scripts
│   ├── test_db.py
│   ├── uploads/                        ← uploaded user files (gitignored)
│   ├── storage/                        ← (empty folder, purpose unclear)
│   ├── static/
│   │   ├── *.png                       ← generated QR images
│   │   └── js/voice_search.js          ← (empty file)
│   ├── templates/
│   │   ├── session.html
│   │   ├── upload.html
│   │   ├── file_settings.html
│   │   └── price_summary.html
│   └── app/
│       ├── main.py                     ← FastAPI app entry point
│       ├── core/
│       │   ├── config.py               ← minimal (BASE_URL only)
│       │   ├── job_store.py            ← in-memory list (unused)
│       │   └── cleanup.py              ← (empty file)
│       ├── utils/
│       │   └── logger.py               ← (empty file)
│       ├── database/
│       │   ├── connection.py           ← SQLAlchemy engine + get_db()
│       │   ├── models.py               ← all ORM models
│       │   ├── models.py.backup        ← old backup
│       │   └── models.py.backup_qr    ← old backup
│       ├── schemas/
│       │   ├── job.py
│       │   ├── printer.py
│       │   ├── payment.py
│       │   ├── pricing.py
│       │   ├── settings.py
│       │   ├── owner.py
│       │   ├── queue.py
│       │   ├── file_settings.py
│       │   └── analytics.py
│       ├── services/
│       │   ├── assignment_service.py   ← AI printer scoring & selection
│       │   ├── print_prediction.py     ← ETA calculation
│       │   ├── queue_service.py        ← queue management
│       │   ├── job_service.py          ← job lifecycle
│       │   ├── pricing_engine.py       ← cost calculation
│       │   ├── dispatch_service.py     ← WebSocket dispatch to agent
│       │   ├── page_counter.py         ← PDF/DOCX/image page counting
│       │   ├── analytics_service.py    ← dashboard analytics + AI predictions
│       │   ├── physical_printer_service.py ← Windows printer check (cloud side)
│       │   ├── printer_capability_service.py ← PrintCapabilitiesXML parser
│       │   ├── printer_scheduler.py    ← in-DB job scheduling
│       │   ├── cleanup_service.py      ← delete uploaded files after print
│       │   ├── document_search_service.py ← keyword-in-PDF search
│       │   ├── preview_service.py      ← file preview
│       │   └── payment_service.py      ← ⚠️ COMPLETELY EMPTY (0 bytes)
│       ├── api/
│       │   ├── owner.py
│       │   ├── session.py              ← QR generation + customer entry point
│       │   ├── upload.py
│       │   ├── file_settings.py
│       │   ├── jobs.py
│       │   ├── pricing.py
│       │   ├── payment.py
│       │   ├── printer.py
│       │   ├── queue.py
│       │   ├── agent.py
│       │   ├── ai.py
│       │   ├── ai_document_search.py
│       │   ├── download.py
│       │   ├── analytics.py
│       │   ├── settings.py
│       │   └── status.py
│       └── websocket/
│           ├── manager.py              ← in-memory agent registry
│           └── printer_socket.py      ← WebSocket endpoint /ws/printer
│
└── PRINT_AGENT/                        ← Windows Print Agent
    ├── .env                            ← ⚠️ Contains real SHOP_ID UUID
    ├── .env.example
    ├── requirements.txt
    ├── agent.py                        ← entry point
    ├── core/
    │   ├── config.py                   ← env-based config
    │   ├── constants.py                ← DUPLICATE of config.py (same code)
    │   └── logger.py                   ← file + console logging
    ├── websocket/
    │   ├── client.py                   ← WebSocket client (MODIFIED locally)
    │   └── client.py.backup            ← old version
    ├── services/
    │   ├── job_handler.py              ← orchestrates download→print→report
    │   ├── downloader.py               ← HTTP file download with retry
    │   ├── file_validator.py           ← extension check only
    │   ├── status_reporter.py          ← HTTP PUT to cloud job status
    │   ├── printer_availability.py     ← PowerShell USB/WSD check
    │   └── cleanup.py                  ← secure file wipe
    ├── printers/
    │   ├── manager.py                  ← discover + register + sync printers
    │   ├── discovery.py                ← win32print enumeration
    │   ├── capabilities.py             ← win32print capability detection
    │   ├── devmode.py                  ← Windows DEVMODE configuration
    │   ├── advanced_executor.py        ← PRIMARY executor (SumatraPDF + DEVMODE)
    │   ├── executor.py                 ← OLD executor (win32com Word, os.startfile)
    │   ├── print_monitor.py            ← re-export shim (backward compat)
    │   ├── print_monitors.py           ← actual Windows print queue monitor
    │   └── advanced_executor.py.backup ← old backup
    └── tools/
        ├── SumatraPDF.exe              ← bundled PDF printer
        └── SumatraPDF-settings.txt
```

---

## B. File-by-File Explanation

### Cloud Server

#### `app/main.py`
- **Purpose**: FastAPI application entry point.  
- **Key facts**: Registers 15 API routers and the WebSocket router. Mounts `/static`. CORS is `allow_origins=["*"]` — completely open.
- **Endpoints**: `GET /` (root info), `GET /health`.
- **Dependencies**: All API modules + websocket/printer_socket.

---

#### `app/database/connection.py`
- **Purpose**: SQLAlchemy engine, session factory, and `get_db()` dependency.
- **Input**: `DATABASE_URL` from `.env`.
- **Key function**: `get_db()` — yields a session, closes on exit.
- **Database**: PostgreSQL (Neon serverless, `sslmode=require`).

---

#### `app/database/models.py` (1245 lines)
Defines **6 ORM tables** and **7 Python Enums**:

| Table | Primary Key | Key Fields |
|---|---|---|
| `shop_owners` | `owner_id` (UUID) | shop_name, email, phone, password_hash, upi_id, qr_token, qr_path |
| `shop_settings` | `setting_id` (UUID) | owner_id FK, currency, tax_percentage, pricing_basis, allow_* flags |
| `printers` | `printer_id` (UUID) | owner_id FK, agent_id, status, is_physical, is_available, supports_*, current_queue, total_jobs_printed |
| `active_jobs` | `job_id` (UUID) | owner_id FK, assigned_printer_id FK, status, payment_status, queue_position, subtotal, tax, total_amount |
| `job_files` | `file_id` (UUID) | job_id FK, file_path, page_count, copies, paper_size, print_type, duplex, page_ranges, estimated_cost |
| `payments` | `payment_id` (UUID) | job_id FK, provider, amount, status, transaction_id, verified |
| `analytics_daily` | `analytics_id` (UUID) | owner_id FK, analytics_date, totals, AI prediction fields |
| `pricing_rules` | `pricing_id` (UUID) | owner_id FK, paper_size, print_type, duplex, page_from, page_to, price_per_page |

> **Note**: `ActiveJob` has a commented-out `estimated_seconds` field (`# Estimated Printing Time` at line 578) — **the column definition is missing** but `queue_service.py` references `job.estimated_seconds` directly (runtime AttributeError risk).

**Enums**: `JobStatus`, `PaymentStatus`, `PrinterStatus`, `PrintType`, `PaperSize`, `Orientation`, `PaymentProvider`, `PaymentMethod`, `PricingBasis`.

---

#### `app/services/job_service.py`
- **Purpose**: Full job lifecycle management.
- **Key functions**:
  - `create_job(job, db)` — INSERT ActiveJob.
  - `prepare_job(job_id, db)` — updates summary, calculates priority, calculates cost. **Does NOT assign a printer.**
  - `assign_paid_job(job_id, db)` — runs after payment; calls `assign_printer()` then `add_job_to_queue()`.
  - `calculate_priority(job)` — simple heuristic: base = total_pages + bonuses for >100 pages, >5 files, >10 copies.
  - `mark_payment_success(job_id, db)` — sets `payment_status = PAID`.
  - `cancel_job / complete_job` — status updates.
- **Imports**: `pricing_engine`, `assignment_service`, `queue_service`.

---

#### `app/services/assignment_service.py` ← **AI Printer Selection**
*(See full algorithm description in Section D)*

---

#### `app/services/print_prediction.py` ← **ETA Engine**
- **Constants**: `BASE_SECONDS_PER_PAGE = 4`, `COLOR_MULTIPLIER = 1.35`, `DUPLEX_MULTIPLIER = 1.15`, `COPIES_SETUP_SECONDS = 3`.
- **`estimate_file_seconds(file, printer)`**: pages × copies × seconds_per_page + setup overhead. Color multiplies by 1.35, duplex by 1.15. High-volume printer (≥100 jobs) gets 10% speed bonus.
- **`estimate_printer_queue_seconds(printer, db)`**: sums existing QUEUED jobs' estimated times.
- **`predict_completion_seconds(job, printer, db)`**: queue_seconds + job_seconds = total ETA.

---

#### `app/services/pricing_engine.py`
- **`get_pricing_rule(job, file, db)`**: queries `pricing_rules` matching owner_id + paper_size + print_type + duplex + page_count within `page_from`..`page_to`.
- **`calculate_billable_units(file, pricing_basis)`**: PER_SIDE = page_count; PER_SHEET = ceil(pages/2) for duplex.
- **`calculate_file_cost(job, file, db)`**: billable_units × price_per_page × copies.
- **`calculate_job_cost(job_id, db)`**: sums all files, applies tax%, saves to job.

---

#### `app/services/queue_service.py`
- **`estimate_waiting_time(job)`**: `queue_position × 45` seconds (fixed constant).
- **`get_printer_load(printer)`**: LOW (≤2), MEDIUM (≤5), HIGH (>5) based on `current_queue`.
- **`get_ai_recommendation(job)`**: string message based on `job.estimated_seconds`.
- **`add_job_to_queue(job_id, db)`**: sets status=QUEUED, assigns position, updates printer.current_queue, calls `update_queue_predictions`.
- **`update_queue_predictions(printer_id, db)`**: rebuilds positions 1..n and sets `job.estimated_seconds = position × 45`.
- **`remove_job_from_queue / cancel_queue_job / complete_queue_job`**: self-explanatory.
- **`get_queue_dashboard(printer_id, db)`**: returns queue status dict.
> **Bug**: `queue_service.py` references `job.estimated_seconds` but `ActiveJob` model does **not** have this column defined (line 578 comment, no actual Column declaration).

---

#### `app/services/dispatch_service.py`
- **Purpose**: Sends a job to the correct Print Agent via WebSocket.
- **`dispatch_job_to_agent(job)`**: builds a JSON payload from `job` + `job.files[0]` and calls `send_job_to_shop(owner_id, payload)`.
- **⚠️ Critical Bug**: `download_url` is hard-coded as `"http://localhost:8000/download/job/{job.job_id}/file/{file.file_id}"`. This will **fail** if the cloud server is deployed anywhere other than localhost.
- **⚠️ Only dispatches `files[0]`**: Multi-file jobs only get the first file sent to the agent. The remaining files are silently ignored.

---

#### `app/services/page_counter.py`
- Counts pages using `pypdf` (PDF), `python-docx` (DOCX, character estimation), `PIL` (images = 1 page), text-to-chars (TXT).
- **Dependencies not in requirements.txt**: `pypdf`, `python-docx`, `passlib`, `sqlalchemy`, `psycopg2`, `python-dotenv`, `bcrypt`.

---

#### `app/services/payment_service.py`
- **⚠️ COMPLETELY EMPTY** — 0 bytes, 1 blank line. Nothing is imported from it in the codebase.

---

#### `app/services/physical_printer_service.py`
- **Purpose**: Cloud-side Windows printer availability check (runs PowerShell).
- **`check_printer_available(printer_name, printer_type)`**: queries `Get-Printer | ConvertTo-Json`, checks `WorkOffline`, routes USB printers to PnP check.
- **⚠️ Architecture Problem**: This runs on the **cloud server** machine. If the cloud server is Linux/Docker, PowerShell commands will fail silently (return `[]`). The actual printer is on the **agent** machine, not the cloud. `assignment_service.py` calls this during printer scoring, which would always return `False` on a Linux cloud.

---

#### `app/services/printer_capability_service.py`
- Runs `Get-PrintConfiguration` via PowerShell, parses `PrintCapabilitiesXML`.
- Same Linux/cloud problem as `physical_printer_service.py`.

---

#### `app/services/analytics_service.py`
- `get_dashboard_statistics` — counts jobs, revenue.
- `predict_revenue` — average completed job value × 30 (simple linear extrapolation).
- `predict_busy_hour` — most common hour of job creation (Counter).
- `get_ai_recommendation` — threshold-based string messages (>5 failed → "Investigate", >20 pending → "Add printer").

---

#### `app/services/printer_scheduler.py`
- `schedule_next_job(printer_id, db)` — finds next QUEUED job ordered by priority DESC, created_at ASC; sets PRINTING + marks printer BUSY. **Not wired into the main dispatch flow** — the main flow uses `dispatch_service.py` instead.
- `complete_job(job_id, db)` — calls `cleanup_job_files`.
- `fail_job(job_id, db)` — resets printer to ONLINE.

---

#### `app/websocket/manager.py`
- **In-memory dict**: `connected_agents: Dict[str, dict]` — keyed by `agent_id`.
- **`connect(websocket, agent_id, shop_id)`**: stores agent.
- **`disconnect(websocket)`**: removes by websocket reference.
- **`send_to_shop(shop_id, message)`**: routes to first agent matching `shop_id`.
- **`send_job_to_shop(shop_id, job)`**: wraps job in `{"type":"job","data":job}`.
- **⚠️ In-process only**: Agent registrations are lost on server restart. No Redis or persistent registry.

---

#### `app/websocket/printer_socket.py`
- **Endpoint**: `WS /ws/printer`
- **Protocol**: First message must be `{"type":"register","agent_id":"...","shop_id":"..."}`. Server sends `{"type":"registered"}` back. Subsequent messages: `heartbeat` → `heartbeat_ack`, `pong` → logged.
- **Gap**: The server WebSocket **receives no job-status messages from the agent** — status updates come via HTTP REST (PUT `/jobs/{id}/status`), not WebSocket.

---

#### `app/api/session.py` ← **Customer Entry Point**
- `GET /owner/{owner_id}/qr` — generates QR code PNG pointing to `/qr/{qr_token}`, saved to `static/`.
- `GET /qr/{qr_token}` — customer scans QR → creates new `ActiveJob` → redirects to `GET /upload/{job_id}`.

---

#### `app/api/upload.py`
- `GET /upload/{job_id}` — renders `upload.html`.
- `POST /upload/{job_id}` — saves files to `uploads/`, counts pages, creates `JobFile` records, updates job summary, broadcasts `FILES_UPLOADED` event over WebSocket.

---

#### `app/api/jobs.py`
- `POST /jobs/owner/{owner_id}` — creates new job.
- `GET /jobs/{job_id}` — get job details.
- `POST /jobs/{job_id}/prepare` — triggers pricing.
- `DELETE /jobs/{job_id}` — cancel.
- `PUT /jobs/{job_id}/complete` — mark complete.
- **`PUT /jobs/{job_id}/status`** ← **Called by PRINT_AGENT via HTTP** — updates status, timestamps, dispatches next queued job when COMPLETED.
- `GET /jobs/{job_id}/status` — customer polling endpoint.
- `POST /jobs/dispatch-next/{printer_id}` — manual test endpoint.

---

#### `app/api/payment.py`
- `POST /payment/create/{job_id}` — creates `Payment` record (PENDING, MANUAL/UPI).
- `GET /payment/{payment_id}` — status check.
- `POST /payment/callback/{payment_id}` — payment gateway callback; on success: marks PAID, calls `assign_paid_job`, dispatches to agent if queue_position == 1.
- `POST /payment/cash/{job_id}` — cash payment shortcut; immediately marks PAID and dispatches.

---

#### `app/api/download.py`
- `GET /download/job/{job_id}/file/{file_id}` — **called by Print Agent**; verifies payment_status == PAID, returns `FileResponse`.

---

#### `app/api/printer.py`
- Full CRUD for printers: register/update (upsert by agent_id + printer_name), list, get, update, delete, set default, status update.
- `PUT /printer/{printer_id}/status` ← called by `status_reporter.py` in the agent.

---

#### `app/api/agent.py`
- `POST /agent/register` — bulk-syncs printers for agent, calls `synchronize_printers` (PowerShell check — same Linux problem).
- `POST /agent/heartbeat` — updates last_seen, re-syncs.
- `GET /agent/status/{agent_id}` — reports per-agent printer status.
- **⚠️ Not called by the agent**: The agent's `websocket/client.py` does NOT call `/agent/register` or `/agent/heartbeat` — it uses only the WebSocket and `/printer/register` + `/jobs/{id}/status` HTTP endpoints.

---

### Frontend / Templates

| File | Purpose |
|---|---|
| `templates/session.html` | Shows owner QR code |
| `templates/upload.html` | File upload form for customer |
| `templates/file_settings.html` | Per-file print settings form |
| `templates/price_summary.html` | Price summary before payment |
| `static/js/voice_search.js` | **Empty file** |
| `static/*.png` | Generated QR images |

---

### PRINT_AGENT

#### `agent.py` — Entry Point
1. Registers signal handlers (SIGINT/SIGTERM → `shutdown()`).
2. `asyncio.run(start_agent())`:
   - Calls `sync_printers(SHOP_ID)` (initial printer sync via HTTP to cloud).
   - Creates background task `printer_sync_loop()` (repeats every `PRINTER_SYNC_INTERVAL` = 60s).
   - Calls `connect()` (WebSocket client — blocks until disconnected or crashed).
3. On exit, cancels the sync task.

---

#### `websocket/client.py` — WebSocket Client (**Modified locally, not committed**)
- `connect()` — infinite reconnect loop (5s delay). Connects to `WEBSOCKET_URL`.
- `register(websocket)` — sends `{"type":"register","agent_id":...,"shop_id":...}`.
- `heartbeat(websocket)` — sends heartbeat every 30s.
- `receive_messages(websocket)` — handles:
  - `registered` → log.
  - `heartbeat_ack` → log.
  - `job` → validates fields, calls `handle_job(job)` (**synchronously, blocking the event loop**).
  - `ping` → sends pong.

> **⚠️ Blocking Issue**: `handle_job(job)` is synchronous and calls blocking I/O (HTTP download, subprocess, win32print). Called directly in the async `receive_messages` coroutine — this will **block all WebSocket communication** during printing.

---

#### `services/job_handler.py`
Orchestrates the print pipeline:
1. `download_file(job)` → local file path.
2. `verify_download(file_path)` → existence + non-zero size.
3. `validate_file(file_path)` → extension check.
4. `report_job_started(job_id)` → HTTP PUT to cloud.
5. `execute_print_job(job)` → `advanced_executor.py`.
6. `report_job_completed(job_id, actual_seconds)` → HTTP PUT to cloud.
7. `secure_delete(file_path)` → wipe file.
8. On exception: `report_job_failed(job_id, reason)` + cleanup.

---

#### `services/downloader.py`
- `download_file(job)`: HTTP GET with `stream=True`, up to `MAX_RETRY` (3) attempts, `RETRY_DELAY` (5s) between. Uses `download_url` from job payload.
- `verify_download(file_path)`: exists + size > 0.

---

#### `services/status_reporter.py`
- `send_status(job_id, status, message, actual_seconds)`: `PUT {CLOUD_API_URL}/jobs/{job_id}/status?status=...&message=...`.
- `report_job_started` → PRINTING.
- `report_job_completed` → COMPLETED + actual_seconds.
- `report_job_failed` → FAILED + reason.
- `report_printer_online/offline`: `PUT {CLOUD_API_URL}/printer/{printer_id}/status` — **never called in the current flow**.

---

#### `services/file_validator.py`
- `validate_file(filepath)`: checks extension in `{.pdf, .doc, .docx, .txt, .jpg, .jpeg, .png}`.
- **⚠️ `.doc` is in ALLOWED_EXTENSIONS but SumatraPDF cannot print `.doc`** — only `.pdf` is handled by `advanced_executor.py`.

---

#### `services/cleanup.py`
- `secure_delete(file_path)`: overwrites with `secrets.token_bytes(file_size)` then `os.remove()`.
- `cleanup_download_folder(folder_path)`: wipes all files in folder.

---

#### `services/printer_availability.py`
- `get_windows_printer(printer_name)`: PowerShell `Get-Printer`.
- `get_pnp_devices(printer_name)`: PowerShell `Get-PnpDevice` fuzzy name match.
- `verify_physical_printer(printer_name)`:
  1. Checks Windows printer queue exists.
  2. Checks not WorkOffline.
  3. USB → checks PnP device; WSD/Network → accept if queue not offline.
- This is the authoritative agent-side availability check.

---

#### `printers/advanced_executor.py` — **PRIMARY Executor**
1. `verify_physical_printer(printer_name)` — final check before printing.
2. `configure_printer(printer_name, job)` via `devmode.py` — sets orientation, paper size, duplex, color, copies, quality via Windows DEVMODE API. Falls back gracefully if DEVMODE fails.
3. Builds SumatraPDF command: `SumatraPDF.exe -silent -print-to <printer> [-print-settings <page_ranges>] <file_path>`.
4. Launches with `subprocess.Popen` (not `.run`).
5. Waits 2s, checks if Sumatra exited early.
6. Calls `monitor_print(printer_name)` — polls Windows print queue.
7. Terminates Sumatra if still running.
8. In `finally`: restores DEVMODE via `restore_devmode`.

---

#### `printers/executor.py` — **OLD Executor (Unused)**
- Uses `win32com.client` (Word COM for DOCX), `os.startfile("print")` for images/text, SumatraPDF for PDF.
- `validate_environment()` runs on module import — **if Word is not installed, it logs a warning but does not fail**.
- **⚠️ Not used by `job_handler.py`** — `job_handler.py` imports `advanced_executor.execute_print_job`, not this module. However, this file **is imported at module load time** via `validate_environment()`, which runs `win32com.client.Dispatch("Word.Application")` during import — potential startup error if Word is absent and exception path is not handled safely.

> Actually reviewing carefully: `validate_environment()` calls `word_available()` which catches the exception and just returns `False`. It only raises if `sumatra_available()` is False. So it may raise on import if SumatraPDF.exe is missing.

---

#### `printers/devmode.py`
- Opens Windows printer handle, reads/writes DEVMODE struct.
- `configure_printer(printer_name, job)`: applies orientation, paper_size, duplex, color, copies, quality=HIGH.
- `restore_devmode(handle, printer_info, backup)`: restores original settings.
- Windows constants: PORTRAIT=1, LANDSCAPE=2, COLOR_MONOCHROME=1, COLOR_COLOR=2, DUPLEX_SIMPLEX=1, DUPLEX_VERTICAL=2, A4=9, A3=8, LEGAL=5.

---

#### `printers/discovery.py`
- `discover_printers()`: `win32print.EnumPrinters(LOCAL|CONNECTIONS)` → calls `get_printer_capabilities` for each.
- Classifies PHYSICAL vs VIRTUAL by keyword matching.
- Returns list of capability dicts.

---

#### `printers/capabilities.py`
- `is_virtual_printer(name)`: keyword match (PDF, OneNote, Fax, XPS, Kindle, etc.).
- `get_printer_status(name)`: reads Windows PRINTER_STATUS_* flags → maps to Online/Busy/Offline.
- `get_printer_capabilities(name)`: detects color (DC_COLORDEVICE), paper sizes (DC_PAPERS, checks 8=A3, 5=Legal), duplex (DC_DUPLEX).

---

#### `printers/manager.py`
- `sync_printers(owner_id)`:
  1. `discover_printers()` — enumerate Windows printers.
  2. For each: `register_printer(owner_id, printer)` — POST `/printer/register`.
  3. `get_cloud_printers(owner_id)` — GET `/printer/owner/{owner_id}`.
  4. Printers in cloud but not local → PUT status=Offline.

---

#### `printers/print_monitor.py`
- Thin re-export shim: re-exports `monitor_print, open_printer, close_printer, get_jobs` from `print_monitors.py` for backward compatibility.

#### `printers/print_monitors.py`
- `monitor_print(printer_name, timeout=120, settle_time=3)`: polls `EnumJobs` every 1s. Returns True when queue empties after a job was seen. Timeout = 120s.

#### `core/config.py`
- Loads `CLOUD_API_URL`, `WEBSOCKET_URL`, `AGENT_ID`, `SHOP_ID`, `DOWNLOAD_FOLDER`, `HEARTBEAT_INTERVAL`, `MAX_RETRY`, `RETRY_DELAY`, `PRINTER_SYNC_INTERVAL` from `.env`.

#### `core/constants.py`
- **⚠️ DUPLICATE** of `config.py` — identical code. Neither imports the other.

#### `core/logger.py`
- Standard Python `logging` to `logs/agent.log` + stdout. Level=INFO.

---

## C. Actual End-to-End Execution Flow

```
1. SETUP
   Owner registers → POST /owner/register
   Owner gets QR  → GET /owner/{owner_id}/qr
                     → generates qr_token, creates PNG in static/
                     → QR points to: GET /qr/{qr_token}

2. PRINT AGENT STARTUP (Windows machine)
   python agent.py
   → sync_printers(SHOP_ID)
       → win32print.EnumPrinters → get_printer_capabilities
       → POST /printer/register  (for each printer)
       → GET  /printer/owner/{SHOP_ID} (check for removed printers)
   → printer_sync_loop() [background, every 60s]
   → websockets.connect(WEBSOCKET_URL)
   → send {"type":"register","agent_id":"agent_001","shop_id":"<uuid>"}
   ← receive {"type":"registered"}
   → heartbeat task: send {"type":"heartbeat"} every 30s
   → receive_messages: wait for jobs

3. CUSTOMER SCANS QR
   GET /qr/{qr_token}
   → finds ShopOwner by qr_token
   → creates ActiveJob(owner_id=owner.owner_id)
   → 303 redirect to GET /upload/{job_id}
   → customer sees upload.html

4. FILE UPLOAD
   POST /upload/{job_id}  [multipart/form-data]
   → saves file to uploads/{uuid}{ext}
   → count_pages(file_path) via pypdf / docx / PIL
   → creates JobFile (page_count, print_type=BW, duplex=False by default)
   → update_job_summary(job_id) → total_files, total_pages, total_copies
   → broadcast_job({"event":"FILES_UPLOADED"}) over WebSocket [agents receive but ignore]

5. FILE SETTINGS (via API or UI)
   PUT /file-settings/{file_id}
   → updates paper_size, print_type, duplex, copies, page_ranges, etc.

6. PRICING
   POST /payment/create/{job_id}
   → if job.total_amount == 0: calls prepare_job(job_id)
       → update_job_summary
       → calculate_priority (total_pages + bonuses)
       → calculate_job_cost:
           for each file:
               get_pricing_rule (match paper_size, print_type, duplex, page_count)
               calculate_billable_units (PER_SIDE or PER_SHEET)
               cost = units × price_per_page × copies
           subtotal = sum, tax = subtotal × tax_percentage / 100
           total = subtotal + tax
   → creates Payment(status=PENDING, provider=MANUAL, method=UPI)
   ← returns {payment_id, amount, currency}

7. PAYMENT (UPI or Cash)
   Option A (UPI): POST /payment/callback/{payment_id}?success=true
   Option B (Cash): POST /payment/cash/{job_id}

8. PAYMENT VERIFICATION
   → payment.status = PAID
   → job.payment_status = PAID
   → assign_paid_job(job_id):
       → assign_printer(job, db):
           → query printers WHERE owner_id=job.owner_id
                              AND status=ONLINE
                              AND is_physical=True
                              AND is_available=True
           → for each printer:
               check_printer_available(printer_name, printer_type) [PowerShell — cloud side!]
               calculate_printer_score(printer, job)  [AI scoring]
               predict_completion_seconds(job, printer, db)  [ETA]
           → select printer with lowest ETA (tie-break: highest score)
           → job.assigned_printer_id = best_printer.printer_id
       → add_job_to_queue(job_id):
           → job.status = QUEUED
           → job.queue_position = current_count + 1
           → printer.current_queue += 1
           → update_queue_predictions (rebuild positions × 45s)
   → if queue_position == 1: dispatch_job_to_agent(job)

9. DISPATCH TO PRINT AGENT
   dispatch_job_to_agent(job):
   → builds payload from job + job.files[0]
   → download_url = "http://localhost:8000/download/job/{job_id}/file/{file_id}"  ⚠️ HARDCODED
   → send_job_to_shop(owner_id, payload)
   → WebSocket: {"type":"job","data":{...payload...}}

10. PRINT AGENT RECEIVES JOB
    receive_messages: message_type == "job"
    → validates required fields (job_id, file_id, download_url, stored_filename, printer_name)
    → handle_job(job) [SYNCHRONOUS — blocks WebSocket]

11. FILE DOWNLOAD
    download_file(job):
    → GET download_url (= http://localhost:8000/download/job/.../file/...)
    → cloud checks payment_status == PAID before serving file
    → streams to downloads/{stored_filename}
    → verify_download: exists + size > 0
    → validate_file: extension in allowed list

12. STATUS UPDATE — PRINTING
    report_job_started(job_id):
    → PUT /jobs/{job_id}/status?status=Printing
    → cloud: job.status = PRINTING, job.started_at = now

13. PHYSICAL PRINTING
    execute_print_job(job) [advanced_executor.py]:
    → verify_physical_printer(printer_name) [PowerShell on agent machine]
    → configure_printer(printer_name, job) [Windows DEVMODE API]
        → open printer handle
        → backup original DEVMODE
        → set orientation, paper_size, duplex, color, copies, quality=HIGH
        → apply via win32print.SetPrinter
    → build SumatraPDF command:
        SumatraPDF.exe -silent -print-to <printer> [-print-settings <pages>] <file_path>
    → subprocess.Popen(command)
    → sleep(2), check if Sumatra exited
    → monitor_print(printer_name, timeout=120):
        → win32print.EnumJobs every 1s
        → wait for queue to empty after job is seen
        → settle_time=3s after empty
    → terminate Sumatra if still running
    → restore_devmode (in finally block)

14. STATUS UPDATE — COMPLETED/FAILED
    report_job_completed(job_id, actual_seconds):
    → PUT /jobs/{job_id}/status?status=Completed&actual_seconds=N
    → cloud: job.status=COMPLETED, job.completed_at=now
    → complete_queue_job(job_id): removes from queue, updates printer.total_jobs_printed
    → get next queued job → dispatch_job_to_agent(next_job)  ← chain next job

15. FILE CLEANUP
    Agent side: secure_delete(file_path) — overwrite + remove
    Cloud side: cleanup_job_files(job_id) [called by printer_scheduler.complete_job]
                → deletes uploads/{stored_filename}, nullifies file_path in DB

16. CUSTOMER / OWNER MONITORING
    GET /status/{job_id}          ← customer can poll
    GET /jobs/{job_id}/status     ← detailed status
    GET /ai/dashboard/{owner_id}  ← owner analytics
    GET /analytics/...            ← analytics
```

---

## D. Actual AI Printer-Selection Algorithm

**Location**: [`app/services/assignment_service.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/assignment_service.py) + [`app/services/print_prediction.py`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/services/print_prediction.py)

### Step 1 — Printer Filtering (`assign_printer`)
Query DB for printers WHERE:
- `owner_id == job.owner_id`
- `status == ONLINE`
- `is_physical == True`
- `is_available == True`

### Step 2 — Physical Availability Check (per printer)
Calls `check_printer_available(printer_name, printer_type)` from `physical_printer_service.py`:
- Runs PowerShell `Get-Printer` on the **cloud server machine** (NOT the agent machine).
- Checks `WorkOffline`, routes USB to PnP check.
- **Problem**: Cloud is typically Linux/Docker — this will always return `False`, effectively blocking all printer assignments in production.

### Step 3 — Capability Scoring (`calculate_printer_score`)
```
Start:  score = 100

For each file in job:
  BW required:
    if printer.supports_bw: score += 10
    else: return -1  (disqualified)

  COLOR required:
    if printer.supports_color: score += 20
    else: return -1

  MIXED required:
    if printer.supports_color: score += 20
    else: return -1

  DUPLEX required:
    if printer.supports_duplex: score += 10
    else: return -1

  A3 required:
    if printer.supports_a3: score += 10
    else: return -1

  LEGAL required:
    if printer.supports_legal: score += 10
    else: return -1

Queue load penalty:
  score -= current_queue × 12

Default printer bonus:
  if printer.is_default: score += 5

Reliability bonus:
  bonus = min(total_jobs_printed // 100, 10)
  score += bonus
```
Score < 0 → printer is skipped.

### Step 4 — ETA Prediction (`predict_completion_seconds`)
```
queue_seconds = sum of estimate_file_seconds for all QUEUED jobs ahead
job_seconds   = sum of estimate_file_seconds for THIS job's files

estimate_file_seconds(file, printer):
  pages_per_file = page_count × copies
  seconds = pages × BASE_SECONDS_PER_PAGE (4s)
  if COLOR or MIXED: × 1.35
  if duplex: × 1.15
  if printer.total_jobs_printed >= 100: × 0.90  (speed bonus)
  elif >= 50: × 0.95
  + setup_time = max(copies-1, 0) × 3

total_ETA = queue_seconds + job_seconds
```

### Step 5 — Printer Selection
```
Primary objective:   lowest predicted ETA (fastest completion)
Tie-break:           highest capability score

if predicted_seconds < best_eta:   replace best
elif same ETA AND score > best_score: replace best
```

### Step 6 — Assignment
```
job.assigned_printer_id = best_printer.printer_id
db.commit()
```

**Summary**: The algorithm is a multi-criteria optimization with hard capability constraints (return -1 on mismatch) and a soft objective function (minimize ETA, maximize reliability). There is **no machine learning** involved — it is a deterministic rule-based scoring algorithm.

---

## E. Actual Print Agent Architecture

```
agent.py
    │
    ├── printers/manager.py → sync_printers()
    │       ├── printers/discovery.py → discover_printers()
    │       │       └── printers/capabilities.py → get_printer_capabilities()
    │       │               └── win32print (Windows API)
    │       └── HTTP POST /printer/register (cloud)
    │
    └── websocket/client.py → connect()
            ├── register() → send {"type":"register"}
            ├── heartbeat() → send {"type":"heartbeat"} every 30s
            └── receive_messages() → on message_type=="job":
                    └── services/job_handler.py → handle_job()
                            ├── services/downloader.py → download_file()
                            │       └── HTTP GET /download/job/.../file/...
                            ├── services/file_validator.py → validate_file()
                            ├── services/status_reporter.py → report_job_started()
                            │       └── HTTP PUT /jobs/{id}/status?status=Printing
                            ├── printers/advanced_executor.py → execute_print_job()
                            │       ├── services/printer_availability.py → verify_physical_printer()
                            │       │       └── PowerShell Get-Printer, Get-PnpDevice
                            │       ├── printers/devmode.py → configure_printer()
                            │       │       └── win32print (DEVMODE API)
                            │       ├── subprocess.Popen(SumatraPDF.exe)
                            │       └── printers/print_monitors.py → monitor_print()
                            │               └── win32print.EnumJobs
                            ├── services/status_reporter.py → report_job_completed/failed()
                            │       └── HTTP PUT /jobs/{id}/status
                            └── services/cleanup.py → secure_delete()
```

### PRINT_AGENT File Status

| File | Status | Content |
|---|---|---|
| `agent.py` | ✅ Complete | Entry point, async loops |
| `websocket/client.py` | ⚠️ Locally modified, not committed | Full WebSocket client |
| `websocket/client.py.backup` | ℹ️ Old backup | Previous version |
| `core/config.py` | ✅ Complete | All env-based config |
| `core/constants.py` | ⚠️ Duplicate | Identical to config.py |
| `core/logger.py` | ✅ Complete | Logging setup |
| `services/job_handler.py` | ✅ Complete | Full pipeline |
| `services/downloader.py` | ✅ Complete | HTTP download + retry |
| `services/file_validator.py` | ⚠️ Minimal | Extension-only check |
| `services/status_reporter.py` | ✅ Complete | HTTP status updates |
| `services/printer_availability.py` | ✅ Complete | PowerShell verification |
| `services/cleanup.py` | ✅ Complete | Secure wipe |
| `printers/advanced_executor.py` | ✅ Complete | PRIMARY executor |
| `printers/advanced_executor.py.backup` | ℹ️ Backup | Old version |
| `printers/executor.py` | ⚠️ Old/unused | Not called by job_handler |
| `printers/manager.py` | ✅ Complete | Sync with cloud |
| `printers/discovery.py` | ✅ Complete | win32print enumeration |
| `printers/capabilities.py` | ✅ Complete | win32print capability detection |
| `printers/devmode.py` | ✅ Complete | Windows DEVMODE API |
| `printers/print_monitor.py` | ℹ️ Shim | Re-exports print_monitors |
| `printers/print_monitors.py` | ✅ Complete | Queue monitoring |
| `tools/SumatraPDF.exe` | ✅ Present | Bundled PDF printer (20MB) |

---

## F. Cloud Server ↔ Print Agent Communication

### Channel 1: WebSocket (persistent, bidirectional)
```
Agent → Cloud:
  {"type": "register",       "agent_id": "...", "shop_id": "..."}
  {"type": "heartbeat",      "agent_id": "..."}
  {"type": "pong",           "agent_id": "..."}

Cloud → Agent:
  {"type": "registered",     "agent_id": "...", "shop_id": "..."}
  {"type": "heartbeat_ack",  "agent_id": "..."}
  {"type": "job",            "data": {job_payload}}
  {"type": "ping"}  ← NOT actually sent by current cloud code
```

**Job Payload (Cloud → Agent)**:
```json
{
  "job_id": "uuid",
  "file_id": "uuid",
  "download_url": "http://localhost:8000/download/job/.../file/...",
  "stored_filename": "8a6f3d....pdf",
  "printer_id": "uuid",
  "printer_name": "HP LaserJet Pro",
  "file_type": ".pdf",
  "page_count": 10,
  "copies": 1,
  "paper_size": "A4",
  "orientation": "Portrait",
  "duplex": false,
  "print_type": "BW",
  "color_mode": "AUTO",
  "page_ranges": null
}
```

### Channel 2: HTTP REST (Agent → Cloud)
```
Agent → Cloud:
  POST /printer/register            ← register/update printers (on startup and sync)
  PUT  /printer/{printer_id}/status ← mark printer online/offline
  PUT  /jobs/{job_id}/status        ← update job status (PRINTING/COMPLETED/FAILED)
  GET  /download/job/.../file/...   ← download file for printing
  GET  /printer/owner/{owner_id}    ← get cloud printer list (for sync)
```

### Interface Mismatches

| Issue | Details |
|---|---|
| **Hardcoded localhost URL** | `dispatch_service.py` line 25: `"http://localhost:8000"` — agent will try to download from localhost, which is wrong if cloud is remote |
| **Status string mismatch** | `status_reporter.py` maps `"PRINTING"→"Printing"`, `"COMPLETED"→"Completed"` etc. But `jobs.py` `update_job_status` receives `JobStatus` enum. If agent sends `"Printing"` as a query param, FastAPI will try to parse it as `JobStatus` enum — may fail if enum value doesn't match |
| **Multi-file jobs** | `dispatch_service.py` only sends `job.files[0]`. Cloud creates one `JobFile` per uploaded file, but agent only ever receives and prints the first file |
| **No status WebSocket feedback** | Agent sends job status via HTTP REST, not WebSocket. The cloud WebSocket manager has `broadcast_payment`, `broadcast_queue` etc. but these are never called in the current flow |
| **Agent heartbeat vs HTTP heartbeat** | Agent sends WebSocket heartbeat only. Cloud's `/agent/heartbeat` HTTP endpoint is never called by the agent |
| **`/agent/register` never called** | The agent does NOT call `POST /agent/register` — only `POST /printer/register` per printer |

---

## G. Missing / Incomplete / Problematic Files

### Empty / Zero-byte Files
| File | Problem |
|---|---|
| `cloud_server/app/services/payment_service.py` | **0 bytes** — completely empty. Nothing imports from it, so no crash, but indicates unimplemented payment gateway integration |
| `cloud_server/app/core/cleanup.py` | **Empty** |
| `cloud_server/app/utils/logger.py` | **Empty** — no logging infrastructure on cloud side |
| `cloud_server/static/js/voice_search.js` | **Empty** |

### Broken / Missing Model Field
- `ActiveJob.estimated_seconds` — referenced in `queue_service.py` (lines 59, 106, 266) but **no Column definition** in `models.py`. Runtime `AttributeError` when queue operations run.

### Duplicate Modules
- `PRINT_AGENT/core/config.py` and `PRINT_AGENT/core/constants.py` — **identical code**. Both define CLOUD_API_URL, WEBSOCKET_URL, AGENT_ID, SHOP_ID, DOWNLOAD_FOLDER, MAX_RETRY, RETRY_DELAY. Should be one file.

### Suspicious Renamed / Backup Files
| File | Issue |
|---|---|
| `cloud_server/app/database/models.py.backup` | Old model backup — committed to repo |
| `cloud_server/app/database/models.py.backup_qr` | Another backup — committed |
| `PRINT_AGENT/printers/advanced_executor.py.backup` | Backup in repo |
| `PRINT_AGENT/websocket/client.py.backup` | Backup in repo |

### Unused Modules
| Module | Status |
|---|---|
| `printers/executor.py` | Not imported anywhere in the actual flow (job_handler uses `advanced_executor`). Still runs `validate_environment()` on import if imported. |
| `cloud_server/app/core/job_store.py` | `print_jobs: List[Dict] = []` — unused in-memory store |
| `cloud_server/app/core/config.py` | `BASE_URL = os.getenv("BASE_URL")` — unused |
| `app/services/printer_scheduler.py` | Defines `schedule_next_job`, `complete_job`, `fail_job` — **not used** in any API router. The actual scheduling flow goes through `queue_service.py` + `dispatch_service.py`. |

### Hard-coded URLs
| Location | Hard-coded value | Problem |
|---|---|---|
| `dispatch_service.py` line 25 | `"http://localhost:8000"` | Breaks when cloud server is deployed remotely |
| `PRINT_AGENT/.env` | `CLOUD_API_URL=http://localhost:8000` | Configurable but default wrong for production |
| `PRINT_AGENT/.env` | `WEBSOCKET_URL=ws://localhost:8000/ws/printer` | Same |

---

## H. Dependencies / Packages Required

### Cloud Server (`requirements.txt` is incomplete)

**Listed in requirements.txt**:
```
fastapi, uvicorn[standard], jinja2, python-multipart, qrcode, pillow
```

**Missing (used in code but not listed)**:
```
sqlalchemy          ← database ORM
psycopg2-binary     ← PostgreSQL driver
python-dotenv       ← .env loading
passlib[bcrypt]     ← password hashing
pypdf               ← PDF page counting
python-docx         ← DOCX page counting
websockets          ← WebSocket (may be included via uvicorn[standard])
```

### PRINT_AGENT (`requirements.txt`)
```
websockets
pywin32             ← win32print, pywintypes
requests            ← HTTP calls to cloud
```

**Missing**:
```
python-dotenv       ← .env loading (used in core/config.py)
```

---

## I. Security / GitHub Issues

### 🔴 CRITICAL — Secrets Committed to GitHub

| File | Secret | Status |
|---|---|---|
| `cloud_server/.env` | `DATABASE_URL` with PostgreSQL password: `npg_PjM36IoKiUBh` | **EXPOSED ON GITHUB** — Neon cloud DB credentials visible publicly |
| `PRINT_AGENT/.env` | `SHOP_ID=08abeab6-1fc3-47d0-a3ab-d8903d0703c1` | Owner UUID exposed |

> The root `.gitignore` lists `.env` — but `cloud_server/.gitignore` also lists `.env`. Both files were committed **before** the gitignore rules were active, or were force-added. They appear in `git ls-files` as tracked.
> 
> **Action Required**: Rotate the Neon DB password immediately. Revoke and regenerate credentials.

### 🔴 Authentication — None
- No JWT, session tokens, or API keys anywhere.
- Any client knowing a `job_id` or `payment_id` can call any endpoint.
- `POST /payment/callback/{payment_id}?success=true` — anyone can mark a payment as successful.

### 🟡 CORS — Wildcard
- `allow_origins=["*"]` — accepts requests from any origin.

### 🟡 File Upload — No Security
- No file size validation in `upload.py` (relies on settings but not enforced in handler).
- No file content validation (magic bytes) — only extension check.
- Uploaded files stored with UUID names, but path traversal not explicitly blocked.

### 🟡 Download Endpoint — Unprotected
- `GET /download/job/{job_id}/file/{file_id}` has no authentication.
- Anyone with a valid job_id + file_id can download after payment.

---

## J. Recommended Next Steps

### 🚨 Immediate (Security)
1. **Rotate Neon DB password** — the current credentials in `cloud_server/.env` are public.
2. **Add `cloud_server/.env` to root `.gitignore`** and verify it is untracked (`git rm --cached cloud_server/.env`).
3. **Add API key or JWT authentication** to all endpoints.
4. **Fix payment callback** — add signature verification or secret token to prevent fraudulent payment confirmations.

### 🔴 Critical Bugs to Fix
5. **Add `estimated_seconds` column** to `ActiveJob` model — `queue_service.py` will crash with `AttributeError` without it.
6. **Fix hardcoded `localhost` URL** in `dispatch_service.py` — use `CLOUD_BASE_URL` from env or request object.
7. **Fix `physical_printer_service.py` on Linux** — the cloud server runs PowerShell commands meant for Windows. Either remove this check from the cloud, or move it to the agent.
8. **Multi-file dispatch** — `dispatch_service.py` only sends `files[0]`. All files need to be dispatched (sequentially or as a list in the payload).
9. **Async job handling** — `handle_job()` is synchronous blocking in an async coroutine. Wrap with `await asyncio.to_thread(handle_job, job)`.

### 🟡 Architecture Issues to Address
10. **Status string matching** — verify `JobStatus` enum values match what `status_reporter.py` sends as query params to `PUT /jobs/{id}/status`.
11. **Agent heartbeat** — decide if the HTTP `/agent/heartbeat` or WebSocket heartbeat is canonical; currently both exist but only WebSocket is used.
12. **WebSocket persistence** — use Redis for agent registry (`connected_agents`) so server restarts don't lose connections.
13. **Remove `core/constants.py`** (duplicate of `config.py`) or merge them.
14. **Implement `payment_service.py`** — currently empty. Should contain actual payment gateway integration logic (Cashfree / Razorpay).
15. **Add `cloud_server/requirements.txt` full dependencies** — SQLAlchemy, psycopg2, python-dotenv, passlib, pypdf, python-docx are all used but unlisted.
16. **Add `PRINT_AGENT/requirements.txt` entry for `python-dotenv`**.

### 🟢 Code Quality
17. Delete backup files from repo (`*.backup`, `*.backup_qr`).
18. Remove `executor.py` if `advanced_executor.py` is the definitive implementation, or clearly document which is active.
19. Implement cloud-side `logger.py` (currently empty) and `cleanup.py`.
20. Implement `voice_search.js` or remove the empty file.
21. Remove `core/job_store.py` if unused.
22. Add `PRINTER_SYNC_INTERVAL` to `PRINT_AGENT/requirements.txt` documentation (env var missing from `.env.example`).
