"""
Editor camera management.

Handles creation and serialization of the editor's camera entity.

Coordinate convention: Y-forward, Z-up
  - X: right
  - Y: forward (depth, camera looks along +Y)
  - Z: up
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from termin.scene import Entity
from termin.input import INPUT_SOURCE_EDITOR, INPUT_SOURCE_RUNTIME
from termin.input._input_native import set_input_source_mask
from termin.render_components import OrbitCameraController
from termin.render_components.camera import CameraComponent

if TYPE_CHECKING:
    from termin.scene import TcScene as Scene


class EditorCameraManager:
    """
    Manages the editor camera and editor entities root.

    Handles:
    - Creation of EditorEntities root entity
    - Creation of editor camera with OrbitCameraController
    - Serialization/deserialization of camera state

    Supports two usage patterns:
    1. Legacy: EditorCameraManager(scene) - creates EditorEntities immediately
    2. New: EditorCameraManager() + attach_to_scene(scene) - deferred creation
    """

    def __init__(
        self,
        scene: "Scene | None" = None,
        *,
        camera_overlay_factory: Callable[[Entity, object], Entity | None] | None = None,
    ):
        self._scene: "Scene | None" = None
        self.editor_entities: Entity | None = None
        self.camera: CameraComponent | None = None
        self._camera_overlay_factory = camera_overlay_factory

        # Legacy: if scene provided, attach immediately
        if scene is not None:
            self.attach_to_scene(scene)

    def attach_to_scene(self, scene: "Scene") -> None:
        """
        Attach to a scene and create EditorEntities.

        Args:
            scene: Scene to attach to.
        """
        if self._scene is not None:
            self.detach_from_scene()

        self._scene = scene
        self._ensure_editor_entities_root()
        self._ensure_editor_camera()
        print(f"[DEBUG] EditorCameraManager.attach_to_scene: camera={self.camera}, camera.entity={self.camera.entity if self.camera else None}", flush=True)

    def detach_from_scene(self) -> None:
        """
        Detach from current scene and remove EditorEntities.

        After detach, camera and editor_entities become None.
        """
        if self._scene is None:
            return

        self.destroy_editor_entities()
        self._scene = None

    def _ensure_editor_entities_root(self) -> None:
        """Find or create root entity for editor objects (camera, gizmo, etc.)."""
        # EditorEntities live in standalone pool, not in scene
        if self.editor_entities is not None and self.editor_entities.valid():
            return

        editor_entities = Entity(name="EditorEntities")
        self.editor_entities = editor_entities

    def _ensure_editor_camera(self) -> None:
        """Find or create editor camera entity with OrbitCameraController."""
        # Look for existing camera under EditorEntities
        if self.editor_entities is not None:
            for child in self.editor_entities.transform.children:
                if child.entity and child.entity.name == "camera":
                    camera = child.entity.get_component_by_type("CameraComponent")
                    if camera is not None:
                        self.camera = camera
                        self._ensure_camera_controller(child.entity)
                        self._enable_editor_input_sources(child.entity)
                        print(f"[DEBUG] _ensure_editor_camera: FOUND existing camera={camera}", flush=True)
                        return

        # Create camera in standalone pool (not in scene)
        camera_entity = Entity(name="camera")
        camera_entity.add_component_by_name("CameraComponent")
        camera_entity.add_component_by_name("OrbitCameraController")
        camera = camera_entity.get_component_by_type("CameraComponent")
        print(f"[DEBUG] _ensure_editor_camera: CREATED new camera={camera}, entity={camera_entity}", flush=True)

        self._ensure_camera_controller(camera_entity)

        # Link camera to EditorEntities
        if self.editor_entities is not None:
            self.editor_entities.transform.link(camera_entity.transform)

        self.camera = camera
        self._enable_editor_input_sources(camera_entity)

    def _enable_editor_input_sources(self, camera_entity: Entity) -> None:
        """Opt editor-owned input components into editor viewport events."""
        orbit = camera_entity.get_component_by_type("OrbitCameraController")
        if orbit is not None:
            set_input_source_mask(
                orbit.c_component_ptr(),
                INPUT_SOURCE_RUNTIME | INPUT_SOURCE_EDITOR,
            )

    def _ensure_camera_controller(self, camera_entity: Entity):
        """Attach serialized mode state and optional frontend projection."""

        from termin.editor_core.resource_manager import ResourceManager

        controller_cls = ResourceManager.instance().get_component("EditorCameraUIController")
        if controller_cls is None:
            return None
        controller = camera_entity.get_component(controller_cls)
        if controller is None:
            controller = controller_cls()
            camera_entity.add_component(controller)
        if self._camera_overlay_factory is not None:
            overlay = self._camera_overlay_factory(camera_entity, controller)
            if overlay is not None:
                camera_entity.transform.link(overlay.transform)
        return controller

    @property
    def orbit_controller(self) -> OrbitCameraController | None:
        """Get OrbitCameraController for the editor camera."""
        if self.camera is None or self.camera.entity is None:
            return None
        return self.camera.entity.get_component_by_type("OrbitCameraController")

    def get_camera_data(self) -> dict | None:
        """
        Get camera state for serialization.

        Saves transform (position, rotation), radius, and EditorEntities components.
        """
        if self.camera is None or self.camera.entity is None:
            return None

        entity = self.camera.entity
        pose = entity.transform.global_pose()
        orbit_ctrl = self.orbit_controller

        result = {
            "position": [pose.lin.x, pose.lin.y, pose.lin.z],
            "rotation": [pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w],
            "radius": float(orbit_ctrl.radius) if orbit_ctrl else 5.0,
        }

        # Serialize EditorEntities hierarchy components
        if self.editor_entities is not None:
            editor_entities_data = self._serialize_editor_entities_components()
            if editor_entities_data:
                result["editor_entities"] = editor_entities_data

        return result

    def _serialize_editor_entities_components(self) -> dict | None:
        """Serialize components of all entities in EditorEntities hierarchy."""
        if self.editor_entities is None:
            return None

        entities = []
        self._collect_hierarchy(self.editor_entities, entities)

        result = {}
        for ent in entities:
            # Serialize only components (not the entity itself)
            import traceback
            components_data = []
            for ref in ent.tc_components:
                print(f"[DEBUG] serializing {ref.type_name} on '{ent.name}'", flush=True)
                try:
                    comp_data = ref.serialize()
                except Exception as e:
                    print(f"[DEBUG] FAILED {ref.type_name}: {e}", flush=True)
                    traceback.print_exc()
                    continue
                if comp_data:
                    components_data.append(comp_data)
            if components_data:
                result[ent.name] = components_data

        return result if result else None

    def set_camera_data(self, data: dict) -> None:
        """
        Apply saved camera state.

        Restores transform, radius, and EditorEntities components.
        """
        if self.camera is None or self.camera.entity is None:
            return

        entity = self.camera.entity
        orbit_ctrl = self.orbit_controller

        # Restore radius first (needed for _sync_from_transform)
        if orbit_ctrl and "radius" in data:
            orbit_ctrl.radius = float(data["radius"])

        # Restore transform
        if "position" in data and "rotation" in data:
            from termin.geombase import GeneralPose3, Vec3, Quat
            pos = data["position"]
            rot = data["rotation"]
            pose = GeneralPose3(
                Quat(rot[0], rot[1], rot[2], rot[3]),
                Vec3(pos[0], pos[1], pos[2]),
                Vec3(1.0, 1.0, 1.0),
            )
            entity.transform.set_global_pose(pose)

        # Sync orbit controller from new transform
        if orbit_ctrl:
            orbit_ctrl._sync_from_transform()

        # Restore EditorEntities components
        if "editor_entities" in data:
            self._deserialize_editor_entities_components(data["editor_entities"])

    def _deserialize_editor_entities_components(self, data: dict) -> None:
        """Deserialize components of all entities in EditorEntities hierarchy."""
        if self.editor_entities is None or not data:
            return

        entities = []
        self._collect_hierarchy(self.editor_entities, entities)

        # Get scene for handle resolution during deserialization
        # TcScene is now a non-owning reference, no need for scene_ref()
        scene_ref = self._scene

        # Before the native viewport projection existed, this controller lived
        # on the tcgui-only ``editor_ui`` child. Its state is frontend-neutral,
        # so migrate those persisted fields onto the camera component owner.
        legacy_overlay_components = data.get("editor_ui", [])
        camera_components = data.setdefault("camera", [])
        if not any(
            item.get("type") == "EditorCameraUIController"
            for item in camera_components
        ):
            for item in legacy_overlay_components:
                if item.get("type") == "EditorCameraUIController":
                    camera_components.append(item)
                    break

        for ent in entities:
            components_data = data.get(ent.name)
            if not components_data:
                continue

            for comp_data in components_data:
                comp_type = comp_data.get("type")
                comp_data_inner = comp_data.get("data", {})

                # Find matching component by type
                ref = ent.get_tc_component(comp_type)
                if ref:
                    ref.deserialize_data(comp_data_inner, scene_ref)

    def recreate_in_scene(self, new_scene: "Scene") -> None:
        """
        Recreate editor entities and camera in a new scene.

        Called when scene is reset or loaded.
        """
        self._scene = new_scene
        self.editor_entities = None
        self.camera = None

        self._ensure_editor_entities_root()
        self._ensure_editor_camera()

    def destroy_editor_entities(self) -> None:
        """Destroy EditorEntities (they live in standalone pool, not in scene)."""
        if self.editor_entities is None:
            return

        # Entities are in standalone pool, just drop references
        # The entities will be cleaned up when no longer referenced
        self.editor_entities = None
        self.camera = None

    def _collect_hierarchy(self, entity: Entity, result: list) -> None:
        """Recursively collect entity and all descendants."""
        result.append(entity)
        for child_tf in entity.transform.children:
            if child_tf.entity is not None:
                self._collect_hierarchy(child_tf.entity, result)
