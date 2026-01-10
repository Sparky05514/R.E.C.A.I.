import logging
import os
from pathlib import Path

# Setup logging directory
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Main log file
SYSTEM_LOG = LOG_DIR / "system.log"

def setup_logger():
    """Configures and returns the system logger."""
    logger = logging.getLogger("recaizade_crew")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(SYSTEM_LOG)
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        
    return logger

# Global logger instance
log = setup_logger()
