import os
import time
import requests

from core.config import (
    DOWNLOAD_FOLDER,
    MAX_RETRY,
    RETRY_DELAY
)

from core.logger import (
    info,
    error
)


# ==========================================================
# Create Download Folder
# ==========================================================

os.makedirs(
    DOWNLOAD_FOLDER,
    exist_ok=True
)


# ==========================================================
# Download File
# ==========================================================

def download_file(job: dict):

    """
    Downloads a file from the cloud.

    The cloud should send only:

    job = {

        "file_id": "...",

        "download_url": "...",

        "stored_filename": "8a6f3d....pdf"

    }

    """

    download_url = job["download_url"]

    stored_filename = job["stored_filename"]

    destination = os.path.join(
        DOWNLOAD_FOLDER,
        stored_filename
    )

    retry = 0

    while retry < MAX_RETRY:

        try:

            info(
                f"Downloading file: {stored_filename}"
            )

            response = requests.get(

                download_url,

                stream=True,

                timeout=60

            )

            response.raise_for_status()

            with open(destination, "wb") as file:

                for chunk in response.iter_content(
                    chunk_size=8192
                ):

                    if chunk:

                        file.write(chunk)

            info(
                "Download completed successfully."
            )

            return destination

        except Exception as e:

            retry += 1

            error(
                f"Download failed (Attempt {retry}/{MAX_RETRY}) : {e}"
            )

            time.sleep(RETRY_DELAY)

    raise Exception(
        "Maximum download retry exceeded."
    )


# ==========================================================
# Verify Download
# ==========================================================

def verify_download(file_path: str):

    if not os.path.exists(file_path):

        return False

    if os.path.getsize(file_path) == 0:

        return False

    return True