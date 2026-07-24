"""Editor window integration for the C++ Framegraph Debugger view."""

from __future__ import annotations

from dataclasses import dataclass
import weakref
from typing import Callable

from termin.editor._editor_native import FrameGraphDebuggerView
from termin.editor_native.ui_host import EditorWindowRegistry, EditorWindowSlot
from termin.gui_native import (
    TcDocument,
    tc_ui_document_create,
    tc_ui_document_destroy,
)


@dataclass
class NativeFramegraphDebugger:
    """Attach the native view to the editor's secondary-window lifecycle."""

    document: TcDocument
    model: object
    window_manager: EditorWindowRegistry
    view: FrameGraphDebuggerView
    request_scene_render: Callable[[], None]
    window: EditorWindowSlot | None = None
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native framegraph debugger is closed")
        if self.window is not None and not self.window.closed:
            return False
        self.view.activate()
        try:
            window = self.window_manager.create_window(
                "Framegraph Debugger",
                1180,
                760,
                document=self.document,
                always_on_top=True,
                on_close=self._on_window_closed,
            )
        except Exception:
            self.view.deactivate()
            raise
        self.window = window
        window.content.add_pre_render_callback(self.view.render_previews)
        self.request_render()
        return True

    def update(self) -> bool:
        if self.window is None or self.window.closed:
            return False
        return self.view.update()

    def show_resource(self, resource_name: str) -> bool:
        if self.window is None or self.window.closed:
            self.show()
        return self.view.show_resource(resource_name)

    def refresh_depth(self) -> str:
        return self.view.refresh_depth(self.window_manager.main.content.device)

    def dismiss(self) -> None:
        if self.window is not None and not self.window.closed:
            self.window.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.dismiss()
        self.view.close()
        tc_ui_document_destroy(self.document)

    def request_render(self) -> None:
        self.request_scene_render()
        if self.window is not None and not self.window.closed:
            self.window.request_render_update()

    def _on_window_closed(self) -> None:
        window = self.window
        if window is not None:
            window.content.remove_pre_render_callback(self.view.render_previews)
        self.window = None
        self.view.deactivate()


def build_native_framegraph_debugger(
    window_manager: EditorWindowRegistry,
    model: object,
    *,
    request_render: Callable[[], None],
) -> NativeFramegraphDebugger:
    document = tc_ui_document_create()
    try:
        return _build_native_framegraph_debugger(
            document,
            window_manager,
            model,
            request_render=request_render,
        )
    except Exception:
        tc_ui_document_destroy(document)
        raise


def _build_native_framegraph_debugger(
    document: TcDocument,
    window_manager: EditorWindowRegistry,
    model: object,
    *,
    request_render: Callable[[], None],
) -> NativeFramegraphDebugger:
    owner_ref: weakref.ReferenceType[NativeFramegraphDebugger] | None = None

    def request_native_render() -> None:
        owner = owner_ref() if owner_ref is not None else None
        if owner is not None:
            owner.request_render()
        else:
            request_render()

    view = FrameGraphDebuggerView(document, model, request_native_render)
    result = NativeFramegraphDebugger(
        document=document,
        model=model,
        window_manager=window_manager,
        view=view,
        request_scene_render=request_render,
    )
    owner_ref = weakref.ref(result)
    return result


def connect_framegraph_debugger_command(menu_bar, command_id: int, debugger) -> None:
    weak_debugger = weakref.ref(debugger)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_debugger()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeFramegraphDebugger",
    "build_native_framegraph_debugger",
    "connect_framegraph_debugger_command",
]
