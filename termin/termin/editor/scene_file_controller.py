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
from termin.project.settings import ProjectSettingsManager
from tcbase import log

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
        on_before_close_scene: Callable[[str], None] | None = None,
        store_editor_data: Callable[[str, dict], None] | None = None,
        collect_editor_data: Callable[[], dict] | None = None,
    ):
        self._parent = parent
        self._get_scene_manager = get_scene_manager
        self._switch_to_scene = switch_to_scene
        self._on_after_save = on_after_save
        self._get_project_path = get_project_path
        self._get_editor_scene_name = get_editor_scene_name
        self._set_editor_scene_name = set_editor_scene_name
        self._on_before_close_scene = on_before_close_scene
        self._store_editor_data = store_editor_data
        self._collect_editor_data = collect_editor_data

    def _validate_scene_path(self, file_path: str) -> bool:
        """Check that scene file is inside the project directory.

        Returns True if valid or no project is open.
        Shows a warning dialog and returns False if outside project.
        """
        import os
        if self._get_project_path is None:
            return True
        project_path = self._get_project_path()
        if not project_path:
            return True

        real_file = os.path.realpath(file_path)
        real_project = os.path.realpath(project_path)
        if not real_file.startswith(real_project + os.sep) and real_file != real_project:
            QMessageBox.warning(
                self._parent,
                "Scene Outside Project",
                f"The scene file must be inside the project directory.\n\n"
                f"Scene: {file_path}\n"
                f"Project: {project_path}",
            )
            return False
        return True

    def _update_last_scene(self, file_path: str) -> None:
        """Store last scene path in both project settings and global settings."""
        EditorSettings.instance().set_last_scene_path(file_path)
        psm = ProjectSettingsManager.instance()
        if psm.project_path is not None:
            psm.set_last_scene(file_path)

    def new_scene(self) -> bool:
        """
        Create new scene from default template with confirmation.

        Returns:
            True if scene was created, False if cancelled.
        """
        import os
        import tempfile
        from termin.default_scene import write_default_scene

        reply = QMessageBox.question(
            self._parent,
            "New Scene",
            "Create a new scene?\n\nThis will remove all entities and resources.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return False

        sm = self._get_scene_manager()
        if sm is None:
            return False

        # Close existing editor scene if any
        old_scene_name = None
        if self._get_editor_scene_name is not None:
            old_scene_name = self._get_editor_scene_name()
        if old_scene_name and sm.has_scene(old_scene_name):
            if self._on_before_close_scene is not None:
                self._on_before_close_scene(old_scene_name)
            sm.close_scene(old_scene_name)

        # Load default scene template via temp file
        new_scene_name = "untitled"
        fd, tmp_path = tempfile.mkstemp(suffix=".scene")
        try:
            os.close(fd)
            write_default_scene(tmp_path)

            if self._set_editor_scene_name is not None:
                self._set_editor_scene_name(new_scene_name)

            sm.load_scene(new_scene_name, tmp_path)

            if self._store_editor_data is not None:
                editor_data = self._extract_editor_data(tmp_path)
                self._store_editor_data(new_scene_name, editor_data)
        finally:
            os.unlink(tmp_path)

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
        if not self._validate_scene_path(file_path):
            return False

        try:
            sm = self._get_scene_manager()
            if sm is None:
                raise RuntimeError("SceneManager not initialized")

            scene_name = None
            if self._get_editor_scene_name is not None:
                scene_name = self._get_editor_scene_name()
            if scene_name is None:
                raise RuntimeError("No editor scene to save")

            # Collect editor data
            editor_data = None
            if self._collect_editor_data is not None:
                editor_data = self._collect_editor_data()

            sm.save_scene(scene_name, file_path, editor_data)
            self._update_last_scene(file_path)
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

        if not self._validate_scene_path(file_path):
            return False

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
                # Notify before closing (unbind UI, set INACTIVE)
                if self._on_before_close_scene is not None:
                    self._on_before_close_scene(old_scene_name)
                sm.close_scene(old_scene_name)

            # Set editor scene name BEFORE load (load triggers _restore_editor_state)
            if self._set_editor_scene_name is not None:
                self._set_editor_scene_name(new_scene_name)

            sm.load_scene(new_scene_name, file_path)

            # Extract and store editor data for later application
            if self._store_editor_data is not None:
                editor_data = self._extract_editor_data(file_path)
                self._store_editor_data(new_scene_name, editor_data)

            self._switch_to_scene(new_scene_name)

            self._update_last_scene(file_path)
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

        Checks per-project settings first, falls back to global editor settings.

        Returns:
            True if loaded, False if no last scene or error.
        """
        import os
        from pathlib import Path

        # Per-project last scene has priority
        last_scene_path = None
        psm = ProjectSettingsManager.instance()
        project_scene = psm.get_last_scene()
        if project_scene is not None and os.path.isfile(project_scene):
            last_scene_path = Path(project_scene)

        # Fallback to global editor settings
        if last_scene_path is None:
            last_scene_path = EditorSettings.instance().get_last_scene_path()

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

            # Extract and store editor data
            if self._store_editor_data is not None:
                editor_data = self._extract_editor_data(str(last_scene_path))
                self._store_editor_data(new_scene_name, editor_data)

            self._switch_to_scene(new_scene_name)
            return True

        except Exception as e:
            import traceback
            log.warning(f"Could not restore last scene: {e}\n{traceback.format_exc()}")
            return False

    def _extract_editor_data(self, file_path: str) -> dict:
        """Extract editor data from scene file."""
        import json
        from termin._native.scene import SceneManager

        json_str = SceneManager.read_json_file(file_path)
        if not json_str:
            return {}

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {}

        editor_data = data.get("editor", {})
        scene_data = data.get("scene") or (data.get("scenes", [{}])[0] if data.get("scenes") else {})

        result = {}

        # Camera (check both locations for backwards compatibility)
        camera_data = editor_data.get("camera")
        if camera_data is None and scene_data:
            camera_data = scene_data.get("editor_camera")
        if camera_data is not None:
            result["camera"] = camera_data

        # Selection
        selected = editor_data.get("selected_entity")
        if selected is None:
            editor_state = data.get("editor_state", {})
            selected = editor_state.get("selected_entity_name")
        if selected:
            result["selected_entity"] = selected

        # Displays
        displays = editor_data.get("displays")
        if displays is not None:
            result["displays"] = displays

        # Expanded entities
        expanded = editor_data.get("expanded_entities")
        if expanded is not None:
            result["expanded_entities"] = expanded

        return result
