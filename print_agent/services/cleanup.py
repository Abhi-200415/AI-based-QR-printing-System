import os
import secrets

from core.logger import (
    info,
    error
)


# ==========================================================
# Secure Delete
# ==========================================================

def secure_delete(file_path: str, job_id: str = None) -> bool:
    """
    Securely delete a temporary file by overwriting it
    with random bytes before unlinking it from disk.
    Logs structured cleanup progress to terminal.
    """
    jid_str = job_id or "N/A"
    print(f"[LOCAL CLEANUP] Starting local cleanup\n[LOCAL CLEANUP] Job ID: {jid_str}", flush=True)

    try:
        if not os.path.exists(file_path):
            print(f"[LOCAL CLEANUP] Cleanup completed (File already removed: {os.path.basename(file_path)})", flush=True)
            return False

        base_name = os.path.basename(file_path)
        print(f"[LOCAL CLEANUP] Temporary file located", flush=True)
        print(f"[LOCAL CLEANUP] Temporary file located: {base_name}", flush=True)

        file_size = os.path.getsize(file_path)
        if file_size > 0:
            with open(file_path, "r+b") as file:
                file.write(secrets.token_bytes(file_size))
                file.flush()
                os.fsync(file.fileno())

        os.remove(file_path)

        print(f"[LOCAL CLEANUP] File deletion successful", flush=True)
        print(f"[LOCAL CLEANUP] File deletion successful: {base_name}", flush=True)
        print(f"[LOCAL CLEANUP] Cleanup completed", flush=True)
        info(f"Securely deleted: {file_path}")
        return True

    except Exception as e:
        safe_msg = f"Failed to securely delete temporary file: {str(e)}"
        print(f"[LOCAL CLEANUP] ERROR: {safe_msg}", flush=True)
        error(f"Secure delete failed: {e}")
        return False


# ==========================================================
# Cleanup Download Folder
# ==========================================================

def cleanup_download_folder(folder_path: str):

    if not os.path.exists(folder_path):

        return

    for filename in os.listdir(folder_path):

        file_path = os.path.join(
            folder_path,
            filename
        )

        if os.path.isfile(file_path):

            secure_delete(file_path)