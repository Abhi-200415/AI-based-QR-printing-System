import os
import win32ui
import win32gui
import win32print
import win32con
from PIL import Image, ImageWin
import pypdfium2 as pdfium

from core.logger import info, warn, error


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


def print_pdf_native_gdi(
    printer_name: str,
    pdf_path: str,
    copies: int = 1,
    orientation: str = "PORTRAIT",
    page_ranges: str = None,
    color: bool = False
) -> bool:
    """
    Renders and prints a PDF document using Windows GDI device context scaling.
    This guarantees true 100% full-size A4 printing on all printer drivers,
    including the HP LaserJet Mono PCLmS Class Driver which mis-scales external GDI bitmaps.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pdf = pdfium.PdfDocument(pdf_path)
    total_pages = len(pdf)
    pages_to_print = parse_page_ranges(page_ranges, total_pages)
    
    info(f"[Native GDI Print] Opened PDF '{os.path.basename(pdf_path)}' ({total_pages} pages). Printing pages: {[p + 1 for p in pages_to_print]}")

    handle = win32print.OpenPrinter(printer_name)
    try:
        printer_info = win32print.GetPrinter(handle, 2)
        devmode = printer_info["pDevMode"]

        # Configure DEVMODE explicitly for A4 and orientation
        devmode.PaperSize = win32con.DMPAPER_A4
        devmode.Fields |= win32con.DM_PAPERSIZE

        is_landscape = (orientation or "PORTRAIT").upper() == "LANDSCAPE"
        if is_landscape:
            devmode.Orientation = win32con.DMORIENT_LANDSCAPE
        else:
            devmode.Orientation = win32con.DMORIENT_PORTRAIT
        devmode.Fields |= win32con.DM_ORIENTATION

        # Defensively sanitize driver-specific private data to force N-Up=1 and PaperSize=A4
        if hasattr(devmode, "DriverData") and devmode.DriverData:
            raw_data = devmode.DriverData
            if b"DocumentNUp\x004\x00" in raw_data:
                raw_data = raw_data.replace(b"DocumentNUp\x004\x00", b"DocumentNUp\x001\x00")
            elif b"DocumentNUp\x002\x00" in raw_data:
                raw_data = raw_data.replace(b"DocumentNUp\x002\x00", b"DocumentNUp\x001\x00")
            if b"PaperSize\x00LETTER\x00" in raw_data:
                raw_data = raw_data.replace(b"PaperSize\x00LETTER\x00", b"PaperSize\x00A4\x00\x00\x00\x00\x00")
            devmode.DriverData = raw_data

        # Create DC bound to customized DEVMODE
        h_dc = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
        hdc = win32ui.CreateDCFromHandle(h_dc)

        printable_w = hdc.GetDeviceCaps(win3con_horz := win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win3con_vert := win32con.VERTRES)
        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)

        info(
            f"[Native GDI Print] Printer DC initialized: "
            f"{printable_w}x{printable_h} px @ {dpi_x}x{dpi_y} DPI | Paper: A4 | Orientation: {'LANDSCAPE' if is_landscape else 'PORTRAIT'}"
        )

        doc_title = os.path.basename(pdf_path)

        for copy_idx in range(copies):
            if copies > 1:
                info(f"[Native GDI Print] Sending copy {copy_idx + 1} of {copies} to spooler...")

            hdc.StartDoc(doc_title)

            for page_idx in pages_to_print:
                page = pdf[page_idx]

                # Render page at 300 DPI for sharp output and optimal spool file size
                render_scale = 300.0 / 72.0
                pil_img = page.render(scale=render_scale).to_pil()

                # Handle color vs monochrome
                if not color:
                    pil_img = pil_img.convert("L").convert("RGB")
                else:
                    pil_img = pil_img.convert("RGB")

                img_w, img_h = pil_img.size

                # Auto-orient page to match DC printable bounds
                # If DC is portrait but page is landscape, rotate to maximize printable area
                if not is_landscape and img_w > img_h:
                    pil_img = pil_img.rotate(270, expand=True)
                    img_w, img_h = pil_img.size
                elif is_landscape and img_h > img_w:
                    pil_img = pil_img.rotate(270, expand=True)
                    img_w, img_h = pil_img.size

                # Compute scale to fit printable area while preserving aspect ratio
                scale_fit = min(printable_w / img_w, printable_h / img_h)
                target_w = int(img_w * scale_fit)
                target_h = int(img_h * scale_fit)

                # Center within printable area
                offset_x = (printable_w - target_w) // 2
                offset_y = (printable_h - target_h) // 2

                hdc.StartPage()
                dib = ImageWin.Dib(pil_img)
                # Draw directly stretched onto the full physical DC raster
                dib.draw(
                    hdc.GetHandleOutput(),
                    (offset_x, offset_y, offset_x + target_w, offset_y + target_h)
                )
                hdc.EndPage()

            hdc.EndDoc()

        del hdc
        win32gui.DeleteDC(h_dc)
        info(f"[Native GDI Print] Successfully spooled all {len(pages_to_print)} pages x {copies} copies.")
        return True

    finally:
        win32print.ClosePrinter(handle)
        pdf.close()


def print_image_native_gdi(
    printer_name: str,
    image_path: str,
    copies: int = 1,
    orientation: str = "PORTRAIT",
    color: bool = False
) -> bool:
    """
    Directly renders and prints an image file using Windows GDI device context scaling.
    Guarantees full-page A4 output.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    handle = win32print.OpenPrinter(printer_name)
    try:
        printer_info = win32print.GetPrinter(handle, 2)
        devmode = printer_info["pDevMode"]

        devmode.PaperSize = win32con.DMPAPER_A4
        devmode.Fields |= win32con.DM_PAPERSIZE

        is_landscape = (orientation or "PORTRAIT").upper() == "LANDSCAPE"
        if is_landscape:
            devmode.Orientation = win32con.DMORIENT_LANDSCAPE
        else:
            devmode.Orientation = win32con.DMORIENT_PORTRAIT
        devmode.Fields |= win32con.DM_ORIENTATION

        if not color:
            devmode.Color = win32con.DMCOLOR_MONOCHROME
            devmode.Fields |= win32con.DM_COLOR

        # Defensively sanitize driver-specific private data to force N-Up=1 and PaperSize=A4
        if hasattr(devmode, "DriverData") and devmode.DriverData:
            raw_data = devmode.DriverData
            if b"DocumentNUp\x004\x00" in raw_data:
                raw_data = raw_data.replace(b"DocumentNUp\x004\x00", b"DocumentNUp\x001\x00")
            elif b"DocumentNUp\x002\x00" in raw_data:
                raw_data = raw_data.replace(b"DocumentNUp\x002\x00", b"DocumentNUp\x001\x00")
            if b"PaperSize\x00LETTER\x00" in raw_data:
                raw_data = raw_data.replace(b"PaperSize\x00LETTER\x00", b"PaperSize\x00A4\x00\x00\x00\x00\x00")
            devmode.DriverData = raw_data

        h_dc = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
        hdc = win32ui.CreateDCFromHandle(h_dc)

        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)
        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)

        info(
            f"[Native GDI Print Image] DC: {printable_w}x{printable_h} px @ {dpi_x}x{dpi_y} DPI | "
            f"Paper: A4 | Orientation: {'LANDSCAPE' if is_landscape else 'PORTRAIT'}"
        )

        with Image.open(image_path) as img:
            if not color:
                pil_img = img.convert("L").convert("RGB")
            else:
                pil_img = img.convert("RGB")

            img_w, img_h = pil_img.size

            if not is_landscape and img_w > img_h:
                pil_img = pil_img.rotate(270, expand=True)
                img_w, img_h = pil_img.size
            elif is_landscape and img_h > img_w:
                pil_img = pil_img.rotate(270, expand=True)
                img_w, img_h = pil_img.size

            scale_fit = min(printable_w / img_w, printable_h / img_h)
            target_w = int(img_w * scale_fit)
            target_h = int(img_h * scale_fit)

            offset_x = (printable_w - target_w) // 2
            offset_y = (printable_h - target_h) // 2

            doc_title = os.path.basename(image_path)

            for copy_idx in range(copies):
                if copies > 1:
                    info(f"[Native GDI Print Image] Sending copy {copy_idx + 1} of {copies}...")

                hdc.StartDoc(doc_title)
                hdc.StartPage()
                dib = ImageWin.Dib(pil_img)
                dib.draw(
                    hdc.GetHandleOutput(),
                    (offset_x, offset_y, offset_x + target_w, offset_y + target_h)
                )
                hdc.EndPage()
                hdc.EndDoc()

        del hdc
        win32gui.DeleteDC(h_dc)
        info(f"[Native GDI Print Image] Successfully spooled image x {copies} copies.")
        return True

    finally:
        win32print.ClosePrinter(handle)
