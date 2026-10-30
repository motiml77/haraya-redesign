import os
import sys

APP_NAME = "HebWordSearch"


def data_dir() -> str:
    override = os.environ.get("HEBSEARCH_DATA")
    if override:
        base = override
    elif sys.platform == "win32":
        base = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
    elif sys.platform == "darwin":
        base = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    else:
        base = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), APP_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def default_db_path() -> str:
    return os.path.join(data_dir(), "index.sqlite3")
