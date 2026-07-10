import threading
import time

from termin.editor_core.python_executor import EditorPythonExecutor


def test_editor_python_executor_captures_output_and_context():
    executor = EditorPythonExecutor(lambda: {"project_path": "/tmp/project"})

    result = executor.execute_script("print(project_path)")

    assert result.ok
    assert result.output == "/tmp/project\n"


def test_editor_python_executor_refreshes_context_for_each_script():
    selected = {"entity": "first"}
    executor = EditorPythonExecutor(lambda: {"selected": selected["entity"]})

    first = executor.execute_script("print(selected)")
    selected["entity"] = "second"
    second = executor.execute_script("print(selected)")

    assert first.ok
    assert first.output == "first\n"
    assert second.ok
    assert second.output == "second\n"


def test_editor_python_executor_exposes_scene_control_value_types():
    executor = EditorPythonExecutor(lambda: {})

    result = executor.execute_script(
        "print(Vec3(1, 2, 3).tolist())\n"
        "print(Quat.identity().__class__.__name__)\n"
        "print(Pose3().__class__.__name__)\n"
        "print(GeneralPose3.identity().__class__.__name__)\n"
        "print(GeneralTransform3.__name__)\n"
    )

    assert result.ok
    assert result.output == (
        "[1.0, 2.0, 3.0]\n"
        "Quat\n"
        "Pose3\n"
        "GeneralPose3\n"
        "GeneralTransform3\n"
    )


def test_editor_python_executor_exposes_refresh_helper_for_editor_context():
    class FakeEditor:
        def __init__(self) -> None:
            self.render_update_count = 0

        def request_viewport_update(self) -> None:
            self.render_update_count += 1

    editor = FakeEditor()
    executor = EditorPythonExecutor(lambda: {"editor": editor})

    result = executor.execute_script("request_render_update()\nrefresh_editor()")

    assert result.ok
    assert result.output == ""
    assert editor.render_update_count == 2


def test_editor_python_executor_reports_refresh_helper_without_editor_context():
    executor = EditorPythonExecutor(lambda: {})

    result = executor.execute_script("request_render_update()")

    assert not result.ok
    assert result.error == "RuntimeError: request_render_update requires an editor context"


def test_editor_python_executor_reports_system_exit_as_script_error():
    executor = EditorPythonExecutor(lambda: {})

    result = executor.execute_script("raise SystemExit('stop editor')")

    assert not result.ok
    assert result.error == "SystemExit: stop editor"
    assert "SystemExit: stop editor" in result.output


def test_editor_python_executor_queues_external_thread_work_on_main_thread():
    main_thread_id = threading.get_ident()
    executor = EditorPythonExecutor(lambda: {"main_thread_id": main_thread_id})
    received = {}

    def worker():
        received["result"] = executor.execute_script_from_any_thread(
            "import threading\nprint(threading.get_ident() == main_thread_id)",
            timeout=2.0,
        )

    thread = threading.Thread(target=worker)
    thread.start()

    deadline = time.monotonic() + 2.5
    while thread.is_alive() and time.monotonic() < deadline:
        executor.process_pending()
        thread.join(timeout=0.01)

    assert not thread.is_alive()
    result = received["result"]
    assert result.ok
    assert result.output == "True\n"
