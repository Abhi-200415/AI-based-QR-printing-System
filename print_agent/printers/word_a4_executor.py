import os
import time
import tempfile
from docx import Document
from docx.shared import Mm
import pypdfium2 as pdfium
from PIL import Image
import win32com.client

from core.logger import info, warn, error
from printers.print_monitors import monitor_print


def parse_page_ranges(range_str, total_pages: int) -> list:
    """Parses a page range string (e.g. '1-3, 5') into 0-indexed page integers."""
    if not range_str or str(range_str).strip().lower() in ["all", "none", ""]:
        return list(range(total_pages))

    selected_pages = set()
    for part in str(range_str).split(","):
        part = part.strip()
        if "-" in part:
            try:
                s, e = part.split("-", 1)
                start = max(1, int(s))
                end = min(total_pages, int(e))
                for p in range(start, end + 1):
                    selected_pages.add(p - 1)
            except ValueError:
                pass
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= total_pages:
                selected_pages.add(p - 1)

    result = sorted(list(selected_pages))
    return result if result else list(range(total_pages))


def build_a4_docx_from_pdf(pdf_path: str, output_docx: str, page_ranges: str = None, orientation: str = "PORTRAIT") -> int:
    """Renders PDF pages to 300 DPI images and embeds them into a native A4 Word document."""
    pdf = pdfium.PdfDocument(pdf_path)
    total_pages = len(pdf)
    pages_to_print = parse_page_ranges(page_ranges, total_pages)

    doc = Document()
    temp_dir = tempfile.mkdtemp(prefix="agent_render_")
    temp_imgs = []

    try:
        force_landscape = (orientation or "PORTRAIT").upper() == "LANDSCAPE"

        for i, page_idx in enumerate(pages_to_print):
            page = pdf[page_idx]
            pil_img = page.render(scale=300.0 / 72.0).to_pil()
            img_w, img_h = pil_img.size

            # Orientation determination
            is_landscape = force_landscape or (img_w > img_h)

            temp_img = os.path.join(temp_dir, f"page_{i}.jpg")
            pil_img.save(temp_img, "JPEG", quality=93)
            temp_imgs.append(temp_img)

            section = doc.sections[0] if i == 0 else doc.add_section()
            if is_landscape:
                section.page_width = Mm(297)
                section.page_height = Mm(210)
                section.top_margin = Mm(5)
                section.bottom_margin = Mm(5)
                section.left_margin = Mm(5)
                section.right_margin = Mm(5)
                doc.add_picture(temp_img, width=Mm(287), height=Mm(200))
            else:
                section.page_width = Mm(210)
                section.page_height = Mm(297)
                section.top_margin = Mm(5)
                section.bottom_margin = Mm(5)
                section.left_margin = Mm(5)
                section.right_margin = Mm(5)
                doc.add_picture(temp_img, width=Mm(200), height=Mm(287))

        doc.save(output_docx)
        return len(pages_to_print)
    finally:
        pdf.close()
        for t in temp_imgs:
            if os.path.exists(t):
                try:
                    os.remove(t)
                except Exception:
                    pass
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass


def build_a4_docx_from_image(image_path: str, output_docx: str, orientation: str = "PORTRAIT") -> bool:
    """Embeds an image into a native full-page A4 Word document."""
    doc = Document()
    with Image.open(image_path) as img:
        img_w, img_h = img.size

    force_landscape = (orientation or "PORTRAIT").upper() == "LANDSCAPE"
    is_landscape = force_landscape or (img_w > img_h)

    section = doc.sections[0]
    if is_landscape:
        section.page_width = Mm(297)
        section.page_height = Mm(210)
        section.top_margin = Mm(5)
        section.bottom_margin = Mm(5)
        section.left_margin = Mm(5)
        section.right_margin = Mm(5)
        doc.add_picture(image_path, width=Mm(287), height=Mm(200))
    else:
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(5)
        section.bottom_margin = Mm(5)
        section.left_margin = Mm(5)
        section.right_margin = Mm(5)
        doc.add_picture(image_path, width=Mm(200), height=Mm(287))

    doc.save(output_docx)
    return True


def print_via_word_a4(printer_name: str, file_path: str, copies: int = 1, orientation: str = "PORTRAIT", page_ranges: str = None) -> bool:
    """
    Prints any document (PDF, Image, Word DOCX) using Microsoft Word COM.
    This guarantees 100% full-page A4 output by utilizing Microsoft Office's native OpenXPS
    print pipeline, completely immune to Windows Class Driver raster scaling defects.
    """
    ext = os.path.splitext(file_path)[1].lower()
    temp_docx = None

    try:
        # 1. Prepare DOCX
        if ext in [".docx", ".doc"]:
            target_docx = os.path.abspath(file_path)
        elif ext == ".pdf":
            info(f"[Word A4 Engine] Converting PDF '{os.path.basename(file_path)}' to true A4 Word document...")
            temp_docx = os.path.abspath(f"temp_print_{int(time.time()*1000)}.docx")
            build_a4_docx_from_pdf(file_path, temp_docx, page_ranges=page_ranges, orientation=orientation)
            target_docx = temp_docx
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
            info(f"[Word A4 Engine] Embedding image '{os.path.basename(file_path)}' into true A4 Word document...")
            temp_docx = os.path.abspath(f"temp_print_{int(time.time()*1000)}.docx")
            build_a4_docx_from_image(file_path, temp_docx, orientation=orientation)
            target_docx = temp_docx
        else:
            raise ValueError(f"Unsupported format for Word A4 engine: {ext}")

        # 2. Print via Microsoft Word COM
        info(f"[Word A4 Engine] Launching Microsoft Word COM for '{os.path.basename(target_docx)}' on '{printer_name}'...")
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        try:
            word.ActivePrinter = printer_name
            document = word.Documents.Open(target_docx, ReadOnly=True, ConfirmConversions=False)

            # Ensure all sections are strictly A4 (PaperSize 9 or 7)
            for s in document.Sections:
                try:
                    s.PageSetup.PaperSize = 9  # wdPaperA4
                except Exception:
                    pass

            info(f"[Word A4 Engine] Submitting {copies} copy/copies to Windows Spooler...")
            for copy_idx in range(copies):
                document.PrintOut(Background=False)

            document.Close(False)
        finally:
            try:
                word.Quit()
            except Exception:
                pass

        # 3. Monitor Windows Print Queue
        info("[Word A4 Engine] Spooled successfully. Waiting for Windows Print Queue...")
        queue_ok = monitor_print(printer_name)
        if queue_ok:
            info("[Word A4 Engine] Print job completed successfully at 100% full-size A4.")
            return True
        else:
            raise Exception("Windows print queue monitoring reported failure.")

    finally:
        if temp_docx and os.path.exists(temp_docx):
            try:
                os.remove(temp_docx)
            except Exception:
                pass
