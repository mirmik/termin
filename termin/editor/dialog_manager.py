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
    from termin.editor.audio_debugger import AudioDebugDialog
    from termin.editor.core_registry_viewer import CoreRegistryViewer
    from termin.editor.project_file_watcher import ProjectFileWatcher
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
        project_file_watcher: "ProjectFileWatcher | None" = None,
    ):
        self._parent = parent
        self._undo_stack = undo_stack
        self._undo_stack_changed_signal = undo_stack_changed_signal
        self._get_scene = get_scene
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command
        self._request_viewport_update = request_viewport_update
        self._project_file_watcher = project_file_watcher

        # Lazy-initialized dialogs
        self._scene_inspector_dialog = None
        self._undo_stack_viewer: "UndoStackViewer | None" = None
        self._framegraph_debugger: "FramegraphDebugDialog | None" = None
        self._resource_manager_viewer: "ResourceManagerViewer | None" = None
        self._audio_debugger: "AudioDebugDialog | None" = None
        self._core_registry_viewer: "CoreRegistryViewer | None" = None
        self._inspect_registry_viewer = None
        self._navmesh_registry_viewer = None

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
        window_backend,
        graphics: "GraphicsBackend",
        rendering_controller,
        on_request_update=None,
        initial_resource: str | None = None,
    ):
        """Opens framegraph texture viewer dialog.

        Args:
            window_backend: SDL window backend.
            graphics: Graphics backend.
            rendering_controller: Rendering controller.
            on_request_update: Callback for requesting render update.
            initial_resource: Initial resource to show (e.g., "shadow_maps").

        Returns:
            The FramegraphDebugDialog instance.
        """
        # Always create new dialog (old one is destroyed on close)
        from termin.editor.framegraph_debugger import FramegraphDebugDialog

        self._framegraph_debugger = FramegraphDebugDialog(
            window_backend=window_backend,
            graphics=graphics,
            rendering_controller=rendering_controller,
            on_request_update=on_request_update,
            parent=self._parent,
        )
        # Clear reference when dialog is destroyed
        self._framegraph_debugger.destroyed.connect(self._on_framegraph_debugger_destroyed)

        if initial_resource:
            self._framegraph_debugger.set_initial_resource(initial_resource)

        self._framegraph_debugger.debugger_request_update()
        self._framegraph_debugger.show()
        self._framegraph_debugger.raise_()
        self._framegraph_debugger.activateWindow()
        return self._framegraph_debugger

    def _on_framegraph_debugger_destroyed(self) -> None:
        """Called when framegraph debugger is destroyed."""
        self._framegraph_debugger = None

    def show_resource_manager_viewer(self) -> None:
        """Opens resource manager viewer dialog."""
        if self._resource_manager_viewer is None:
            from termin.editor.resource_manager_viewer import ResourceManagerViewer

            self._resource_manager_viewer = ResourceManagerViewer(
                self._resource_manager,
                project_file_watcher=self._project_file_watcher,
                parent=self._parent,
            )

        self._resource_manager_viewer.refresh()
        self._resource_manager_viewer.show()
        self._resource_manager_viewer.raise_()
        self._resource_manager_viewer.activateWindow()

    def show_audio_debugger(self) -> None:
        """Opens audio debugger dialog."""
        if self._audio_debugger is None:
            from termin.editor.audio_debugger import AudioDebugDialog

            self._audio_debugger = AudioDebugDialog(parent=self._parent)

        self._audio_debugger.show()
        self._audio_debugger.raise_()
        self._audio_debugger.activateWindow()

    def show_core_registry_viewer(self) -> None:
        """Opens core registry viewer dialog."""
        if self._core_registry_viewer is None:
            from termin.editor.core_registry_viewer import CoreRegistryViewer

            self._core_registry_viewer = CoreRegistryViewer(parent=self._parent)

        self._core_registry_viewer.refresh()
        self._core_registry_viewer.show()
        self._core_registry_viewer.raise_()
        self._core_registry_viewer.activateWindow()

    def show_inspect_registry_viewer(self) -> None:
        """Opens inspect registry viewer dialog."""
        if self._inspect_registry_viewer is None:
            from termin.editor.inspect_registry_viewer import InspectRegistryViewer

            self._inspect_registry_viewer = InspectRegistryViewer(parent=self._parent)

        self._inspect_registry_viewer.refresh()
        self._inspect_registry_viewer.show()
        self._inspect_registry_viewer.raise_()
        self._inspect_registry_viewer.activateWindow()

    def show_navmesh_registry_viewer(self) -> None:
        """Opens NavMesh registry viewer dialog."""
        if self._navmesh_registry_viewer is None:
            from termin.editor.navmesh_registry_viewer import NavMeshRegistryViewer

            self._navmesh_registry_viewer = NavMeshRegistryViewer(parent=self._parent)

        self._navmesh_registry_viewer.refresh()
        self._navmesh_registry_viewer.show()
        self._navmesh_registry_viewer.raise_()
        self._navmesh_registry_viewer.activateWindow()

    def show_settings_dialog(self) -> None:
        """Opens editor settings dialog."""
        from termin.editor.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self._parent)
        dialog.exec()

    def show_layers_dialog(self) -> None:
        """Opens layers and flags configuration dialog."""
        from termin.editor.layers_dialog import LayersDialog

        scene = self._get_scene()
        dialog = LayersDialog(scene, self._parent)
        dialog.exec()

    def show_shadow_settings_dialog(self) -> None:
        """Opens shadow settings dialog (non-modal for live preview)."""
        from termin.editor.shadow_settings_dialog import ShadowSettingsDialog

        # Reuse existing dialog if open
        if hasattr(self, '_shadow_settings_dialog') and self._shadow_settings_dialog is not None:
            self._shadow_settings_dialog.raise_()
            self._shadow_settings_dialog.activateWindow()
            return

        scene = self._get_scene()
        dialog = ShadowSettingsDialog(
            scene,
            self._parent,
            on_changed=self._request_viewport_update,
        )
        dialog.setModal(False)
        dialog.finished.connect(lambda: setattr(self, '_shadow_settings_dialog', None))
        self._shadow_settings_dialog = dialog
        dialog.show()

    def show_agent_types_dialog(self) -> None:
        """Opens agent types configuration dialog."""
        from termin.editor.agent_types_dialog import AgentTypesDialog

        # Reuse existing dialog if open
        if hasattr(self, '_agent_types_dialog') and self._agent_types_dialog is not None:
            self._agent_types_dialog.raise_()
            self._agent_types_dialog.activateWindow()
            return

        dialog = AgentTypesDialog(
            parent=self._parent,
            on_changed=self._request_viewport_update,
        )
        dialog.setModal(False)
        dialog.finished.connect(lambda: setattr(self, '_agent_types_dialog', None))
        self._agent_types_dialog = dialog
        dialog.show()
