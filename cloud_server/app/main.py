from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import session, upload
from app.websocket.manager import websocket_router

app = FastAPI()

app.include_router(session.router)
app.include_router(upload.router)
app.include_router(websocket_router)

app.mount("/static", StaticFiles(directory="static"), name="static")
