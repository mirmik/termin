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
from PyQt6.QtCore import QTimer, QElapsedTimer

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.resources import ResourceManager


class SceneMode(Enum):
    """Scene update mode."""
    INACTIVE = 0  # Loaded but not updated
    STOP = 1      # Editor update (gizmos, selection)
    PLAY = 2      # Full simulation


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
        on_after_render: Optional[Callable[[], None]] = None,
        use_internal_timer: bool = False,
        on_before_scene_close: Optional[Callable[["Scene"], None]] = None,
        # Editor state callbacks
        get_editor_camera_data: Optional[Callable[[], dict]] = None,
        set_editor_camera_data: Optional[Callable[[dict], None]] = None,
        get_selected_entity_uuid: Optional[Callable[[], str | None]] = None,
        select_entity_by_uuid: Optional[Callable[[str], None]] = None,
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
            on_after_render: Callback to run after render (e.g. editor features).
            use_internal_timer: If True, use internal QTimer for PLAY scenes.
            on_before_scene_close: Callback(scene) called before scene is destroyed.
            get_editor_camera_data: Callback to get editor camera state.
            set_editor_camera_data: Callback to set editor camera state.
            get_selected_entity_uuid: Callback to get selected entity UUID.
            select_entity_by_uuid: Callback to select entity by UUID.
            get_displays_data: Callback to get displays/viewports data.
            set_displays_data: Callback to set displays/viewports data.
            get_expanded_entities: Callback to get expanded entity names in tree.
            set_expanded_entities: Callback to set expanded entity names.
            rescan_file_resources: Callback to rescan project file resources.
        """
        self._resource_manager = resource_manager
        self._scene_factory = scene_factory
        self._on_after_render = on_after_render
        self._use_internal_timer = use_internal_timer
        self._on_before_scene_close = on_before_scene_close

        # Game loop timer (auto-starts when GAME scenes exist)
        self._game_timer = QTimer()
        self._game_timer.timeout.connect(self._game_loop_tick)
        self._elapsed_timer = QElapsedTimer()

        # Editor state callbacks
        self._get_editor_camera_data = get_editor_camera_data
        self._set_editor_camera_data = set_editor_camera_data
        self._get_selected_entity_uuid = get_selected_entity_uuid
        self._select_entity_by_uuid = select_entity_by_uuid
        self._get_displays_data = get_displays_data
        self._set_displays_data = set_displays_data
        self._get_expanded_entities = get_expanded_entities
        self._set_expanded_entities = set_expanded_entities
        self._rescan_file_resources = rescan_file_resources

        # Named scenes
        self._scenes: dict[str, "Scene"] = {}
        self._modes: dict[str, SceneMode] = {}
        self._paths: dict[str, str | None] = {}  # scene_name -> file_path
        self._editor_data: dict[str, dict] = {}  # scene_name -> stored editor data

        # Resources initialized flag
        self._resources_initialized: bool = False
        self._render_requested: bool = False

    @property
    def resource_manager(self) -> "ResourceManager":
        """Resource manager."""
        return self._resource_manager

    @property
    def scene_names(self) -> list[str]:
        """List of all scene names."""
        return list(self._scenes.keys())

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

    def _create_new_scene(self, name: str = "") -> "Scene":
        """Create a new empty scene."""
        if self._scene_factory is not None:
            return self._scene_factory()
        from termin.visualization.core.scene import Scene
        return Scene(name=name)

    # --- Scene Lifecycle ---

    def create_scene(self, name: str) -> "Scene":
        """
        Create a new empty scene with given name.

        Args:
            name: Scene name (must be unique).

        Returns:
            Created scene.

        Raises:
            ValueError: If scene with this name already exists.
        """
        if name in self._scenes:
            raise ValueError(f"Scene '{name}' already exists")

        scene = self._create_new_scene(name)
        self._scenes[name] = scene
        self._modes[name] = SceneMode.INACTIVE
        self._paths[name] = None

        return scene

    def copy_scene(self, source_name: str, dest_name: str) -> "Scene":
        """
        Create a copy of existing scene.

        Args:
            source_name: Name of scene to copy.
            dest_name: Name for the copy (must be unique).

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
        dest = self._create_new_scene(dest_name)
        dest.load_from_data(scene_data, context=None, update_settings=True)

        # Copy runtime state (not serialized)
        dest.editor_viewport_camera_name = source.editor_viewport_camera_name
        dest.editor_entities_data = source.editor_entities_data

        self._scenes[dest_name] = dest
        self._modes[dest_name] = SceneMode.INACTIVE
        self._paths[dest_name] = None  # Copy has no file path

        return dest

    def load_scene(self, name: str, path: str) -> "Scene":
        """
        Load scene from file.

        Args:
            name: Name for the loaded scene.
            path: File path to load from.

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

        # Set scene name BEFORE loading data (components need it for cache)
        scene_file_name = os.path.splitext(os.path.basename(path))[0]
        scene = self._create_new_scene(scene_file_name)

        # Support both new format "scene" and old "scenes"
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])
        if scene_data:
            scene.load_from_data(scene_data, context=None, update_settings=True)

        self._scenes[name] = scene
        self._modes[name] = SceneMode.INACTIVE
        self._paths[name] = path

        # Store editor data for later application (after editor entities are created)
        self._editor_data[name] = self._extract_editor_data(data)

        # Notify editor start
        scene.notify_editor_start()

        return scene

    def _extract_editor_data(self, data: dict) -> dict:
        """Extract editor data from loaded file in normalized form."""
        editor_data = data.get("editor", {})
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])

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

    def get_stored_editor_data(self, name: str) -> dict:
        """
        Get stored editor data for a scene.

        Returns editor data that was stored when scene was loaded.
        Used by EditorWindow to apply camera/selection/etc. after creating editor entities.
        """
        return self._editor_data.get(name, {})

    def clear_stored_editor_data(self, name: str) -> None:
        """Clear stored editor data for a scene (after it's been applied)."""
        self._editor_data.pop(name, None)

    def apply_editor_data(self, data: dict) -> None:
        """
        Apply editor data (camera, selection, displays, expanded entities).

        Called by EditorWindow after editor entities are created.
        """
        # Camera
        camera_data = data.get("camera")
        if camera_data is not None and self._set_editor_camera_data is not None:
            self._set_editor_camera_data(camera_data)

        # Selection
        selected_uuid = data.get("selected_entity")
        if selected_uuid and self._select_entity_by_uuid is not None:
            self._select_entity_by_uuid(selected_uuid)

        # Displays - always call to attach viewport_configs from scene
        if self._set_displays_data is not None:
            self._set_displays_data(data.get("displays"))

        # Expanded entities
        expanded_entities = data.get("expanded_entities")
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

        if self._get_selected_entity_uuid is not None:
            selected_uuid = self._get_selected_entity_uuid()
            if selected_uuid is not None:
                editor_data["selected_entity"] = selected_uuid

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

        scene = self._scenes[name]

        # Notify before closing (allows cleanup of viewports, etc.)
        if self._on_before_scene_close is not None:
            self._on_before_scene_close(scene)

        self._scenes.pop(name)
        self._modes.pop(name, None)
        self._paths.pop(name, None)
        self._editor_data.pop(name, None)

        self._update_timer_state()

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

        old_mode = self._modes.get(name, SceneMode.INACTIVE)
        scene = self._scenes[name]

        # When transitioning to INACTIVE, notify components and remove viewports
        if mode == SceneMode.INACTIVE and old_mode != SceneMode.INACTIVE:
            scene.notify_scene_inactive()
            if self._on_before_scene_close is not None:
                self._on_before_scene_close(scene)

        self._modes[name] = mode
        self._update_timer_state()

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
        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        profiler.begin_frame()

        has_play_scenes = any(m == SceneMode.PLAY for m in self._modes.values())
        
        for name, scene in self._scenes.items():
            mode = self._modes.get(name, SceneMode.INACTIVE)

            if mode == SceneMode.INACTIVE:
                continue
            elif mode == SceneMode.STOP:
                # Editor mode: minimal update for gizmos, etc.
                with profiler.section(f"Scene Editor Update: {name}"):
                    scene.editor_update(dt)
            elif mode == SceneMode.PLAY:
                # Game mode: full simulation
                with profiler.section(f"Scene Update: {name}"):
                    scene.update(dt)

        should_render = has_play_scenes or self._render_requested
        if should_render:
            self._render_requested = False  # Reset before callbacks to allow re-request
            with profiler.section(f"Scene Manager Before Render"):
                self.before_render()
            from termin.visualization.render import RenderingManager

            with profiler.section(f"Scene Manager Render"):
               RenderingManager.instance().render_all(present=True)
            if self._on_after_render is not None:
                with profiler.section(f"Scene Manager After Render"):
                    self._on_after_render()
        
        profiler.end_frame()

    def before_render(self) -> None:
        """
        Call before_render on all non-INACTIVE scenes.

        Updates bone matrices for skinning, etc.
        """
        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        for name, scene in self._scenes.items():
            mode = self._modes.get(name, SceneMode.INACTIVE)
            if mode != SceneMode.INACTIVE:
                with profiler.section(f"Scene: {name}"):
                    scene.before_render()

    def _update_timer_state(self) -> None:
        """Start or stop game timer based on whether GAME scenes exist."""
        if not self._use_internal_timer:
            return
        has_game_scenes = any(m == SceneMode.PLAY for m in self._modes.values())

        if has_game_scenes and not self._game_timer.isActive():
            self._elapsed_timer.start()
            self._game_timer.start(16)  # ~60 FPS
        elif not has_game_scenes and self._game_timer.isActive():
            self._game_timer.stop()

    def _game_loop_tick(self) -> None:
        """Called by game timer to update GAME scenes."""
        elapsed_ms = self._elapsed_timer.restart()
        dt = elapsed_ms / 1000.0

        self.tick(dt)

    def request_render(self) -> None:
        """Request render on the next tick."""
        self._render_requested = True

    def set_render_callbacks(
        self,
        on_after_render: Optional[Callable[[], None]] = None,
    ) -> None:
        """Configure render callbacks for the editor."""
        if on_after_render is not None:
            self._on_after_render = on_after_render

    # @property
    # def is_game_mode(self) -> bool:
    #     """True if any scene is in GAME mode."""
    #     return any(m == SceneMode.PLAY for m in self._modes.values())

    # --- Reset/New Scene ---

    def close_all_scenes(self) -> None:
        """Close and destroy all scenes."""
        for name in list(self._scenes.keys()):
            self.close_scene(name)

    def reset(self) -> None:
        """Reset manager state by closing all scenes and clearing editor data."""
        self.close_all_scenes()
        self._editor_data.clear()
        self._update_timer_state()

    # --- Debug Info ---

    def get_debug_info(self) -> dict:
        """
        Get debug information about all scenes.

        Returns:
            Dict with scene info: {name: {mode, entity_count, path}, ...}
        """
        info = {}
        for name, scene in self._scenes.items():
            mode = self._modes.get(name, SceneMode.INACTIVE)
            info[name] = {
                "mode": mode.name,
                "entity_count": len(list(scene.entities)),
                "path": self._paths.get(name),
            }
        return info
