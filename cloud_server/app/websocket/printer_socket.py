from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect
)

from app.websocket.manager import (
    connect,
    disconnect
)

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

            await websocket.close(
                code=1008
            )

            return

        agent_id = message.get("agent_id")
        shop_id = message.get("shop_id")

        if not agent_id or not shop_id:

            await websocket.close(
                code=1008
            )

            return

        # ==================================================
        # Register Agent
        # ==================================================

        await connect(
            websocket,
            agent_id,
            shop_id
        )

        await websocket.send_json({

            "type": "registered",

            "agent_id": agent_id,

            "shop_id": shop_id

        })

        # ==================================================
        # Message Loop
        # ==================================================

        while True:

            message = await websocket.receive_json()

            message_type = message.get("type")

            # ==================================================
            # Heartbeat
            # ==================================================

            if message_type == "heartbeat":

                print(
                    "Heartbeat received from:",
                    message.get("agent_id")
                )

                await websocket.send_json({

                    "type": "heartbeat_ack",

                    "agent_id":
                        message.get("agent_id")

                })

            # ==================================================
            # Pong
            # ==================================================

            elif message_type == "pong":

                print(
                    "Pong received from:",
                    message.get("agent_id")
                )

            # ==================================================
            # Unknown
            # ==================================================

            else:

                print(
                    "Unknown printer message:",
                    message
                )

    except WebSocketDisconnect:

        if websocket:

            disconnect(websocket)

        print(
            "Print Agent disconnected."
        )

    except Exception as e:

        print(
            f"Printer WebSocket error: {e}"
        )

        disconnect(websocket)