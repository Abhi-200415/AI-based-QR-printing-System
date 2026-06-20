import os


def get_file_path(file_path: str):

    if not os.path.exists(file_path):
        return None

    return file_path