import subprocess
import re


def get_windows_printers():
    """
    Return Windows printer information.
    Works on the Windows machine running the print agent.
    """

    try:

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Printer | Select-Object Name,PrinterStatus,WorkOffline,PortName | ConvertTo-Json"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        output = result.stdout.strip()

        if not output:
            return []

        import json

        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

        return data

    except Exception:
        return []


def is_usb_printer_present(printer_name: str) -> bool:
    """
    Check whether a physical USB printer with the given
    Windows printer name is currently present.
    """

    try:

        command = f'''
        Get-PnpDevice -PresentOnly |
        Where-Object {{
            $_.Class -eq "USB" -and
            $_.FriendlyName -like "*{printer_name}*"
        }} |
        Select-Object Status,FriendlyName,InstanceId |
        ConvertTo-Json
        '''

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                command
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False

        output = result.stdout.strip()

        if not output:
            return False

        return True

    except Exception:
        return False


def check_printer_available(
    printer_name: str,
    printer_type: str | None = None
) -> bool:
    """
    Determine whether a Windows printer is actually available.

    USB:
        Requires physical USB PnP presence.

    Network:
        Uses Windows printer status and WorkOffline.

    Other:
        Uses Windows printer status.
    """

    printers = get_windows_printers()

    target = None

    for printer in printers:

        if printer.get("Name") == printer_name:

            target = printer
            break

    if not target:
        return False

    work_offline = target.get("WorkOffline")

    if work_offline is True:
        return False

    port = str(
        target.get("PortName") or ""
    )

    # USB printer
    if port.upper().startswith("USB"):

        return is_usb_printer_present(
            printer_name
        )

    # Network / WSD printer
    status = str(
        target.get("PrinterStatus") or ""
    )

    if status.lower() not in (
        "normal",
        "online"
    ):
        return False

    return True
