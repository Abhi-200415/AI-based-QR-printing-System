from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.api import session, upload
from app.websocket.manager import websocket_router
from app.database.connection import engine
from app.database.models import Base

app = FastAPI(title="AI-Based QR Printing System")
Base.metadata.create_all(bind=engine)
app.include_router(session.router)
app.include_router(upload.router)
app.include_router(websocket_router)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def root():
    return RedirectResponse(url="/session")
