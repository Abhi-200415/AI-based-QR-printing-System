from pathlib import Path

from PIL import Image
from docx import Document
from pypdf import PdfReader


# ==========================================================
# PDF
# ==========================================================

def count_pdf_pages(file_path: str) -> int:
    return len(PdfReader(file_path).pages)


# ==========================================================
# DOCX
# ==========================================================

def count_docx_pages(file_path: str) -> int:
    document = Document(file_path)

    total_characters = sum(
        len(paragraph.text)
        for paragraph in document.paragraphs
    )

    chars_per_page = 3000

    return max(1, (total_characters + chars_per_page - 1) // chars_per_page)


# ==========================================================
# TXT
# ==========================================================

def count_txt_pages(file_path: str) -> int:
    with open(
        file_path,
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

def count_image_pages(file_path: str) -> int:
    try:
        Image.open(file_path)
        return 1
    except Exception:
        return 0


# ==========================================================
# MAIN
# ==========================================================

def count_pages(file_path: str) -> int:

    extension = Path(file_path).suffix.lower()

    page_counter = {
        ".pdf": count_pdf_pages,
        ".docx": count_docx_pages,
        ".txt": count_txt_pages,
        ".png": count_image_pages,
        ".jpg": count_image_pages,
        ".jpeg": count_image_pages,
    }

    counter = page_counter.get(extension)

    if counter is None:
        raise ValueError(f"Unsupported file format: {extension}")

    return counter(file_path)