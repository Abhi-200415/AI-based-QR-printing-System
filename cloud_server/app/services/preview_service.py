import mimetypes
import os
from pathlib import Path

from app.services.page_counter import count_pages


# ==========================================================
# File Exists
# ==========================================================

def file_exists(file_path: str) -> bool:
    return Path(file_path).exists()


# ==========================================================
# File Preview Information
# ==========================================================

def get_file_preview(file_path: str):

    if not file_exists(file_path):
        return None

    return {
        "file_name": Path(file_path).name,
        "file_path": file_path,
        "file_type": mimetypes.guess_type(file_path)[0],
        "file_size": os.path.getsize(file_path),
        "page_count": count_pages(file_path)
    }


# ==========================================================
# Validate Upload
# ==========================================================

def validate_file(file_path: str):

    if not file_exists(file_path):
        return False, "File not found."

    extension = Path(file_path).suffix.lower()

    allowed_extensions = {
        ".pdf",
        ".docx",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg"
    }

    if extension not in allowed_extensions:
        return False, "Unsupported file type."

    return True, "Valid file."


# ==========================================================
# AI Preview Summary
# ==========================================================

def get_preview_summary(file_path: str):

    preview = get_file_preview(file_path)

    if not preview:
        return None

    return {
        **preview,
        "ai_status": "Ready for AI color detection"
    }