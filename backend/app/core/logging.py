"""Structured logging with contextvars. ponytail: JSON lines, no structlog dep."""
from __future__ import annotations

import json
import logging
import contextvars
import time

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")
task_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("task_id", default="")


class StructuredFormatter(logging.Formatter):
    """JSON log formatter with request context. ponytail: stdlib logging, no deps."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get("")
        if rid:
            log_entry["request_id"] = rid
        sid = session_id_var.get("")
        if sid:
            log_entry["session_id"] = sid
        tid = task_id_var.get("")
        if tid:
            log_entry["task_id"] = tid
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Replace root handler with structured JSON. ponytail: call once at startup."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
