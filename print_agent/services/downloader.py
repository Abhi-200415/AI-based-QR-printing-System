import os
import time
import requests

from core.config import (
    DOWNLOAD_FOLDER,
    MAX_RETRY,
    RETRY_DELAY,
    AGENT_ID
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

def resolve_destination_filename(job: dict, response_headers: dict = None) -> str:
    """Determine the proper filename and printable extension for a downloaded file."""
    stored_filename = job.get("stored_filename", "") or "document"
    original_filename = job.get("original_filename", "") or ""
    file_type = job.get("file_type", "") or ""
    file_id = job.get("file_id", "") or ""

    # Check Content-Disposition header if available
    cd_filename = ""
    if response_headers:
        cd = response_headers.get("Content-Disposition", "")
        if "filename=" in cd:
            import re
            m = re.search(r'filename=["\']?([^"\';]+)["\']?', cd)
            if m:
                cd_filename = m.group(1).strip()

    # Extract target extension
    ext = ""
    for candidate in [cd_filename, original_filename]:
        if candidate and "." in candidate:
            candidate_ext = os.path.splitext(candidate)[1].lower()
            if candidate_ext and candidate_ext != ".enc":
                ext = candidate_ext
                break

    if not ext:
        # Fallback from stored_filename
        base, s_ext = os.path.splitext(stored_filename)
        if s_ext.lower() != ".enc" and s_ext:
            ext = s_ext.lower()
        elif "." in base:
            ext = os.path.splitext(base)[1].lower()

    if not ext:
        if "pdf" in file_type.lower():
            ext = ".pdf"
        elif "word" in file_type.lower() or "docx" in file_type.lower():
            ext = ".docx"
        elif "jpeg" in file_type.lower() or "jpg" in file_type.lower():
            ext = ".jpg"
        elif "png" in file_type.lower():
            ext = ".png"
        else:
            ext = ".pdf"  # Default printable format

    # Base identifier (clean uuid or stored name without .enc)
    clean_base = stored_filename
    if clean_base.endswith(".enc"):
        clean_base = clean_base[:-4]
    if not clean_base:
        clean_base = file_id or f"file_{int(time.time())}"

    return f"{clean_base}{ext}"


def download_file(job: dict) -> str:
    """
    Downloads a file from the cloud and saves it with its proper printable extension.
    """
    download_url = job.get("download_url")
    if not download_url:
        raise ValueError("Missing download_url in job payload.")

    retry = 0
    while retry < MAX_RETRY:
        try:
            headers = {"X-Agent-Token": AGENT_ID}
            response = requests.get(
                download_url,
                headers=headers,
                stream=True,
                timeout=60
            )
            response.raise_for_status()

            # Resolve proper filename (e.g. .pdf instead of .enc)
            filename = resolve_destination_filename(job, response.headers)
            destination = os.path.join(DOWNLOAD_FOLDER, filename)

            info(f"Downloading file: {filename}")

            with open(destination, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            info("Download completed successfully.")
            return destination

        except Exception as e:
            retry += 1
            error(f"Download failed (Attempt {retry}/{MAX_RETRY}) : {e}")
            time.sleep(RETRY_DELAY)

    raise Exception("Maximum download retry exceeded.")


# ==========================================================
# Verify Download
# ==========================================================

def verify_download(file_path: str):

    if not os.path.exists(file_path):

        return False

    if os.path.getsize(file_path) == 0:

        return False

    return True