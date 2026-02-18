import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from app.paths import get_user_data_dir

class SafeRotatingFileHandler(RotatingFileHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except (OSError, UnicodeEncodeError):
            try:
                # Try to re-open or just ignore
                if self.stream:
                    try:
                        self.stream.close()
                    except Exception:
                        pass
                self.stream = self._open()
                super().emit(record)
            except Exception:
                pass

def setup_logging():
    # Fix Windows console encoding if needed
    if sys.platform == 'win32':
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception:
                pass

    log_dir = get_user_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "app.log"
    
    # Ensure root logger has our file handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Check if file handler already exists to avoid duplicates
    has_file_handler = any(isinstance(h, SafeRotatingFileHandler) for h in root_logger.handlers)
    
    if not has_file_handler:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        file_handler = SafeRotatingFileHandler(log_file, maxBytes=1024*1024*5, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Also add stream handler if no handlers exist at all
        if not root_logger.handlers:
             stream_handler = logging.StreamHandler()
             stream_handler.setFormatter(formatter)
             root_logger.addHandler(stream_handler)
    
    logging.info("Logging initialized")
    logging.info(f"Log file: {log_file}")
    return log_file
