from termin.editor_core.python_console_model import PythonConsoleController
from termin.editor_core.python_executor import EditorPythonExecutor


def test_python_console_controller_handles_output_errors_and_multiline_completion():
    executor = EditorPythonExecutor(lambda: {"answer": 42})
    controller = PythonConsoleController(executor)
    snapshots = []
    controller.changed.connect(snapshots.append)

    snapshot = controller.execute("answer")
    assert ">>> answer" in snapshot.transcript
    assert "42" in snapshot.transcript
    assert snapshot.prompt == ">>>"

    snapshot = controller.execute("for i in range(2):")
    assert snapshot.prompt == "..."
    snapshot = controller.execute("    print(i)")
    assert snapshot.prompt == "..."
    snapshot = controller.execute("")
    assert snapshot.prompt == ">>>"
    assert "0\n1\n" in snapshot.transcript

    snapshot = controller.execute("1 / 0")
    assert "ZeroDivisionError" in snapshot.transcript
    assert snapshots[-1] == snapshot

    snapshot = controller.clear()
    assert snapshot.transcript == ""
    assert snapshot.prompt == ">>>"
