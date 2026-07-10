import gc
import weakref

from tcbase import Key

from termin.editor_core.python_console_model import PythonConsoleController
from termin.editor_core.python_executor import EditorPythonExecutor
from termin.editor_native.python_console import (
    build_native_python_console,
    connect_python_console_command,
)
from termin.editor_native.shell import build_native_editor_shell
from termin.gui_native import Document, Rect


def test_native_python_console_f6_executes_clears_reopens_and_releases():
    document = Document()
    shell = build_native_editor_shell(document)
    controller = PythonConsoleController(EditorPythonExecutor(lambda: {"answer": 42}))
    renders = []
    console = build_native_python_console(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 720.0),
        request_render=lambda: renders.append(True),
    )
    connect_python_console_command(shell.menu_bar, shell.python_console_command, console)

    assert shell.menu_bar.dispatch_shortcut(Key.F6.value, 0)
    assert console.dialog.open
    console.input.text = "answer + 1"
    snapshot = console.execute()
    assert "43" in snapshot.transcript
    assert "43" in console.output_model.text
    assert console.input.text == ""

    console.clear()
    assert console.output_model.text == ""
    assert console.dialog.activate("close")
    assert console.show()

    console.close()
    assert not document.is_alive(console.dialog.handle)
    console_ref = weakref.ref(console)
    del console
    gc.collect()
    assert console_ref() is None
    assert renders
