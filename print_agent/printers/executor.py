import os
import subprocess
import tempfile
import time

import win32com.client

from core.logger import (
    info,
    error
)

from core.config import DOWNLOAD_FOLDER


# ==========================================================
# SumatraPDF Location
# ==========================================================

SUMATRA_PATH = os.path.join(
    os.getcwd(),
    "tools",
    "SumatraPDF.exe"
)


# ==========================================================
# Supported Extensions
# ==========================================================

SUPPORTED_FILES = [

    ".pdf",

    ".docx",

    ".txt",

    ".jpg",

    ".jpeg",

    ".png"

]


# ==========================================================
# Validate Print Job
# ==========================================================

def validate_job(job):

    required = [

        "job_id",

        "file_path",

        "printer_name"

    ]

    for key in required:

        if key not in job:

            raise Exception(
                f"Missing {key}"
            )

    if not os.path.exists(

        job["file_path"]

    ):

        raise Exception(
            "Downloaded file not found."
        )

    extension = os.path.splitext(

        job["file_path"]

    )[1].lower()

    if extension not in SUPPORTED_FILES:

        raise Exception(
            f"Unsupported file : {extension}"
        )

    return extension


# ==========================================================
# Execute Print Job
# ==========================================================

def print_file(job):

    try:

        extension = validate_job(job)

        info(
            f"Printing Job {job['job_id']}"
        )

        if extension == ".pdf":

            return print_pdf(job)

        elif extension == ".docx":

            return print_docx(job)

        elif extension in [

            ".jpg",

            ".jpeg",

            ".png"

        ]:

            return print_image(job)

        elif extension == ".txt":

            return print_text(job)

        else:

            raise Exception(
                "Unsupported File"
            )

    except Exception as e:

        error(str(e))

        return False


# ==========================================================
# PDF Printing
# ==========================================================

# ==========================================================
# PDF Printing (SumatraPDF)
# ==========================================================

def print_pdf(job):

    file_path = job["file_path"]

    printer_name = job["printer_name"]

    page_ranges = job.get(
        "page_ranges",
        None
    )

    copies = int(
        job.get(
            "copies",
            1
        )
    )

    orientation = job.get("orientation", "PORTRAIT")
    color = (job.get("print_type") or "").upper() == "COLOR"

    try:
        from printers.word_a4_executor import print_via_word_a4
        info(f"Attempting Word A4 print for guaranteed full-size A4: {file_path}")
        return print_via_word_a4(
            printer_name=printer_name,
            file_path=file_path,
            copies=copies,
            orientation=orientation,
            page_ranges=page_ranges
        )
    except Exception as we:
        warn(f"Word A4 print attempt failed ({we}). Trying native GDI fallback...")

    try:
        from printers.native_gdi_executor import print_pdf_native_gdi
        info(f"Attempting native GDI print for full-size A4: {file_path}")
        return print_pdf_native_gdi(
            printer_name=printer_name,
            pdf_path=file_path,
            copies=copies,
            orientation=orientation,
            page_ranges=page_ranges,
            color=color
        )
    except Exception as ne:
        warn(f"Native GDI print attempt failed ({ne}). Trying SumatraPDF fallback...")

    if not os.path.exists(
        SUMATRA_PATH
    ):
        raise Exception(
            "SumatraPDF.exe not found."
        )

    command = [

        SUMATRA_PATH,

        "-silent",

        "-print-to",

        printer_name

    ]

    # -----------------------------------------
    # Page Range
    # -----------------------------------------

    if page_ranges:

        command.extend([

            "-print-settings",

            page_ranges

        ])

    command.append(
        file_path
    )

    info(
        f"Printing PDF : {file_path}"
    )

    info(
        f"Printer : {printer_name}"
    )

    if page_ranges:

        info(
            f"Pages : {page_ranges}"
        )

    # -----------------------------------------
    # Copies
    # -----------------------------------------

    for i in range(copies):

        process = subprocess.run(

            command,

            capture_output=True,

            text=True

        )

        if process.returncode != 0:

            raise Exception(

                process.stderr

            )

    info(
        "PDF printed successfully."
    )

    return True
# ==========================================================
# DOCX Printing
# ==========================================================

# ==========================================================
# DOCX Printing
# ==========================================================

