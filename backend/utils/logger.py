"""Structured logging setup for XDEI backend.

Outputs JSON lines with common fields: timestamp, level, logger, message,
request_id (if available) and any extra fields passed via `extra=`.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Optional
from config import settings


class StructuredFormatter(logging.Formatter):
    """Formatter that emits a single-line JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        payload = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id and other extras if available
        try:
            if hasattr(record, "request_id") and record.request_id:
                payload["request_id"] = record.request_id
        except Exception:
            pass

        # Include other extra fields set on the record
        for key, value in record.__dict__.items():
            if key in ("name", "msg", "args", "levelname", "levelno", "pathname", "filename",
                       "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                       "created", "msecs", "relativeCreated", "thread", "threadName", "processName",
                       "process", "message"):
                continue
            if key.startswith("_"):
                continue
            if key in ("request_id",):
                # already handled
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except Exception:
                payload[key] = str(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logger(
    name: str,
    level: Optional[str] = None,
) -> logging.Logger:
    """Create or return a logger configured to write JSON to stderr.

    Args:
        name: logger name
        level: optional log level string (e.g., 'DEBUG')
    """
    logger = logging.getLogger(name)
    log_level = level or getattr(settings.app, "log_level", "INFO")
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Avoid adding multiple handlers when module is imported repeatedly
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(getattr(logging, log_level, logging.INFO))
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)

    return logger


# Module-level logger for this package
logger = setup_logger(__name__)
