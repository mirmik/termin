"""
Manager for editor dialogs (debug windows, inspectors, etc.).

Handles lazy creation and lifecycle of modal and non-modal dialogs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from termin.editor.undo_stack import UndoStack
    from termin.editor.scene_inspector import SceneInspector
    from termin.editor.undo_stack_viewer import UndoStackViewer
    from termin.editor.framegraph_debugger import FramegraphDebugDialog
    from termin.editor.resource_manager_viewer import ResourceManagerViewer
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.platform.backends.base import GraphicsBackend


class DialogManager:
    """
    Manages editor dialogs with lazy initialization.

    Dialogs are created on first access and reused on subsequent calls.
    """

    def __init__(
        self,
        parent: "QWidget",
        undo_stack: "UndoStack",
        undo_stack_changed_signal,
        get_scene: Callable[[], "Scene"],
        resource_manager: "ResourceManager",
        push_undo_command: Callable,
        request_viewport_update: Callable,
    ):
        self._parent = parent
        self._undo_stack = undo_stack
        self._undo_stack_changed_signal = undo_stack_changed_signal
        self._get_scene = get_scene
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command
        self._request_viewport_update = request_viewport_update

        # Lazy-initialized dialogs
        self._scene_inspector_dialog = None
        self._undo_stack_viewer: "UndoStackViewer | None" = None
        self._framegraph_debugger: "FramegraphDebugDialog | None" = None
        self._resource_manager_viewer: "ResourceManagerViewer | None" = None

    @property
    def framegraph_debugger(self) -> "FramegraphDebugDialog | None":
        """Access to framegraph debugger (may be None if not yet created)."""
        return self._framegraph_debugger

    def show_scene_properties(self) -> None:
        """Opens scene properties dialog."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
        from termin.editor.scene_inspector import SceneInspector

        if self._scene_inspector_dialog is None:
            dialog = QDialog(self._parent)
            dialog.setWindowTitle("Scene Properties")
            dialog.setMinimumWidth(300)

            layout = QVBoxLayout(dialog)

            inspector = SceneInspector(dialog)
            inspector.set_scene(self._get_scene())
            inspector.set_undo_command_handler(self._push_undo_command)
            inspector.scene_changed.connect(self._request_viewport_update)

            layout.addWidget(inspector)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            button_box.rejected.connect(dialog.close)
            layout.addWidget(button_box)

            dialog._inspector = inspector
            self._scene_inspector_dialog = dialog

        # Update values on each open
        self._scene_inspector_dialog._inspector.set_scene(self._get_scene())

        self._scene_inspector_dialog.show()
        self._scene_inspector_dialog.raise_()
        self._scene_inspector_dialog.activateWindow()

    def show_undo_stack_viewer(self) -> None:
        """Opens undo/redo stack viewer window."""
        if self._undo_stack_viewer is None:
            from termin.editor.undo_stack_viewer import UndoStackViewer

            self._undo_stack_viewer = UndoStackViewer(
                self._undo_stack,
                self._parent,
                stack_changed_signal=self._undo_stack_changed_signal,
            )

        self._undo_stack_viewer.refresh()
        self._undo_stack_viewer.show()
        self._undo_stack_viewer.raise_()
        self._undo_stack_viewer.activateWindow()

    def show_framegraph_debugger(
        self,
        graphics: "GraphicsBackend",
        viewport_controller,
    ) -> None:
        """Opens framegraph texture viewer dialog."""
        if self._framegraph_debugger is None:
            from termin.editor.framegraph_debugger import FramegraphDebugDialog

            get_resources = None
            set_source = None
            get_paused = None
            set_paused = None
            get_passes_info = None
            get_pass_internal_symbols = None
            set_pass_internal_symbol = None
            get_debug_blit_pass = None
            get_fbos = lambda: {}

            if viewport_controller is not None:
                get_resources = viewport_controller.get_available_framegraph_resources
                set_source = viewport_controller.set_debug_source_resource
                get_paused = viewport_controller.get_debug_paused
                set_paused = viewport_controller.set_debug_paused
                get_passes_info = viewport_controller.get_passes_info
                get_pass_internal_symbols = viewport_controller.get_pass_internal_symbols
                set_pass_internal_symbol = viewport_controller.set_pass_internal_symbol
                get_debug_blit_pass = viewport_controller.get_debug_blit_pass
                get_fbos = lambda: viewport_controller.render_state.fbos

            self._framegraph_debugger = FramegraphDebugDialog(
                graphics=graphics,
                get_fbos=get_fbos,
                resource_name="debug",
                parent=self._parent,
                get_available_resources=get_resources,
                set_source_resource=set_source,
                get_paused=get_paused,
                set_paused=set_paused,
                get_passes_info=get_passes_info,
                get_pass_internal_symbols=get_pass_internal_symbols,
                set_pass_internal_symbol=set_pass_internal_symbol,
                get_debug_blit_pass=get_debug_blit_pass,
            )

            if viewport_controller is not None:
                viewport_controller.set_framegraph_debugger(self._framegraph_debugger)

        self._framegraph_debugger.debugger_request_update()
        self._framegraph_debugger.show()
        self._framegraph_debugger.raise_()
        self._framegraph_debugger.activateWindow()

    def show_resource_manager_viewer(self) -> None:
        """Opens resource manager viewer dialog."""
        if self._resource_manager_viewer is None:
            from termin.editor.resource_manager_viewer import ResourceManagerViewer

            self._resource_manager_viewer = ResourceManagerViewer(
                self._resource_manager,
                parent=self._parent,
            )

        self._resource_manager_viewer.refresh()
        self._resource_manager_viewer.show()
        self._resource_manager_viewer.raise_()
        self._resource_manager_viewer.activateWindow()

    def show_settings_dialog(self) -> None:
        """Opens editor settings dialog."""
        from termin.editor.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self._parent)
        dialog.exec()
