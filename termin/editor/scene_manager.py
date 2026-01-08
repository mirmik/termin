"""
SceneManager - manages scene lifecycle, update cycles, and editor state.

Responsibilities:
- Named scene storage and lifecycle (create, copy, load, save, close)
- Scene modes (INACTIVE, EDITOR, GAME)
- Editor entities injection
- Scene update tick
- Editor state persistence (camera, selection, expanded entities)
- Debug info
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.resources import ResourceManager


class SceneMode(Enum):
    """Scene update mode."""
    INACTIVE = 0  # Loaded but not updated
    EDITOR = 1    # Editor update (gizmos, selection)
    GAME = 2      # Full simulation


def numpy_encoder(obj):
    """Convert numpy types to Python types for JSON."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _validate_serializable(obj, path: str = ""):
    """Validate that object contains only JSON-serializable types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return
    if isinstance(obj, (np.floating, np.integer)):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _validate_serializable(v, f"{path}.{k}" if path else k)
        return
    if isinstance(obj, (list, tuple, np.ndarray)):
        for i, v in enumerate(obj):
            _validate_serializable(v, f"{path}[{i}]")
        return
    raise TypeError(f"Non-serializable type {type(obj).__name__} at path: {path or 'root'}")


class SceneManager:
    """
    Manages scene lifecycle, update cycles, and editor state.

    Scenes are identified by name (e.g., "editor", "game", "prefab_preview").
    Each scene has a mode controlling how it's updated.

    Standard scene names:
    - "editor" - main editor scene
    - "game" - copy of editor scene for game mode
    - "prefab" - isolated scene for prefab editing
    """

    def __init__(
        self,
        resource_manager: "ResourceManager",
        scene_factory: Optional[Callable[[], "Scene"]] = None,
        on_scene_changed: Optional[Callable[[str, "Scene | None"], None]] = None,
        # Editor state callbacks
        get_editor_camera_data: Optional[Callable[[], dict]] = None,
        set_editor_camera_data: Optional[Callable[[dict], None]] = None,
        get_selected_entity_name: Optional[Callable[[], str | None]] = None,
        select_entity_by_name: Optional[Callable[[str], None]] = None,
        get_displays_data: Optional[Callable[[], list]] = None,
        set_displays_data: Optional[Callable[[list], None]] = None,
        get_expanded_entities: Optional[Callable[[], list[str]]] = None,
        set_expanded_entities: Optional[Callable[[list[str]], None]] = None,
        rescan_file_resources: Optional[Callable[[], None]] = None,
    ):
        """
        Args:
            resource_manager: Resource manager for loading assets.
            scene_factory: Factory for creating new scenes. If None, uses Scene().
            on_scene_changed: Callback when scene changes (name, scene).
            get_editor_camera_data: Callback to get editor camera state.
            set_editor_camera_data: Callback to set editor camera state.
            get_selected_entity_name: Callback to get selected entity name.
            select_entity_by_name: Callback to select entity by name.
            get_displays_data: Callback to get displays/viewports data.
            set_displays_data: Callback to set displays/viewports data.
            get_expanded_entities: Callback to get expanded entity names in tree.
            set_expanded_entities: Callback to set expanded entity names.
            rescan_file_resources: Callback to rescan project file resources.
        """
        self._resource_manager = resource_manager
        self._scene_factory = scene_factory
        self._on_scene_changed = on_scene_changed

        # Editor state callbacks
        self._get_editor_camera_data = get_editor_camera_data
        self._set_editor_camera_data = set_editor_camera_data
        self._get_selected_entity_name = get_selected_entity_name
        self._select_entity_by_name = select_entity_by_name
        self._get_displays_data = get_displays_data
        self._set_displays_data = set_displays_data
        self._get_expanded_entities = get_expanded_entities
        self._set_expanded_entities = set_expanded_entities
        self._rescan_file_resources = rescan_file_resources

        # Named scenes
        self._scenes: dict[str, "Scene"] = {}
        self._modes: dict[str, SceneMode] = {}
        self._paths: dict[str, str | None] = {}  # scene_name -> file_path

        # Resources initialized flag
        self._resources_initialized: bool = False

        # Active scene name
        self._active_scene_name: str | None = None

    @property
    def resource_manager(self) -> "ResourceManager":
        """Resource manager."""
        return self._resource_manager

    @property
    def scene_names(self) -> list[str]:
        """List of all scene names."""
        return list(self._scenes.keys())

    @property
    def active_scene_name(self) -> str | None:
        """Name of the currently active scene."""
        return self._active_scene_name

    @property
    def scene(self) -> "Scene | None":
        """Currently active scene (for backwards compatibility)."""
        if self._active_scene_name is None:
            return None
        return self._scenes.get(self._active_scene_name)

    @property
    def current_scene_path(self) -> str | None:
        """Path of the currently active scene."""
        if self._active_scene_name is None:
            return None
        return self._paths.get(self._active_scene_name)

    def initialize_resources(self) -> None:
        """
        Initialize file resources once on startup.
        Should be called once after editor is ready.
        """
        if self._resources_initialized:
            return
        self._resources_initialized = True

        if self._rescan_file_resources is not None:
            self._rescan_file_resources()

    # --- Scene Factory ---

    def _create_new_scene(self) -> "Scene":
        """Create a new empty scene."""
        if self._scene_factory is not None:
            return self._scene_factory()
        from termin.visualization.core.scene import Scene
        return Scene()

    # --- Scene Lifecycle ---

    def create_scene(self, name: str, activate: bool = True) -> "Scene":
        """
        Create a new empty scene with given name.

        Args:
            name: Scene name (must be unique).
            activate: If True, set as active scene.

        Returns:
            Created scene.

        Raises:
            ValueError: If scene with this name already exists.
        """
        if name in self._scenes:
            raise ValueError(f"Scene '{name}' already exists")

        scene = self._create_new_scene()
        self._scenes[name] = scene
        self._modes[name] = SceneMode.INACTIVE
        self._paths[name] = None

        if activate:
            self._active_scene_name = name
            self._modes[name] = SceneMode.EDITOR

        self._notify_scene_changed(name, scene)
        return scene

    def copy_scene(self, source_name: str, dest_name: str, activate: bool = False) -> "Scene":
        """
        Create a copy of existing scene.

        Args:
            source_name: Name of scene to copy.
            dest_name: Name for the copy (must be unique).
            activate: If True, set copy as active scene.

        Returns:
            Copied scene.

        Raises:
            KeyError: If source scene doesn't exist.
            ValueError: If dest scene already exists.
        """
        if source_name not in self._scenes:
            raise KeyError(f"Scene '{source_name}' not found")
        if dest_name in self._scenes:
            raise ValueError(f"Scene '{dest_name}' already exists")

        source = self._scenes[source_name]

        # Serialize and deserialize to create deep copy
        scene_data = source.serialize()
        dest = self._create_new_scene()
        dest.load_from_data(scene_data, context=None, update_settings=True)

        self._scenes[dest_name] = dest
        self._modes[dest_name] = SceneMode.INACTIVE
        self._paths[dest_name] = None  # Copy has no file path

        if activate:
            self._active_scene_name = dest_name
            self._modes[dest_name] = SceneMode.EDITOR

        self._notify_scene_changed(dest_name, dest)
        return dest

    def load_scene(self, name: str, path: str, activate: bool = True) -> "Scene":
        """
        Load scene from file.

        Args:
            name: Name for the loaded scene.
            path: File path to load from.
            activate: If True, set as active scene.

        Returns:
            Loaded scene.

        Raises:
            ValueError: If scene with this name already exists.
            FileNotFoundError: If file doesn't exist.
        """
        if name in self._scenes:
            raise ValueError(f"Scene '{name}' already exists")

        with open(path, "r", encoding="utf-8") as f:
            json_str = f.read()
        data = json.loads(json_str)

        scene = self._create_new_scene()

        # Support both new format "scene" and old "scenes"
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])
        if scene_data:
            scene.load_from_data(scene_data, context=None, update_settings=True)

        self._scenes[name] = scene
        self._modes[name] = SceneMode.INACTIVE
        self._paths[name] = path

        if activate:
            self._active_scene_name = name
            self._modes[name] = SceneMode.EDITOR

        # Notify editor start
        scene.notify_editor_start()

        self._notify_scene_changed(name, scene)

        # Restore editor state from file
        self._restore_editor_state(data)

        return scene

    def _restore_editor_state(self, data: dict) -> None:
        """Restore editor state from loaded data."""
        editor_data = data.get("editor", {})
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])

        # Camera
        editor_camera_data = editor_data.get("camera")
        if editor_camera_data is None and scene_data:
            editor_camera_data = scene_data.get("editor_camera")
        if editor_camera_data is not None and self._set_editor_camera_data is not None:
            self._set_editor_camera_data(editor_camera_data)

        # Selection
        selected_name = editor_data.get("selected_entity")
        if selected_name is None:
            editor_state = data.get("editor_state", {})
            selected_name = editor_state.get("selected_entity_name")
        if selected_name and self._select_entity_by_name is not None:
            self._select_entity_by_name(selected_name)

        # Displays
        displays_data = editor_data.get("displays")
        if self._set_displays_data is not None:
            self._set_displays_data(displays_data)

        # Expanded entities
        expanded_entities = editor_data.get("expanded_entities")
        if expanded_entities is not None and self._set_expanded_entities is not None:
            self._set_expanded_entities(expanded_entities)

    def save_scene(self, name: str, path: str | None = None) -> dict:
        """
        Save scene to file.

        Args:
            name: Scene name.
            path: File path. If None, uses previously saved path.

        Returns:
            Statistics dict.

        Raises:
            KeyError: If scene doesn't exist.
            ValueError: If no path provided and scene was never saved.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        scene = self._scenes[name]

        if path is None:
            path = self._paths.get(name)
        if path is None:
            raise ValueError(f"No path specified for scene '{name}'")

        # Collect editor state
        editor_data = self._collect_editor_state()

        scene_data = scene.serialize()
        _validate_serializable(scene_data, "scene")

        resources_data = self._resource_manager.serialize()
        _validate_serializable(resources_data, "resources")

        data = {
            "version": "1.0",
            "scene": scene_data,
            "editor": editor_data,
            "resources": resources_data,
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=numpy_encoder)

        # Atomic write
        dir_path = os.path.dirname(path) or "."
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            dir=dir_path,
            delete=False
        ) as f:
            f.write(json_str)
            temp_path = f.name

        os.replace(temp_path, path)
        self._paths[name] = path

        return {
            "entities": sum(1 for e in scene.entities if e.transform.parent is None and e.serializable),
            "materials": len(self._resource_manager.materials),
            "meshes": len(self._resource_manager._mesh_assets),
        }

    def _collect_editor_state(self) -> dict:
        """Collect current editor state for saving."""
        editor_data = {}

        if self._get_editor_camera_data is not None:
            camera_data = self._get_editor_camera_data()
            if camera_data is not None:
                editor_data["camera"] = camera_data

        if self._get_selected_entity_name is not None:
            selected_name = self._get_selected_entity_name()
            if selected_name is not None:
                editor_data["selected_entity"] = selected_name

        if self._get_displays_data is not None:
            displays_data = self._get_displays_data()
            if displays_data is not None:
                editor_data["displays"] = displays_data

        if self._get_expanded_entities is not None:
            expanded = self._get_expanded_entities()
            if expanded:
                editor_data["expanded_entities"] = expanded

        return editor_data

    def close_scene(self, name: str) -> None:
        """
        Close and destroy a scene.

        Args:
            name: Scene name.

        Raises:
            KeyError: If scene doesn't exist.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        scene = self._scenes.pop(name)
        self._modes.pop(name, None)
        self._paths.pop(name, None)

        # Update active scene if closing active
        if self._active_scene_name == name:
            self._active_scene_name = None

        scene.destroy()

    def get_scene(self, name: str) -> "Scene | None":
        """
        Get scene by name.

        Args:
            name: Scene name.

        Returns:
            Scene or None if not found.
        """
        return self._scenes.get(name)

    def get_scene_path(self, name: str) -> str | None:
        """Get file path for scene."""
        return self._paths.get(name)

    def has_scene(self, name: str) -> bool:
        """Check if scene exists."""
        return name in self._scenes

    def set_active(self, name: str) -> None:
        """
        Set scene as active.

        Args:
            name: Scene name.

        Raises:
            KeyError: If scene doesn't exist.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")
        self._active_scene_name = name

    # --- Scene Mode ---

    def set_mode(self, name: str, mode: SceneMode) -> None:
        """
        Set scene update mode.

        Args:
            name: Scene name.
            mode: New mode.

        Raises:
            KeyError: If scene doesn't exist.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")
        self._modes[name] = mode

    def get_mode(self, name: str) -> SceneMode:
        """
        Get scene mode.

        Args:
            name: Scene name.

        Returns:
            Scene mode.

        Raises:
            KeyError: If scene doesn't exist.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")
        return self._modes[name]

    # --- Editor Entities ---

    def add_editor_entities(self, name: str) -> None:
        """
        Add editor entities (gizmos, grid, etc.) to scene.

        Args:
            name: Scene name.

        Raises:
            KeyError: If scene doesn't exist.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        # Editor entities are managed by EditorCameraManager
        # This is called by EditorWindow after scene creation
        pass

    def remove_editor_entities(self, name: str) -> None:
        """
        Remove editor entities from scene.

        Args:
            name: Scene name.

        Raises:
            KeyError: If scene doesn't exist.
        """
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        # Editor entities are managed by EditorCameraManager
        pass

    # --- Update Cycle ---

    def tick(self, dt: float) -> None:
        """
        Update all active scenes.

        Args:
            dt: Delta time in seconds.
        """
        for name, scene in self._scenes.items():
            mode = self._modes.get(name, SceneMode.INACTIVE)

            if mode == SceneMode.INACTIVE:
                continue
            elif mode == SceneMode.EDITOR:
                # Editor mode: minimal update for gizmos, etc.
                scene.editor_update(dt)
            elif mode == SceneMode.GAME:
                # Game mode: full simulation
                scene.update(dt)

    # --- Reset/New Scene ---

    def close_all_scenes(self) -> None:
        """Close and destroy all scenes."""
        for name in list(self._scenes.keys()):
            scene = self._scenes.pop(name)
            scene.destroy()
        self._modes.clear()
        self._paths.clear()
        self._active_scene_name = None

    # --- Debug Info ---

    def get_debug_info(self) -> dict:
        """
        Get debug information about all scenes.

        Returns:
            Dict with scene info: {name: {mode, entity_count, path, active}, ...}
        """
        info = {}
        for name, scene in self._scenes.items():
            mode = self._modes.get(name, SceneMode.INACTIVE)
            info[name] = {
                "mode": mode.name,
                "entity_count": len(list(scene.entities)),
                "path": self._paths.get(name),
                "active": name == self._active_scene_name,
            }
        return info

    # --- Internal ---

    def _notify_scene_changed(self, name: str, scene: "Scene | None") -> None:
        """Notify callback about scene change."""
        if self._on_scene_changed is not None:
            self._on_scene_changed(name, scene)
