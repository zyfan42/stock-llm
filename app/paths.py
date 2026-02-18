import sys
import os
from pathlib import Path

def get_app_dir():
    """Returns the base directory of the application."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return Path(sys._MEIPASS)
    else:
        # Running from source
        return Path(__file__).parent.parent

def get_user_data_dir():
    """Returns the user data directory."""
    # Use local directory to avoid permission issues in restricted environments
    # and to keep data self-contained
    user_data = get_app_dir() / "user_data"
    user_data.mkdir(parents=True, exist_ok=True)
    return user_data

def get_assets_dir():
    return get_app_dir() / "assets"

def get_webui_dir():
    return get_app_dir() / "webui"
