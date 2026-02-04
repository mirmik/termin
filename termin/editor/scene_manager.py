"""
SceneManager - manages scene lifecycle and update cycles.

Thin Python wrapper over C++ SceneManager that stores TcScene objects
for Python access while delegating all logic to C++.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

from termin._native.scene import SceneManager as CxxSceneManager, SceneMode

__all__ = ["SceneManager", "SceneMode"]

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.resources import ResourceManager


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


class SceneManager(CxxSceneManager):
    """
    Manages scene lifecycle, update cycles, and editor state.

    Thin wrapper over C++ SceneManager that stores TcScene objects
    for Python access. Most logic is delegated to C++.
    """

    def __init__(
        self,
        resource_manager: "ResourceManager",
        on_after_render: Optional[Callable[[], None]] = None,
        on_before_scene_close: Optional[Callable[["Scene"], None]] = None,
        # Editor state callbacks (deprecated, use EditorWindow methods directly)
        get_editor_camera_data: Optional[Callable[[], dict]] = None,
        set_editor_camera_data: Optional[Callable[[dict], None]] = None,
        get_selected_entity_uuid: Optional[Callable[[], str | None]] = None,
        select_entity_by_uuid: Optional[Callable[[str], None]] = None,
        get_displays_data: Optional[Callable[[], list]] = None,
        set_displays_data: Optional[Callable[[list], None]] = None,
        get_expanded_entities: Optional[Callable[[], list[str]]] = None,
        set_expanded_entities: Optional[Callable[[list[str]], None]] = None,
        rescan_file_resources: Optional[Callable[[], None]] = None,
        # Deprecated parameters (ignored)
        scene_factory: Optional[Callable[[], "Scene"]] = None,
        use_internal_timer: bool = False,
    ):
        super().__init__()

        self._resource_manager = resource_manager
        self._on_after_render = on_after_render
        self._on_before_scene_close = on_before_scene_close

        # Editor state callbacks (kept for compatibility during transition)
        self._get_editor_camera_data = get_editor_camera_data
        self._set_editor_camera_data = set_editor_camera_data
        self._get_selected_entity_uuid = get_selected_entity_uuid
        self._select_entity_by_uuid = select_entity_by_uuid
        self._get_displays_data = get_displays_data
        self._set_displays_data = set_displays_data
        self._get_expanded_entities = get_expanded_entities
        self._set_expanded_entities = set_expanded_entities
        self._rescan_file_resources = rescan_file_resources

        # TcScene objects storage (Python needs these, not just handles)
        self._scenes: dict[str, "Scene"] = {}

        # Editor data storage (temporary during load)
        self._editor_data: dict[str, dict] = {}

        # Resources initialized flag
        self._resources_initialized: bool = False

    @property
    def resource_manager(self) -> "ResourceManager":
        """Resource manager."""
        return self._resource_manager

    @property
    def scene_names(self) -> list[str]:
        """List of all scene names."""
        return list(self._scenes.keys())

    def initialize_resources(self) -> None:
        """Initialize file resources once on startup."""
        if self._resources_initialized:
            return
        self._resources_initialized = True

        if self._rescan_file_resources is not None:
            self._rescan_file_resources()

    # --- Scene Factory ---

    def _create_new_scene(self, name: str = "") -> "Scene":
        """Create a new empty scene."""
        from termin.visualization.core.scene import Scene
        return Scene.create(name=name)

    # --- Scene Lifecycle ---

    def create_scene(self, name: str) -> "Scene":
        """Create a new empty scene with given name."""
        if name in self._scenes:
            raise ValueError(f"Scene '{name}' already exists")

        scene = self._create_new_scene(name)
        self._scenes[name] = scene

        # Register in C++ SceneManager
        self.register_scene(name, scene.scene_handle())

        return scene

    def add_existing_scene(self, name: str, scene: "Scene") -> None:
        """Register an existing scene with the manager."""
        if name in self._scenes:
            raise ValueError(f"Scene '{name}' already exists")

        self._scenes[name] = scene

        # Register in C++ SceneManager
        self.register_scene(name, scene.scene_handle())

    def copy_scene(self, source_name: str, dest_name: str) -> "Scene":
        """Create a copy of existing scene."""
        if source_name not in self._scenes:
            raise KeyError(f"Scene '{source_name}' not found")
        if dest_name in self._scenes:
            raise ValueError(f"Scene '{dest_name}' already exists")

        source = self._scenes[source_name]

        # Serialize and deserialize to create deep copy
        scene_data = source.serialize()
        dest = self._create_new_scene(dest_name)
        dest.load_from_data(scene_data, context=None, update_settings=True)

        self._scenes[dest_name] = dest

        # Register in C++ SceneManager
        self.register_scene(dest_name, dest.scene_handle())

        return dest

    def load_scene(self, name: str, path: str) -> "Scene":
        """Load scene from file."""
        if name in self._scenes:
            raise ValueError(f"Scene '{name}' already exists")

        # Use C++ file I/O
        json_str = CxxSceneManager.read_json_file(path)
        if not json_str:
            raise FileNotFoundError(f"Failed to read scene file: {path}")
        data = json.loads(json_str)

        # Set scene name BEFORE loading data (components need it for cache)
        scene_file_name = os.path.splitext(os.path.basename(path))[0]
        scene = self._create_new_scene(scene_file_name)

        # Support both new format "scene" and old "scenes"
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])
        if scene_data:
            scene.load_from_data(scene_data, context=None, update_settings=True)

        self._scenes[name] = scene

        # Store path in C++ SceneManager
        self.set_scene_path(name, path)

        # Register in C++ SceneManager
        self.register_scene(name, scene.scene_handle())

        # Store editor data for later application
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
        """Get stored editor data for a scene (used by EditorWindow)."""
        return self._editor_data.get(name, {})

    def clear_stored_editor_data(self, name: str) -> None:
        """Clear stored editor data for a scene."""
        self._editor_data.pop(name, None)

    def apply_editor_data(self, data: dict) -> None:
        """Apply editor data via callbacks (deprecated, use EditorWindow._apply_editor_state)."""
        if self._set_editor_camera_data is not None:
            camera_data = data.get("camera")
            if camera_data is not None:
                self._set_editor_camera_data(camera_data)

        if self._select_entity_by_uuid is not None:
            selected_uuid = data.get("selected_entity")
            if selected_uuid:
                self._select_entity_by_uuid(selected_uuid)

        if self._set_displays_data is not None:
            self._set_displays_data(data.get("displays"))

        if self._set_expanded_entities is not None:
            expanded_entities = data.get("expanded_entities")
            if expanded_entities is not None:
                self._set_expanded_entities(expanded_entities)

    def save_scene(self, name: str, path: str | None = None) -> dict:
        """Save scene to file."""
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        scene = self._scenes[name]

        if path is None:
            path = CxxSceneManager.get_scene_path(self, name)
        if not path:
            raise ValueError(f"No path specified for scene '{name}'")

        # Collect editor state via callbacks
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

        # Use C++ atomic write
        CxxSceneManager.write_json_file(path, json_str)

        # Update path in C++ SceneManager
        self.set_scene_path(name, path)

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
        """Close and destroy a scene."""
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        scene = self._scenes[name]

        # Notify before closing
        if self._on_before_scene_close is not None:
            self._on_before_scene_close(scene)

        # Unregister from C++ SceneManager (also clears path)
        self.unregister_scene(name)

        self._scenes.pop(name)
        self._editor_data.pop(name, None)

        scene.destroy()

    def get_scene(self, name: str) -> "Scene | None":
        """Get scene by name."""
        return self._scenes.get(name)

    def get_scene_path(self, name: str) -> str | None:
        """Get file path for scene."""
        path = CxxSceneManager.get_scene_path(self, name)
        return path if path else None

    def has_scene(self, name: str) -> bool:
        """Check if scene exists."""
        return name in self._scenes

    # --- Scene Mode ---

    def set_mode(self, name: str, mode: SceneMode) -> None:
        """Set scene update mode."""
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")

        old_mode = CxxSceneManager.get_mode(self, name)
        scene = self._scenes[name]

        # When transitioning to INACTIVE, notify callback
        if mode == SceneMode.INACTIVE and old_mode != SceneMode.INACTIVE:
            if self._on_before_scene_close is not None:
                self._on_before_scene_close(scene)

        # Set mode in C++
        CxxSceneManager.set_mode(self, name, mode)

    def get_mode(self, name: str) -> SceneMode:
        """Get scene mode."""
        if name not in self._scenes:
            raise KeyError(f"Scene '{name}' not found")
        return CxxSceneManager.get_mode(self, name)

    # --- Update Cycle ---

    def tick(self, dt: float) -> bool:
        """Update all active scenes."""
        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        profiler.begin_frame()

        # Call C++ tick which updates all scenes based on their mode
        should_render = CxxSceneManager.tick(self, dt)

        if should_render:
            with profiler.section("Scene Manager Before Render"):
                CxxSceneManager.before_render(self)

            from termin.visualization.render import RenderingManager
            with profiler.section("Scene Manager Render"):
                RenderingManager.instance().render_all(present=True)

            if self._on_after_render is not None:
                with profiler.section("Scene Manager After Render"):
                    self._on_after_render()

        profiler.end_frame()
        return should_render

    def set_render_callbacks(
        self,
        on_after_render: Optional[Callable[[], None]] = None,
    ) -> None:
        """Configure render callbacks."""
        if on_after_render is not None:
            self._on_after_render = on_after_render

    # --- Reset ---

    def close_all_scenes(self) -> None:
        """Close and destroy all scenes."""
        for name in list(self._scenes.keys()):
            self.close_scene(name)

    def reset(self) -> None:
        """Reset manager state."""
        self.close_all_scenes()
        self._editor_data.clear()

    # --- Debug Info ---

    def get_debug_info(self) -> dict:
        """Get debug information about all scenes."""
        info = {}
        for name, scene in self._scenes.items():
            mode = CxxSceneManager.get_mode(self, name)
            info[name] = {
                "mode": mode.name,
                "entity_count": len(list(scene.entities)),
                "path": CxxSceneManager.get_scene_path(self, name),
            }
        return info
