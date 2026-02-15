from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

websocket_router = APIRouter()

connected_printers = []

@websocket_router.websocket("/ws/print")
async def printer_ws(websocket: WebSocket):
    await websocket.accept()
    connected_printers.append(websocket)
    print("Printer connected")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_printers.remove(websocket)
        print("Printer disconnected")


async def broadcast_job(job):
    for printer in connected_printers:
        await printer.send_text(json.dumps(job))
