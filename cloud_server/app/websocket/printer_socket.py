from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect
)
from app.websocket.manager import (
    connect,
    disconnect,
    update_heartbeat
)
from app.utils.logger import logger

router = APIRouter()


@router.websocket("/ws/printer")
async def printer_socket(websocket: WebSocket):
    agent_id = None
    shop_id = None

    try:
        await websocket.accept()

        # ==================================================
        # First Message Must Be Registration
        # ==================================================
        message = await websocket.receive_json()

        if message.get("type") != "register":
            logger.warning(f"WebSocket rejected: Expected register message, got {message.get('type')}")
            await websocket.close(code=1008)
            return

        agent_id = message.get("agent_id")
        shop_id = message.get("shop_id")
        printer_ids = message.get("printer_ids", [])

        if not agent_id or not shop_id:
            logger.warning("WebSocket rejected: Missing agent_id or shop_id.")
            await websocket.close(code=1008)
            return

        # ==================================================
        # Register Agent
        # ==================================================
        await connect(
            websocket,
            agent_id,
            shop_id,
            printer_ids
        )

        await websocket.send_json({
            "type": "registered",
            "agent_id": agent_id,
            "shop_id": shop_id,
            "status": "connected"
        })

        # ==================================================
        # Message Loop
        # ==================================================
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "heartbeat":
                update_heartbeat(agent_id)
                await websocket.send_json({
                    "type": "heartbeat_ack",
                    "agent_id": agent_id
                })

            elif message_type == "job_ack":
                job_id = message.get("job_id")
                logger.info(f"Agent {agent_id} acknowledged receipt of Job {job_id}")

            elif message_type == "pong":
                update_heartbeat(agent_id)

            else:
                logger.debug(f"Received WebSocket message from {agent_id}: {message_type}")

    except WebSocketDisconnect:
        if websocket:
            disconnect(websocket)
        logger.info(f"Print Agent {agent_id} disconnected.")

    except Exception as e:
        logger.error(f"Printer WebSocket error for {agent_id}: {e}")
        if websocket:
            disconnect(websocket)