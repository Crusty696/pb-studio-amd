import sys
import logging
import traceback

logger = logging.getLogger(__name__)

class CrashHandler:
    def __init__(self):
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical("Uncaught Exception:\n%s", error_msg)

        # GUI ist jetzt C# WPF — kein PyQt QMessageBox. Crash-Benachrichtigung
        # erfolgt via logging.critical (oben) und SSE-Event falls Backend läuft.
        logger.critical("CRITICAL ERROR CAUGHT. See logs for details.")
        
        # Determine if fatal
        # sys.exit(1) 
