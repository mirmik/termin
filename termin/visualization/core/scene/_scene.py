"""Simple scene graph storing entities and global parameters."""

from __future__ import annotations

from typing import Callable, List, Sequence, TYPE_CHECKING

from termin.visualization.core.component import Component, InputComponent
from termin.visualization.core.entity import Entity
from termin._native.scene import TcScene, TcSceneLighting
from termin.geombase._geom_native import Vec3, Vec4
# Ray3 and SceneRaycastHit are used via C++ TcScene.raycast/closest_to_ray

from termin.visualization.core.viewport_config import (
    ViewportConfig,
    serialize_viewport_config,
    deserialize_viewport_config,
)
from termin.lighting import ShadowSettings


def is_overrides_method(obj, method_name, base_class):
    return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)


class Scene(TcScene):
    """Container for renderable entities and lighting data.

    Inherits from TcScene (C++ class) for optimized entity/component management.
    """

    def __init__(
        self,
        background_color: Sequence[float] | Vec4 | None = None,
        uuid: str | None = None,
        name: str = "",
    ):
        # Initialize C++ TcScene base class with name and uuid
        super().__init__(name, uuid or "")

        # Set Python wrapper for callbacks from C to Python
        self.set_py_wrapper(self)

        from termin._native import log
        log.info(f"[Scene] Created name='{name}', self={id(self):#x}")

        # Set initial background color in C++
        if background_color is not None:
            if isinstance(background_color, Vec4):
                TcScene.background_color.__set__(self, background_color)
            else:
                bc = background_color
                a = float(bc[3]) if len(bc) > 3 else 1.0
                TcScene.background_color.__set__(self, Vec4(float(bc[0]), float(bc[1]), float(bc[2]), a))
        else:
            # Default background color
            TcScene.background_color.__set__(self, Vec4(0.05, 0.05, 0.08, 1.0))

    @property
    def is_destroyed(self) -> bool:
        """Check if scene has been destroyed."""
        return not self.is_alive()

    # --- Background color (RGBA) - Vec4 property inherited from TcScene ---
    # background_color property is inherited from TcScene (returns/accepts Vec4)

    # --- Skybox (stored in tc_scene) ---
    # skybox_color, skybox_top_color, skybox_bottom_color - Vec3 properties inherited from TcScene

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
        type_int = self.get_skybox_type()
        return self._SKYBOX_TYPE_TO_STR.get(type_int, "gradient")

    @skybox_type.setter
    def skybox_type(self, value: str):
        type_int = self._SKYBOX_STR_TO_TYPE.get(value, self._SKYBOX_TYPE_GRADIENT)
        self.set_skybox_type(type_int)

    # skybox_mesh() -> use get_skybox_mesh() directly from TcScene
    # skybox_material() -> use ensure_skybox_material(type) directly from TcScene

    def _ensure_skybox_resources(self) -> None:
        """Ensure skybox mesh and material are created and set in tc_scene."""
        type_int = self.get_skybox_type()
        if type_int == self._SKYBOX_TYPE_NONE:
            return
        # This triggers lazy creation in C
        self.get_skybox_mesh()
        self.ensure_skybox_material(type_int)

    # --- Lighting (stored in tc_scene_lighting) ---
    # ambient_color (Vec3) and ambient_intensity (float) - properties inherited from TcScene

    def _get_lighting(self) -> TcSceneLighting | None:
        """Get TcSceneLighting view from C."""
        ptr = self.lighting_ptr()
        return TcSceneLighting(ptr) if ptr else None

    # light_components -> use get_components_of_type("LightComponent") directly

    @property
    def shadow_settings(self) -> ShadowSettings:
        """Shadow rendering settings."""
        lighting = self._get_lighting()
        if lighting is not None:
            return lighting.shadow_settings
        return ShadowSettings()

    @shadow_settings.setter
    def shadow_settings(self, value: ShadowSettings):
        lighting = self._get_lighting()
        if lighting is not None:
            lighting.shadow_settings = value

    # --- Collision World ---

    @property
    def collision_world(self):
        """Get the collision world for physics and raycasting."""
        return TcScene.collision_world(self)

    # colliders -> use get_components_of_type("ColliderComponent") directly
    # input_components -> use get_components_of_type("InputComponent") directly

    # --- Raycast ---
    # raycast(ray) and closest_to_ray(ray) are inherited from TcScene (C++ implementation)
    # They return SceneRaycastHit with properties: valid, entity, component, point_on_ray, point_on_collider, distance

    # --- Layer and flag names (stored in C) ---

    def get_layer_name(self, index: int) -> str:
        """Get layer name by index, or default 'Layer N' if not set."""
        name = TcScene.get_layer_name(self, index)
        return name if name else f"Layer {index}"

    def get_flag_name(self, index: int) -> str:
        """Get flag name by index, or default 'Flag N' if not set."""
        name = TcScene.get_flag_name(self, index)
        return name if name else f"Flag {index}"

    # set_layer_name(index, name), set_flag_name(index, name) -> inherited from TcScene

    # --- Viewport configuration (stored in C++ TcScene) ---
    # viewport_configs property -> inherited from TcScene
    # add_viewport_config(config) -> inherited from TcScene
    # viewport_config_at(index) -> inherited from TcScene
    # remove_viewport_config(index) -> inherited from TcScene
    # clear_viewport_configs() -> inherited from TcScene

    # --- Scene pipelines ---
    # Pipeline templates stored in C++ tc_scene, compiled pipelines owned by RenderingManager

    @property
    def scene_pipelines(self) -> List:
        """Get scene pipeline template handles (from C++ tc_scene)."""
        result = []
        count = self.pipeline_template_count()
        for i in range(count):
            result.append(self.pipeline_template_at(i))
        return result

    # --- Editor state (stored in metadata) ---

    _METADATA_EDITOR_PREFIX = "termin.editor"

    @property
    def editor_viewport_camera_name(self) -> str | None:
        """Get editor viewport camera name from metadata."""
        value = self.get_metadata_value(f"{self._METADATA_EDITOR_PREFIX}.viewport_camera_name")
        return value if isinstance(value, str) else None

    @editor_viewport_camera_name.setter
    def editor_viewport_camera_name(self, value: str | None) -> None:
        """Set editor viewport camera name in metadata."""
        self.set_metadata_value(f"{self._METADATA_EDITOR_PREFIX}.viewport_camera_name", value)

    @property
    def editor_entities_data(self) -> dict | None:
        """Get stored EditorEntities component data from metadata."""
        value = self.get_metadata_value(f"{self._METADATA_EDITOR_PREFIX}.entities_data")
        return value if isinstance(value, dict) else None

    @editor_entities_data.setter
    def editor_entities_data(self, value: dict | None) -> None:
        """Store EditorEntities component data in metadata."""
        self.set_metadata_value(f"{self._METADATA_EDITOR_PREFIX}.entities_data", value)

    # --- Entity management ---

    @property
    def entities(self) -> List[Entity]:
        """Get all entities in the scene (from pool)."""
        if not self.is_alive():
            return []
        return self.get_all_entities()

    # create_entity(name) -> inherited from TcScene
    # Creates entity in pool but does NOT register components or emit events.
    # Call add() after setup to complete registration.

    def add(self, entity: Entity) -> Entity:
        """Add entity to the scene, including all its children.

        Migrates entity to scene's pool if it's in a different pool.
        Components are automatically registered during migration.
        After add(), original entity reference is invalid - use the
        returned entity instead.
        """
        # Migrate entity to scene's pool (with all children)
        # Migration auto-registers components with scene
        entity = self.migrate_entity(entity)
        if not entity:
            raise RuntimeError("Failed to migrate entity to scene's pool")

        # Notify entity and children about scene addition
        self._notify_entity_added_recursive(entity)
        return entity

    def _notify_entity_added_recursive(self, entity: Entity, scene_ref=None):
        """Notify entity and children that they were added to scene."""
        if scene_ref is None:
            scene_ref = self.scene_ref()
        entity.on_added(scene_ref)
        for child in entity.children():
            self._notify_entity_added_recursive(child, scene_ref)

    def remove(self, entity: Entity):
        entity.on_removed()

        # Remove from C core (frees entity in pool, unregisters components)
        self.remove_entity(entity)

    # on_entity_added/on_entity_removed events removed

    # get_entity(uuid), get_entity_by_pick_id(pick_id), find_entity_by_name(name) -> inherited from TcScene

    # --- Component search ---

    def find_component(self, component_type: type) -> Component | None:
        """
        Find first component of given type in scene.

        Args:
            component_type: Component class to search for.

        Returns:
            First matching component or None.
        """
        for entity in self.get_all_entities():
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
        for entity in self.get_all_entities():
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
        # Use efficient C++ type-based lookup
        components = self.get_components_of_type(class_name)
        return components[0] if components else None

    # --- Component registration ---

    def register_component(self, component: Component):
        """Register component with tc_scene.

        Components are automatically added to type lists based on their type_name.
        Note: This is typically called automatically during entity migration.
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
            self.register_component_ptr(ptr)
        else:
            # C++ component - call base class method
            TcScene.register_component(self, component)

    def unregister_component(self, component: Component):
        """Unregister component from tc_scene.

        Components are automatically removed from type lists.
        Note: on_removed is called by C code in tc_entity_pool_free.
        """
        from termin.visualization.core.python_component import PythonComponent

        # Unregister from TcScene (removes from type lists automatically)
        if isinstance(component, PythonComponent):
            self.unregister_component_ptr(component.c_component_ptr())
        else:
            # C++ component - call base class method
            TcScene.unregister_component(self, component)

    # --- Update loop ---

    def update(self, dt: float):
        # Delegate to C core (includes profiling via tc_profiler)
        TcScene.update(self, dt)

    def editor_update(self, dt: float):
        """
        Update only components with active_in_editor=True.

        Called in editor mode to run editor-specific components.
        Uses the same _started flag as regular update().
        """
        # Delegate to C core
        TcScene.editor_update(self, dt)

    def before_render(self):
        """
        Call before_render() on all components that implement it.

        Should be called once per frame, before rendering begins.
        Used by SkeletonController to update bone matrices.
        """
        self._ensure_skybox_resources()
        TcScene.before_render(self)

    # --- Notification methods (inherited from TcScene) ---
    # notify_editor_start, notify_scene_inactive, notify_scene_active
    # All inherited from TcScene base class

    # --- Input dispatch ---
    # dispatch_mouse_button, dispatch_mouse_move, dispatch_scroll, dispatch_key
    # dispatch_mouse_button_editor, dispatch_mouse_move_editor, dispatch_scroll_editor, dispatch_key_editor
    # All inherited from TcScene base class

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
        # Fast path: use C-level dispatch when no filter is needed
        if filter_fn is None:
            if event_name == "on_mouse_button":
                self.dispatch_mouse_button(event)
            elif event_name == "on_mouse_move":
                self.dispatch_mouse_move(event)
            elif event_name == "on_scroll":
                self.dispatch_scroll(event)
            elif event_name == "on_key":
                self.dispatch_key(event)
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

        self.foreach_component_of_type("InputComponent", dispatch_to_component)

    # --- Serialization ---

    def serialize(self) -> dict:
        """
        Serialize the scene.

        Only saves root serializable entities (without parent).
        Child entities are serialized recursively inside their parents.
        """
        root_entities = [
            e for e in self.get_all_entities()
            if e.transform.parent is None and e.serializable
        ]
        serialized_entities = []
        for e in root_entities:
            data = e.serialize()
            if data is not None:
                serialized_entities.append(data)

        # Lighting settings
        ss = self.shadow_settings

        # Collect layer and flag names from C
        layer_names_dict = {}
        flag_names_dict = {}
        for i in range(64):
            ln = TcScene.get_layer_name(self, i)
            if ln:
                layer_names_dict[str(i)] = ln
            fn = TcScene.get_flag_name(self, i)
            if fn:
                flag_names_dict[str(i)] = fn

        # Collect pipeline template UUIDs
        pipeline_uuids = []
        for i in range(self.pipeline_template_count()):
            t = self.pipeline_template_at(i)
            if t.is_valid:
                pipeline_uuids.append({"uuid": t.uuid})

        result = {
            "uuid": self.uuid,
            "background_color": self.background_color.tolist(),
            "entities": serialized_entities,
            "layer_names": layer_names_dict,
            "flag_names": flag_names_dict,
            "viewport_configs": [serialize_viewport_config(vc) for vc in self.viewport_configs],
            "scene_pipelines": pipeline_uuids,
            # Lighting
            "ambient_color": self.ambient_color.tolist(),
            "ambient_intensity": self.ambient_intensity,
            "shadow_settings": ss.serialize(),
        }
        # Skybox settings
        result["skybox_type"] = self.skybox_type
        result["skybox_color"] = self.skybox_color.tolist()
        result["skybox_top_color"] = self.skybox_top_color.tolist()
        result["skybox_bottom_color"] = self.skybox_bottom_color.tolist()

        # Metadata (extensible storage for tools)
        metadata = self.get_metadata()
        if metadata:
            result["metadata"] = metadata

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
            bg = data.get("background_color", [0.05, 0.05, 0.08, 1.0])
            self.background_color = Vec4(bg[0], bg[1], bg[2], bg[3] if len(bg) > 3 else 1.0)
            # Lighting settings
            ac = data.get("ambient_color", [1.0, 1.0, 1.0])
            self.ambient_color = Vec3(ac[0], ac[1], ac[2])
            self.ambient_intensity = data.get("ambient_intensity", 0.1)
            if "shadow_settings" in data:
                ss = self.shadow_settings
                ss.load_from_data(data["shadow_settings"])
                self.shadow_settings = ss
            # Skybox settings
            self.skybox_type = data.get("skybox_type", "gradient")
            sc = data.get("skybox_color", [0.5, 0.7, 0.9])
            self.skybox_color = Vec3(sc[0], sc[1], sc[2])
            stc = data.get("skybox_top_color", [0.4, 0.6, 0.9])
            self.skybox_top_color = Vec3(stc[0], stc[1], stc[2])
            sbc = data.get("skybox_bottom_color", [0.6, 0.5, 0.4])
            self.skybox_bottom_color = Vec3(sbc[0], sbc[1], sbc[2])
            # Load layer and flag names (into C)
            for k, v in data.get("layer_names", {}).items():
                TcScene.set_layer_name(self, int(k), v)
            for k, v in data.get("flag_names", {}).items():
                TcScene.set_flag_name(self, int(k), v)
            # Load viewport configurations (stored in C++)
            self.clear_viewport_configs()
            for vc_data in data.get("viewport_configs", []):
                vc = deserialize_viewport_config(vc_data)
                self.add_viewport_config(vc)
            # Load scene pipelines from templates (stored in C++ tc_scene)
            from termin._native.render import TcScenePipelineTemplate
            self.clear_pipeline_templates()
            for sp_data in data.get("scene_pipelines", []):
                uuid = sp_data.get("uuid", "")
                if uuid:
                    template = TcScenePipelineTemplate.find_by_uuid(uuid)
                    if template.is_valid:
                        self.add_pipeline_template(template)

            # Note: Compiled pipelines are created by RenderingManager.attach_scene()
            # (not at deserialization time)

            # Load metadata (extensible storage for tools)
            if "metadata" in data:
                self.set_metadata(data["metadata"])

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

        if not self.is_alive():
            return

        log.info(f"[Scene] destroy() name='{self.name}', self={id(self):#x}")

        # Call on_destroy on all components via tc_ref (works for both C++ and Python)
        for entity in self.get_all_entities():
            for tc_ref in entity.tc_components:
                try:
                    tc_ref.on_destroy()
                except Exception as ex:
                    print(f"Error in destroy handler of component '{tc_ref}': {ex}")

        # Entity events removed

        # Release C core scene (call base class TcScene.destroy())
        TcScene.destroy(self)
