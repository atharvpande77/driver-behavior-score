import contextvars
import logging
import logging.config
import sys
from typing import Any

from src.config import app_settings


_REQUEST_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)

_SENSITIVE_KEYS = {
    "password",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "x_api_key",
    "raw_key",
    "key_hash",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _REQUEST_ID_CTX.get()
        return True


class ColorStructuredFormatter(logging.Formatter):
    _RESET = "\033[0m"
    _DIM = "\033[2m"
    _LEVEL_COLORS = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
    }
    _EVENT_COLOR = "\033[34m"  # blue

    def __init__(self, use_colors: bool = False) -> None:
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def _colorize(self, text: str, color: str) -> str:
        if not self.use_colors:
            return text
        return f"{color}{text}{self._RESET}"

    def _extract_event(self, message: str) -> tuple[str, str]:
        if not message.startswith("event="):
            return "-", message

        parts = message.split(" ", 1)
        event_name = parts[0][len("event=") :]
        rest = parts[1] if len(parts) > 1 else ""
        return event_name, rest

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname
        request_id = getattr(record, "request_id", "-")
        message = record.getMessage()
        event_name, fields = self._extract_event(message)

        level_display = self._colorize(level, self._LEVEL_COLORS.get(level, ""))
        event_display = self._colorize(event_name, self._EVENT_COLOR)
        request_display = (
            self._colorize(request_id, self._DIM) if self.use_colors else request_id
        )

        base = (
            f"{timestamp} | {level_display:<8} | {record.name} | "
            f"req={request_display} | event={event_display}"
        )
        if fields:
            return f"{base} | {fields}"
        return base


def configure_logging() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id_filter": {"()": "src.logging_utils.RequestIdFilter"},
            },
            "formatters": {
                "plain_structured": {
                    "()": "src.logging_utils.ColorStructuredFormatter",
                    "use_colors": app_settings.LOG_USE_COLORS,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "plain_structured",
                    "filters": ["request_id_filter"],
                }
            },
            "root": {
                "level": app_settings.LOG_LEVEL.upper(),
                "handlers": ["console"],
            },
        }
    )


def set_request_id(request_id: str) -> contextvars.Token:
    return _REQUEST_ID_CTX.set(request_id)


def reset_request_id(token: contextvars.Token) -> None:
    _REQUEST_ID_CTX.reset(token)


def get_request_id() -> str:
    return _REQUEST_ID_CTX.get()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _sanitize_key(key: str, value: Any) -> Any:
    if key.lower() in _SENSITIVE_KEYS:
        if value is None:
            return None
        if isinstance(value, str):
            if len(value) <= 8:
                return "***"
            return f"{value[:4]}***"
        return "***"
    return value


def log_event(logger: logging.Logger, level: str, event: str, **fields: Any) -> None:
    level_no = getattr(logging, level.upper(), logging.INFO)
    if not logger.isEnabledFor(level_no):
        return

    safe_fields = {
        key: _sanitize_key(key, value)
        for key, value in fields.items()
        if value is not None
    }
    parts = [f"event={event}"] + [
        f"{key}={safe_fields[key]}" for key in sorted(safe_fields.keys())
    ]
    logger.log(level_no, " ".join(parts))
