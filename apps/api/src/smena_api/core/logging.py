"""Structured JSON logging with secret redaction.

Design rules (see SECURITY.md):
- one JSON object per line on stdout (12-factor; container runtime collects);
- never log passwords, tokens, private keys, full capability payloads;
- as a defense-in-depth measure, values whose key looks sensitive are
  redacted by the formatter itself, so a careless ``extra=`` cannot leak.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Substrings that mark a log field as sensitive. Matching is case-insensitive.
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "private_key",
    "capability",
    "signature",
    "authorization",
    "credential",
)

_REDACTED = "[REDACTED]"

# Attributes present on every LogRecord; anything else is user ``extra=``.
_RESERVED = set(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value


class JsonLogFormatter(logging.Formatter):
    """Format records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = _REDACTED if _is_sensitive(key) else _json_safe(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging: JSON to stdout, single handler, no propagation."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    # Keep noisy framework loggers at WARNING unless explicitly debugging.
    for name in ("uvicorn.access",):
        logging.getLogger(name).setLevel(logging.WARNING)
