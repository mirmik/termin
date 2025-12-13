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
    from termin.editor.world_persistence import WorldPersistence
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.entity import Entity


class PrefabEditController:
    """
    Manages prefab editing in isolation mode.

    Similar to GameModeController but for editing prefabs.
    Saves the current scene state, loads prefab into a temporary scene,
    and allows saving changes back to the prefab or discarding them.
    """

    def __init__(
        self,
        world_persistence: "WorldPersistence",
        resource_manager: "ResourceManager",
        on_mode_changed: Optional[Callable[[bool, str | None], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        log_message: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            world_persistence: Scene lifecycle manager.
            resource_manager: Resource manager for materials/meshes.
            on_mode_changed: Callback(is_editing, prefab_name) when mode changes.
            on_request_update: Callback to request viewport update.
            log_message: Callback to log messages to console.
        """
        self._world_persistence = world_persistence
        self._resource_manager = resource_manager
        self._on_mode_changed = on_mode_changed
        self._on_request_update = on_request_update
        self._log_message = log_message

        self._editing = False
        self._prefab_path: Path | None = None
        self._saved_scene_state: dict | None = None
        self._root_entity: "Entity" | None = None

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

        Saves current scene state and loads prefab into a temporary scene.

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

        # Save current scene state
        self._saved_scene_state = self._world_persistence.save_state()
        self._prefab_path = prefab_path

        # Load prefab into a new scene
        try:
            self._load_prefab_into_scene(prefab_path)
        except Exception as e:
            self._log(f"Failed to load prefab: {e}")
            self._saved_scene_state = None
            self._prefab_path = None
            return False

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

        # Find root entity from current scene (not the cached one)
        root_entity = self._find_prefab_root()
        if root_entity is None:
            self._log("No root entity found in scene")
            return False

        # Save prefab
        try:
            from termin.editor.prefab_persistence import PrefabPersistence

            persistence = PrefabPersistence(self._resource_manager)
            stats = persistence.save(root_entity, self._prefab_path)
            self._log(
                f"Saved prefab '{self.prefab_name}': "
                f"{stats['entities']} entities, {stats['materials']} materials"
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
        from termin.editor.prefab_persistence import PrefabPersistence

        scene = self._world_persistence.scene
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

        Simply restores the original scene.
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
        """Exit editing mode and restore original scene."""
        prefab_name = self.prefab_name

        # Restore original scene
        if self._saved_scene_state is not None:
            self._world_persistence.restore_state(self._saved_scene_state)
            self._saved_scene_state = None

        self._editing = False
        self._prefab_path = None
        self._root_entity = None

        if self._on_mode_changed:
            self._on_mode_changed(False, prefab_name)

        if self._on_request_update:
            self._on_request_update()

    def _load_prefab_into_scene(self, prefab_path: Path) -> None:
        """
        Load prefab contents into a new empty scene.
        """
        from termin.editor.prefab_persistence import PrefabPersistence
        from termin.visualization.core.scene import Scene

        # Load prefab entity
        persistence = PrefabPersistence(self._resource_manager)
        root_entity = persistence.load(prefab_path)
        self._root_entity = root_entity

        # Create new empty scene
        new_scene = Scene()

        # Add prefab root entity to scene
        new_scene.add(root_entity)

        # Replace current scene (triggers on_scene_changed in EditorWindow)
        self._world_persistence.replace_scene(new_scene)

    def _log(self, message: str) -> None:
        """Log message to console."""
        if self._log_message:
            self._log_message(f"[Prefab] {message}")
