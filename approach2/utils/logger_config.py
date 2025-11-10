"""logger_config.py - Centralized logging configuration."""
import logging
from pathlib import Path
from datetime import datetime


class MagenticLogger:
    """Custom logger for Magentic orchestration with file and console output."""
    
    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"magentic_run_{timestamp}.log"
        
        self.logger = logging.getLogger("MagenticOrchestrator")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # File handler with detailed format
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Console handler with simple format
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info(f"{'='*70}\n")
    
    def info(self, msg: str) -> None:
        """Log info level message."""
        self.logger.info(msg)
    
    def warning(self, msg: str) -> None:
        """Log warning level message."""
        self.logger.warning(msg)
    
    def error(self, msg: str) -> None:
        """Log error level message."""
        self.logger.error(msg)


# Glob
# al logger instance
magentic_logger = MagenticLogger()