from fastapi import WebSocket
from typing import Dict
import json


# ==========================================================
# Connected Print Agents
# ==========================================================

connected_agents: Dict[str, dict] = {}


# ==========================================================
# Connect
# ==========================================================

async def connect(
    websocket: WebSocket,
    agent_id: str,
    shop_id: str
):
    """
    Register an already-accepted WebSocket connection.

    IMPORTANT:
    websocket.accept() is handled by printer_socket.py.
    Do NOT call websocket.accept() here.
    """

    connected_agents[agent_id] = {

        "websocket": websocket,

        "shop_id": shop_id

    }

    print(
        f"Print Agent Connected: {agent_id}"
    )

    print(
        f"Shop ID: {shop_id}"
    )


# ==========================================================
# Disconnect
# ==========================================================

def disconnect(websocket: WebSocket):

    agent_to_remove = None

    for agent_id, agent in list(
        connected_agents.items()
    ):

        if agent["websocket"] is websocket:

            agent_to_remove = agent_id

            break

    if agent_to_remove:

        del connected_agents[agent_to_remove]

        print(
            f"Print Agent Disconnected: {agent_to_remove}"
        )


# ==========================================================
# Send To Specific Shop
# ==========================================================

async def send_to_shop(
    shop_id: str,
    message: dict
):

    disconnected = []

    for agent_id, agent in list(
        connected_agents.items()
    ):

        if agent["shop_id"] != shop_id:

            continue

        websocket = agent["websocket"]

        try:

            await websocket.send_text(
                json.dumps(message)
            )

            return True

        except Exception:

            disconnected.append(
                websocket
            )

    for websocket in disconnected:

        disconnect(websocket)

    return False


# ==========================================================
# Broadcast Message
# ==========================================================

async def broadcast(message: dict):

    disconnected = []

    for agent_id, agent in list(
        connected_agents.items()
    ):

        try:

            await agent["websocket"].send_text(
                json.dumps(message)
            )

        except Exception:

            disconnected.append(
                agent["websocket"]
            )

    for websocket in disconnected:

        disconnect(websocket)


# ==========================================================
# Send Job To Specific Shop
# ==========================================================

async def send_job_to_shop(
    shop_id: str,
    job: dict
):

    return await send_to_shop(

        shop_id,

        {

            "type": "job",

            "data": job

        }

    )


# ==========================================================
# Broadcast Job
# ==========================================================

async def broadcast_job(job):

    await broadcast({

        "type": "job",

        "data": job

    })


# ==========================================================
# Broadcast Queue
# ==========================================================

async def broadcast_queue(queue):

    await broadcast({

        "type": "queue",

        "data": queue

    })


# ==========================================================
# Broadcast Printer Status
# ==========================================================

async def broadcast_printer(printer):

    await broadcast({

        "type": "printer",

        "data": printer

    })


# ==========================================================
# Broadcast Payment Status
# ==========================================================

async def broadcast_payment(payment):

    await broadcast({

        "type": "payment",

        "data": payment

    })


# ==========================================================
# Broadcast AI Notification
# ==========================================================

async def broadcast_ai(ai_message):

    await broadcast({

        "type": "ai",

        "data": ai_message

    })