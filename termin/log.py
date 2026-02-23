"""
termin.log - Logging module with proper Python exception handling.

Usage:
    from termin import log

    log.info("Hello")
    log.warn("Something wrong")

    try:
        do_something()
    except Exception as e:
        log.error(e, "Failed to do something")  # includes traceback
"""

import traceback
from tcbase import log as _native_log


def debug(msg_or_exc, context: str = ""):
    """Log debug message or exception with context."""
    if isinstance(msg_or_exc, BaseException):
        _log_exception(_native_log.debug, msg_or_exc, context)
    else:
        _native_log.debug(str(msg_or_exc))


def info(msg_or_exc, context: str = ""):
    """Log info message or exception with context."""
    if isinstance(msg_or_exc, BaseException):
        _log_exception(_native_log.info, msg_or_exc, context)
    else:
        _native_log.info(str(msg_or_exc))


def warn(msg_or_exc, context: str = ""):
    """Log warning message or exception with context."""
    if isinstance(msg_or_exc, BaseException):
        _log_exception(_native_log.warn, msg_or_exc, context)
    else:
        _native_log.warn(str(msg_or_exc))


def warning(msg_or_exc, context: str = ""):
    """Alias for warn()."""
    warn(msg_or_exc, context)


def error(msg_or_exc, context: str = ""):
    """Log error message or exception with context."""
    if isinstance(msg_or_exc, BaseException):
        _log_exception(_native_log.error, msg_or_exc, context)
    else:
        _native_log.error(str(msg_or_exc))


def exception(msg: str = ""):
    """Log error with current exception traceback."""
    _native_log.exception(msg)


def _log_exception(log_func, exc: BaseException, context: str):
    """Format and log exception with traceback."""
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    # Get traceback if available
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    if context:
        full_msg = f"{context}: {exc_type}: {exc_msg}\n{tb}"
    else:
        full_msg = f"{exc_type}: {exc_msg}\n{tb}"

    log_func(full_msg)


# Re-export configuration functions
set_level = _native_log.set_level
set_callback = _native_log.set_callback
Level = _native_log.Level
