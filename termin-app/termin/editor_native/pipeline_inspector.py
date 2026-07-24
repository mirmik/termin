"""Native summary projection for pipeline assets."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable
import weakref

from termin.editor_core.pipeline_inspector_model import (
    PipelineInspectorController,
    PipelineInspectorSnapshot,
)
from termin.gui_native import TcDocument, Size, WidgetRef

from .resource_inspectors import _clear, _label_row


_logger = logging.getLogger(__name__)


@dataclass
class NativePipelineInspector:
    document: TcDocument
    controller: PipelineInspectorController
    root: WidgetRef
    request_render: Callable[[], None]
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, target, *, name: str = "", file_path: str | None = None) -> None:
        self.rebuild(self.controller.set_target(target, name=name, file_path=file_path))

    def rebuild(self, snapshot: PipelineInspectorSnapshot) -> None:
        _clear(self.document, self.root, self.controls)
        if not snapshot.available:
            self.root.add_fixed_child(self.document.create_label(snapshot.message), 28.0)
            self.request_render()
            return
        for label, value, key in (
            ("Name", snapshot.name, "name"),
            ("Path", snapshot.path, "path"),
            ("Nodes", str(snapshot.nodes), "nodes"),
            ("Connections", str(snapshot.connections), "connections"),
        ):
            _label_row(self.document, self.root, self.controls, label, value, key)
        self.root.add_fixed_child(self.document.create_label("Passes"), 24.0)
        if snapshot.passes:
            for index, name in enumerate(snapshot.passes):
                self.root.add_fixed_child(
                    self.document.create_label(name, f"native-pipeline-pass-{index}"),
                    24.0,
                )
        else:
            self.root.add_fixed_child(self.document.create_label("No compiled passes"), 24.0)
        if snapshot.path:
            edit = self.document.create_button("Edit Pipeline")
            owner = weakref.ref(self)

            def clicked() -> None:
                current = owner()
                if current is not None:
                    current.controller.edit()
                    current.request_render()

            edit.connect_clicked(clicked)
            self.root.add_fixed_child(edit.widget, 28.0)
            self.controls["edit"] = edit
        self.root.preferred_size = Size(300.0, 4.0 * 28.0 + (len(snapshot.passes) + 1) * 24.0 + 28.0)
        self.request_render()


def build_native_pipeline_inspector(
    document: TcDocument,
    controller: PipelineInspectorController,
    *,
    request_render: Callable[[], None],
) -> NativePipelineInspector:
    root = document.create_vstack("native-pipeline-inspector")
    root.set_layout_spacing(2.0)
    return NativePipelineInspector(document, controller, root, request_render)


__all__ = ["NativePipelineInspector", "build_native_pipeline_inspector"]
