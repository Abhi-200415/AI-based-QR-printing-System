from pypdf import PdfReader
from docx import Document
from PIL import Image
import os


def count_pdf_pages(file_path: str) -> int:
    reader = PdfReader(file_path)
    return len(reader.pages)


def count_docx_pages(file_path: str) -> int:

    doc = Document(file_path)

    text = ""

    for para in doc.paragraphs:
        text += para.text

    chars_per_page = 3000

    pages = max(
        1,
        (len(text) // chars_per_page) + 1
    )

    return pages


def count_txt_pages(file_path: str) -> int:

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        content = f.read()

    chars_per_page = 3000

    pages = max(
        1,
        (len(content) // chars_per_page) + 1
    )

    return pages


def count_image_pages(file_path: str) -> int:
    return 1


def count_pages(file_path: str) -> int:

    extension = (
        os.path.splitext(file_path)[1]
        .lower()
    )

    if extension == ".pdf":
        return count_pdf_pages(file_path)

    elif extension == ".docx":
        return count_docx_pages(file_path)

    elif extension == ".txt":
        return count_txt_pages(file_path)

    elif extension in [
        ".png",
        ".jpg",
        ".jpeg"
    ]:
        return count_image_pages(file_path)

    return 1