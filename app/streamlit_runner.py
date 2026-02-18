import sys
import socket
import threading
import time
import logging
from streamlit.web import cli as st_cli
from app.paths import get_webui_dir

class StreamlitRunner:
    def __init__(self):
        self.port = 8501
        self.server_thread = None
        self.is_running = False

    def _find_free_port(self):
        port = 8501
        while port < 65535:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) != 0:
                    return port
                port += 1
        raise RuntimeError("No free ports found")

    def start(self):
        self.port = self._find_free_port()
        logging.info(f"Starting Streamlit on port {self.port}")
        
        script_path = str(get_webui_dir() / "main_app.py")
        
        def run_server():
            # Mock sys.argv so streamlit thinks it's running from CLI
            sys.argv = [
                "streamlit",
                "run",
                script_path,
                "--server.port", str(self.port),
                "--server.headless", "true",
                "--global.developmentMode", "false",
                "--server.address", "127.0.0.1"
            ]
            try:
                # Monkeypatch signal to avoid "signal only works in main thread" error
                import signal
                original_signal = signal.signal
                def noop_signal(signum, frame):
                    pass
                signal.signal = noop_signal
                
                st_cli.main()
            except SystemExit:
                pass
            except Exception as e:
                logging.error(f"Streamlit server error: {e}")
            finally:
                # Restore signal if needed (though we are in a daemon thread)
                if 'original_signal' in locals():
                    signal.signal = original_signal

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

    def wait_until_ready(self, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to connect to the port to see if it's listening
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    return True
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)
        return False

    def stop(self):
        self.is_running = False
        # The thread is daemon, so it will die when main process exits.
        pass

    def get_url(self):
        return f"http://127.0.0.1:{self.port}"
