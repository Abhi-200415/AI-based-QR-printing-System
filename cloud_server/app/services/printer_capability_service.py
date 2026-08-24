import subprocess
import json
import xml.etree.ElementTree as ET


PSF = "{http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework}"


def get_print_configuration(printer_name: str):
    command = (
        f'Get-PrintConfiguration -PrinterName '
        f'"{printer_name}" | ConvertTo-Json -Compress'
    )

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
            timeout=30
        )

    except subprocess.TimeoutExpired:

        return None

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

def get_printer_capabilities(printer_name: str):
    config = get_print_configuration(printer_name)

    if not config:
        return {
            "success": False,
            "printer_name": printer_name
        }

    xml_text = config.get("PrintCapabilitiesXML")

    capabilities = {
        "success": True,
        "printer_name": printer_name,
        "color": False,
        "duplex": False,
        "paper_sizes": [],
        "orientation": [],
        "raw": {}
    }

    if not xml_text:
        return capabilities

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return capabilities

    for feature in root.iter():
        name = feature.attrib.get("name", "")

        # -----------------------------------------
        # Color capability
        # -----------------------------------------

        if "PageOutputColor" in name:

            for option in feature:

                option_name = (
                    option.attrib.get("name", "")
                    .lower()
                )

                if (
                    "color" in option_name
                    or "rgb" in option_name
                ):
                    capabilities["color"] = True

        # -----------------------------------------
        # Duplex capability
        # -----------------------------------------

        if "Duplex" in name:

            for option in feature:

                option_name = (
                    option.attrib.get("name", "")
                    .lower()
                )

                if (
                    "twosided" in option_name
                    or "duplex" in option_name
                ):
                    capabilities["duplex"] = True

        # -----------------------------------------
        # Paper sizes
        # -----------------------------------------

        if "PageMediaSize" in name:

            for option in feature:

                for child in option:

                    child_name = child.attrib.get(
                        "name",
                        ""
                    )

                    if "DisplayName" not in child_name:
                        continue

                    for value in child:

                        if value.text:
                            paper = value.text.strip()

                            if paper not in capabilities[
                                "paper_sizes"
                            ]:
                                capabilities[
                                    "paper_sizes"
                                ].append(paper)

        # -----------------------------------------
        # Orientation
        # -----------------------------------------

        if "PageOrientation" in name:

            for option in feature:

                for child in option:

                    if "DisplayName" in child.attrib.get(
                        "name",
                        ""
                    ):

                        for value in child:

                            if value.text:

                                orientation = (
                                    value.text.strip()
                                )

                                if orientation not in capabilities[
                                    "orientation"
                                ]:
                                    capabilities[
                                        "orientation"
                                    ].append(
                                        orientation
                                    )

    capabilities["raw"] = {
        "default_color": config.get("Color"),
        "default_duplex": config.get(
            "DuplexingMode"
        ),
        "default_paper": config.get(
            "PaperSize"
        )
    }

    return capabilities


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage: python printer_capability_service.py "
            "\"Printer Name\""
        )

        raise SystemExit(1)

    printer_name = sys.argv[1]

    result = get_printer_capabilities(
        printer_name
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )

