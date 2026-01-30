"""Simple scene graph storing entities and global parameters."""

from __future__ import annotations

from typing import Callable, List, Sequence, TYPE_CHECKING

import numpy as np

from termin.visualization.core.component import Component, InputComponent
from termin.visualization.core.entity import Entity
from termin._native.scene import TcScene
from termin.lighting import Light
from termin.visualization.render.components.light_component import LightComponent
from termin.geombase import Ray3
from termin.colliders.raycast_hit import RaycastHit
from termin.collision._collision_native import CollisionWorld
from termin.core import Event

from .lighting import LightingManager
from .skybox import SkyboxManager
from termin.visualization.core.viewport_config import ViewportConfig


if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.core.material import Material


def _vec3_to_np(v) -> np.ndarray:
    return np.array([v.x, v.y, v.z])


def is_overrides_method(obj, method_name, base_class):
    return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)


# Global current scene - set before update/start loops
# Temporary solution until proper scene wrapper architecture is implemented
_current_scene: "Scene | None" = None


def get_current_scene() -> "Scene | None":
    """Get the current scene being updated."""
    return _current_scene


class Scene:
    """Container for renderable entities and lighting data."""

    _destroyed: bool = False

    def __init__(
        self,
        background_color: Sequence[float] = (0.05, 0.05, 0.08, 1.0),
        uuid: str | None = None,
        name: str = "",
    ):
        self._destroyed = False

        # C core scene for optimized entity/component management
        self._tc_scene = TcScene()
        self._tc_scene.set_py_wrapper(self)

        # Identifiable fields
        self.uuid = uuid or ""
        self.name = name
        self.runtime_id = 0

        # Background color with alpha
        self._background_color = np.array(background_color, dtype=np.float32)

        # Skybox manager
        self._skybox = SkyboxManager()

        # Lighting manager
        self._lighting = LightingManager()
        self._lighting.tc_scene = self._tc_scene

        # Layer and flag names (index -> name)
        self.layer_names: dict[int, str] = {}  # 0-63
        self.flag_names: dict[int, str] = {}   # 0-63 (bit index)

        # Viewport configuration (display_name -> camera/region mapping)
        self._viewport_configs: List[ViewportConfig] = []

        # Scene pipelines (list of handles referencing ScenePipelineAsset)
        from termin.assets.scene_pipeline_handle import ScenePipelineHandle
        self._scene_pipelines: List[ScenePipelineHandle] = []

        # Compiled scene pipelines (name -> RenderPipeline)
        # Populated by compile_scene_pipelines(), runtime only
        from termin.visualization.render.framegraph.pipeline import RenderPipeline
        self._compiled_pipelines: dict[str, RenderPipeline] = {}
        # Target viewports for each compiled pipeline (name -> list of viewport names)
        self._pipeline_targets: dict[str, list[str]] = {}

        # Editor viewport state (runtime only, not serialized)
        # Stores camera name used in editor viewport for restore after game mode
        self.editor_viewport_camera_name: str | None = None

        # Editor entities state (runtime only, not serialized to scene file)
        # Stores EditorEntities component data for deserialization after game mode
        self._editor_entities_data: dict | None = None

        # Entity lifecycle events
        self._on_entity_added: Event[Entity] = Event()
        self._on_entity_removed: Event[Entity] = Event()

    @property
    def is_destroyed(self) -> bool:
        """Check if scene has been destroyed."""
        return self._destroyed

    # --- Background color (with alpha, C++ only has RGB) ---

    @property
    def background_color(self) -> np.ndarray:
        return self._background_color

    @background_color.setter
    def background_color(self, value):
        self._background_color = np.asarray(value, dtype=np.float32)

    # --- Skybox (stored in tc_scene) ---

    # Skybox type constants (match tc_skybox_type enum)
    _SKYBOX_TYPE_NONE = 0
    _SKYBOX_TYPE_GRADIENT = 1
    _SKYBOX_TYPE_SOLID = 2

    _SKYBOX_TYPE_TO_STR = {
        _SKYBOX_TYPE_NONE: "none",
        _SKYBOX_TYPE_GRADIENT: "gradient",
        _SKYBOX_TYPE_SOLID: "solid",
    }
    _SKYBOX_STR_TO_TYPE = {v: k for k, v in _SKYBOX_TYPE_TO_STR.items()}

    @property
    def skybox_type(self) -> str:
        type_int = self._tc_scene.get_skybox_type()
        return self._SKYBOX_TYPE_TO_STR.get(type_int, "gradient")

    @skybox_type.setter
    def skybox_type(self, value: str):
        type_int = self._SKYBOX_STR_TO_TYPE.get(value, self._SKYBOX_TYPE_GRADIENT)
        self._tc_scene.set_skybox_type(type_int)

    @property
    def skybox_color(self) -> np.ndarray:
        r, g, b = self._tc_scene.get_skybox_color()
        return np.array([r, g, b], dtype=np.float32)

    @skybox_color.setter
    def skybox_color(self, value):
        v = np.asarray(value, dtype=np.float32)
        self._tc_scene.set_skybox_color(float(v[0]), float(v[1]), float(v[2]))

    @property
    def skybox_top_color(self) -> np.ndarray:
        r, g, b = self._tc_scene.get_skybox_top_color()
        return np.array([r, g, b], dtype=np.float32)

    @skybox_top_color.setter
    def skybox_top_color(self, value):
        v = np.asarray(value, dtype=np.float32)
        self._tc_scene.set_skybox_top_color(float(v[0]), float(v[1]), float(v[2]))

    @property
    def skybox_bottom_color(self) -> np.ndarray:
        r, g, b = self._tc_scene.get_skybox_bottom_color()
        return np.array([r, g, b], dtype=np.float32)

    @skybox_bottom_color.setter
    def skybox_bottom_color(self, value):
        v = np.asarray(value, dtype=np.float32)
        self._tc_scene.set_skybox_bottom_color(float(v[0]), float(v[1]), float(v[2]))

    def skybox_mesh(self):
        """Get skybox cube mesh (TcMesh). Creates lazily if needed."""
        mesh = self._tc_scene.get_skybox_mesh()
        if not mesh.is_valid:
            mesh = self._skybox._ensure_skybox_mesh()
            self._tc_scene.set_skybox_mesh(mesh)
        return mesh

    def skybox_material(self) -> "Material | None":
        """Get skybox material based on current skybox_type. Creates lazily if needed."""
        if self.skybox_type == "none":
            return None
        # SkyboxManager creates material based on skybox_type stored in tc_scene
        # We need to sync type to SkyboxManager for material creation
        self._skybox.skybox_type = self.skybox_type
        material = self._skybox.material
        if material is not None:
            # Material is now alias for TcMaterial, pass directly
            self._tc_scene.set_skybox_material(material)
        return material

    def set_skybox_type(self, skybox_type: str) -> None:
        """Set skybox type."""
        self.skybox_type = skybox_type

    def _ensure_skybox_resources(self) -> None:
        """Ensure skybox mesh and material are created and set in tc_scene."""
        if self.skybox_type == "none":
            return
        # This triggers lazy creation and sets resources in tc_scene
        self.skybox_mesh()
        self.skybox_material()

    # --- Lighting delegation (backward compatibility) ---

    @property
    def lights(self) -> List[Light]:
        return self._lighting.lights

    @lights.setter
    def lights(self, value: List[Light]):
        self._lighting.lights = value

    @property
    def light_direction(self) -> np.ndarray:
        return self._lighting.light_direction

    @light_direction.setter
    def light_direction(self, value):
        self._lighting.light_direction = np.asarray(value, dtype=np.float32)

    @property
    def light_color(self) -> np.ndarray:
        return self._lighting.light_color

    @light_color.setter
    def light_color(self, value):
        self._lighting.light_color = np.asarray(value, dtype=np.float32)

    @property
    def ambient_color(self) -> np.ndarray:
        return self._lighting.ambient_color

    @ambient_color.setter
    def ambient_color(self, value):
        self._lighting.ambient_color = np.asarray(value, dtype=np.float32)

    @property
    def ambient_intensity(self) -> float:
        return self._lighting.ambient_intensity

    @ambient_intensity.setter
    def ambient_intensity(self, value: float):
        self._lighting.ambient_intensity = value

    @property
    def light_components(self) -> List[LightComponent]:
        """Get all light components from tc_scene type list."""
        return self._tc_scene.get_components_of_type("LightComponent")

    @property
    def shadow_settings(self):
        """Shadow rendering settings."""
        from .lighting import ShadowSettings
        return self._lighting.shadow_settings

    def build_lights(self) -> List[Light]:
        """Build world-space light parameters from all light components."""
        # Ensure skybox resources are ready before render
        self._ensure_skybox_resources()
        return self._lighting.build_lights()

    # --- Collision World ---

    @property
    def collision_world(self) -> CollisionWorld:
        """Get the collision world for physics and raycasting."""
        return self._tc_scene.collision_world()

    @property
    def colliders(self) -> List[Component]:
        """Get all collider components from tc_scene type list."""
        return self._tc_scene.get_components_of_type("ColliderComponent")

    @property
    def input_components(self) -> List[InputComponent]:
        """Get all input components from tc_scene type list."""
        return self._tc_scene.get_components_of_type("InputComponent")

    # --- Raycast ---

    def raycast(self, ray: Ray3):
        """
        Returns first intersection with any ColliderComponent
        where distance == 0 (exact hit).
        """
        result = {"hit": None, "ray_dist": float("inf")}
        origin = _vec3_to_np(ray.origin)

        def check_collider(comp):
            attached = comp.attached
            if attached is None:
                return True

            hit = attached.closest_to_ray(ray)
            if hit.distance != 0.0:
                return True

            p_ray = _vec3_to_np(hit.point_on_ray)
            d_ray = np.linalg.norm(p_ray - origin)

            if d_ray < result["ray_dist"]:
                result["ray_dist"] = d_ray
                result["hit"] = RaycastHit(
                    comp.entity, comp, p_ray, _vec3_to_np(hit.point_on_collider), 0.0
                )
            return True

        self._tc_scene.foreach_component_of_type("ColliderComponent", check_collider)
        return result["hit"]

    def closest_to_ray(self, ray: Ray3):
        """
        Returns closest object to ray (minimum distance).
        Does not require intersection.
        """
        result = {"hit": None, "dist": float("inf")}

        def check_collider(comp):
            attached = comp.attached
            if attached is None:
                return True

            hit = attached.closest_to_ray(ray)
            if hit.distance < result["dist"]:
                result["dist"] = hit.distance
                result["hit"] = RaycastHit(
                    comp.entity, comp,
                    _vec3_to_np(hit.point_on_ray),
                    _vec3_to_np(hit.point_on_collider),
                    hit.distance
                )
            return True

        self._tc_scene.foreach_component_of_type("ColliderComponent", check_collider)
        return result["hit"]

    # --- Layer and flag names ---

    def get_layer_name(self, index: int) -> str:
        """Get layer name by index, or default 'Layer N'."""
        return self.layer_names.get(index, f"Layer {index}")

    def get_flag_name(self, index: int) -> str:
        """Get flag name by bit index, or default 'Flag N'."""
        return self.flag_names.get(index, f"Flag {index}")

    def set_layer_name(self, index: int, name: str):
        """Set layer name. Empty name removes the entry."""
        if name:
            self.layer_names[index] = name
        else:
            self.layer_names.pop(index, None)

    def set_flag_name(self, index: int, name: str):
        """Set flag name. Empty name removes the entry."""
        if name:
            self.flag_names[index] = name
        else:
            self.flag_names.pop(index, None)

    # --- Viewport configuration ---

    @property
    def viewport_configs(self) -> List[ViewportConfig]:
        """Get viewport configurations for this scene."""
        return self._viewport_configs

    def add_viewport_config(self, config: ViewportConfig) -> None:
        """Add a viewport configuration."""
        self._viewport_configs.append(config)

    def remove_viewport_config(self, config: ViewportConfig) -> None:
        """Remove a viewport configuration."""
        if config in self._viewport_configs:
            self._viewport_configs.remove(config)

    def clear_viewport_configs(self) -> None:
        """Clear all viewport configurations."""
        self._viewport_configs.clear()

    # --- Scene pipelines ---

    @property
    def scene_pipelines(self) -> List:
        """Get scene pipeline handles."""
        return self._scene_pipelines

    def add_scene_pipeline(self, handle) -> None:
        """Add a scene pipeline handle."""
        self._scene_pipelines.append(handle)

    def remove_scene_pipeline(self, handle) -> None:
        """Remove a scene pipeline handle."""
        if handle in self._scene_pipelines:
            self._scene_pipelines.remove(handle)

    def clear_scene_pipelines(self) -> None:
        """Clear all scene pipeline handles."""
        self._scene_pipelines.clear()

    # --- Compiled pipelines (runtime) ---

    @property
    def compiled_pipelines(self) -> dict:
        """Get compiled scene pipelines (name -> RenderPipeline)."""
        return self._compiled_pipelines

    def compile_scene_pipelines(self) -> None:
        """
        Compile all scene pipeline assets into RenderPipelines.

        Clears existing compiled pipelines and recompiles from scene_pipelines handles.
        """
        from termin._native import log

        # Destroy old pipelines
        for pipeline in self._compiled_pipelines.values():
            pipeline.destroy()
        self._compiled_pipelines.clear()
        self._pipeline_targets.clear()

        # Compile from handles
        for handle in self._scene_pipelines:
            asset = handle.get_asset()
            if asset is None:
                log.warn(f"[Scene] Scene pipeline asset not found for handle")
                continue

            pipeline = asset.compile()
            if pipeline is None:
                log.warn(f"[Scene] Failed to compile scene pipeline '{asset.name}'")
                continue

            self._compiled_pipelines[asset.name] = pipeline
            self._pipeline_targets[asset.name] = list(asset.target_viewports)

    def get_compiled_pipeline(self, name: str):
        """
        Get compiled scene pipeline by name.

        Args:
            name: Pipeline asset name.

        Returns:
            RenderPipeline or None if not found.
        """
        return self._compiled_pipelines.get(name)

    def get_pipeline_targets(self, name: str) -> list[str]:
        """
        Get target viewport names for a compiled pipeline.

        Args:
            name: Pipeline name.

        Returns:
            List of viewport names or empty list.
        """
        return self._pipeline_targets.get(name, [])

    def destroy_compiled_pipelines(self) -> None:
        """Destroy all compiled pipelines and clear the dicts."""
        for pipeline in self._compiled_pipelines.values():
            pipeline.destroy()
        self._compiled_pipelines.clear()
        self._pipeline_targets.clear()

    # --- Editor entities data (runtime only) ---

    @property
    def editor_entities_data(self) -> dict | None:
        """Get stored EditorEntities component data."""
        return self._editor_entities_data

    @editor_entities_data.setter
    def editor_entities_data(self, value: dict | None) -> None:
        """Store EditorEntities component data for later deserialization."""
        self._editor_entities_data = value

    # --- Entity management ---

    @property
    def entities(self) -> List[Entity]:
        """Get all entities in the scene (from pool)."""
        return self._tc_scene.get_all_entities()

    def create_entity(self, name: str = "") -> Entity:
        """Create a new entity directly in scene's pool.

        Creates entity in pool but does NOT register components or emit events.
        Call add() after setup to complete registration, or use this for
        entities that need no component registration.

        Args:
            name: Entity name (optional)

        Returns:
            New Entity in scene's pool
        """
        return self._tc_scene.create_entity(name)

    def add_non_recurse(self, entity: Entity) -> Entity:
        """Add entity to the scene.

        Migrates entity to scene's pool if it's in a different pool.
        Old entity reference becomes invalid after migration.
        """
        global _current_scene

        # Migrate entity to scene's pool (if not already there)
        # This copies all data (transform, flags, components) to scene's pool
        # and invalidates the old entity handle
        entity = self._tc_scene.migrate_entity(entity)
        if not entity:
            raise RuntimeError("Failed to migrate entity to scene's pool")

        # Register all components with C core scene
        prev_scene = _current_scene
        _current_scene = self
        try:
            for component in entity.components:
                self.register_component(component)

            entity.on_added(self)
            self._on_entity_added.emit(entity)
        finally:
            _current_scene = prev_scene
        return entity

    def add(self, entity: Entity) -> Entity:
        """Add entity to the scene, including all its children.

        Note: Entity migration happens during add, which recursively migrates
        children. After add(), original entity reference is invalid - use the
        returned entity instead.
        """
        # add_non_recurse migrates entity to scene's pool (with all children)
        # So we don't need to iterate children - they're already migrated
        entity = self.add_non_recurse(entity)
        # Children were migrated together with parent, register them
        for child in entity.children():
            self._register_migrated_child(child)
        return entity

    def _register_migrated_child(self, entity: Entity):
        """Register a child entity that was already migrated with its parent."""
        global _current_scene

        prev_scene = _current_scene
        _current_scene = self
        try:
            for component in entity.components:
                self.register_component(component)
            entity.on_added(self)
            self._on_entity_added.emit(entity)
        finally:
            _current_scene = prev_scene

        # Recursively register children
        for child in entity.children():
            self._register_migrated_child(child)

    def remove(self, entity: Entity):
        # Emit event while entity is still valid
        self._on_entity_removed.emit(entity)
        entity.on_removed()

        # Remove from C core (frees entity in pool, unregisters components)
        self._tc_scene.remove_entity(entity)

    @property
    def on_entity_added(self) -> Event[Entity]:
        return self._on_entity_added

    @on_entity_added.setter
    def on_entity_added(self, value: Event[Entity]):
        pass  # __iadd__ modifies in place, setter is no-op

    @property
    def on_entity_removed(self) -> Event[Entity]:
        return self._on_entity_removed

    @on_entity_removed.setter
    def on_entity_removed(self, value: Event[Entity]):
        pass  # __iadd__ modifies in place, setter is no-op

    def get_entity(self, uuid: str) -> Entity | None:
        """O(1) lookup of entity by UUID using hash map."""
        return self._tc_scene.get_entity(uuid)

    def get_entity_by_pick_id(self, pick_id: int) -> Entity | None:
        """O(1) lookup of entity by pick_id using hash map."""
        return self._tc_scene.get_entity_by_pick_id(pick_id)

    def find_entity_by_uuid(self, uuid: str) -> Entity | None:
        """
        Find entity by UUID in the scene hierarchy.

        Searches through all entities and their children recursively.

        Args:
            uuid: The UUID to search for

        Returns:
            Entity with matching UUID or None if not found
        """
        for entity in self.entities:
            if entity.uuid == uuid:
                return entity
        return None

    def find_entity_by_name(self, name: str) -> Entity | None:
        """
        Find entity by name in the scene hierarchy.

        Searches through all entities and their children recursively.

        Args:
            name: The name to search for
        Returns:
            Entity with matching name or None if not found
        """
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None

    # --- Component search ---

    def find_component(self, component_type: type) -> Component | None:
        """
        Find first component of given type in scene.

        Args:
            component_type: Component class to search for.

        Returns:
            First matching component or None.
        """
        for entity in self.entities:
            comp = entity.get_component(component_type)
            if comp is not None:
                return comp
        return None

    def find_components(self, component_type: type) -> List[Component]:
        """
        Find all components of given type in scene.

        Args:
            component_type: Component class to search for.

        Returns:
            List of all matching components.
        """
        result = []
        for entity in self.entities:
            comp = entity.get_component(component_type)
            if comp is not None:
                result.append(comp)
        return result

    def find_component_by_name(self, class_name: str) -> Component | None:
        """
        Find first component by class name string.

        Args:
            class_name: Name of the component class (e.g. "TweenManagerComponent").

        Returns:
            First matching component or None.
        """
        for entity in self.entities:
            for comp in entity.components:
                if type(comp).__name__ == class_name:
                    return comp
        return None

    # --- Component registration ---

    def register_component(self, component: Component):
        """Register component with tc_scene.

        Components are automatically added to type lists based on their type_name.
        """
        from termin.visualization.core.python_component import PythonComponent

        is_python = isinstance(component, PythonComponent)

        # For Python components, check if method is overridden and set flags
        if is_python:
            if is_overrides_method(component, "update", PythonComponent):
                component.has_update = True
            if is_overrides_method(component, "fixed_update", PythonComponent):
                component.has_fixed_update = True

        # Register with TcScene (adds to type lists automatically)
        # on_added callback is called by C code in tc_scene_register_component
        if is_python:
            ptr = component.c_component_ptr()
            self._tc_scene.register_component_ptr(ptr)
        else:
            self._tc_scene.register_component(component)

    def unregister_component(self, component: Component):
        """Unregister component from tc_scene.

        Components are automatically removed from type lists.
        Note: on_removed is called by C code in tc_entity_pool_free.
        """
        from termin.visualization.core.python_component import PythonComponent

        # Unregister from TcScene (removes from type lists automatically)
        if isinstance(component, PythonComponent):
            self._tc_scene.unregister_component_ptr(component.c_component_ptr())
        else:
            self._tc_scene.unregister_component(component)

    # --- Update loop ---

    def update(self, dt: float):
        global _current_scene
        _current_scene = self
        try:
            # Delegate to C core (includes profiling via tc_profiler)
            self._tc_scene.update(dt)
        finally:
            _current_scene = None

    def editor_update(self, dt: float):
        """
        Update only components with active_in_editor=True.

        Called in editor mode to run editor-specific components.
        Uses the same _started flag as regular update().
        """
        global _current_scene
        _current_scene = self
        try:
            # Delegate to C core
            self._tc_scene.editor_update(dt)
        finally:
            _current_scene = None

    def before_render(self):
        """
        Call before_render() on all components that implement it.

        Should be called once per frame, before rendering begins.
        Used by SkeletonController to update bone matrices.
        """
        self._tc_scene.before_render()

    def notify_editor_start(self):
        """Notify all components that scene started in editor mode."""
        self._tc_scene.notify_editor_start()

    def notify_scene_inactive(self):
        """Notify all components that scene is becoming inactive."""
        self._tc_scene.notify_scene_inactive()

    def notify_scene_active(self):
        """Notify all components that scene is becoming active (from INACTIVE)."""
        self._tc_scene.notify_scene_active()

    # --- Input dispatch ---

    def dispatch_mouse_button(self, event) -> None:
        """Dispatch mouse button event to all input handler components."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_mouse_button(event)

    def dispatch_mouse_move(self, event) -> None:
        """Dispatch mouse move event to all input handler components."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_mouse_move(event)

    def dispatch_scroll(self, event) -> None:
        """Dispatch scroll event to all input handler components."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_scroll(event)

    def dispatch_key(self, event) -> None:
        """Dispatch key event to all input handler components."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_key(event)

    # --- Editor dispatch methods (with active_in_editor filter) ---

    def dispatch_mouse_button_editor(self, event) -> None:
        """Dispatch mouse button event to input handlers with active_in_editor=True."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_mouse_button_editor(event)

    def dispatch_mouse_move_editor(self, event) -> None:
        """Dispatch mouse move event to input handlers with active_in_editor=True."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_mouse_move_editor(event)

    def dispatch_scroll_editor(self, event) -> None:
        """Dispatch scroll event to input handlers with active_in_editor=True."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_scroll_editor(event)

    def dispatch_key_editor(self, event) -> None:
        """Dispatch key event to input handlers with active_in_editor=True."""
        if self._tc_scene is not None:
            self._tc_scene.dispatch_key_editor(event)

    def dispatch_input(self, event_name: str, event, filter_fn: Callable[[InputComponent], bool] | None = None):
        """Dispatch input event to InputComponents.

        Args:
            event_name: Name of the handler method (e.g., "on_mouse_button").
            event: Event object to dispatch.
            filter_fn: Optional filter function. If provided, only components
                       for which filter_fn(component) returns True receive the event.

        Note: For best performance without filter_fn, use the specific dispatch methods
        (dispatch_mouse_button, dispatch_mouse_move, dispatch_scroll, dispatch_key).
        """
        if self._tc_scene is None:
            return

        # Fast path: use C-level dispatch when no filter is needed
        if filter_fn is None:
            if event_name == "on_mouse_button":
                self._tc_scene.dispatch_mouse_button(event)
            elif event_name == "on_mouse_move":
                self._tc_scene.dispatch_mouse_move(event)
            elif event_name == "on_scroll":
                self._tc_scene.dispatch_scroll(event)
            elif event_name == "on_key":
                self._tc_scene.dispatch_key(event)
            return

        # Slow path with filter: iterate components and call methods
        def dispatch_to_component(component):
            if not filter_fn(component):
                return True
            handler = getattr(component, event_name, None)
            if handler:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Error in input handler '{event_name}' of component '{component}': {e}")
            return True

        self._tc_scene.foreach_component_of_type("InputComponent", dispatch_to_component)

    # --- Serialization ---

    def serialize(self) -> dict:
        """
        Serialize the scene.

        Only saves root serializable entities (without parent).
        Child entities are serialized recursively inside their parents.
        """
        root_entities = [
            e for e in self.entities
            if e.transform.parent is None and e.serializable
        ]
        serialized_entities = []
        for e in root_entities:
            data = e.serialize()
            if data is not None:
                serialized_entities.append(data)

        result = {
            "uuid": self.uuid,
            "background_color": list(self.background_color),
            "entities": serialized_entities,
            "layer_names": {str(k): v for k, v in self.layer_names.items()},
            "flag_names": {str(k): v for k, v in self.flag_names.items()},
            "viewport_configs": [vc.serialize() for vc in self._viewport_configs],
            "scene_pipelines": [h.serialize() for h in self._scene_pipelines],
        }
        result.update(self._lighting.serialize())
        # Skybox settings
        result["skybox_type"] = self.skybox_type
        result["skybox_color"] = list(self.skybox_color)
        result["skybox_top_color"] = list(self.skybox_top_color)
        result["skybox_bottom_color"] = list(self.skybox_bottom_color)
        return result

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "Scene":
        """Deserialize a scene."""
        scene = cls(
            name=data.get("name", ""),
            background_color=data.get("background_color", (0.05, 0.05, 0.08, 1.0)),
            uuid=data.get("uuid"),
        )
        scene.load_from_data(data, context, update_settings=True)
        return scene

    def load_from_data(self, data: dict, context=None, update_settings: bool = True) -> int:
        """
        Load data into existing scene.

        Parameters:
            data: Serialized scene data
            context: Deserialization context
            update_settings: Whether to update scene settings (background, light)

        Returns:
            Number of loaded entities
        """
        if update_settings:
            self.background_color = np.asarray(
                data.get("background_color", [0.05, 0.05, 0.08, 1.0]),
                dtype=np.float32
            )
            self._lighting.load_from_data(data)
            # Skybox settings
            self.skybox_type = data.get("skybox_type", "gradient")
            self.skybox_color = np.asarray(
                data.get("skybox_color", [0.5, 0.7, 0.9]),
                dtype=np.float32
            )
            self.skybox_top_color = np.asarray(
                data.get("skybox_top_color", [0.4, 0.6, 0.9]),
                dtype=np.float32
            )
            self.skybox_bottom_color = np.asarray(
                data.get("skybox_bottom_color", [0.6, 0.5, 0.4]),
                dtype=np.float32
            )
            # Load layer and flag names
            self.layer_names = {int(k): v for k, v in data.get("layer_names", {}).items()}
            self.flag_names = {int(k): v for k, v in data.get("flag_names", {}).items()}
            # Load viewport configurations
            self._viewport_configs = [
                ViewportConfig.deserialize(vc_data)
                for vc_data in data.get("viewport_configs", [])
            ]
            # Load scene pipelines
            from termin.assets.scene_pipeline_handle import ScenePipelineHandle
            self._scene_pipelines = [
                ScenePipelineHandle.deserialize(sp_data)
                for sp_data in data.get("scene_pipelines", [])
            ]

        entities_data = data.get("entities", [])

        # Two-phase deserialization:
        # Phase 1: Create all entities with hierarchy (no components)
        # Phase 2: Deserialize components (now all entities exist for reference resolution)

        # Collect (entity, data) pairs for phase 2
        entity_data_pairs: list[tuple[Entity, dict]] = []

        for ent_data in entities_data:
            self._deserialize_entity_hierarchy(ent_data, context, entity_data_pairs)

        # Phase 2: Deserialize components for all entities
        for ent, ent_data in entity_data_pairs:
            Entity.deserialize_components(ent, ent_data, context, scene=self)

        return len(entities_data)

    def _deserialize_entity_hierarchy(
        self,
        data: dict,
        context,
        entity_data_pairs: list[tuple[Entity, dict]]
    ) -> Entity | None:
        """Phase 1: Create entity with children, no components.

        Recursively creates entity hierarchy and collects (entity, data) pairs
        for component deserialization in phase 2.
        """
        ent = Entity.deserialize_base(data, context, scene=self)
        if ent is None:
            return None

        # Collect for phase 2
        entity_data_pairs.append((ent, data))

        # Deserialize children and set parent
        for child_data in data.get("children", []):
            child = self._deserialize_entity_hierarchy(child_data, context, entity_data_pairs)
            if child:
                child.set_parent(ent)

        return ent

    # --- Destroy ---

    def destroy(self) -> None:
        """
        Explicitly destroy scene and release all resources.

        Breaks cyclic references that prevent Python GC from collecting scene.
        Call this when scene is no longer needed (e.g., exit_game_mode, scene change).
        """
        from termin._native import log

        if self._destroyed:
            return
        self._destroyed = True


        # Destroy all components in all entities
        for entity in self.entities:
            for component in entity.components:
                if hasattr(component, 'destroy'):
                    component.destroy()

        # Destroy managers
        if self._lighting is not None:
            self._lighting.destroy()
            self._lighting = None

        # Clear collision world
        self._collision_world = None

        # Clear runtime editor state
        self._editor_entities_data = None
        self.editor_viewport_camera_name = None

        # Clear events (break subscriber references)
        self._on_entity_added.clear()
        self._on_entity_removed.clear()

        # Release C core scene
        if self._tc_scene is not None:
            self._tc_scene.destroy()
            self._tc_scene = None
