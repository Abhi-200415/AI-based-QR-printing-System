import os
import sys

# Ensure TESTING mode is enabled so DB falls back to local SQLite immediately
os.environ["TESTING"] = "1"

# Ensure cloud_server and PRINT_AGENT are in Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

CLOUD_DIR = os.path.join(ROOT_DIR, "cloud_server")
if CLOUD_DIR not in sys.path:
    sys.path.insert(0, CLOUD_DIR)

AGENT_DIR = os.path.join(ROOT_DIR, "PRINT_AGENT")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)
