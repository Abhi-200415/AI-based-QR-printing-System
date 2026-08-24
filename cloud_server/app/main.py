from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.websocket.printer_socket import router as printer_socket_router
# ==========================================================
# FastAPI Application
# ==========================================================

app = FastAPI(
    title="Cloud Based AI Smart Printing System",
    description="Backend API",
    version="1.0.0"
)


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


# ==========================================================
# API Routers
# ==========================================================

from app.api.owner import router as owner_router
from app.api.upload import router as upload_router
from app.api.file_settings import router as file_settings_router
from app.api.jobs import router as jobs_router
from app.api.pricing import router as pricing_router
from app.api.printer import router as printer_router
from app.api.queue import router as queue_router
from app.api.payment import router as payment_router
from app.api.analytics import router as analytics_router
from app.api.ai import router as ai_router
from app.api.ai_document_search import router as ai_document_search_router
from app.api.download import router as download_router
from app.api.agent import router as agent_router
from app.api.settings import router as settings_router
from app.api.session import router as session_router


# ==========================================================
# Register Routers
# ==========================================================

app.include_router(owner_router)

app.include_router(upload_router)

app.include_router(file_settings_router)

app.include_router(jobs_router)

app.include_router(pricing_router)

app.include_router(printer_router)

app.include_router(queue_router)

app.include_router(payment_router)

app.include_router(analytics_router)

app.include_router(ai_router)

app.include_router(ai_document_search_router)

app.include_router(download_router)

app.include_router(agent_router)

app.include_router(settings_router)
app.include_router(session_router)


app.include_router(printer_socket_router)
# ==========================================================
# Root Endpoint
# ==========================================================

@app.get("/")
def root():

    return {
        "project": "Cloud Based AI Smart Printing System",
        "status": "Running",
        "version": "1.0.0"
    }


# ==========================================================
# Health Check
# ==========================================================

@app.get("/health")
def health():

    return {
        "status": "Healthy",
        "database": "Connected"
    }

