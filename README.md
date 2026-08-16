AI-Based QR Smart Printing System

Overview

The AI-Based QR Smart Printing System is a cloud-based smart printing platform designed to simplify document printing through QR-based access, online document upload, automated pricing, payment verification, queue management, printer assignment, analytics, and AI/ML-based waiting-time prediction.

The system allows customers to access a printing shop by scanning its unique QR code, upload documents, configure printing requirements, make a payment, and track their print job.

Shop owners/operators can manage print jobs, printers, queues, pricing, payments, analytics, and AI-based predictions through a separate dashboard.

---

Main Objectives

- Provide a QR-based printing workflow.
- Allow customers to upload documents remotely.
- Automatically calculate printing costs.
- Support online payment and payment verification.
- Manage printing queues efficiently.
- Automatically assign jobs to suitable printers.
- Provide real-time job status.
- Predict approximate customer waiting time using AI/ML.
- Provide analytics for shop owners.
- Support independent printing shops.

---

Key Features

Customer Features

- Scan a unique shop QR code.
- Access the selected shop directly.
- Upload PDF and supported documents.
- Configure:
  - Paper size
  - Black & white / color printing
  - Duplex printing
  - Page range
  - Number of copies
- View calculated printing cost.
- Make online payment.
- Receive job/order identification.
- Track print-job status.
- View estimated waiting time.
- Download/collect completed documents according to the shop workflow.

Owner / Operator Features

- Owner registration and authentication.
- Shop profile management.
- Unique shop QR.
- Pricing configuration.
- Printer management.
- Printer capability management.
- Job management.
- Queue management.
- Payment status monitoring.
- Analytics dashboard.
- Revenue statistics.
- Printer utilization.
- AI-based recommendations.
- Busy-hour prediction.
- Revenue prediction.
- Job prioritization.
- Printer assignment.

---

AI / ML Features

1. Intelligent Printer Assignment

The system evaluates available printers based on factors such as:

- Current queue length
- Black & white capability
- Color capability
- Duplex capability
- Paper-size support
- Default-printer preference
- Printer reliability

The best suitable printer is selected automatically.

2. Intelligent Job Priority

Jobs are assigned a priority score based on characteristics such as:

- Total pages
- Number of files
- Number of copies
- Job complexity

3. Waiting-Time Prediction

The system is designed to estimate how long a customer may need to wait before their print job is completed.

The prediction can use historical and real-time information such as:

- Queue length
- Number of pages
- Number of copies
- Printer workload
- Print type
- Historical printing duration
- Time of day
- Printer availability

4. ETL Pipeline

Historical printing information can be processed through an ETL pipeline:

Raw Printing Data
       ↓
Extract
       ↓
Transform
       ↓
Clean / Validate
       ↓
Feature Engineering
       ↓
ML Training Data
       ↓
Prediction

Initially, synthetic historical data can be used for development and testing. Once the system is deployed with real printing shops, actual operational data can replace the synthetic dataset.

5. Analytics and Recommendations

The owner dashboard can provide:

- Job statistics
- Revenue trends
- Printer utilization
- Busy-hour analysis
- Operational recommendations

---

Payment Workflow

The payment system is designed around server-side verification.

Customer
   ↓
Select Print Settings
   ↓
Calculate Price
   ↓
Create Payment Order
   ↓
Payment Gateway
   ↓
Customer Payment
   ↓
Webhook / Server-side Verification
   ↓
Verify Amount + Order + Status
   ↓
Payment = PAID
   ↓
Job Added to Queue

The frontend is not trusted to declare a payment successful.

Payment credentials and secrets are stored as environment variables and are not committed to GitHub.

The development version can use payment-gateway test mode. Production payment onboarding can be configured separately when real printing shops are connected.

---

QR Workflow

Each printing shop has a unique QR identifier.

Shop QR
   ↓
Identify Shop
   ↓
Open Shop Printing Page
   ↓
Upload Document
   ↓
Print Configuration
   ↓
Price
   ↓
Payment
   ↓
Print Job

The QR identifies the shop rather than containing sensitive credentials.

Shop settings can therefore be changed without changing the physical QR.

---

System Architecture

                     Customer
                        │
              ┌─────────┴─────────┐
              │                   │
           QR Scan            Frontend
              │                   │
              └─────────┬─────────┘
                        ↓
                  FastAPI Backend
                        │
        ┌───────────────┼────────────────┐
        ↓               ↓                ↓
   Neon Database   File Storage      AI / ML
        │               │                │
        │               │                │
        └───────────────┼────────────────┘
                        ↓
                 Printing Workflow
                        │
                ┌───────┴────────┐
                ↓                ↓
             Queue          Printer Agent
                                  │
                                  ↓
                              Printer

