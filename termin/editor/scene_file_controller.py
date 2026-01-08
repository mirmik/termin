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
from termin._native import log

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager


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
        get_scene_manager: Callable[[], "SceneManager | None"],
        switch_to_scene: Callable[[str], None],
        on_after_save: Callable[[], None],
        get_project_path: Callable[[], str | None] | None = None,
        get_editor_scene_name: Callable[[], str | None] | None = None,
        set_editor_scene_name: Callable[[str | None], None] | None = None,
        log_message: Callable[[str], None] | None = None,
    ):
        self._parent = parent
        self._get_scene_manager = get_scene_manager
        self._switch_to_scene = switch_to_scene
        self._on_after_save = on_after_save
        self._get_project_path = get_project_path
        self._get_editor_scene_name = get_editor_scene_name
        self._set_editor_scene_name = set_editor_scene_name

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

        sm = self._get_scene_manager()
        if sm is not None:
            # Close existing editor scene if any
            old_scene_name = None
            if self._get_editor_scene_name is not None:
                old_scene_name = self._get_editor_scene_name()
            if old_scene_name and sm.has_scene(old_scene_name):
                sm.close_scene(old_scene_name)

            # Create new untitled scene
            new_scene_name = "untitled"
            sm.create_scene(new_scene_name)

            if self._set_editor_scene_name is not None:
                self._set_editor_scene_name(new_scene_name)

            self._switch_to_scene(new_scene_name)

        return True

    def save_scene(self) -> bool:
        """
        Save scene to current file or prompt for new file.

        Returns:
            True if saved, False otherwise.
        """
        sm = self._get_scene_manager()
        if sm is None:
            return False

        scene_name = self._get_editor_scene_name() if self._get_editor_scene_name else None
        current_path = sm.get_scene_path(scene_name) if scene_name else None
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
        import os
        default_dir = ""
        if self._get_project_path is not None:
            project_path = self._get_project_path()
            if project_path:
                default_dir = project_path
        default_path = os.path.join(default_dir, "scene.scene") if default_dir else "scene.scene"

        file_path, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Save Scene As",
            default_path,
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
            sm = self._get_scene_manager()
            if sm is None:
                raise RuntimeError("SceneManager not initialized")

            scene_name = None
            if self._get_editor_scene_name is not None:
                scene_name = self._get_editor_scene_name()
            if scene_name is None:
                raise RuntimeError("No editor scene to save")

            sm.save_scene(scene_name, file_path)
            EditorSettings.instance().set_last_scene_path(file_path)
            log.info(f"Scene saved: {file_path}")
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
        default_dir = ""
        if self._get_project_path is not None:
            project_path = self._get_project_path()
            if project_path:
                default_dir = project_path

        file_path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Load Scene",
            default_dir,
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
        import os

        try:
            sm = self._get_scene_manager()
            if sm is None:
                raise RuntimeError("SceneManager not initialized")

            # Get scene name from file path
            new_scene_name = os.path.splitext(os.path.basename(file_path))[0]

            # Close existing editor scene if any
            old_scene_name = None
            if self._get_editor_scene_name is not None:
                old_scene_name = self._get_editor_scene_name()
            if old_scene_name and sm.has_scene(old_scene_name):
                sm.close_scene(old_scene_name)

            # Set editor scene name BEFORE load (load triggers _restore_editor_state)
            if self._set_editor_scene_name is not None:
                self._set_editor_scene_name(new_scene_name)

            sm.load_scene(new_scene_name, file_path)

            self._switch_to_scene(new_scene_name)

            EditorSettings.instance().set_last_scene_path(file_path)
            log.info(f"Scene loaded: {file_path}")
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
        import os

        settings = EditorSettings.instance()
        last_scene_path = settings.get_last_scene_path()

        if last_scene_path is None:
            return False

        try:
            sm = self._get_scene_manager()
            if sm is None:
                return False

            # Get scene name from file path
            new_scene_name = os.path.splitext(os.path.basename(str(last_scene_path)))[0]

            # Close existing editor scene if any
            old_scene_name = None
            if self._get_editor_scene_name is not None:
                old_scene_name = self._get_editor_scene_name()
            if old_scene_name and sm.has_scene(old_scene_name):
                sm.close_scene(old_scene_name)

            # Set editor scene name BEFORE load (load triggers _restore_editor_state)
            if self._set_editor_scene_name is not None:
                self._set_editor_scene_name(new_scene_name)

            sm.load_scene(new_scene_name, str(last_scene_path))

            self._switch_to_scene(new_scene_name)
            return True

        except Exception as e:
            import traceback
            log.warning(f"Could not restore last scene: {e}\n{traceback.format_exc()}")
            return False
