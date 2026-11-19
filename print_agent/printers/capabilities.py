import socket
try:
    import winreg
except ImportError:
    winreg = None

try:
    import win32print
except ImportError:
    win32print = None


# ==========================================================
# Hardware Port Connectivity Check
# ==========================================================

def check_hardware_port_active(port_name: str) -> bool:
    """
    Checks whether a Windows printer port corresponds to an active,
    physically attached hardware device or reachable network printer.
    """
    if not port_name or winreg is None:
        return True

    port = str(port_name).upper().strip()

    # 1. Virtual / output prompt ports
    if port in ("FILE:", "PORTPROMPT:", "NUL:", "NULL:", "NUL"):
        return False

    # 2. Legacy parallel ports (LPT1:, LPT2:, LPT3:, etc.)
    if port.startswith("LPT"):
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\PARALLEL PORTS")
            sub_count, val_count, _ = winreg.QueryInfoKey(k)
            winreg.CloseKey(k)
            if val_count == 0 and sub_count == 0:
                return False
        except OSError:
            # Motherboard has no physical parallel port hardware
            return False

    # 3. Legacy serial ports (COM1:, COM2:, etc.)
    if port.startswith("COM"):
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
            vals = []
            i = 0
            while True:
                try:
                    _, val, _ = winreg.EnumValue(k, i)
                    vals.append(str(val).upper().rstrip(":"))
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(k)
            if port.rstrip(":") not in vals:
                return False
        except OSError:
            return False

    # 4. USB Ports (USB001, USB002, etc.)
    if port.startswith("USB"):
        active_usb = set()
        usbprint_path = r"SYSTEM\CurrentControlSet\Enum\USBPRINT"
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, usbprint_path)
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                    sub_k = winreg.OpenKey(root, sub)
                    j = 0
                    while True:
                        try:
                            inst = winreg.EnumKey(sub_k, j)
                            inst_k = winreg.OpenKey(sub_k, inst)
                            try:
                                cf, _ = winreg.QueryValueEx(inst_k, "ConfigFlags")
                            except OSError:
                                cf = 0
                            if cf == 0:
                                try:
                                    dp = winreg.OpenKey(inst_k, "Device Parameters")
                                    pname, _ = winreg.QueryValueEx(dp, "PortName")
                                    active_usb.add(str(pname).upper().strip())
                                    winreg.CloseKey(dp)
                                except OSError:
                                    pass
                                for part in inst.split("&"):
                                    if part.upper().startswith("USB"):
                                        active_usb.add(part.upper().strip())
                            winreg.CloseKey(inst_k)
                            j += 1
                        except OSError:
                            break
                    winreg.CloseKey(sub_k)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(root)
        except OSError:
            pass

        if port not in active_usb and port.rstrip(":") not in active_usb:
            return False

    # 5. TCP/IP Network Ports
    if port.startswith("IP_") or (port.replace(".", "").isdigit() and "." in port):
        ip = port[3:] if port.startswith("IP_") else port
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((ip, 9100))
            s.close()
        except Exception:
            return False

    return True


# ==========================================================
# Virtual Printer Detection
# ==========================================================

def is_virtual_printer(printer_name: str) -> bool:

    name = printer_name.lower().strip()

    virtual_keywords = (
        "microsoft print to pdf",
        "onenote",
        "fax",
        "xps document writer",
        "send to kindle",
        "pdf",
        "onenote desktop",
        "anydesk printer",
        "cuteftp",
        "root print queue",
        "print to pdf",
        "adobe pdf",
        "foxit",
        "nitro",
        "pdfcreator",
        "bullzip",
        "do_pdf",
        "dopdf",
        "pdf24"
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

            port_name = printer_info.get(
                "pPortName",
                ""
            )

            is_virtual = is_virtual_printer(printer_name)
            port_active = check_hardware_port_active(port_name) if not is_virtual else True

            # ------------------------------------------------
            # Windows Status Flags & Attributes
            # ------------------------------------------------

            # PRINTER_ATTRIBUTE_WORK_OFFLINE = 0x00000400 (1024)
            is_work_offline = bool(attributes & 0x00000400)

            status_flags = {

                "work_offline":
                    is_work_offline,

                "port_disconnected":
                    not port_active,

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
                    ) or is_work_offline or (not port_active),

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
                or status_flags["port_disconnected"]
                or is_work_offline
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