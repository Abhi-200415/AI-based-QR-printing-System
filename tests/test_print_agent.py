import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath("PRINT_AGENT"))

from core.config import AGENT_ID, DOWNLOAD_FOLDER, HEARTBEAT_INTERVAL
from services.file_validator import validate_file
from services.downloader import verify_download
from printers.discovery import discover_printers, get_physical_printers

class TestPrintAgent(unittest.TestCase):

    def test_agent_config(self):
        self.assertTrue(bool(AGENT_ID))
        self.assertEqual(DOWNLOAD_FOLDER, "downloads")
        self.assertGreater(HEARTBEAT_INTERVAL, 0)

    def test_file_validator_with_dummy_file(self):
        # Create small test file
        test_file = Path("test_temp_val.pdf")
        test_file.write_bytes(b"%PDF-1.4 header test content %%EOF")
        try:
            self.assertTrue(validate_file(str(test_file)))
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_printer_discovery_graceful(self):
        # Must execute without throwing exceptions regardless of OS
        printers = discover_printers()
        self.assertIsInstance(printers, list)
        physical = get_physical_printers()
        self.assertIsInstance(physical, list)

    def test_image_to_a4_pdf_conversion(self):
        from services.image_converter import convert_image_to_printable_pdf
        from PIL import Image

        temp_img = Path("test_sample_img.png")
        Image.new("RGB", (800, 600), (255, 0, 0)).save(temp_img)
        pdf_path = None
        try:
            pdf_path, orientation = convert_image_to_printable_pdf(str(temp_img), paper_size="A4", orientation="PORTRAIT")
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 0)
            self.assertEqual(orientation, "PORTRAIT")
        finally:
            if temp_img.exists():
                temp_img.unlink()
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)


if __name__ == "__main__":
    unittest.main()
