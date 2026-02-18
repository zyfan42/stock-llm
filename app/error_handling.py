import sys
import logging
import traceback
import ctypes

def show_error_dialog(title, message):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10) # 0x10 = MB_ICONERROR
    except:
        print(f"Error: {message}")

def setup_error_handling():
    def exception_hook(exctype, value, tb):
        error_msg = "".join(traceback.format_exception(exctype, value, tb))
        logging.error(f"Uncaught exception:\n{error_msg}")
        
        # Get log file path if available
        log_file = "check logs"
        try:
            from app.logging_setup import get_user_data_dir
            log_file = get_user_data_dir() / "logs" / "app.log"
        except:
            pass
            
        show_error_dialog("Application Error", f"An unexpected error occurred.\n\nLog file: {log_file}\n\nError: {value}")
        sys.exit(1)
        
    sys.excepthook = exception_hook
