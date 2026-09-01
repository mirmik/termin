"""Pull native and Python logs into the editor's bounded presentation model."""

from __future__ import annotations

import logging

from termin.base import log

from .editor_log_model import EditorLogModel


class _EditorPythonLogFilter(logging.Filter):
    """Keep verbose editor diagnostics without importing dependency noise."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "watchdog" or record.name.startswith("watchdog."):
            return record.levelno >= logging.WARNING
        return True


class _TcLogHandler(logging.Handler):
    """Forward standard Python records through the canonical C logger."""

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        if record.levelno >= logging.ERROR:
            log.error(message)
        elif record.levelno >= logging.WARNING:
            log.warning(message)
        elif record.levelno >= logging.INFO:
            log.info(message)
        else:
            log.debug(message)


def _format_native_record(level, message: str) -> str:
    if level == log.Level.ERROR:
        level_name = "ERROR"
    elif level == log.Level.WARN:
        level_name = "WARN"
    elif level == log.Level.INFO:
        level_name = "INFO"
    else:
        level_name = "DEBUG"
    return f"[{level_name}] {message}"


class EditorLogCapture:
    """Own native capture and the Python logging bridge for one editor session."""

    def __init__(
        self,
        model: EditorLogModel,
        *,
        capacity: int = 2048,
        drain_batch_size: int = 512,
        python_logger: logging.Logger | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        if drain_batch_size < 1:
            raise ValueError("drain_batch_size must be positive")

        self._model = model
        self._drain_batch_size = drain_batch_size
        self._python_logger = python_logger or logging.getLogger()
        self._previous_python_level = self._python_logger.level
        self._handler = _TcLogHandler()
        self._handler.setLevel(logging.DEBUG)
        self._handler.addFilter(_EditorPythonLogFilter())
        self._handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        self._closed = False

        log.capture_start(capacity)
        self._python_logger.setLevel(logging.DEBUG)
        self._python_logger.addHandler(self._handler)

    def drain(self) -> bool:
        if self._closed:
            return False
        records, dropped_count = log.capture_drain(self._drain_batch_size)
        lines: list[str] = []
        if dropped_count:
            lines.append(
                f"[WARN] Editor log capture dropped {dropped_count} "
                "oldest record(s)"
            )
        lines.extend(
            _format_native_record(level, message)
            for level, message in records
        )
        self._model.append_many(lines)
        return bool(lines)

    def close(self) -> None:
        if self._closed:
            return
        self._python_logger.removeHandler(self._handler)
        self._python_logger.setLevel(self._previous_python_level)
        self.drain()
        log.capture_stop()
        self._closed = True


__all__ = ["EditorLogCapture"]
