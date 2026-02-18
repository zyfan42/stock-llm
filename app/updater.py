import requests
import logging
from app.version import get_version

def check_for_updates(update_url):
    """
    Checks for updates from the given URL.
    Returns a dict with update info if available, or None.
    """
    if not update_url or "example.com" in update_url:
        logging.warning("Update URL is not configured or is example.com")
        return None

    try:
        response = requests.get(update_url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        latest_version = data.get("version")
        current_version = get_version()
        
        if latest_version and latest_version != current_version:
            # Simple string comparison or semantic versioning check could be added here
            # For now, just inequality
            return data
            
    except Exception as e:
        logging.error(f"Failed to check for updates: {e}")
        
    return None
