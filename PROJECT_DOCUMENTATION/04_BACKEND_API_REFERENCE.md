# 04 — Backend API Reference Catalogue

This catalogue details all 50+ HTTP endpoints and WebSocket channels registered in the **AI-Based QR Printing System** backend (`FastAPI`).

---

## 1. Authentication & Shop Owner API (`/owner`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/owner/register` | `register_owner` ([`api/owner.py:L35`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L35)) | Public | `OwnerRegisterRequest` (name, email, password, phone, upi_id) | `OwnerResponse` + QR Token | `shop_owners`, `shop_settings`, `pricing_rules`, `finishing_services` | `owner_login.html` (Register Tab) |
| `POST` | `/owner/login` | `login_owner` ([`api/owner.py:L100`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L100)) | Public | `OwnerLoginRequest` (email, password) | `TokenResponse` (`access_token`, `token_type`, `owner_id`) | `shop_owners` | `owner_login.html` (Login Tab) |
| `POST` | `/owner/reset-password` | `reset_owner_password` ([`api/owner.py:L145`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L145)) | Public | `ResetPasswordRequest` (email, new_password) | Success Message | `shop_owners` | Owner Password Reset Flow |
| `GET` | `/owner/me` | `get_my_profile` ([`api/owner.py:L185`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L185)) | Bearer JWT | None | `OwnerResponse` | `shop_owners` | Owner Navigation Bar |
| `GET` | `/owner/{owner_id}` | `get_owner` ([`api/owner.py:L200`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L200)) | Public | `owner_id: UUID` (Path) | `OwnerResponse` | `shop_owners` | Customer Upload Banner |
| `GET` | `/owner/dashboard/{owner_id}` | `owner_dashboard` ([`api/owner.py:L220`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/owner.py#L220)) | Bearer JWT | `owner_id: UUID` (Path) | JSON Dashboard Stats (queue, printers, revenue) | `shop_owners`, `active_jobs`, `printers`, `payments` | `dashboard.html` Polling |

---

## 2. Dynamic QR & Customer Ingestion API (`/qr`, `/upload`, `/file`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/qr/{qr_token}` | `qr_scan` ([`api/session.py:L25`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/session.py#L25)) | Public | `qr_token: str` (Path) | `303 Redirect` to `/upload/{job_id}` | `shop_owners`, `active_jobs` | Customer Mobile Camera |
| `GET` | `/owner/{owner_id}/qr` | `owner_qr` ([`api/session.py:L70`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/session.py#L70)) | Public | `owner_id: UUID` (Path) | `image/png` QR binary | `shop_owners` | `dashboard.html` (Print QR Standee) |
| `GET` | `/upload/{job_id}` | `upload_page` ([`api/upload.py:L30`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/upload.py#L30)) | Public | `job_id: UUID` (Path) | HTML (`upload.html`) | `active_jobs`, `shop_owners`, `shop_settings` | Customer Browser |
| `POST` | `/upload/{job_id}` | `upload_files` ([`api/upload.py:L65`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/upload.py#L65)) | Public | `files: List[UploadFile]` (Multipart) | JSON (`job_id`, `files_uploaded`, `redirect_url`) | `active_jobs`, `job_files`, `pricing_rules` | `upload.html` Dropzone |
| `GET` | `/preview/job/{job_id}/file/{file_id}` | `preview_file` ([`api/preview.py:L25`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/preview.py#L25)) | Public | `job_id: UUID`, `file_id: UUID` (Path) | `image/png` Thumbnail Stream | `job_files` | `file_settings.html` |
| `GET` | `/file/settings-page/{file_id}` | `settings_page` ([`api/file_settings.py:L30`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/file_settings.py#L30)) | Public | `file_id: UUID` (Path) | HTML (`file_settings.html`) | `job_files`, `active_jobs`, `finishing_services` | Customer Browser |
| `PUT` | `/file/{file_id}/settings` | `update_file_settings` ([`api/file_settings.py:L85`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/file_settings.py#L85)) | Public | `FileSettingsUpdateRequest` (copies, color, duplex, pages) | JSON (`estimated_cost`, `total_job_amount`) | `job_files`, `active_jobs`, `pricing_rules` | `file_settings.html` Inputs |
| `GET` | `/file/summary/{file_id}` | `price_summary` ([`api/file_settings.py:L205`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/file_settings.py#L205)) | Public | `file_id: UUID` (Path) | HTML (`price_summary.html`) | `job_files`, `active_jobs`, `shop_owners` | Customer Browser |

---

## 3. Payment Gateway API (`/payment`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/payment/create/{job_id}` | `create_payment` ([`api/payment.py:L45`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L45)) | Public | `job_id: UUID` (Path) | JSON (`order_id`, `amount`, `currency`, `key_id`) | `active_jobs`, `payments`, `printers` | `price_summary.html` (Pay Button) |
| `POST` | `/payment/verify` | `verify_payment` ([`api/payment.py:L130`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L130)) | Public | `PaymentVerifyRequest` (razorpay IDs + signature) | JSON (`status: "PAID"`, `redirect_url`) | `payments`, `active_jobs`, `analytics_daily` | Razorpay Checkout Handler |
| `POST` | `/payment/webhook` | `payment_webhook` ([`api/payment.py:L225`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L225)) | Webhook Signature | Raw Razorpay Webhook Event Body | JSON (`status: "received"`) | `payments`, `active_jobs` | Razorpay Cloud Servers |
| `POST` | `/payment/cash/{job_id}` | `cash_payment_request` ([`api/payment.py:L275`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L275)) | Public | `job_id: UUID` (Path) | JSON (`status: "PENDING_CASH_APPROVAL"`) | `payments`, `active_jobs` | `price_summary.html` (Cash Option) |
| `POST` | `/payment/cash-confirm/{job_id}` | `confirm_cash_payment` ([`api/payment.py:L335`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L335)) | Bearer JWT | `job_id: UUID` (Path) | JSON (`status: "PAID"`) | `payments`, `active_jobs` | `dashboard.html` (Cashier Modal) |
| `POST` | `/payment/cash-reject/{job_id}` | `reject_cash_payment` ([`api/payment.py:L395`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L395)) | Bearer JWT | `job_id: UUID` (Path) | JSON (`status: "CANCELLED"`) | `payments`, `active_jobs` | `dashboard.html` (Cashier Modal) |
| `GET` | `/payment/pending-cash/{owner_id}` | `get_pending_cash_jobs` ([`api/payment.py:L430`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/payment.py#L430)) | Bearer JWT | `owner_id: UUID` (Path) | JSON List of Pending Cash Jobs | `active_jobs`, `payments` | `dashboard.html` Polling |

---

## 4. Value-Added Finishing Services API (`/services`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/services/owner/{owner_id}` | `get_owner_finishing_services` ([`api/services.py:L35`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L35)) | Bearer JWT | `owner_id: UUID` (Path) | JSON List of `FinishingServiceResponse` | `finishing_services` | `dashboard.html` (Services Tab) |
| `POST` | `/services/owner/{owner_id}` | `create_finishing_service` ([`api/services.py:L60`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L60)) | Bearer JWT | `FinishingServiceCreate` (name, price, charge_type) | `FinishingServiceResponse` | `finishing_services` | `dashboard.html` |
| `PUT` | `/services/{service_id}` | `update_finishing_service` ([`api/services.py:L95`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L95)) | Bearer JWT | `FinishingServiceUpdate` | `FinishingServiceResponse` | `finishing_services` | `dashboard.html` |
| `DELETE` | `/services/{service_id}` | `delete_finishing_service` ([`api/services.py:L130`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L130)) | Bearer JWT | `service_id: UUID` (Path) | Success Confirmation | `finishing_services` | `dashboard.html` |
| `GET` | `/services/shop/{owner_id}/available` | `get_available_shop_services` ([`api/services.py:L160`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L160)) | Public | `owner_id: UUID` (Path) | JSON List of Active Services | `finishing_services` | `file_settings.html` |
| `POST` | `/services/job/{job_id}/select` | `select_job_finishing_services` ([`api/services.py:L185`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L185)) | Public | `JobFinishingSelectRequest` (service_ids, file_id) | Updated Job Total Summary | `job_finishing_services`, `active_jobs` | `file_settings.html` Checkboxes |
| `POST` | `/services/job/{job_id}/complete-finishing` | `complete_operator_finishing` ([`api/services.py:L240`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/services.py#L240)) | Bearer JWT | `job_id: UUID` (Path) | Success Confirmation | `active_jobs` | `dashboard.html` (Operator Action) |

---

## 5. Jobs & Queue Management API (`/jobs`, `/queue`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/jobs/dispatch-next/{printer_id}` | `dispatch_next_queued_job` ([`api/jobs.py:L35`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/jobs.py#L35)) | Bearer / Internal | `printer_id: UUID` (Path) | JSON (`dispatched: bool`, `job_id`) | `active_jobs`, `printers` | Edge Agent / Dispatch Loop |
| `GET` | `/jobs/owner/{owner_id}` | `get_owner_jobs` ([`api/jobs.py:L90`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/jobs.py#L90)) | Bearer JWT | `owner_id: UUID` (Path) | JSON List of `JobResponse` | `active_jobs`, `job_files` | `dashboard.html` Queue View |
| `GET` | `/jobs/{job_id}` | `get_single_job` ([`api/jobs.py:L130`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/jobs.py#L130)) | Public | `job_id: UUID` (Path) | `JobResponse` + Files | `active_jobs`, `job_files` | `job_status.html` |
| `PUT` | `/jobs/{job_id}/status` | `update_job_status` ([`api/jobs.py:L170`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/jobs.py#L170)) | Bearer / Agent | `status: JobStatus` | Updated Status | `active_jobs`, `analytics_daily` | Local Print Agent Reporter |
| `GET` | `/queue/statistics/summary` | `queue_statistics` ([`api/queue.py:L30`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/queue.py#L30)) | Public | None | Total queued, avg wait time | `active_jobs` | Shop Telemetry Banner |
| `GET` | `/queue/printer/{printer_id}` | `get_printer_queue` ([`api/queue.py:L60`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/queue.py#L60)) | Public | `printer_id: UUID` (Path) | List of Jobs Assigned to Printer | `active_jobs` | Edge Print Agent |
| `POST` | `/queue/{job_id}` | `queue_job` ([`api/queue.py:L95`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/queue.py#L95)) | Public / Internal | `job_id: UUID` (Path) | Queue Position and Estimated Time | `active_jobs` | Payment Verification |

---

## 6. Secure Edge Download & Agent Telemetry API (`/download`, `/agent`, `/ws/printer`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/download/job/{job_id}/file/{file_id}` | `download_file` ([`api/download.py:L35`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/download.py#L35)) | Bearer / Paid Gate | `job_id: UUID`, `file_id: UUID` (Path) | Decrypted Binary Octet-Stream | `active_jobs`, `job_files` | `PRINT_AGENT/services/downloader.py` |
| `POST` | `/agent/register` | `register_agent` ([`api/agent.py:L35`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/agent.py#L35)) | Secret Header | `AgentRegisterRequest` (agent_id, shop_id, printers) | Registration Confirmation + Tokens | `printers` | `PRINT_AGENT/core/auth.py` |
| `POST` | `/agent/heartbeat` | `heartbeat` ([`api/agent.py:L110`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/agent.py#L110)) | Secret Header | `HeartbeatRequest` (agent_id, printer_statuses) | Heartbeat Acknowledgment | `printers` | Local Print Agent Daemon |
| `WS` | `/ws/printer` | `printer_socket` ([`websocket/printer_socket.py:L20`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/websocket/printer_socket.py#L20)) | Query / Header Auth | Bidirectional WebSocket Frame Stream | JSON Events (`JOB_DISPATCH`, `STATUS_UPDATE`) | In-memory connection map | `PRINT_AGENT/websocket/client.py` |

---

## 7. Digital Receipt & Analytics API (`/receipt`, `/analytics`, `/ai`)

| Method | Path | Handler Function & Source File | Auth Required | Request Parameters / Body | Response Schema / Type | Database Tables Touched | Calling Component |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/receipt/job/{job_id}` | `get_receipt_json` ([`api/receipt.py:L30`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/receipt.py#L30)) | Public | `job_id: UUID` (Path) | Authoritative Receipt JSON | `active_jobs`, `job_files`, `shop_owners`, `payments`, `job_finishing_services` | Customer App |
| `GET` | `/receipt/job/{job_id}/view` | `view_receipt_html` ([`api/receipt.py:L85`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/receipt.py#L85)) | Public | `job_id: UUID` (Path) | Rendered HTML (`receipt.html`) | Same as above | Customer Browser |
| `GET` | `/receipt/job/{job_id}/download` | `download_receipt_html` ([`api/receipt.py:L140`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/receipt.py#L140)) | Public | `job_id: UUID` (Path) | HTML File Attachment | Same as above | Customer Browser |
| `GET` | `/analytics/dashboard/{owner_id}` | `dashboard` ([`api/analytics.py:L25`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/analytics.py#L25)) | Bearer JWT | `owner_id: UUID` (Path) | Analytics Overview JSON | `analytics_daily`, `active_jobs` | `dashboard.html` |
| `GET` | `/analytics/forecast/{owner_id}` | `revenue_forecast` ([`api/analytics.py:L65`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/analytics.py#L65)) | Bearer JWT | `owner_id: UUID` (Path) | 7-day ML Forecast JSON | `analytics_daily` | `dashboard.html` (Chart.js) |
| `POST` | `/ai/printer/{job_id}` | `recommend_printer` ([`api/ai.py:L55`](file:///c:/Users/Abhilash%20S/Desktop/AI-based-QR-printing-System/cloud_server/app/api/ai.py#L55)) | Public / Internal | `job_id: UUID` (Path) | `RecommendedPrinterResponse` | `active_jobs`, `printers` | Dispatch Logic |
