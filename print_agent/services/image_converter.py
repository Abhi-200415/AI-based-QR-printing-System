import os
from PIL import Image, ImageOps

from core.logger import info, error, warn


# Standard paper dimensions at 300 DPI
PAPER_DIMENSIONS_300DPI = {
    "A4": (2480, 3508),
    "A3": (3508, 4960),
    "LEGAL": (2550, 4200),
    "LETTER": (2550, 3300),
}


def convert_image_to_printable_pdf(
    image_path: str,
    paper_size: str = "A4",
    orientation: str = "PORTRAIT"
) -> tuple[str, str]:
    """
    Converts any raster image (PNG, JPG, BMP, etc.) into an exact full-page PDF
    rendered at 300 DPI for the target paper size (default A4).

    The image is scaled to fit the full printable page area while preserving its
    aspect ratio, composited cleanly over a white background (handling alpha
    channels/transparency), and centered with hardware safety margins.

    Returns:
        (pdf_path, effective_orientation)
    """
    try:
        with Image.open(image_path) as raw_img:
            # Respect mobile camera EXIF orientation metadata
            img = ImageOps.exif_transpose(raw_img)

            # Handle alpha channel and transparency by compositing over pure white
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Determine canvas dimensions
            paper_key = (paper_size or "A4").upper()
            canvas_w, canvas_h = PAPER_DIMENSIONS_300DPI.get(paper_key, (2480, 3508))

            img_w, img_h = img.size
            eff_orientation = (orientation or "AUTO").upper()

            if eff_orientation == "AUTO":
                eff_orientation = "LANDSCAPE" if img_w > img_h else "PORTRAIT"

            if eff_orientation == "LANDSCAPE":
                canvas_w, canvas_h = max(canvas_w, canvas_h), min(canvas_w, canvas_h)
            else:
                canvas_w, canvas_h = min(canvas_w, canvas_h), max(canvas_w, canvas_h)

            # Hardware margin to avoid edge clipping by printer physical rollers
            # 60 pixels ≈ 5 mm at 300 DPI
            margin = 60
            avail_w = max(100, canvas_w - (2 * margin))
            avail_h = max(100, canvas_h - (2 * margin))

            # Scale to fit full page
            scale = min(avail_w / img_w, avail_h / img_h)
            new_w = max(1, int(img_w * scale))
            new_h = max(1, int(img_h * scale))

            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Center image on canvas
            page = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
            paste_x = (canvas_w - new_w) // 2
            paste_y = (canvas_h - new_h) // 2
            page.paste(resized, (paste_x, paste_y))

            # Save as 300 DPI PDF
            clean_base = os.path.splitext(image_path)[0]
            out_pdf = f"{clean_base}_fullpage.pdf"
            page.save(out_pdf, "PDF", resolution=300.0)

            info(
                f"Converted image '{os.path.basename(image_path)}' to full-size "
                f"{paper_key} PDF ({canvas_w}x{canvas_h}px @ 300DPI, {eff_orientation})"
            )
            return out_pdf, eff_orientation

    except Exception as e:
        error(f"Failed to convert image to full-page PDF: {e}")
        raise
