import logging
import webbrowser
import sys
from app.version import get_version

def run_webview_or_browser(url, title_prefix="StockLLM"):
    title = f"{title_prefix} v{get_version()}"
    
    try:
        import webview
        logging.info("Starting pywebview...")
        
        window = webview.create_window(title, url, width=1280, height=800)
        webview.start()
        
    except ImportError:
        logging.warning("pywebview not installed or failed to import. Fallback to browser.")
        webbrowser.open(url)
    except Exception as e:
        logging.error(f"Failed to start pywebview: {e}. Fallback to browser.")
        webbrowser.open(url)
