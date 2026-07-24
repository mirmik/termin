"""Native editor Python console backed by the shared REPL controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.python_console_model import PythonConsoleController, PythonConsoleSnapshot
from termin.gui_native import DialogAction, TcDocument, EdgeInsets, Rect, RichTextModel, Size, WidgetRef


def _ref(document: TcDocument, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativePythonConsole:
    document: TcDocument
    controller: PythonConsoleController
    dialog: object | None
    root: WidgetRef
    output_model: RichTextModel
    output: object
    prompt: object
    input: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    changed_callback: Callable[[PythonConsoleSnapshot], None]
    activate_embedded: Callable[[], None] | None = None
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native Python console is closed")
        if self.dialog is None:
            if self.activate_embedded is None:
                raise RuntimeError("embedded native Python console has no activation callback")
            self.apply_snapshot(self.controller.snapshot)
            self.activate_embedded()
            self.request_render()
            return True
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.snapshot)
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def execute(self, text: str | None = None) -> PythonConsoleSnapshot:
        source = self.input.text if text is None else text
        snapshot = self.controller.execute(source)
        self.input.text = ""
        self.request_render()
        return snapshot

    def clear(self) -> None:
        self.controller.clear()

    def apply_snapshot(self, snapshot: PythonConsoleSnapshot) -> None:
        self.output_model.set_text(snapshot.transcript)
        self.prompt.text = snapshot.prompt
        self.request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.controller.changed.disconnect(self.changed_callback)
        if self.dialog is not None and self.dialog.open:
            self.dialog.close()
        if self.dialog is not None and self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_python_console(
    document: TcDocument,
    controller: PythonConsoleController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    embedded: bool = False,
    activate_embedded: Callable[[], None] | None = None,
) -> NativePythonConsole:
    root = document.create_vstack("native-python-console")
    root.stable_id = "editor.python-console"
    root.preferred_size = Size(920.0, 560.0)
    root.set_layout_padding(EdgeInsets(5.0, 5.0, 5.0, 5.0))
    root.set_layout_spacing(5.0)
    output_model = RichTextModel()
    output = document.create_rich_text_view(output_model)
    output.word_wrap = True
    output.placeholder = "Python console output"
    root.add_stretch_child(_ref(document, output))
    input_row = document.create_hstack("python-console-input")
    input_row.set_layout_spacing(4.0)
    prompt = document.create_status_bar(">>>")
    input_row.add_fixed_child(_ref(document, prompt), 34.0)
    text_input = document.create_text_input()
    input_row.add_stretch_child(_ref(document, text_input))
    run = document.create_button("Run")
    input_row.add_fixed_child(_ref(document, run), 58.0)
    clear = document.create_button("Clear")
    input_row.add_fixed_child(_ref(document, clear), 66.0)
    root.add_fixed_child(input_row, 32.0)
    dialog = None
    if embedded:
        if activate_embedded is None:
            raise ValueError("embedded native Python console requires an activation callback")
    else:
        dialog = document.create_dialog("Python Console")
        dialog.actions = [DialogAction("close", "Close", is_default=False, is_cancel=True)]
        dialog.set_content(root)
    placeholder = lambda _snapshot: None
    result = NativePythonConsole(
        document=document,
        controller=controller,
        dialog=dialog,
        root=root,
        output_model=output_model,
        output=output,
        prompt=prompt,
        input=text_input,
        viewport=viewport,
        request_render=request_render,
        changed_callback=placeholder,
        activate_embedded=activate_embedded,
    )
    weak_result = weakref.ref(result)

    def changed(snapshot: PythonConsoleSnapshot) -> None:
        owner = weak_result()
        if owner is not None:
            owner.apply_snapshot(snapshot)

    result.changed_callback = changed
    controller.changed.connect(changed)

    def submitted(text: str) -> None:
        owner = weak_result()
        if owner is not None:
            owner.execute(text)

    def run_clicked() -> None:
        owner = weak_result()
        if owner is not None:
            owner.execute()

    def clear_clicked() -> None:
        owner = weak_result()
        if owner is not None:
            owner.clear()

    text_input.connect_submitted(submitted)
    run.connect_clicked(run_clicked)
    clear.connect_clicked(clear_clicked)
    result.apply_snapshot(controller.snapshot)
    return result


def connect_python_console_command(menu_bar, command_id: int, console: NativePythonConsole) -> None:
    weak_console = weakref.ref(console)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_console()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativePythonConsole",
    "build_native_python_console",
    "connect_python_console_command",
]
