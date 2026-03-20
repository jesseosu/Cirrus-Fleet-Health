"""Structured JSON logger with X-Ray trace correlation.

Provides a consistent logging interface across all Cirrus Lambda functions,
outputting JSON-formatted log entries with trace context for observability.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON with trace correlation."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        trace_id = os.environ.get("_X_AMZN_TRACE_ID", "")
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "function": record.funcName,
            "trace_id": trace_id,
            "message": record.getMessage(),
        }
        if hasattr(record, "instance_id"):
            log_entry["instance_id"] = record.instance_id  # type: ignore[attr-defined]
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)  # type: ignore[attr-defined]
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
            log_entry["exception_type"] = type(
                record.exc_info[1]
            ).__name__
        return json.dumps(log_entry, default=str)


def get_logger(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a structured JSON logger for a Cirrus service.

    Args:
        service_name: Name of the service (e.g., 'health-checker').
        level: Logging level, defaults to INFO.

    Returns:
        Configured logger instance with JSON formatting.
    """
    logger = logging.getLogger(f"cirrus.{service_name}")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter(service_name))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    instance_id: str = "",
    **kwargs: Any,
) -> None:
    """Log a message with additional structured context fields.

    Args:
        logger: Logger instance to use.
        level: Log level (e.g., logging.INFO).
        message: Log message.
        instance_id: Optional EC2 instance ID for correlation.
        **kwargs: Additional key-value pairs to include in the log entry.
    """
    extra: dict[str, Any] = {}
    if instance_id:
        extra["instance_id"] = instance_id
    if kwargs:
        extra["extra_fields"] = kwargs
    logger.log(level, message, extra=extra)
