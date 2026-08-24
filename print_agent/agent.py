import asyncio
import signal
import sys

from core.logger import (
    info,
    error
)

from core.config import (
    SHOP_ID,
    PRINTER_SYNC_INTERVAL
)

from printers.manager import (
    sync_printers
)

from websocket.client import (
    connect
)


# ==========================================================
# Shutdown Handler
# ==========================================================

def shutdown(signum=None, frame=None):

    info(
        "Stopping Print Agent..."
    )

    sys.exit(0)


# ==========================================================
# Continuous Printer Synchronization
# ==========================================================

async def printer_sync_loop():

    while True:

        try:

            await asyncio.sleep(
                PRINTER_SYNC_INTERVAL
            )

            info(
                "Running automatic printer synchronization..."
            )

            success = await asyncio.to_thread(

                sync_printers,

                SHOP_ID

            )

            if success:

                info(
                    "Automatic printer synchronization successful."
                )

            else:

                error(
                    "Automatic printer synchronization completed "
                    "with errors."
                )

        except asyncio.CancelledError:

            info(
                "Printer synchronization stopped."
            )

            break

        except Exception as e:

            error(
                f"Printer synchronization error: {e}"
            )


# ==========================================================
# Start Print Agent
# ==========================================================

async def start_agent():

    info("=" * 60)

    info(
        "AI Smart Printing Agent Started"
    )

    info("=" * 60)

    # -----------------------------------------
    # Initial Printer Synchronization
    # -----------------------------------------

    info(
        "Detecting printers..."
    )

    registered = await asyncio.to_thread(

        sync_printers,

        SHOP_ID

    )

    if registered:

        info(
            "Printers synchronized successfully."
        )

    else:

        error(
            "Printer synchronization completed with errors."
        )

    # -----------------------------------------
    # Start Continuous Synchronization
    # -----------------------------------------

    sync_task = asyncio.create_task(

        printer_sync_loop()

    )

    # -----------------------------------------
    # Connect WebSocket
    # -----------------------------------------

    info(
        "Connecting to Cloud..."
    )

    try:

        await connect()

    finally:

        sync_task.cancel()

        try:

            await sync_task

        except asyncio.CancelledError:

            pass


# ==========================================================
# Main
# ==========================================================

def main():

    signal.signal(
        signal.SIGINT,
        shutdown
    )

    signal.signal(
        signal.SIGTERM,
        shutdown
    )

    try:

        asyncio.run(
            start_agent()
        )

    except KeyboardInterrupt:

        shutdown()

    except Exception as e:

        error(
            f"Agent crashed : {e}"
        )


if __name__ == "__main__":

    main()