import sys
import logging
import traceback

class CrashHandler:
    def __init__(self):
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.critical("Uncaught Exception:\n" + error_msg)
        
        # TODO: Once GUI is ready, show a QMessageBox here
        print("CRITICAL ERROR CAUGHT. Checked logs for details.")
        
        # Determine if fatal
        # sys.exit(1) 
