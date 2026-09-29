import mimetypes
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from app.services.page_counter import count_pages, count_pages_from_bytes


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg"
}

# Magic bytes mapping for deep file validation
MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".docx": b"PK\x03\x04", # ZIP container magic bytes
}


def validate_file_content(data: bytes, extension: str) -> Tuple[bool, str]:
    """Validates file bytes against size and magic byte signatures."""
    if len(data) == 0:
        return False, "File is empty."

    ext = extension.lower()
    if not ext.startswith("."):
        ext = f".{ext}"

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'."

    # Validate magic bytes where applicable
    expected_magic = MAGIC_BYTES.get(ext)
    if expected_magic and not data.startswith(expected_magic):
        # Specific check for JPEG (alternate headers)
        if ext in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8"):
            pass
        else:
            return False, f"File signature does not match claimed format '{ext}'."

    return True, "Valid file."


def analyze_uploaded_bytes(data: bytes, original_filename: str) -> Dict[str, Any]:
    """Analyzes uploaded document from in-memory bytes before encryption."""
    extension = Path(original_filename).suffix.lower()
    valid, msg = validate_file_content(data, extension)
    if not valid:
        raise ValueError(msg)

    page_count = count_pages_from_bytes(data, extension)
    return {
        "file_name": original_filename,
        "file_type": mimetypes.guess_type(original_filename)[0] or "application/octet-stream",
        "file_size": len(data),
        "page_count": max(page_count, 1)
    }


def file_exists(file_path: str) -> bool:
    return Path(file_path).exists()


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


def analyze_uploaded_file(file_path: str):
    preview = get_file_preview(file_path)
    if not preview:
        raise ValueError("File could not be read.")
    return preview


def validate_file(file_path: str):
    if not file_exists(file_path):
        return False, "File not found."

    extension = Path(file_path).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type."

    return True, "Valid file."