def print_docx(job):

    file_path = job["file_path"]

    printer_name = job["printer_name"]

    copies = int(
        job.get(
            "copies",
            1
        )
    )

    info(
        f"Printing DOCX : {file_path}"
    )

    try:

        word = win32com.client.Dispatch(
            "Word.Application"
        )

        word.Visible = False

        word.ActivePrinter = printer_name

        document = word.Documents.Open(
            os.path.abspath(file_path)
        )

        # Enforce target paper size (A4 default) and orientation
        try:
            paper_size_req = (job.get("paper_size") or "A4").upper()
            wd_paper_map = {"A4": 9, "A3": 8, "LEGAL": 5, "LETTER": 2}
            wd_paper = wd_paper_map.get(paper_size_req, 9)

            ori_req = (job.get("orientation") or "PORTRAIT").upper()
            wd_ori = 1 if ori_req == "PORTRAIT" else 2

            for s in document.Sections:
                s.PageSetup.PaperSize = wd_paper
                s.PageSetup.Orientation = wd_ori
        except Exception as pe:
            pass

        for _ in range(copies):

            document.PrintOut(
                Background=False
            )

        document.Close(False)

        word.Quit()

        info(
            "DOCX printed successfully."
        )

        return True

    except Exception as e:

        error(str(e))

        try:
            word.Quit()
        except:
            pass

        return False


# ==========================================================
# Image Printing
# ==========================================================

def print_image(job):

    file_path = job["file_path"]

    printer_name = job["printer_name"]

    copies = int(
        job.get(
            "copies",
            1
        )
    )

    orientation = job.get("orientation", "PORTRAIT")
    color = (job.get("print_type") or "").upper() == "COLOR"

    info(
        f"Printing Image : {file_path}"
    )

    try:
        from printers.word_a4_executor import print_via_word_a4
        info(f"Attempting Word A4 print for full-size A4 image: {file_path}")
        return print_via_word_a4(
            printer_name=printer_name,
            file_path=file_path,
            copies=copies,
            orientation=orientation
        )
    except Exception as we:
        warn(f"Word A4 image print failed ({we}). Trying native GDI fallback...")

    try:
        from printers.native_gdi_executor import print_image_native_gdi
        info(f"Attempting native GDI print for full-size A4 image: {file_path}")
        return print_image_native_gdi(
            printer_name=printer_name,
            image_path=file_path,
            copies=copies,
            orientation=orientation,
            color=color
        )
    except Exception as ie:
        warn(f"Native GDI image print failed ({ie}). Falling back to shell print...")

    try:

        for _ in range(copies):

            os.startfile(
                file_path,
                "print"
            )

            time.sleep(3)

        info(
            "Image printed successfully."
        )

        return True

    except Exception as e:

        error(str(e))

        return False


# ==========================================================
# Text Printing
# ==========================================================

def print_text(job):

    file_path = job["file_path"]

    copies = int(
        job.get(
            "copies",
            1
        )
    )

    info(
        f"Printing Text : {file_path}"
    )

    try:

        for _ in range(copies):

            os.startfile(
                file_path,
                "print"
            )

            time.sleep(2)

        info(
            "Text printed successfully."
        )

        return True

    except Exception as e:

        error(str(e))

        return False

# ==========================================================
# Check SumatraPDF
# ==========================================================

def sumatra_available():

    return os.path.exists(
        SUMATRA_PATH
    )


# ==========================================================
# Check Microsoft Word
# ==========================================================

def word_available():

    try:

        word = win32com.client.Dispatch(
            "Word.Application"
        )

        word.Quit()

        return True

    except Exception:

        return False


# ==========================================================
# Printer Exists
# ==========================================================

def printer_exists(printer_name):

    try:

        import win32print

        printers = win32print.EnumPrinters(

            win32print.PRINTER_ENUM_LOCAL
            |
            win32print.PRINTER_ENUM_CONNECTIONS

        )

        for printer in printers:

            if printer["pPrinterName"] == printer_name:

                return True

        return False

    except Exception:

        return False


# ==========================================================
# Validate Environment
# ==========================================================

def validate_environment():

    if not sumatra_available():

        raise Exception(
            "SumatraPDF.exe not found inside tools folder."
        )

    if not word_available():

        info(
            "Microsoft Word not detected. DOCX printing unavailable."
        )

    info(
        "Printing environment validated."
    )

    return True


# ==========================================================
# Safe Close Word
# ==========================================================

def close_word(word):

    try:

        if word:

            word.Quit()

    except Exception:

        pass


# ==========================================================
# Print Information
# ==========================================================

def print_summary(job):

    info("=" * 60)

    info(f"Job ID       : {job.get('job_id')}")

    info(f"Printer      : {job.get('printer_name')}")

    info(f"File         : {job.get('file_path')}")

    info(f"Copies       : {job.get('copies',1)}")

    info(f"Duplex       : {job.get('duplex',False)}")

    info(f"Paper Size   : {job.get('paper_size','A4')}")

    info(f"Orientation  : {job.get('orientation','PORTRAIT')}")

    info(f"Page Range   : {job.get('page_ranges','ALL')}")

    info("=" * 60)


# ==========================================================
# Executor Ready
# ==========================================================

validate_environment()