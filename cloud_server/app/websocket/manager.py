from fastapi import APIRouter, WebSocket
import asyncio
import json

websocket_router = APIRouter()
session_jobs = {}

@websocket_router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    try:
        while True:
            await asyncio.sleep(2)

            if session_id in session_jobs:
                job = session_jobs[session_id]
                await websocket.send_text(json.dumps(job))
                del session_jobs[session_id]

    except:
        pass
