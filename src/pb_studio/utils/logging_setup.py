import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(app_name="pb_studio"):
    # BUG-091 FIX: Absolute Pfade relativ zum Script
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"{app_name}.log"
    
    # Root Logger
    logger = logging.getLogger()
    
    # BUG-091 FIX: Keine doppelten Handler hinzufuegen
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler (Rotating: 5MB max, 3 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging initialized. Log file: {log_file.absolute()}")
    return logger
