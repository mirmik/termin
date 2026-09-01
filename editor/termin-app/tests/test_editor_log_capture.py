import logging

from termin.base import log

from termin.editor_core.editor_log_capture import EditorLogCapture
from termin.editor_core.editor_log_model import EditorLogModel


def test_editor_log_capture_pulls_native_and_python_records_once() -> None:
    model = EditorLogModel()
    python_logger = logging.Logger("termin.test.editor_log")
    capture = EditorLogCapture(
        model,
        capacity=8,
        python_logger=python_logger,
    )
    try:
        log.info("native record")
        python_logger.warning("python record")

        assert model.text == ""
        assert capture.drain()
        assert model.text.splitlines() == [
            "[INFO] native record",
            "[WARN] termin.test.editor_log: python record",
        ]
        assert not capture.drain()
    finally:
        capture.close()


def test_editor_log_capture_reports_overflow_and_stops_cleanly() -> None:
    model = EditorLogModel()
    python_logger = logging.Logger("termin.test.editor_log.overflow")
    previous_level = python_logger.level
    capture = EditorLogCapture(
        model,
        capacity=2,
        python_logger=python_logger,
    )
    log.info("first")
    log.info("second")
    log.info("third")

    assert capture.drain()
    assert model.text.splitlines() == [
        "[WARN] Editor log capture dropped 1 oldest record(s)",
        "[INFO] second",
        "[INFO] third",
    ]

    capture.close()
    assert python_logger.level == previous_level
    text_after_close = model.text
    log.info("after close")
    assert not capture.drain()
    assert model.text == text_after_close


def test_editor_log_capture_suppresses_watchdog_debug_noise() -> None:
    model = EditorLogModel()
    root_logger = logging.getLogger()
    watchdog_logger = logging.getLogger("watchdog.observers.inotify_buffer")
    previous_watchdog_level = watchdog_logger.level
    capture = EditorLogCapture(model, capacity=8, python_logger=root_logger)
    try:
        watchdog_logger.setLevel(logging.DEBUG)
        watchdog_logger.debug("in-event noise")
        watchdog_logger.warning("observer warning")

        assert capture.drain()
        assert model.text.splitlines() == [
            "[WARN] watchdog.observers.inotify_buffer: observer warning",
        ]
    finally:
        watchdog_logger.setLevel(previous_watchdog_level)
        capture.close()
