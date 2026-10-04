import os
import sys
import getpass
import socket
import re
import requests
from pathlib import Path
from core.logger import info, error, warn

ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"


def get_default_agent_id() -> str:
    """Generate a dynamic, machine-specific agent ID if none is configured."""
    try:
        raw_hostname = socket.gethostname()
        clean_hostname = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_hostname).lower()
        return f"agent_{clean_hostname}"
    except Exception:
        return "agent_local_node"


def save_env_setting(key: str, value: str):
    """Safely updates or adds a key=value setting in PRINT_AGENT/.env."""
    try:
        lines = []
        if ENV_FILE_PATH.exists():
            lines = ENV_FILE_PATH.read_text(encoding="utf-8").splitlines()

        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"# {key}="):
                new_lines.append(f"{key}={value}")
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f"{key}={value}")

        ENV_FILE_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        warn(f"Could not automatically save {key} to .env: {e}")


def verify_shop_id(cloud_url: str, shop_id: str) -> dict:
    """Checks if a Shop ID exists on the cloud server."""
    try:
        resp = requests.get(f"{cloud_url}/owner/{shop_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def interactive_login(cloud_url: str) -> str:
    """
    Prompts the user to log in with their Shop Owner Email/Password or Shop UUID.
    Returns the authenticated shop_id (UUID).
    """
    print("\n" + "=" * 65)
    print(" 🤖 AI Smart Print Agent - Shop Owner Authentication")
    print("=" * 65)
    print(f" Connecting to Cloud Server: {cloud_url}")
    print("\n [1] Log in with Shop Owner Email & Password (Recommended)")
    print(" [2] Enter Shop Owner ID (UUID) manually")
    print(" [3] Exit")
    print("=" * 65)

    while True:
        try:
            choice = input("\nSelect an option [1/2/3]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted setup.")
            sys.exit(0)

        if choice == "1":
            try:
                email = input("Shop Email : ").strip().lower()
                password = getpass.getpass("Password   : ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted setup.")
                sys.exit(0)

            if not email or not password:
                print("❌ Email and password cannot be empty.")
                continue

            print("\nAuthenticating with cloud server...")
            try:
                resp = requests.post(
                    f"{cloud_url}/owner/login",
                    json={"email": email, "password": password},
                    timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    shop_id = data.get("owner_id")
                    shop_name = data.get("shop_name", "Your Shop")
                    owner_name = data.get("owner_name", "")
                    print(f"✅ Successfully authenticated with: {shop_name} ({owner_name})")
                    print(f"📋 Shop ID: {shop_id}")
                    save_env_setting("SHOP_ID", shop_id)
                    return shop_id
                else:
                    detail = "Invalid credentials."
                    try:
                        detail = resp.json().get("detail", detail)
                    except Exception:
                        pass
                    print(f"❌ Login failed: {detail}")
            except Exception as e:
                print(f"❌ Connection error: {e}")

        elif choice == "2":
            try:
                shop_id = input("Enter Shop Owner UUID: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted setup.")
                sys.exit(0)

            if not shop_id:
                print("❌ Shop ID cannot be empty.")
                continue

            print("\nVerifying Shop ID with cloud server...")
            owner_info = verify_shop_id(cloud_url, shop_id)
            if owner_info:
                shop_name = owner_info.get("shop_name", "Your Shop")
                print(f"✅ Verified Shop: {shop_name}")
                save_env_setting("SHOP_ID", shop_id)
                return shop_id
            else:
                print(f"❌ Could not find an active shop with ID: {shop_id}")

        elif choice == "3":
            print("Exiting Print Agent.")
            sys.exit(0)
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
