import asyncio
import websockets
import json
import requests
import os
import time
import win32api
import win32print

SERVER_URL = "wss://qr-printing-system.onrender.com/ws/print"
HTTP_BASE = "https://qr-printing-system.onrender.com"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def print_file(filepath):
    try:
        printer_name = win32print.GetDefaultPrinter()
        print(f"Using printer: {printer_name}")

        # Send file to default printer silently
        win32api.ShellExecute(
            0,
            "print",
            filepath,
            None,
            ".",
            0
        )

        print("Print command sent successfully 🖨")
        return True

    except Exception as e:
        print("Printing error:", e)
        return False


async def connect():
    while True:
        try:
            print("=== Print Agent Started ===")
            print("Connecting to server...")

            async with websockets.connect(SERVER_URL) as websocket:
                print("Connected to server ✅")

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    print("\nJob Received:", data)

                    file_id = data["file_id"]
                    filename = data["filename"]

                    file_url = f"{HTTP_BASE}/uploads/{file_id}_{filename}"

                    print("Downloading:", file_url)

                    response = requests.get(file_url)

                    if response.status_code == 200:

                        local_file = os.path.join(
                            DOWNLOAD_DIR,
                            f"{file_id}_{filename}"
                        )

                        with open(local_file, "wb") as f:
                            f.write(response.content)

                        print("Downloaded:", local_file)

                        # Print file
                        success = print_file(local_file)

                        if success:
                            time.sleep(3)  # small delay to allow spool start

                            # Auto delete after printing
                            try:
                                os.remove(local_file)
                                print("File auto-deleted ✅")
                            except:
                                pass

                    else:
                        print("Download failed:", response.status_code)

        except Exception as e:
            print("Connection error:", e)
            print("Reconnecting in 5 seconds...\n")
            time.sleep(5)


if __name__ == "__main__":
    asyncio.run(connect())
