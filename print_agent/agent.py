import asyncio
import signal
import sys

from core.logger import (
    info,
    error,
    warn
)

from core.config import (
    SHOP_ID,
    AGENT_ID,
    PRINTER_SYNC_INTERVAL,
    CLOUD_API_URL,
    WEBSOCKET_URL
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
    info("Stopping Print Agent gracefully...")
    sys.exit(0)


# ==========================================================
# Continuous Printer Synchronization Loop
# ==========================================================

async def printer_sync_loop():
    while True:
        try:
            await asyncio.sleep(PRINTER_SYNC_INTERVAL)
            if not SHOP_ID:
                continue

            info("Running automatic printer synchronization...")
            success = await asyncio.to_thread(sync_printers, SHOP_ID)
            if success:
                info("Printer synchronization complete.")
            else:
                warn("Printer synchronization reported warnings.")

        except asyncio.CancelledError:
            break
        except Exception as e:
            error(f"Printer synchronization error: {e}")


# ==========================================================
# Start Agent
# ==========================================================

async def start_agent():
    info("=" * 65)
    info(f"AI Smart Printing Agent Started [Agent ID: {AGENT_ID}]")
    info(f"Target Cloud Server : {CLOUD_API_URL}")
    info(f"WebSocket Endpoint  : {WEBSOCKET_URL}")
    info("=" * 65)

    if not SHOP_ID:
        warn("NOTICE: SHOP_ID is not configured in .env.")
        warn("Printers will not sync until SHOP_ID (Shop Owner UUID) is provided in PRINT_AGENT/.env.")
    else:
        info(f"Configured for Shop Owner ID: {SHOP_ID}")
        info("Detecting and synchronizing local printers...")
        try:
            registered = await asyncio.to_thread(sync_printers, SHOP_ID)
            if registered:
                info("Printers synchronized with Cloud.")
            else:
                warn("Printer synchronization completed with warnings.")
        except Exception as e:
            error(f"Initial printer synchronization failed: {e}")

    # Start background sync task
    sync_task = asyncio.create_task(printer_sync_loop())

    try:
        await connect()
    finally:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        asyncio.run(start_agent())
    except KeyboardInterrupt:
        shutdown()
    except Exception as e:
        error(f"Agent fatal crash: {e}")


if __name__ == "__main__":
    main()