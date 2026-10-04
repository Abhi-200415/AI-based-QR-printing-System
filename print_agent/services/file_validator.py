import os
from core.logger import info, warn

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
}


def is_valid_magic_bytes(header: bytes) -> bool:
    """Check magic bytes for common document/image types."""
    if header.startswith(b"%PDF"):
        return True
    if header.startswith(b"PK\x03\x04"):  # DOCX / ZIP
        return True
    if header.startswith(b"\xff\xd8\xff"):  # JPEG
        return True
    if header.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return True
    if header.startswith(b"BM"):  # BMP
        return True
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):  # Legacy DOC
        return True
    # Plain text check (printable ASCII / UTF-8)
    try:
        header[:64].decode("utf-8")
        return True
    except Exception:
        pass
    return False


def validate_file(filepath: str) -> bool:
    """Validate that the file exists, is non-empty, and is a recognized printable format."""
    if not os.path.exists(filepath):
        return False

    size = os.path.getsize(filepath)
    if size == 0:
        return False

    extension = os.path.splitext(filepath)[1].lower()
    if extension in ALLOWED_EXTENSIONS:
        return True

    # Fallback to inspecting content magic bytes
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
            return is_valid_magic_bytes(header)
    except Exception as e:
        warn(f"File magic bytes check error: {e}")
        return False