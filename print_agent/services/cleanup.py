import os
import secrets

from core.logger import (
    info,
    error
)


# ==========================================================
# Secure Delete
# ==========================================================

def secure_delete(file_path: str):

    """
    Securely delete a file by overwriting it
    with random data before removing it.
    """

    try:

        if not os.path.exists(file_path):

            return False

        file_size = os.path.getsize(file_path)

        with open(file_path, "r+b") as file:

            file.write(
                secrets.token_bytes(file_size)
            )

            file.flush()

            os.fsync(file.fileno())

        os.remove(file_path)

        info(
            f"Securely deleted: {file_path}"
        )

        return True

    except Exception as e:

        error(
            f"Secure delete failed: {e}"
        )

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