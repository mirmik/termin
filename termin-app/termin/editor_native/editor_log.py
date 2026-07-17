"""Native projection of the editor/build log."""

from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.editor_log_model import EditorLogModel
from termin.gui_native import Document, RichTextModel, WidgetRef


@dataclass
class NativeEditorLog:
    root: WidgetRef
    output_model: RichTextModel
    output: object
    controller: EditorLogModel
    changed_callback: object

    def close(self) -> None:
        self.controller.changed.disconnect(self.changed_callback)


def build_native_editor_log(document: Document, controller: EditorLogModel, request_render) -> NativeEditorLog:
    root = document.create_vstack("native-editor-log")
    root.stable_id = "editor.log"
    output_model = RichTextModel()
    output_model.set_text(controller.text)
    output = document.create_rich_text_view(output_model)
    output.word_wrap = True
    output.placeholder = "Editor and build messages"
    root.add_stretch_child(document.ref(output.handle))
    clear = document.create_button("Clear")
    root.add_fixed_child(document.ref(clear.handle), 30.0)

    def changed(text: str) -> None:
        output_model.set_text(text)
        request_render()

    controller.changed.connect(changed)
    clear.connect_clicked(controller.clear)
    return NativeEditorLog(root, output_model, output, controller, changed)


__all__ = ["NativeEditorLog", "build_native_editor_log"]
