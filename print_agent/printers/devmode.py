import win32print
import pywintypes

from core.logger import (
    info,
    error
)

# ==========================================================
# Open Printer
# ==========================================================

def open_printer(printer_name):

    try:

        return win32print.OpenPrinter(
            printer_name
        )

    except Exception as e:

        error(
            f"Unable to open printer : {e}"
        )

        raise


# ==========================================================
# Close Printer
# ==========================================================

def close_printer(handle):

    try:

        win32print.ClosePrinter(
            handle
        )

    except Exception:

        pass


# ==========================================================
# Get Current DEVMODE
# ==========================================================

def get_devmode(printer_name):

    handle = open_printer(
        printer_name
    )

    try:

        printer_info = win32print.GetPrinter(
            handle,
            2
        )

        devmode = printer_info["pDevMode"]

        info(
            "Current DEVMODE Loaded"
        )

        return handle, printer_info, devmode

    except Exception as e:

        close_printer(handle)

        error(str(e))

        raise


# ==========================================================
# Save Original DEVMODE
# ==========================================================

def backup_devmode(devmode):

    backup = pywintypes.DEVMODEType()

    backup.Fields = devmode.Fields

    backup.Orientation = devmode.Orientation

    backup.PaperSize = devmode.PaperSize

    backup.Copies = devmode.Copies

    backup.Color = devmode.Color

    backup.Duplex = devmode.Duplex

    backup.PrintQuality = devmode.PrintQuality

    return backup


# ==========================================================
# Restore Original DEVMODE
# ==========================================================

def restore_devmode(

    handle,

    printer_info,

    backup

):

    try:

        printer_info["pDevMode"] = backup

        win32print.SetPrinter(

            handle,

            2,

            printer_info,

            0

        )

        info(
            "Printer Settings Restored"
        )

    except Exception as e:

        error(str(e))


# ==========================================================
# Apply DEVMODE
# ==========================================================

def apply_devmode(

    handle,

    printer_info,

    devmode

):

    try:

        printer_info["pDevMode"] = devmode

        win32print.SetPrinter(

            handle,

            2,

            printer_info,

            0

        )

        info(
            "Printer Settings Applied"
        )

    except Exception as e:

        error(str(e))

        raise

# ==========================================================
# Windows Constants
# ==========================================================

# Orientation
ORIENTATION_PORTRAIT = 1
ORIENTATION_LANDSCAPE = 2

# Color
COLOR_MONOCHROME = 1
COLOR_COLOR = 2

# Duplex
DUPLEX_SIMPLEX = 1
DUPLEX_VERTICAL = 2
DUPLEX_HORIZONTAL = 3

# Paper Size
PAPER_A4 = 9
PAPER_A3 = 8
PAPER_LEGAL = 5

# ==========================================================
# Apply Orientation
# ==========================================================

def set_orientation(devmode, orientation):

    if not orientation:
        return

    orientation = orientation.upper()

    if orientation == "PORTRAIT":

        devmode.Orientation = ORIENTATION_PORTRAIT

    elif orientation == "LANDSCAPE":

        devmode.Orientation = ORIENTATION_LANDSCAPE

    info(f"Orientation : {orientation}")


# ==========================================================
# Apply Paper Size
# ==========================================================

def set_paper_size(devmode, paper_size):

    if not paper_size:
        return

    paper_size = paper_size.upper()

    if paper_size == "A4":

        devmode.PaperSize = PAPER_A4

    elif paper_size == "A3":

        devmode.PaperSize = PAPER_A3

    elif paper_size == "LEGAL":

        devmode.PaperSize = PAPER_LEGAL

    info(f"Paper Size : {paper_size}")


# ==========================================================
# Apply Duplex
# ==========================================================

def set_duplex(devmode, duplex):

    if duplex:

        devmode.Duplex = DUPLEX_VERTICAL

        info("Duplex Enabled")

    else:

        devmode.Duplex = DUPLEX_SIMPLEX

        info("Simplex Enabled")


# ==========================================================
# Apply Color Mode
# ==========================================================

def set_color(devmode, print_type):

    if not print_type:
        return

    print_type = print_type.upper()

    if print_type == "COLOR":

        devmode.Color = COLOR_COLOR

        info("Color Printing")

    else:

        devmode.Color = COLOR_MONOCHROME

        info("Black & White Printing")


# ==========================================================
# Apply Copies
# ==========================================================

def set_copies(devmode, copies):

    if copies and copies > 0:

        devmode.Copies = copies

        info(f"Copies : {copies}")


# ==========================================================
# Apply Print Quality
# ==========================================================

def set_print_quality(devmode, quality="HIGH"):

    quality = quality.upper()

    if quality == "HIGH":

        devmode.PrintQuality = -4

    elif quality == "MEDIUM":

        devmode.PrintQuality = -3

    elif quality == "LOW":

        devmode.PrintQuality = -2

    info(f"Quality : {quality}")


# ==========================================================
# Configure Printer
# ==========================================================

def configure_printer(printer_name, job):

    handle, printer_info, devmode = get_devmode(
        printer_name
    )

    backup = backup_devmode(devmode)

    set_orientation(

        devmode,

        job.get("orientation")

    )

    set_paper_size(

        devmode,

        job.get("paper_size")

    )

    set_duplex(

        devmode,

        job.get("duplex")

    )

    set_color(

        devmode,

        job.get("print_type")

    )

    set_copies(

        devmode,

        job.get("copies")

    )

    set_print_quality(

        devmode,

        "HIGH"

    )

    apply_devmode(

        handle,

        printer_info,

        devmode

    )

    return handle, printer_info, backup