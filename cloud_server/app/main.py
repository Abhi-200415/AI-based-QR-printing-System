from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.api import session, upload
from app.websocket.manager import websocket_router

app = FastAPI(title="AI-Based QR Printing System")

# Include API routes
app.include_router(session.router)
app.include_router(upload.router)
app.include_router(websocket_router)

# Mount static folder (QR images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount uploads folder (important for print_agent download)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Root route → automatically redirect to session page
@app.get("/")
def root():
    return RedirectResponse(url="/session")
