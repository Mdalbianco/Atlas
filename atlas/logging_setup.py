"""Logging strutturato (JSON) con oscuramento automatico dei segreti."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

_SECRET_PATTERNS = [
    # token bot Telegram: 123456789:AA....
    re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}"),
    # chiavi/segreti espliciti in stringhe chiave=valore o JSON
    re.compile(r"(?i)(api[_-]?key|secret|token|password|signature)(['\"]?\s*[:=]\s*['\"]?)([^\s'\",}]+)"),
    # stringhe base64 lunghe (es. secret Kraken)
    re.compile(r"\b[A-Za-z0-9+/]{64,}={0,2}"),
]

_registered_secrets: set[str] = set()


def register_secret(value: str | None) -> None:
    """Registra un valore da oscurare sempre nei log."""
    if value and len(value) >= 6:
        _registered_secrets.add(value)


def redact(text: str) -> str:
    for secret in _registered_secrets:
        text = text.replace(secret, "***")
    text = _SECRET_PATTERNS[0].sub("***", text)
    text = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    text = _SECRET_PATTERNS[2].sub("***", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()))
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "data", None)
        if extra:
            payload["data"] = extra
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return redact(json.dumps(payload, ensure_ascii=False, default=str))


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra = getattr(record, "data", None)
        if extra:
            base += " " + json.dumps(extra, ensure_ascii=False, default=str)
        return redact(base)


def setup_logging(level: str = "INFO", json_output: bool = True, log_file: str | None = None) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    formatter: logging.Formatter = (
        JsonFormatter() if json_output else TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        from logging.handlers import RotatingFileHandler

        handlers.append(RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)
    # Le librerie HTTP possono registrare URL contenenti il token Telegram.
    for noisy in ("httpx", "httpcore", "urllib3", "telegram", "ccxt"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
