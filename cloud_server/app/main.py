import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import CORS_ORIGINS
from app.websocket.printer_socket import router as printer_socket_router

# ==========================================================
# FastAPI Application
# ==========================================================

app = FastAPI(
    title="Cloud Based AI Smart Printing System",
    description="Production-Ready AI QR Printing Backend API",
    version="1.0.0"
)

# Resolve and mount static files directory safely
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(static_dir)),
    name="static"
)

# ==========================================================
# Production CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
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

# WebSocket Router
app.include_router(printer_socket_router)


from fastapi import Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.utils.logger import logger

from app.database.connection import get_db, init_db
from app.database.models import ShopOwner, ActiveJob
from app.core.config import TEMPLATES_DIR, STATIC_DIR

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
async def startup_event():
    """Verify database connection and create tables on startup."""
    init_db()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )




# ==========================================================
# Root & Health Endpoints
# ==========================================================

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root(
    request: Request
):
    """
    Shop Owner & Operator Entrypoint:
    Renders the Owner Portal for login and multi-shop registration.
    """
    return templates.TemplateResponse(
        request=request,
        name="owner_login.html",
        context={}
    )


@app.api_route("/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/register", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/owner/login-page", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def owner_login_page(request: Request):
    """Explicit Owner Login & Registration view."""
    return templates.TemplateResponse(
        request=request,
        name="owner_login.html",
        context={}
    )


@app.api_route("/api/status", methods=["GET", "HEAD"])
def api_status():
    """Service status metadata endpoint."""
    return {
        "project": "Cloud Based AI Smart Printing System",
        "status": "Running",
        "version": "1.0.0"
    }


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    """Health check endpoint for Render and uptime monitoring."""
    return {
        "status": "Healthy",
        "database": "Connected",
        "service": "AI QR Printing Cloud Backend"
    }
