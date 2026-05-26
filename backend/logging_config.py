from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

# Context variable for request trace ID (propagated across async calls)
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production use."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        trace_id = trace_id_ctx.get("")
        if trace_id:
            log_entry["trace_id"] = trace_id

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include extra fields
        for key in ("model", "elapsed_ms", "tokens", "status_code", "method", "path"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = trace_id_ctx.get("")
        prefix = f"[{trace_id[:8]}] " if trace_id else ""
        return f"{prefix}{record.levelname:8s} {record.name}: {record.getMessage()}"


def setup_logging(level: int = logging.INFO, structured: bool = False) -> None:
    """Configure application logging.

    Args:
        level: Logging level.
        structured: If True, use JSON output (for production). Otherwise human-readable.
    """
    handler = logging.StreamHandler(sys.stdout)

    if structured:
        handler.setFormatter(StructuredFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    else:
        handler.setFormatter(HumanFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


def generate_trace_id() -> str:
    """Generate a new trace ID for request tracking."""
    return uuid.uuid4().hex[:16]
