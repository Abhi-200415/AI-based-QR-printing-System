import os


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png"
}


def validate_file(filepath: str) -> bool:

    if not os.path.exists(filepath):
        return False

    extension = os.path.splitext(filepath)[1].lower()

    return extension in ALLOWED_EXTENSIONS