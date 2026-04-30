"""
Structured logging setup for XDEI backend.
"""

import logging
import sys
from typing import Optional
from config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with timestamps and context."""
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname
        name = record.name
        message = record.getMessage()
        
        # Include exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            return f"[{timestamp}] {level:8s} {name:20s} {message}\n{exc_text}"
        
        return f"[{timestamp}] {level:8s} {name:20s} {message}"


def setup_logger(
    name: str,
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Set up a logger with structured formatting.
    
    Args:
        name: Logger name (usually __name__)
        level: Log level (default: from settings.app.log_level)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Use provided level or default from settings
    log_level = level or settings.app.log_level
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Only add handler if not already present (avoid duplicates)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(getattr(logging, log_level, logging.INFO))
        
        formatter = StructuredFormatter()
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    return logger


# Module-level logger for this package
logger = setup_logger(__name__)
