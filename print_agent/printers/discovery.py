import win32print

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

def discover_printers():

    printers = []

    try:

        default_printer = (
            win32print.GetDefaultPrinter()
        )

        installed_printers = (
            win32print.EnumPrinters(

                win32print.PRINTER_ENUM_LOCAL
                | win32print.PRINTER_ENUM_CONNECTIONS,

                None,

                2

            )
        )

        for printer in installed_printers:

            printer_name = (
                printer["pPrinterName"]
            )

            capability = (
                get_printer_capabilities(
                    printer_name
                )
            )

            # --------------------------------------------------
            # Default Printer
            # --------------------------------------------------

            capability["is_default"] = (

                printer_name
                ==
                default_printer

            )

            # --------------------------------------------------
            # Printer Type
            # --------------------------------------------------

            if capability.get("is_virtual"):

                capability["printer_type"] = (
                    "VIRTUAL"
                )

            else:

                capability["printer_type"] = (
                    "PHYSICAL"
                )

            printers.append(
                capability
            )

        info(
            f"{len(printers)} printer(s) detected."
        )

    except Exception as e:

        error(
            f"Printer discovery failed : {e}"
        )

    return printers


# ==========================================================
# Get Physical Available Printers
# ==========================================================

def get_available_physical_printers():

    printers = discover_printers()

    available = [

        printer

        for printer in printers

        if (
            printer.get("is_physical", False)
            and
            printer.get("is_available", False)
        )

    ]

    return available


# ==========================================================
# Get Physical Printers
# ==========================================================

def get_physical_printers():

    printers = discover_printers()

    return [

        printer

        for printer in printers

        if printer.get(
            "is_physical",
            False
        )

    ]


# ==========================================================
# Get Virtual Printers
# ==========================================================

def get_virtual_printers():

    printers = discover_printers()

    return [

        printer

        for printer in printers

        if printer.get(
            "is_virtual",
            False
        )

    ]


# ==========================================================
# Display Installed Printers
# ==========================================================

def display_printers():

    printers = discover_printers()

    print()
    print("=" * 70)
    print("DETECTED PRINTERS")
    print("=" * 70)

    for printer in printers:

        print(
            f"Name        : "
            f"{printer.get('printer_name')}"
        )

        print(
            f"Type        : "
            f"{printer.get('printer_type')}"
        )

        print(
            f"Physical    : "
            f"{printer.get('is_physical')}"
        )

        print(
            f"Virtual     : "
            f"{printer.get('is_virtual')}"
        )

        print(
            f"Status      : "
            f"{printer.get('status')}"
        )

        print(
            f"Available   : "
            f"{printer.get('is_available')}"
        )

        print(
            f"Default     : "
            f"{printer.get('is_default')}"
        )

        print(
            f"B/W         : "
            f"{printer.get('supports_bw')}"
        )

        print(
            f"Color       : "
            f"{printer.get('supports_color')}"
        )

        print(
            f"Duplex      : "
            f"{printer.get('supports_duplex')}"
        )

        print(
            f"A3          : "
            f"{printer.get('supports_a3')}"
        )

        print(
            f"Legal       : "
            f"{printer.get('supports_legal')}"
        )

        print("-" * 70)

    # ------------------------------------------------------
    # Summary
    # ------------------------------------------------------

    physical = [

        printer

        for printer in printers

        if printer.get(
            "is_physical",
            False
        )

    ]

    virtual = [

        printer

        for printer in printers

        if printer.get(
            "is_virtual",
            False
        )

    ]

    available = [

        printer

        for printer in printers

        if (
            printer.get(
                "is_physical",
                False
            )
            and
            printer.get(
                "is_available",
                False
            )
        )

    ]

    print()
    print("=" * 70)
    print("PRINTER SUMMARY")
    print("=" * 70)

    print(
        f"Total detected             : "
        f"{len(printers)}"
    )

    print(
        f"Physical printers          : "
        f"{len(physical)}"
    )

    print(
        f"Virtual printers           : "
        f"{len(virtual)}"
    )

    print(
        f"Physical available         : "
        f"{len(available)}"
    )

    print("=" * 70)