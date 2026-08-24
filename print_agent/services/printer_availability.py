import subprocess
import json


def run_powershell(command: str, timeout: int = 10):

    try:

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                command
            ],
            capture_output=True,
            text=True,
            timeout=timeout
        )

    except Exception:

        return None

    if result.returncode != 0:

        return None

    output = result.stdout.strip()

    if not output:

        return None

    try:

        return json.loads(output)

    except Exception:

        return None


def get_windows_printer(printer_name: str):

    command = (
        "Get-Printer -Name "
        f'"{printer_name}" '
        "| Select-Object Name,PrinterStatus,"
        "WorkOffline,PortName,DriverName "
        "| ConvertTo-Json -Compress"
    )

    return run_powershell(command)


def get_pnp_devices(printer_name: str):

    command = (
        "Get-PnpDevice -PresentOnly | "
        "Where-Object { "
        f'$_.FriendlyName -like "*{printer_name}*" '
        "} | "
        "Select-Object Status,Class,FriendlyName,InstanceId "
        "| ConvertTo-Json -Compress"
    )

    result = run_powershell(command)

    if result is None:

        return []

    if isinstance(result, dict):

        return [result]

    if isinstance(result, list):

        return result

    return []


def get_usb_pnp_devices():

    command = (
        "Get-PnpDevice -PresentOnly | "
        "Where-Object { "
        '$_.Class -eq "USB" '
        "} | "
        "Select-Object Status,Class,FriendlyName,InstanceId "
        "| ConvertTo-Json -Compress"
    )

    result = run_powershell(command)

    if result is None:

        return []

    if isinstance(result, dict):

        return [result]

    if isinstance(result, list):

        return result

    return []


def is_printer_queue_available(
    printer: dict
) -> bool:

    if not printer:

        return False

    # Explicit Windows offline flag
    if printer.get("WorkOffline") is True:

        return False

    # PrinterStatus is driver-dependent.
    #
    # Some Windows printer drivers expose:
    #
    #     PrinterStatus = 0
    #
    # even when the queue is usable.
    #
    # Therefore we do NOT require a specific "Normal"
    # or "Online" value here.
    #
    # The existence of the Windows printer queue plus
    # absence of an explicit offline state is sufficient
    # for network/WSD printers.

    status = printer.get("PrinterStatus")

    if isinstance(status, str):

        normalized = status.lower().strip()

        if normalized in (
            "offline",
            "error",
            "unknown offline"
        ):

            return False

    return True

def is_usb_printer_present(
    printer_name: str
) -> bool:

    devices = get_pnp_devices(
        printer_name
    )

    for device in devices:

        status = str(
            device.get("Status") or ""
        ).lower()

        device_class = str(
            device.get("Class") or ""
        ).lower()

        if (
            status == "ok"
            and
            device_class == "usb"
        ):

            return True

    return False


def verify_physical_printer(
    printer_name: str
) -> bool:

    # ------------------------------------------------------
    # Step 1
    # Windows printer queue must exist
    # ------------------------------------------------------

    printer = get_windows_printer(
        printer_name
    )

    if not printer:

        return False

    # ------------------------------------------------------
    # Step 2
    # Windows queue must not be offline
    # ------------------------------------------------------

    if not is_printer_queue_available(
        printer
    ):

        return False

    # ------------------------------------------------------
    # Step 3
    # Determine printer connection type
    # ------------------------------------------------------

    port = str(
        printer.get("PortName") or ""
    ).upper()

    # ------------------------------------------------------
    # USB
    # ------------------------------------------------------

    if port.startswith("USB"):

        return is_usb_printer_present(
            printer_name
        )

    # ------------------------------------------------------
    # WSD / Ethernet / TCP-IP / Network
    #
    # Windows normally exposes these through the
    # installed printer queue. If the queue is online,
    # accept it as available.
    # ------------------------------------------------------

    return True


def is_printer_available(
    printer_name: str
) -> bool:

    return verify_physical_printer(
        printer_name
    )


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage: python printer_availability.py "
            '"Printer Name"'
        )

        raise SystemExit(1)

    printer_name = sys.argv[1]

    result = verify_physical_printer(
        printer_name
    )

    print(
        json.dumps(
            {
                "printer_name":
                    printer_name,

                "available":
                    result
            },
            indent=2
        )
    )

