"""
Scene file operations controller.

Handles new/save/load scene operations with dialogs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from termin.editor.settings import EditorSettings

if TYPE_CHECKING:
    from termin.editor.world_persistence import WorldPersistence


class SceneFileController:
    """
    Handles scene file operations (new, save, load).

    Provides:
    - New scene with confirmation dialog
    - Save/Save As with file dialog
    - Load with file dialog
    - Auto-load last scene on startup
    """

    def __init__(
        self,
        parent: QWidget,
        get_world_persistence: Callable[[], "WorldPersistence | None"],
        on_after_new: Callable[[], None],
        on_after_save: Callable[[], None],
        on_after_load: Callable[[], None],
        log_message: Callable[[str], None] | None = None,
    ):
        self._parent = parent
        self._get_world_persistence = get_world_persistence
        self._on_after_new = on_after_new
        self._on_after_save = on_after_save
        self._on_after_load = on_after_load
        self._log = log_message or (lambda msg: None)

    def new_scene(self) -> bool:
        """
        Create new empty scene with confirmation.

        Returns:
            True if scene was created, False if cancelled.
        """
        reply = QMessageBox.question(
            self._parent,
            "New Scene",
            "Create a new empty scene?\n\nThis will remove all entities and resources.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return False

        wp = self._get_world_persistence()
        if wp is not None:
            wp.reset()

        self._on_after_new()
        return True

    def save_scene(self) -> bool:
        """
        Save scene to current file or prompt for new file.

        Returns:
            True if saved, False otherwise.
        """
        wp = self._get_world_persistence()
        if wp is None:
            return False

        current_path = wp.current_scene_path
        if current_path is not None:
            return self.save_scene_to_file(current_path)
        else:
            return self.save_scene_as()

    def save_scene_as(self) -> bool:
        """
        Save scene to new file with dialog.

        Returns:
            True if saved, False if cancelled.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Save Scene As",
            "scene.scene",
            "Scene Files (*.scene);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return False

        if not file_path.endswith(".scene"):
            file_path += ".scene"

        return self.save_scene_to_file(file_path)

    def save_scene_to_file(self, file_path: str) -> bool:
        """
        Save scene to specified file.

        Returns:
            True if saved, False on error.
        """
        try:
            wp = self._get_world_persistence()
            if wp is None:
                raise RuntimeError("WorldPersistence not initialized")

            wp.save(file_path)
            EditorSettings.instance().set_last_scene_path(file_path)
            self._log(f"Scene saved: {file_path}")
            self._on_after_save()
            return True

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self._parent,
                "Error Saving Scene",
                f"Failed to save scene to:\n{file_path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )
            return False

    def load_scene(self) -> bool:
        """
        Load scene with file dialog.

        Returns:
            True if loaded, False if cancelled.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Load Scene",
            "",
            "Scene Files (*.scene);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return False

        return self.load_scene_from_file(file_path)

    def load_scene_from_file(self, file_path: str) -> bool:
        """
        Load scene from specified file.

        Returns:
            True if loaded, False on error.
        """
        try:
            wp = self._get_world_persistence()
            if wp is None:
                raise RuntimeError("WorldPersistence not initialized")

            wp.load(file_path)
            EditorSettings.instance().set_last_scene_path(file_path)
            self._log(f"Scene loaded: {file_path}")
            self._on_after_load()
            return True

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self._parent,
                "Error Loading Scene",
                f"Failed to load scene from:\n{file_path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )
            return False

    def load_last_scene(self) -> bool:
        """
        Load last opened scene on editor startup.

        Returns:
            True if loaded, False if no last scene or error.
        """
        settings = EditorSettings.instance()
        last_scene_path = settings.get_last_scene_path()

        if last_scene_path is None:
            self._on_after_load()  # Update title even without scene
            return False

        try:
            wp = self._get_world_persistence()
            if wp is None:
                return False

            wp.load(str(last_scene_path))
            self._on_after_load()
            return True

        except Exception as e:
            import traceback
            self._log(f"Could not restore last scene: {e}\n{traceback.format_exc()}")
            self._on_after_load()  # Update title
            return False
