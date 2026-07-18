"""
platform_core/logging_config.py

Central logging configuration for AI Employee Platform.
Emits JSON-structured log lines so every entry is machine-parseable.

Usage in every module:
    from platform_core.logging_config import get_logger
    logger = get_logger(__name__)

Log line format (JSON):
    {
        "timestamp": "2026-07-18T10:00:00.000Z",
        "level":     "INFO",
        "logger":    "platform_core.ai_gateway",
        "msg":       "Human-readable message",
        "tenant_id": "tenant-1",        # included when passed as extra
        "agent":     "ProspectAgent",   # included when passed as extra
        ...                             # any extra fields passed via extra={}
    }

Rule 10 compliance:
    - Every log line has level, msg, logger, timestamp.
    - Callers pass identifiers (tenant_id, prospect_id, agent) via the
      extra= kwarg so they appear as top-level JSON fields.
    - NO print() statements are used anywhere in platform_core or workers.
"""

import logging
import json
import datetime
import sys


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.datetime.utcfromtimestamp(record.created).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Attach any extra fields the caller passed via extra={...}
        _reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _reserved and not key.startswith("_"):
                log_obj[key] = value

        # Attach exception info if present
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def _build_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    return handler


def configure_logging(level: int = logging.INFO) -> None:
    """
    Call once at application entry-point (worker main, test runner, etc.)
    to configure the root logger with JSON output.

    Args:
        level: Python logging level (default INFO).
    """
    root = logging.getLogger()
    # Avoid adding duplicate handlers if called more than once
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(_build_handler())
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger that will emit JSON-structured lines.
    Modules should call this instead of logging.getLogger() directly.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        logging.Logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Prospect found", extra={"tenant_id": tid, "prospect_id": pid})
    """
    return logging.getLogger(name)
