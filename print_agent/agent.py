import argparse
import asyncio
import signal
import sys

from core.logger import (
    info,
    error,
    warn
)

from core import config
from core.auth import interactive_login, verify_shop_id, save_env_setting

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
            await asyncio.sleep(config.PRINTER_SYNC_INTERVAL)
            if not config.SHOP_ID:
                continue

            info("Running automatic printer synchronization...")
            success = await asyncio.to_thread(sync_printers, config.SHOP_ID)
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
    info(f"AI Smart Printing Agent Started [Agent ID: {config.AGENT_ID}]")
    info(f"Target Cloud Server : {config.CLOUD_API_URL}")
    info(f"WebSocket Endpoint  : {config.WEBSOCKET_URL}")
    info("=" * 65)

    if not config.SHOP_ID:
        warn("NOTICE: No Shop ID configured.")
        config.SHOP_ID = interactive_login(config.CLOUD_API_URL)

    info(f"Configured for Shop Owner ID: {config.SHOP_ID}")
    info("Detecting and synchronizing local printers...")
    try:
        registered = await asyncio.to_thread(sync_printers, config.SHOP_ID)
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
    parser = argparse.ArgumentParser(description="AI Smart Print Agent")
    parser.add_argument("--login", action="store_true", help="Authenticate with Shop Owner credentials")
    parser.add_argument("--shop-id", type=str, help="Specify Shop Owner UUID dynamically")
    parser.add_argument("--server", type=str, help="Specify Cloud Server URL dynamically")
    parser.add_argument("--agent-id", type=str, help="Specify Agent ID dynamically")
    args = parser.parse_args()

    if args.server:
        config.CLOUD_API_URL = args.server.rstrip("/")
        config.WEBSOCKET_URL = config.CLOUD_API_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws/printer"

    if args.agent_id:
        config.AGENT_ID = args.agent_id

    if args.shop_id:
        config.SHOP_ID = args.shop_id
        save_env_setting("SHOP_ID", config.SHOP_ID)

    if args.login:
        config.SHOP_ID = interactive_login(config.CLOUD_API_URL)

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