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

    copies = int(
        job.get(
            "copies",
            1
        )
    )

    info(
        f"Printing Image : {file_path}"
    )

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