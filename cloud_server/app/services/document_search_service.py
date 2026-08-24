import os
from typing import List

from pypdf import PdfReader
from docx import Document


# ==========================================================
# PDF Page Extraction
# ==========================================================

def extract_pdf(file_path: str):

    reader = PdfReader(file_path)

    pages = []

    for page_no, page in enumerate(reader.pages, start=1):

        text = page.extract_text() or ""

        pages.append({
            "page": page_no,
            "text": text
        })

    return pages


# ==========================================================
# DOCX Extraction
# ==========================================================

def extract_docx(file_path: str):

    document = Document(file_path)

    text = ""

    for para in document.paragraphs:
        text += para.text + "\n"

    return [{
        "page": 1,
        "text": text
    }]


# ==========================================================
# TXT Extraction
# ==========================================================

def extract_txt(file_path: str):

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        text = file.read()

    return [{
        "page": 1,
        "text": text
    }]


# ==========================================================
# Detect File Type
# ==========================================================

def extract_document(file_path: str):

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return extract_pdf(file_path)

    elif extension == ".docx":
        return extract_docx(file_path)

    elif extension == ".txt":
        return extract_txt(file_path)

    return []


# ==========================================================
# AI Search
# ==========================================================

def search_document(
    file_path: str,
    search_text: str
):

    pages = extract_document(file_path)

    search_text = search_text.lower().strip()

    matched_pages = []

    for page in pages:

        if search_text in page["text"].lower():

            matched_pages.append(page["page"])

    return matched_pages


# ==========================================================
# Convert Pages to Print Range
# ==========================================================

def pages_to_range(
    pages: List[int]
):

    if not pages:
        return ""

    return ",".join(
        str(page)
        for page in pages
    )


# ==========================================================
# AI Search Result
# ==========================================================

def search_summary(
    file_path: str,
    search_text: str
):

    pages = search_document(
        file_path,
        search_text
    )

    return {

        "search_text": search_text,

        "matched_pages": pages,

        "page_ranges": pages_to_range(pages),

        "total_matches": len(pages),

        "found": len(pages) > 0
    }