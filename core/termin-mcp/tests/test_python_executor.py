import threading
import time
import weakref

from termin.mcp.python_executor import PythonScriptExecutor


def test_executor_exposes_only_host_supplied_asset_context() -> None:
    resource_manager = object()
    executor = PythonScriptExecutor(
        lambda: {"rm": resource_manager, "resource_manager": resource_manager}
    )

    result = executor.execute_script("print(rm is resource_manager)")

    assert result.ok
    assert result.output == "True\n"


def test_executor_does_not_inject_scene_context() -> None:
    executor = PythonScriptExecutor(lambda: {})

    result = executor.execute_script("print('GeneralTransform3' in globals())")

    assert result.ok
    assert result.output == "False\n"


def test_repl_blank_line_completes_buffered_multiline_statement():
    executor = PythonScriptExecutor(lambda: {})

    assert executor.execute_repl_line("for i in range(2):").wants_more
    assert executor.execute_repl_line("    print(i)").wants_more
    result = executor.execute_repl_line("")

    assert result.ok
    assert not result.wants_more
    assert result.output == "0\n1\n"


def test_timed_out_queued_request_is_cancelled_before_main_thread_poll() -> None:
    events: list[str] = []
    executor = PythonScriptExecutor(lambda: {"events": events})
    result_holder = []

    worker = threading.Thread(
        target=lambda: result_holder.append(
            executor.execute_script_from_any_thread("events.append('late')", timeout=0.01)
        )
    )
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert result_holder[0].error == "Timed out waiting for main thread"
    assert executor.process_pending() == 0
    assert events == []


def test_main_thread_claim_wins_timeout_race_and_returns_completed_result() -> None:
    started = threading.Event()
    release = threading.Event()
    executor = PythonScriptExecutor(lambda: {"started": started, "release": release})
    result_holder = []

    worker = threading.Thread(
        target=lambda: result_holder.append(
            executor.execute_script_from_any_thread(
                "started.set()\nrelease.wait()\nprint('completed')",
                timeout=0.01,
            )
        )
    )
    worker.start()

    def release_after_claim() -> None:
        assert started.wait(timeout=1.0)
        time.sleep(0.05)
        release.set()

    releaser = threading.Thread(target=release_after_claim)
    releaser.start()
    deadline = time.monotonic() + 1.0
    processed = 0
    while processed == 0 and time.monotonic() < deadline:
        processed = executor.process_pending()
        if processed == 0:
            time.sleep(0.001)
    assert processed == 1
    worker.join(timeout=1.0)
    releaser.join(timeout=1.0)

    assert not worker.is_alive()
    assert result_holder[0].ok
    assert result_holder[0].output == "completed\n"


def test_close_cancels_queued_work_and_rejects_new_requests() -> None:
    executor = PythonScriptExecutor(lambda: {})
    result_holder = []

    worker = threading.Thread(
        target=lambda: result_holder.append(
            executor.execute_script_from_any_thread("print('never runs')", timeout=None)
        )
    )
    worker.start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        with executor._pending_lock:
            if executor._pending:
                break
        time.sleep(0.001)

    executor.close()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert result_holder[0].error == "Python executor closed before execution"
    assert executor.process_pending() == 0

    rejected = threading.Thread(
        target=lambda: result_holder.append(
            executor.execute_script_from_any_thread("print('rejected')", timeout=None)
        )
    )
    rejected.start()
    rejected.join(timeout=1.0)
    assert not rejected.is_alive()
    assert result_holder[1].error == "Python executor is closed"


def test_close_releases_persistent_host_context_on_owner_thread() -> None:
    class HostValue:
        pass

    class HostContext:
        def __init__(self) -> None:
            self.value = HostValue()

        def build(self) -> dict[str, object]:
            return {"value": self.value}

    context = HostContext()
    context_ref = weakref.ref(context)
    value_ref = weakref.ref(context.value)
    executor = PythonScriptExecutor(context.build)

    result = executor.execute_script("retained_value = value")
    assert result.ok
    del context
    assert context_ref() is not None
    assert value_ref() is not None

    executor.close()

    assert context_ref() is None
    assert value_ref() is None
    assert executor._console.locals == {}
    assert executor.execute_script("print('closed')").error == "Python executor is closed"
    assert executor.execute_repl_line("print('closed')").error == "Python executor is closed"


def test_owner_close_releases_context_after_off_owner_close() -> None:
    class HostValue:
        pass

    context = {"value": HostValue()}
    value_ref = weakref.ref(context["value"])
    executor = PythonScriptExecutor(lambda: context)
    assert executor.execute_script("retained_value = value").ok
    context.clear()

    worker = threading.Thread(target=executor.close)
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert value_ref() is not None

    executor.close()

    assert value_ref() is None
    assert executor._console.locals == {}


def test_wakeup_observes_published_requests_and_bounded_backlog() -> None:
    executor = PythonScriptExecutor(lambda: {})
    ready = threading.Condition()
    notifications: list[bool] = []

    def wake() -> None:
        # This also proves notification does not hold the pending queue lock.
        pending = executor.has_pending
        with ready:
            notifications.append(pending)
            ready.notify_all()

    executor.set_wakeup(wake)
    results = []
    workers = [threading.Thread(target=lambda: results.append(
        executor.execute_script_from_any_thread("print('done')", timeout=5.0)
    )) for _ in range(10)]
    try:
        for worker in workers:
            worker.start()
        with ready:
            assert ready.wait_for(lambda: len(notifications) == 10, timeout=2.0)
        assert all(notifications)
        assert executor.process_pending() == 8
        assert executor.has_pending
        assert executor.process_pending() == 2
        assert not executor.has_pending
    finally:
        executor.close()
        for worker in workers:
            worker.join(timeout=2.0)
    assert all(not worker.is_alive() for worker in workers)
    assert len(results) == 10
    assert all(result.ok for result in results)


def test_wakeup_failure_cancels_request_instead_of_hanging() -> None:
    executor = PythonScriptExecutor(lambda: {})

    def fail() -> None:
        raise RuntimeError("notification unavailable")

    executor.set_wakeup(fail)
    results = []
    worker = threading.Thread(target=lambda: results.append(
        executor.execute_script_from_any_thread("print('never')", timeout=None)
    ))
    worker.start()
    worker.join(timeout=2.0)
    try:
        assert not worker.is_alive()
        assert results[0].error == "Failed to wake owner loop"
        assert not executor.has_pending
    finally:
        executor.close()


def test_install_wakeup_notifies_existing_work_and_close_detaches() -> None:
    executor = PythonScriptExecutor(lambda: {})
    queued = threading.Event()
    executor.set_wakeup(queued.set)
    worker = threading.Thread(target=lambda: executor.execute_script_from_any_thread(
        "print('cancelled')", timeout=None
    ))
    worker.start()
    assert queued.wait(timeout=2.0)
    observed = []
    executor.set_wakeup(lambda: observed.append(executor.has_pending))
    assert observed == [True]
    executor.close()
    worker.join(timeout=2.0)
    executor.set_wakeup(lambda: observed.append(False))
    assert observed == [True]
    assert not executor.has_pending
