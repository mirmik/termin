import logging
import threading

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


def test_log_wakeup_from_worker_and_backlog_after_bounded_drain() -> None:
    capture = EditorLogCapture(EditorLogModel(), capacity=16, drain_batch_size=2,
                               python_logger=logging.Logger("capture-worker"))
    wakes = []
    capture.set_wakeup(lambda: wakes.append(capture.has_pending))
    try:
        worker = threading.Thread(target=lambda: [log.info(f"worker {i}") for i in range(5)])
        worker.start()
        worker.join(timeout=2.0)
        assert not worker.is_alive()
        assert wakes == [True]
        assert capture.drain()
        assert capture.has_pending
        assert capture.drain()
        assert capture.has_pending
        assert capture.drain()
        assert not capture.has_pending
        log.info("next burst")
        assert wakes == [True, True]
    finally:
        capture.close()
    log.info("after close")
    assert wakes == [True, True]
    assert not capture.has_pending


def test_log_wakeup_unsubscribe_waits_for_inflight_producer() -> None:
    capture = EditorLogCapture(EditorLogModel(), python_logger=logging.Logger("capture-close"))
    started = threading.Event()
    release = threading.Event()
    detached = threading.Event()

    def notify() -> None:
        started.set()
        assert release.wait(timeout=2.0)

    capture.set_wakeup(notify)
    producer = threading.Thread(target=lambda: log.info("queued before close"))
    producer.start()
    assert started.wait(timeout=2.0)

    def release_notification() -> None:
        # Owner must wait for this callback before releasing its Python object.
        assert not detached.is_set()
        release.set()

    releaser = threading.Thread(target=release_notification)
    releaser.start()
    capture.set_wakeup(None)
    detached.set()
    producer.join(timeout=2.0)
    releaser.join(timeout=2.0)
    assert not producer.is_alive()
    assert capture.has_pending
    capture.close()
