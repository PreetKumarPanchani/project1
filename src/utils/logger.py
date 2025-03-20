import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

class CustomFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""
    
    # ANSI escape codes for colors
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[41m'   # Red background
    }
    RESET = '\033[0m'

    def format(self, record):
        # Add color to console output
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            level_color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{level_color}{record.levelname}{self.RESET}"
            
        return super().format(record)

def setup_logger(
    name: str = "nl2db",
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 3
) -> logging.Logger:
    """
    Setup application logger with console and file handlers.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        max_bytes: Maximum bytes per log file
        backup_count: Number of backup files
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    console_formatter = CustomFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

class JSONLogger:
    """JSON formatted logger for structured logging"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log(self, level: str, message: str, **kwargs):
        """Log message with additional context as JSON"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        
        # Use appropriate log level
        log_func = getattr(self.logger, level.lower())
        log_func(json.dumps(log_entry))

# Simple test
if __name__ == "__main__":
    print("\n=== Testing Logger ===\n")
    
    # Create test log directory
    test_dir = Path("test_logs")
    test_dir.mkdir(exist_ok=True)
    
    # Setup test logger
    logger = setup_logger(
        name="test_logger",
        level="DEBUG",
        log_file="test_logs/test.log"
    )
    
    print("1. Testing different log levels:")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    print("\n2. Testing JSON logger:")
    json_logger = JSONLogger(logger)
    json_logger.log(
        "INFO",
        "Database query executed",
        query="SELECT * FROM users",
        duration_ms=150,
        rows_returned=10
    )
    
    print("\n3. Check log file content:")
    with open("test_logs/test.log", "r") as f:
        print(f.read())
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)
    
    print("\nTest completed!")