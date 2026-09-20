from fastapi import WebSocket
from typing import Dict, Optional, List
import json
from datetime import datetime

from app.utils.logger import logger

# ==========================================================
# Connected Print Agents
# ==========================================================
# Structure:
# {
#     "agent_id": {
#         "websocket": WebSocket,
#         "shop_id": str,
#         "printer_ids": List[str],
#         "connected_at": datetime,
#         "last_heartbeat": datetime
#     }
# }
connected_agents: Dict[str, dict] = {}


# ==========================================================
# Connect Agent
# ==========================================================

async def connect(
    websocket: WebSocket,
    agent_id: str,
    shop_id: str,
    printer_ids: Optional[List[str]] = None
):
    """
    Register an accepted WebSocket connection with agent_id and shop_id.
    """
    connected_agents[agent_id] = {
        "websocket": websocket,
        "shop_id": shop_id,
        "printer_ids": printer_ids or [],
        "connected_at": datetime.utcnow(),
        "last_heartbeat": datetime.utcnow()
    }
    logger.info(f"Print Agent Connected: {agent_id} (Shop: {shop_id})")


# ==========================================================
# Disconnect Agent
# ==========================================================

def disconnect(websocket: WebSocket):
    agent_to_remove = None
    for agent_id, agent in list(connected_agents.items()):
        if agent["websocket"] is websocket:
            agent_to_remove = agent_id
            break

    if agent_to_remove:
        del connected_agents[agent_to_remove]
        logger.info(f"Print Agent Disconnected: {agent_to_remove}")


def update_heartbeat(agent_id: str):
    if agent_id in connected_agents:
        connected_agents[agent_id]["last_heartbeat"] = datetime.utcnow()


# ==========================================================
# Send To Specific Agent
# ==========================================================

async def send_job_to_agent(agent_id: str, job: dict) -> bool:
    """
    Directly routes a job to the specific Print Agent responsible for the printer.
    """
    agent = connected_agents.get(agent_id)
    if not agent:
        return False

    websocket = agent["websocket"]
    try:
        await websocket.send_text(
            json.dumps({
                "type": "job",
                "data": job
            })
        )
        return True
    except Exception as e:
        logger.error(f"Error sending job to agent {agent_id}: {e}")
        disconnect(websocket)
        return False


# ==========================================================
# Send To Specific Shop
# ==========================================================

async def send_to_shop(shop_id: str, message: dict) -> bool:
    disconnected = []
    sent = False

    for agent_id, agent in list(connected_agents.items()):
        if agent["shop_id"] != shop_id:
            continue

        websocket = agent["websocket"]
        try:
            await websocket.send_text(json.dumps(message))
            sent = True
            break  # routed successfully
        except Exception:
            disconnected.append(websocket)

    for websocket in disconnected:
        disconnect(websocket)

    return sent


async def send_job_to_shop(shop_id: str, job: dict) -> bool:
    return await send_to_shop(
        shop_id,
        {
            "type": "job",
            "data": job
        }
    )


# ==========================================================
# Broadcast Helpers
# ==========================================================

async def broadcast(message: dict):
    disconnected = []
    for agent_id, agent in list(connected_agents.items()):
        try:
            await agent["websocket"].send_text(json.dumps(message))
        except Exception:
            disconnected.append(agent["websocket"])

    for websocket in disconnected:
        disconnect(websocket)


async def broadcast_job(job):
    await broadcast({"type": "job", "data": job})


async def broadcast_queue(queue):
    await broadcast({"type": "queue", "data": queue})


async def broadcast_printer(printer):
    await broadcast({"type": "printer", "data": printer})


async def broadcast_payment(payment):
    await broadcast({"type": "payment", "data": payment})


async def broadcast_ai(ai_message):
    await broadcast({"type": "ai", "data": ai_message})