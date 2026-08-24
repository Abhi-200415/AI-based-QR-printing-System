import win32print


# ==========================================================
# Virtual Printer Detection
# ==========================================================

def is_virtual_printer(printer_name: str) -> bool:

    name = printer_name.lower()

    virtual_keywords = (
        "microsoft print to pdf",
        "onenote",
        "fax",
        "xps document writer",
        "send to kindle",
        "pdf",
        "onenote desktop"
    )

    return any(
        keyword in name
        for keyword in virtual_keywords
    )


# ==========================================================
# Windows Printer Status
# ==========================================================

def get_printer_status(printer_name: str):

    try:

        handle = win32print.OpenPrinter(
            printer_name
        )

        try:

            printer_info = win32print.GetPrinter(
                handle,
                2
            )

            status = printer_info.get(
                "Status",
                0
            )

            attributes = printer_info.get(
                "Attributes",
                0
            )

            # ------------------------------------------------
            # Windows Status Flags
            # ------------------------------------------------

            status_flags = {

                "paused":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_PAUSED
                    ),

                "error":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_ERROR
                    ),

                "pending_deletion":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_PENDING_DELETION
                    ),

                "paper_jam":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_PAPER_JAM
                    ),

                "paper_out":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_PAPER_OUT
                    ),

                "offline":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_OFFLINE
                    ),

                "busy":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_BUSY
                    ),

                "printing":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_PRINTING
                    ),

                "output_bin_full":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_OUTPUT_BIN_FULL
                    ),

                "not_available":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_NOT_AVAILABLE
                    ),

                "waiting":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_WAITING
                    ),

                "processing":
                    bool(
                        status &
                        win32print.PRINTER_STATUS_PROCESSING
                    )
            }

            # ------------------------------------------------
            # Determine Hardware Availability
            # ------------------------------------------------

            unavailable = (
                status_flags["paused"]
                or status_flags["error"]
                or status_flags["pending_deletion"]
                or status_flags["paper_jam"]
                or status_flags["paper_out"]
                or status_flags["offline"]
                or status_flags["not_available"]
                or status_flags["output_bin_full"]
            )

            busy = (
                status_flags["busy"]
                or status_flags["printing"]
                or status_flags["processing"]
            )

            if unavailable:

                printer_status = "Offline"

            elif busy:

                printer_status = "Busy"

            else:

                printer_status = "Online"

            return {

                "status": printer_status,

                "is_available":
                    not unavailable,

                "windows_status":
                    status,

                "attributes":
                    attributes,

                "status_flags":
                    status_flags
            }

        finally:

            win32print.ClosePrinter(
                handle
            )

    except Exception as e:

        return {

            "status": "Offline",

            "is_available": False,

            "windows_status": None,

            "attributes": None,

            "status_flags": {},

            "error": str(e)
        }


# ==========================================================
# Get Printer Capabilities
# ==========================================================

def get_printer_capabilities(
    printer_name: str
):

    virtual = is_virtual_printer(
        printer_name
    )

    printer_status = get_printer_status(
        printer_name
    )

    # ======================================================
    # Base Information
    # ======================================================

    capabilities = {

        "printer_name":
            printer_name,

        "is_virtual":
            virtual,

        "is_physical":
            not virtual,

        "status":
            printer_status["status"],

        "is_available":
            (
                printer_status["is_available"]
                and not virtual
            ),

        "windows_status":
            printer_status["windows_status"],

        "status_flags":
            printer_status["status_flags"],

        "supports_bw":
            True,

        "supports_color":
            False,

        "supports_duplex":
            False,

        "supports_a3":
            False,

        "supports_legal":
            False
    }

    # ======================================================
    # Virtual Printers
    # ======================================================

    if virtual:

        capabilities["status"] = "Online"

        capabilities["is_available"] = False

        return capabilities

    # ======================================================
    # Physical Printer Capabilities
    # ======================================================

    try:

        handle = win32print.OpenPrinter(
            printer_name
        )

        try:

            # ------------------------------------------------
            # Color
            # ------------------------------------------------

            try:

                color = win32print.DeviceCapabilities(
                    printer_name,
                    None,
                    win32print.DC_COLORDEVICE
                )

                capabilities[
                    "supports_color"
                ] = bool(color)

            except Exception:

                capabilities[
                    "supports_color"
                ] = False

            # ------------------------------------------------
            # Paper Sizes
            # ------------------------------------------------

            try:

                papers = win32print.DeviceCapabilities(
                    printer_name,
                    None,
                    win32print.DC_PAPERS
                )

                if papers:

                    capabilities[
                        "supports_a3"
                    ] = 8 in papers

                    capabilities[
                        "supports_legal"
                    ] = 5 in papers

            except Exception:

                pass

            # ------------------------------------------------
            # Duplex
            # ------------------------------------------------

            try:

                duplex = win32print.DeviceCapabilities(
                    printer_name,
                    None,
                    win32print.DC_DUPLEX
                )

                capabilities[
                    "supports_duplex"
                ] = bool(duplex)

            except Exception:

                capabilities[
                    "supports_duplex"
                ] = False

        finally:

            win32print.ClosePrinter(
                handle
            )

    except Exception as e:

        print(
            f"Capability detection failed: {e}"
        )

    return capabilities


# ==========================================================
# Display Capabilities
# ==========================================================

def display_capabilities(
    printer_name: str
):

    data = get_printer_capabilities(
        printer_name
    )

    print()
    print("=" * 60)
    print("PRINTER INFORMATION")
    print("=" * 60)

    print(
        f"Name          : "
        f"{data['printer_name']}"
    )

    print(
        f"Physical      : "
        f"{data['is_physical']}"
    )

    print(
        f"Virtual       : "
        f"{data['is_virtual']}"
    )

    print(
        f"Status        : "
        f"{data['status']}"
    )

    print(
        f"Available     : "
        f"{data['is_available']}"
    )

    print(
        f"B/W           : "
        f"{data['supports_bw']}"
    )

    print(
        f"Color         : "
        f"{data['supports_color']}"
    )

    print(
        f"Duplex        : "
        f"{data['supports_duplex']}"
    )

    print(
        f"A3            : "
        f"{data['supports_a3']}"
    )

    print(
        f"Legal         : "
        f"{data['supports_legal']}"
    )

    print("=" * 60)