---

Backend Technologies

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Neon PostgreSQL
- Pydantic
- Uvicorn
- WebSockets
- REST APIs

---

Frontend Technologies

The frontend provides separate interfaces for:

Customer

- Shop access
- Document upload
- Print configuration
- Price
- Payment
- Job tracking
- Waiting-time information

Owner / Operator

- Dashboard
- Jobs
- Queue
- Printers
- Payments
- Analytics
- AI predictions
- Shop settings

---

Database

Neon PostgreSQL is used as the cloud database.

The database stores structured information such as:

- Shop owners
- Shops
- Jobs
- Files metadata
- Printers
- Pricing
- Payments
- Queue information
- Analytics data
- AI/ML-related data

Actual uploaded documents are kept separately from the relational database.

---

File Storage

Uploaded documents are handled separately from the database.

Development:

FastAPI
   ↓
Local Storage
   ↓
PDF / Documents

Production can use object storage:

FastAPI
   ↓
Object Storage
   ↓
PDF / Documents

The database stores file metadata and storage references rather than storing large document files directly in PostgreSQL.

---

API Modules

The backend contains separate API modules for major system functions:

/api/owner.py
/api/upload.py
/api/file_settings.py
/api/jobs.py
/api/pricing.py
/api/printer.py
/api/queue.py
/api/payment.py
/api/analytics.py
/api/ai.py
/api/ai_document_search.py
/api/download.py
/api/agent.py

This modular structure keeps the backend maintainable and allows individual features to be developed and tested independently.

---

Printer Management

The system can manage printers based on:

- Online/offline state
- Busy state
- Maintenance state
- Current queue
- Supported paper sizes
- Black & white support
- Color support
- Duplex support
- Printing history

A virtual/demo printer can be used during development when physical printers are unavailable.

Actual printers can later be connected through a local print agent.

---

Queue Management

A print job follows a workflow similar to:

PENDING
   ↓
QUEUED
   ↓
ASSIGNED
   ↓
PRINTING
   ↓
COMPLETED

Failure and cancellation states are also supported.

---

WebSocket Communication

WebSockets can be used for real-time communication between the cloud server, frontend, and printer/agent components.

This allows the system to update:

- Queue status
- Printer status
- Job status
- Printing progress

without requiring constant page refreshes.

---

Deployment

Development

Frontend → Local
FastAPI → Local
Neon → Cloud PostgreSQL
File Storage → Local initially
Payment → Test Mode

Production

Frontend → Hosted
FastAPI → Render
Database → Neon PostgreSQL
File Storage → Object Storage
Payment → Live Payment Gateway
Printer → Local Print Agent

---

Security

Sensitive information is not committed to the repository.

Examples:

- Database connection strings
- Payment API secrets
- Webhook secrets
- Application secrets
- Passwords

These values are provided through environment variables.

Uploaded customer documents should not be stored in public GitHub repositories.

---

Project Status

Completed / Integrated

- FastAPI backend structure
- PostgreSQL/Neon database connection
- SQLAlchemy models
- Database tables
- Owner APIs
- Job APIs
- Pricing functionality
- Printer assignment logic
- Queue functionality
- Analytics APIs
- AI-related backend modules
- Payment module structure
- WebSocket support

In Progress

- Cloud file storage
- Customer frontend
- Owner frontend
- Payment gateway test integration
- ETL pipeline
- Waiting-time ML prediction
- Virtual printer testing

Future Enhancements

- Real printing-shop deployment
- Physical printer integration
- Real-world historical dataset
- Production payment onboarding
- Location-based shop discovery
- Advanced ML models
- Customer notifications
- Expanded shop management

---

Technology Stack

Layer| Technology
Frontend| Web-based UI
Backend| Python, FastAPI
Database| PostgreSQL
Cloud Database| Neon
ORM| SQLAlchemy
API| REST
Real-time| WebSockets
AI/ML| Python ML pipeline
ETL| Python data-processing pipeline
Payment| Payment Gateway
Deployment| Render
Printer Integration| Local Print Agent

---

Project Goal

The goal of the project is to transform conventional local printing into a cloud-connected smart printing workflow where customers can submit documents remotely, make payments, monitor jobs, and receive estimated waiting times while shop owners can efficiently manage printers, queues, payments, and operational analytics.

---

Authors

AI-Based QR Smart Printing System

Academic Major Project
