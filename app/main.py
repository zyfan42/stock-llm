import os
import sys
import logging
import threading
import time
import webbrowser
from app.paths import get_webui_dir, get_app_dir
from app.config import load_config
from app.logging_setup import setup_logging
from app.error_handling import setup_error_handling
from app.streamlit_runner import StreamlitRunner
from app.webview_app import run_webview_or_browser
from app.version import get_version

def main():
    # 1. Setup logging and error handling
    setup_logging()
    setup_error_handling()
    
    logging.info("Application starting...")
    logging.info(f"Version: {get_version()}")
    logging.info(f"App Dir: {get_app_dir()}")
    
    # 2. Load Config
    config = load_config()
    logging.info(f"Config loaded: {config}")

    # 3. Start Streamlit in a separate thread
    runner = StreamlitRunner()
    
    # Check if we need to pass custom config
    # For now, StreamlitRunner has hardcoded defaults but could use config
    
    runner.start()
    
    # 4. Wait for Streamlit to be ready
    if not runner.wait_until_ready(timeout=60):
        logging.error("Streamlit failed to start within timeout.")
        sys.exit(1)
        
    logging.info("Streamlit is ready.")
    
    # 5. Launch UI (WebView or Browser)
    # This blocks until the window is closed
    url = runner.get_url()
    run_webview_or_browser(url, title_prefix="StockLLM")
    
    # 6. Cleanup
    logging.info("Shutting down...")
    runner.stop()
    sys.exit(0)

if __name__ == "__main__":
    main()
