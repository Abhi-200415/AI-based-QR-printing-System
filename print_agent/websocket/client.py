import asyncio
import json

import websockets

from core.config import (
    WEBSOCKET_URL,
    AGENT_ID,
    SHOP_ID
)

from core.logger import (
    info,
    error
)

from services.job_handler import (
    handle_job
)


# ==========================================================
# Register Agent
# ==========================================================

async def register(websocket):

    payload = {

        "type": "register",

        "agent_id": AGENT_ID,

        "shop_id": SHOP_ID

    }

    await websocket.send(
        json.dumps(payload)
    )

    info(
        "Agent registration message sent."
    )


# ==========================================================
# Heartbeat
# ==========================================================

async def heartbeat(websocket):

    while True:

        try:

            payload = {

                "type": "heartbeat",

                "agent_id": AGENT_ID

            }

            await websocket.send(
                json.dumps(payload)
            )

            await asyncio.sleep(30)

        except Exception as e:

            error(
                f"Heartbeat stopped: {e}"
            )

            break


# ==========================================================
# Receive Messages
# ==========================================================

async def receive_messages(websocket):

    while True:

        message = await websocket.recv()

        data = json.loads(message)

        message_type = data.get("type")

        # ==================================================
        # Agent Registration Confirmation
        # ==================================================

        if message_type == "registered":

            info(
                "Cloud registered agent: "
                f"{data.get('agent_id')}"
            )

        # ==================================================
        # Heartbeat Acknowledgement
        # ==================================================

        elif message_type == "heartbeat_ack":

            info(
                "Heartbeat acknowledged by cloud."
            )

        # ==================================================
        # Print Job
        # ==================================================

        elif message_type == "job":

            # Cloud manager sends:
            #
            # {
            #     "type": "job",
            #     "data": {...}
            # }
            #
            # But accepting both formats makes the
            # agent more robust.

            job = data.get(
                "data",
                data
            )

            job_id = job.get(
                "job_id"
            )

            info(
                f"Received Job: {job_id}"
            )

            handle_job(
                job
            )

        # ==================================================
        # Ping
        # ==================================================

        elif message_type == "ping":

            await websocket.send(

                json.dumps({

                    "type": "pong",

                    "agent_id": AGENT_ID

                })

            )

            info(
                "Ping received. Pong sent."
            )

        # ==================================================
        # Unknown Message
        # ==================================================

        else:

            info(
                f"Unknown cloud message: {data}"
            )


# ==========================================================
# Connect To Cloud
# ==========================================================

async def connect():

    while True:

        try:

            info(
                f"Connecting to cloud: "
                f"{WEBSOCKET_URL}"
            )

            async with websockets.connect(

                WEBSOCKET_URL

            ) as websocket:

                info(
                    "Connected To Cloud"
                )

                # ------------------------------------------
                # Register Agent
                # ------------------------------------------

                await register(
                    websocket
                )

                # ------------------------------------------
                # Start Heartbeat
                # ------------------------------------------

                heartbeat_task = asyncio.create_task(

                    heartbeat(
                        websocket
                    )

                )

                # ------------------------------------------
                # Receive Cloud Messages
                # ------------------------------------------

                receive_task = asyncio.create_task(

                    receive_messages(
                        websocket
                    )

                )

                try:

                    await asyncio.gather(

                        heartbeat_task,

                        receive_task

                    )

                finally:

                    heartbeat_task.cancel()

                    receive_task.cancel()

        except Exception as e:

            error(
                f"Connection Lost: {e}"
            )

            info(
                "Reconnecting in 5 seconds..."
            )

            await asyncio.sleep(
                5
            )