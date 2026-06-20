from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.api import preview
from app.api import (
    session,
    upload,
    owner,
    pricing,
    printer,
    jobs,
    file_settings
)

from app.websocket.manager import websocket_router

from app.database.connection import engine
from app.database.models import Base

# Create FastAPI application
app = FastAPI(
    title="AI-Based QR Printing System"
)

# Create database tables
Base.metadata.create_all(bind=engine)

# API Routers
app.include_router(session.router)
app.include_router(upload.router)
app.include_router(owner.router)
app.include_router(pricing.router)
app.include_router(printer.router)
app.include_router(jobs.router)
app.include_router(file_settings.router)
app.include_router(preview.router)

# WebSocket Router
app.include_router(websocket_router)

# Static Files
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

# Root Route
@app.get("/")
def root():
    return RedirectResponse(url="/session")
