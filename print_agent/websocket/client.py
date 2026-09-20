import asyncio
import json
import websockets

from core.logger import (
    info,
    error,
    warn
)

from core.config import (
    WEBSOCKET_URL,
    AGENT_ID,
    SHOP_ID,
    HEARTBEAT_INTERVAL
)

from services.job_handler import (
    handle_job
)


# ==========================================================
# Background Non-Blocking Print Execution
# ==========================================================

async def run_job_in_background(job: dict):
    """
    Runs the blocking physical print process in a background thread
    so the WebSocket event loop, heartbeat, and ping/pong remain responsive.
    """
    try:
        await asyncio.to_thread(handle_job, job)
    except Exception as e:
        error(f"Error in background job execution: {e}")


# ==========================================================
# Agent Registration
# ==========================================================

async def register(websocket):
    info("Registering Print Agent with Cloud...")

    payload = {
        "type": "register",
        "agent_id": AGENT_ID,
        "shop_id": SHOP_ID
    }

    await websocket.send(json.dumps(payload))
    response = await websocket.recv()
    data = json.loads(response)

    if data.get("type") == "registered":
        info(f"Agent Registered Successfully: {AGENT_ID}")
        return True

    error("Agent registration rejected by Cloud.")
    return False


# ==========================================================
# Heartbeat Loop
# ==========================================================

async def send_heartbeat(websocket):
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            payload = {
                "type": "heartbeat",
                "agent_id": AGENT_ID
            }
            await websocket.send(json.dumps(payload))
        except asyncio.CancelledError:
            break
        except Exception as e:
            warn(f"Heartbeat failed : {e}")
            break


# ==========================================================
# Receive Messages
# ==========================================================

async def receive_messages(websocket):
    while True:
        try:
            message = await websocket.recv()
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "job":
                job = data.get("data", data)

                if job.get("event") == "FILES_UPLOADED":
                    info(f"File upload notification for job: {job.get('job_id')}")
                    continue

                # Validate job has minimum identifiers
                job_id = job.get("job_id")
                printer_name = job.get("printer_name")

                if not job_id or not printer_name:
                    error("Received invalid job payload: missing job_id or printer_name.")
                    continue

                info(f"Received Print Job: {job_id} for printer '{printer_name}'")

                # Send job receipt acknowledgement
                try:
                    await websocket.send(json.dumps({
                        "type": "job_ack",
                        "job_id": job_id,
                        "agent_id": AGENT_ID
                    }))
                except Exception as e:
                    warn(f"Failed to send job_ack: {e}")

                # Run job asynchronously in background thread
                asyncio.create_task(run_job_in_background(job))

            elif message_type == "ping":
                await websocket.send(json.dumps({"type": "pong", "agent_id": AGENT_ID}))

            elif message_type == "heartbeat_ack":
                pass

            else:
                info(f"Received message: {data}")

        except websockets.exceptions.ConnectionClosed:
            warn("WebSocket connection closed by server.")
            break
        except asyncio.CancelledError:
            break
        except Exception as e:
            error(f"Error receiving WebSocket message: {e}")
            break


# ==========================================================
# Connection Manager with Reconnection Logic
# ==========================================================

async def connect():
    while True:
        try:
            info(f"Connecting to Cloud WebSocket: {WEBSOCKET_URL}")
            async with websockets.connect(WEBSOCKET_URL, ping_interval=20, ping_timeout=20) as websocket:
                registered = await register(websocket)
                if not registered:
                    await asyncio.sleep(5)
                    continue

                heartbeat_task = asyncio.create_task(send_heartbeat(websocket))
                receive_task = asyncio.create_task(receive_messages(websocket))

                done, pending = await asyncio.wait(
                    [heartbeat_task, receive_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

        except Exception as e:
            error(f"WebSocket connection failed : {e}. Retrying in 5 seconds...")

        await asyncio.sleep(5)
