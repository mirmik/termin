from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import gc
import weakref

from termin.editor_core.python_console_model import PythonConsoleController
from termin.editor_core.python_executor import EditorPythonExecutor
from termin.editor_native.python_console import (
    build_native_python_console,
    connect_python_console_command,
)
from termin.editor_native.shell import build_native_editor_shell
from termin.gui_native import Rect


def test_native_python_console_command_executes_clears_reopens_and_releases():
    document = tc_ui_document_create()
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

    assert console.show()
    assert console.dialog.open
    console.input.text = "answer + 1"
    snapshot = console.execute()
    assert "43" in snapshot.transcript
    assert "43" in console.output_model.text
    assert console.output.word_wrap
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
    tc_ui_document_destroy(document)


def test_native_python_console_wraps_long_output_in_narrow_view():
    document = tc_ui_document_create()
    controller = PythonConsoleController(EditorPythonExecutor(lambda: {}))
    console = build_native_python_console(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 180.0, 180.0),
        request_render=lambda: None,
        embedded=True,
        activate_embedded=lambda: None,
    )
    assert document.add_root(console.root.handle)
    console.execute("'long console output ' * 20")
    document.layout_roots(Rect(0.0, 0.0, 180.0, 180.0))

    assert console.output.word_wrap
    assert console.output.visual_line_count > len(console.output_model.lines)
    console.close()
    tc_ui_document_destroy(document)


def test_native_python_console_embeds_in_dedicated_bottom_tab():
    document = tc_ui_document_create()
    shell = build_native_editor_shell(document)
    controller = PythonConsoleController(EditorPythonExecutor(lambda: {}))
    console = build_native_python_console(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 720.0),
        request_render=lambda: None,
        embedded=True,
        activate_embedded=lambda: _select_python_console_tab(shell),
    )
    shell.python_console_host.add_stretch_child(console.root)
    connect_python_console_command(shell.menu_bar, shell.python_console_command, console)

    assert console.dialog is None
    assert shell.bottom_tabs.selected_index == 0
    assert console.show()
    assert shell.bottom_tabs.selected_index == 2
    assert console.root.parent.handle == shell.python_console_host.handle
    console.close()
    tc_ui_document_destroy(document)


def _select_python_console_tab(shell) -> None:
    shell.bottom_tabs.selected_index = 2
