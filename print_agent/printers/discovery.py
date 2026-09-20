import sys
from typing import List, Dict, Any

try:
    import win32print
except ImportError:
    win32print = None

from printers.capabilities import (
    get_printer_capabilities
)
from core.logger import (
    info,
    error
)


# ==========================================================
# Discover Installed Printers
# ==========================================================

def discover_printers() -> List[Dict[str, Any]]:
    if win32print is None:
        info("win32print not available (non-Windows environment). Returning simulated printer discovery.")
        return []

    printers = []

    try:
        default_printer = win32print.GetDefaultPrinter()

        installed_printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS,
            None,
            2
        )

        for printer in installed_printers:
            printer_name = printer["pPrinterName"]
            capability = get_printer_capabilities(printer_name)

            capability["is_default"] = (printer_name == default_printer)

            if capability.get("is_virtual"):
                capability["printer_type"] = "VIRTUAL"
            else:
                capability["printer_type"] = "PHYSICAL"

            printers.append(capability)

        info(f"{len(printers)} printer(s) detected.")

    except Exception as e:
        error(f"Printer discovery failed : {e}")

    return printers


# ==========================================================
# Get Physical Available Printers
# ==========================================================

def get_available_physical_printers():
    printers = discover_printers()
    return [
        printer for printer in printers
        if printer.get("is_physical", False) and printer.get("is_available", False)
    ]


def get_physical_printers():
    printers = discover_printers()
    return [
        printer for printer in printers
        if printer.get("is_physical", False)
    ]


def get_virtual_printers():
    printers = discover_printers()
    return [
        printer for printer in printers
        if printer.get("is_virtual", False)
    ]