import io
from pathlib import Path
from typing import Union

from PIL import Image
from docx import Document
from pypdf import PdfReader


# ==========================================================
# PDF
# ==========================================================

def count_pdf_pages(source: Union[str, bytes, io.BytesIO]) -> int:
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    return len(PdfReader(source).pages)


# ==========================================================
# DOCX
# ==========================================================

def count_docx_pages(source: Union[str, bytes, io.BytesIO]) -> int:
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    document = Document(source)

    total_characters = sum(
        len(paragraph.text)
        for paragraph in document.paragraphs
    )

    chars_per_page = 3000

    return max(1, (total_characters + chars_per_page - 1) // chars_per_page)


# ==========================================================
# TXT
# ==========================================================

def count_txt_pages(source: Union[str, bytes, io.BytesIO]) -> int:
    if isinstance(source, bytes):
        content = source.decode("utf-8", errors="ignore")
    elif isinstance(source, io.BytesIO):
        content = source.getvalue().decode("utf-8", errors="ignore")
    else:
        with open(
            source,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:
            content = file.read()

    chars_per_page = 3000

    return max(1, (len(content) + chars_per_page - 1) // chars_per_page)


# ==========================================================
# IMAGE
# ==========================================================

def count_image_pages(source: Union[str, bytes, io.BytesIO]) -> int:
    try:
        if isinstance(source, bytes):
            source = io.BytesIO(source)
        Image.open(source)
        return 1
    except Exception:
        return 0


# ==========================================================
# MAIN DISPATCHERS
# ==========================================================

PAGE_COUNTERS = {
    ".pdf": count_pdf_pages,
    ".docx": count_docx_pages,
    ".txt": count_txt_pages,
    ".png": count_image_pages,
    ".jpg": count_image_pages,
    ".jpeg": count_image_pages,
}


def count_pages_from_bytes(data: bytes, extension: str) -> int:
    """Counts pages directly from in-memory bytes before encryption."""
    ext = extension.lower()
    if not ext.startswith("."):
        ext = f".{ext}"

    counter = PAGE_COUNTERS.get(ext)
    if counter is None:
        raise ValueError(f"Unsupported file format: {ext}")

    return counter(data)


def count_pages(file_path: str) -> int:
    """Counts pages from a file path."""
    extension = Path(file_path).suffix.lower()
    counter = PAGE_COUNTERS.get(extension)

    if counter is None:
        raise ValueError(f"Unsupported file format: {extension}")

    return counter(file_path)