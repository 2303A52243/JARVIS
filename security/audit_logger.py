"""Audit logging system for JARVIS.

Records structured security events, tool calls, and user confirmations.
Guarantees redaction of sensitive credentials, API keys, and private tokens.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# Regular expressions for identifying sensitive tokens to redact
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"api[_-]?key[\"'\s:=]+[\"']?([a-zA-Z0-9_\-]{16,})[\"']?", re.IGNORECASE),
    re.compile(r"password[\"'\s:=]+[\"']?([^\s\"']+)[\"']?", re.IGNORECASE),
]


def redact_sensitive_info(text: str) -> str:
    """Scan and redact any suspected API keys, tokens, or passwords from string."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def sanitize_payload(payload: Any) -> Any:
    """Recursively sanitize nested dictionaries and lists."""
    if isinstance(payload, dict):
        clean_dict = {}
        for k, v in payload.items():
            if any(s in k.lower() for s in ("key", "password", "token", "secret", "auth")):
                clean_dict[k] = "[REDACTED_SECRET]"
            else:
                clean_dict[k] = sanitize_payload(v)
        return clean_dict
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    elif isinstance(payload, str):
        return redact_sensitive_info(payload)
    return payload


class AuditLogger:
    """Thread-safe structured audit and application logger."""

    _instance: Optional[AuditLogger] = None
    _lock = threading.Lock()

    def __init__(self, log_dir: Path, log_level: str = "INFO"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.log_dir / "audit.jsonl"
        self.log_file = self.log_dir / "jarvis.log"
        self._write_lock = threading.Lock()

        # Configure standard python logger
        self.logger = logging.getLogger("JARVIS")
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        self.logger.propagate = False

        if not self.logger.handlers:
            # Console handler
            c_handler = logging.StreamHandler(sys.stdout)
            c_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            c_handler.setFormatter(c_formatter)
            self.logger.addHandler(c_handler)

            # Rotating/standard file handler
            f_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            f_handler.setFormatter(c_formatter)
            self.logger.addHandler(f_handler)

    @classmethod
    def get_instance(cls, log_dir: Optional[Path] = None, log_level: str = "INFO") -> AuditLogger:
        with cls._lock:
            if cls._instance is None:
                if log_dir is None:
                    from app.config import get_settings
                    log_dir = get_settings().jarvis_log_dir
                    log_level = get_settings().jarvis_log_level
                cls._instance = cls(log_dir=log_dir, log_level=log_level)
            return cls._instance

    def log_event(
        self,
        event_type: str,
        action: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
    ) -> None:
        """Write an immutable structured event to the audit log."""
        timestamp = datetime.now(timezone.utc).isoformat()
        clean_details = sanitize_payload(details or {})

        record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "action": action,
            "status": status,
            "details": clean_details,
        }

        # Format human readable summary for log file
        summary = f"[{event_type}] {action} -> {status}"
        if clean_details:
            summary += f" | {json.dumps(clean_details, ensure_ascii=False)}"

        log_fn = getattr(self.logger, level.lower(), self.logger.info)
        log_fn(summary)

        # Append to audit JSONL file
        try:
            with self._write_lock:
                with open(self.audit_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.error(f"Failed writing audit record: {e}")

    def info(self, message: str) -> None:
        self.logger.info(redact_sensitive_info(message))

    def warning(self, message: str) -> None:
        self.logger.warning(redact_sensitive_info(message))

    def error(self, message: str) -> None:
        self.logger.error(redact_sensitive_info(message))

    def debug(self, message: str) -> None:
        self.logger.debug(redact_sensitive_info(message))


def get_audit_logger() -> AuditLogger:
    """Helper to retrieve audit logger instance."""
    return AuditLogger.get_instance()
