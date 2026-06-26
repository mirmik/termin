"""
Prefab edit controller — manages prefab isolation mode.

When editing a prefab, the current scene is saved and a temporary scene
is created with the prefab contents. Changes can be saved back to the
prefab file or discarded.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from termin.engine import SceneManager
    from termin.assets.resources import ResourceManager
    from termin.scene import Entity


class PrefabEditController:
    """
    Manages prefab editing in isolation mode.

    Uses SceneManager to create a "prefab" scene for editing.
    The current editor scene is set to INACTIVE while editing prefab.
    """

    def __init__(
        self,
        scene_manager: "SceneManager",
        resource_manager: "ResourceManager",
        on_mode_changed: Optional[Callable[[bool, str | None], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        log_message: Optional[Callable[[str], None]] = None,
        get_editor_scene_name: Optional[Callable[[], str | None]] = None,
    ):
        """
        Args:
            scene_manager: Scene lifecycle manager.
            resource_manager: Resource manager for materials/meshes.
            on_mode_changed: Callback(is_editing, prefab_name) when mode changes.
            on_request_update: Callback to request viewport update.
            log_message: Callback to log messages to console.
            get_editor_scene_name: Callback returning the scene to restore after edit.
        """
        self._scene_manager = scene_manager
        self._resource_manager = resource_manager
        self._on_mode_changed = on_mode_changed
        self._on_request_update = on_request_update
        self._log_message = log_message
        self._get_editor_scene_name = get_editor_scene_name

        self._editing = False
        self._prefab_path: Path | None = None
        self._root_entity: "Entity" | None = None
        self._previous_scene_name: str | None = None

    @property
    def is_editing(self) -> bool:
        """True if currently editing a prefab."""
        return self._editing

    @property
    def prefab_path(self) -> Path | None:
        """Path to the currently edited prefab file."""
        return self._prefab_path

    @property
    def prefab_name(self) -> str | None:
        """Name of the currently edited prefab (filename without extension)."""
        if self._prefab_path is None:
            return None
        return self._prefab_path.stem

    @property
    def root_entity(self) -> "Entity | None":
        """Root entity of the prefab being edited."""
        return self._root_entity

    def open_prefab(self, prefab_path: str | Path) -> bool:
        """
        Enter prefab editing mode.

        Creates a "prefab" scene and sets the current editor scene to INACTIVE.

        Args:
            prefab_path: Path to .prefab file to edit.

        Returns:
            True if prefab was opened successfully.
        """
        if self._editing:
            self._log(f"Already editing prefab: {self.prefab_name}")
            return False

        prefab_path = Path(prefab_path)
        if not prefab_path.exists():
            self._log(f"Prefab file not found: {prefab_path}")
            return False

        self._prefab_path = prefab_path
        self._previous_scene_name = self._current_editor_scene_name()

        # Load prefab into a new "prefab" scene
        try:
            self._load_prefab_into_scene(prefab_path)
        except Exception as e:
            self._log(f"Failed to load prefab: {e}")
            self._prefab_path = None
            self._previous_scene_name = None
            return False

        # Set editor scene to inactive
        from termin.engine import scene as engine_scene
        SceneMode = engine_scene.SceneMode
        if self._previous_scene_name and self._scene_manager.has_scene(self._previous_scene_name):
            self._scene_manager.set_mode(self._previous_scene_name, SceneMode.INACTIVE)

        self._editing = True
        self._log(f"Editing prefab: {self.prefab_name}")

        if self._on_mode_changed:
            self._on_mode_changed(True, self.prefab_name)

        if self._on_request_update:
            self._on_request_update()

        return True

    def save(self) -> bool:
        """
        Save changes to prefab file (without exiting).

        Returns:
            True if saved successfully.
        """
        if not self._editing:
            return False

        if self._prefab_path is None:
            self._log("No prefab path set")
            return False

        # Find root entity from current scene
        root_entity = self._find_prefab_root()
        if root_entity is None:
            self._log("No root entity found in scene")
            return False

        # Save prefab
        try:
            from termin.editor_core.prefab_persistence import PrefabPersistence

            persistence = PrefabPersistence(self._resource_manager)
            stats = persistence.save(root_entity, self._prefab_path)
            self._log(
                f"Saved prefab '{self.prefab_name}': {stats['entities']} entities"
            )
            return True
        except Exception as e:
            self._log(f"Failed to save prefab: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_prefab_root(self) -> "Entity | None":
        """
        Find the prefab root entity in current scene.

        Looks for entity named "[Root]" first, then falls back to
        first serializable root entity (without parent).
        """
        from termin.editor_core.prefab_persistence import PrefabPersistence

        scene = self._scene_manager.get_scene("prefab")
        if scene is None:
            return None

        fallback = None

        for entity in scene.entities:
            # Skip non-serializable entities (editor entities like camera, gizmo)
            if not entity.serializable:
                continue
            # Root entity has no parent
            if entity.transform.parent is not None:
                continue

            # Prefer entity with special root name
            if entity.name == PrefabPersistence.ROOT_ENTITY_NAME:
                return entity

            # Remember first root as fallback
            if fallback is None:
                fallback = entity

        return fallback

    def exit(self) -> None:
        """
        Exit editing mode without saving.

        Closes prefab scene and reactivates editor scene.
        """
        if not self._editing:
            return

        self._log(f"Exited prefab editing: {self.prefab_name}")
        self._exit_editing_mode()

    def save_and_exit(self) -> bool:
        """
        Save changes to prefab file and exit editing mode.

        Returns:
            True if saved successfully.
        """
        if self.save():
            self._exit_editing_mode()
            return True
        return False

    def _exit_editing_mode(self) -> None:
        """Exit editing mode and restore editor scene."""
        prefab_name = self.prefab_name

        # Close prefab scene
        if self._scene_manager.has_scene("prefab"):
            self._scene_manager.close_scene("prefab")

        # Reactivate editor scene
        from termin.engine import scene as engine_scene
        SceneMode = engine_scene.SceneMode
        if self._previous_scene_name and self._scene_manager.has_scene(self._previous_scene_name):
            self._scene_manager.set_mode(self._previous_scene_name, SceneMode.STOP)

        self._editing = False
        self._prefab_path = None
        self._root_entity = None
        self._previous_scene_name = None

        if self._on_mode_changed:
            self._on_mode_changed(False, prefab_name)

        if self._on_request_update:
            self._on_request_update()

    def _load_prefab_into_scene(self, prefab_path: Path) -> None:
        """
        Load prefab contents into a new "prefab" scene.
        """
        from termin.editor_core.prefab_persistence import PrefabPersistence
        from termin.engine import scene as engine_scene
        from termin.engine import default_scene_extensions
        SceneMode = engine_scene.SceneMode

        # Load prefab entity
        persistence = PrefabPersistence(self._resource_manager)
        root_entity = persistence.load(prefab_path)
        self._root_entity = root_entity

        # Create new "prefab" scene
        prefab_scene = self._scene_manager.create_scene("prefab", default_scene_extensions())

        # Add prefab root entity to scene
        prefab_scene.add(root_entity)

        # Set mode to EDITOR for prefab scene
        self._scene_manager.set_mode("prefab", SceneMode.STOP)

    def _current_editor_scene_name(self) -> str | None:
        if self._get_editor_scene_name is not None:
            return self._get_editor_scene_name()
        return "editor"

    def _log(self, message: str) -> None:
        """Log message to console."""
        if self._log_message:
            self._log_message(f"[Prefab] {message}")
