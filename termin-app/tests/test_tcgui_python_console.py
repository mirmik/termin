from termin.editor_core.python_executor import EditorPythonExecutor
from termin.editor_tcgui.python_console_panel import PythonConsolePanel


def test_tcgui_python_console_projects_shared_controller_and_multiline_repl():
    panel = PythonConsolePanel()
    panel.set_context(
        editor=None,
        get_scene=lambda: None,
        get_project_path=lambda: None,
        executor=EditorPythonExecutor(lambda: {"answer": 42}),
    )

    panel._execute("answer")
    assert "42" in panel._output.text
    panel._execute("for i in range(2):")
    panel._execute("    print(i)")
    panel._execute("")

    assert panel._prompt.text == ">>>"
    assert "0\n1\n" in panel._output.text
