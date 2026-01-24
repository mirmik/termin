"""
Editor camera management.

Handles creation and serialization of the editor's camera entity.

Coordinate convention: Y-forward, Z-up
  - X: right
  - Y: forward (depth, camera looks along +Y)
  - Z: up
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.entity import Entity
from termin.visualization.core.camera import CameraComponent, OrbitCameraController
from termin.visualization.core.viewport_hint import ViewportHintComponent
from termin.visualization.ui.widgets.component import UIComponent

# Import to register component in ComponentRegistry
from termin.editor.editor_camera_ui_controller import EditorCameraUIController  # noqa: F401

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


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

    def __init__(self, scene: "Scene | None" = None):
        self._scene: "Scene | None" = None
        self.editor_entities: Entity | None = None
        self.camera: PerspectiveCameraComponent | None = None

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
        editor_entities.serializable = False
        self.editor_entities = editor_entities

    def _ensure_editor_camera(self) -> None:
        """Find or create editor camera entity with OrbitCameraController."""
        # Look for existing camera under EditorEntities
        if self.editor_entities is not None:
            for child in self.editor_entities.transform.children:
                if child.entity and child.entity.name == "camera":
                    camera = child.entity.get_component(PerspectiveCameraComponent)
                    if camera is not None:
                        self.camera = camera
                        return

        # Create camera in standalone pool (not in scene)
        camera_entity = Entity(name="camera")
        camera_entity.serializable = False
        # camera = PerspectiveCameraComponent()
        # camera_entity.add_component(camera)
        # camera_entity.add_component(OrbitCameraController())
        camera_entity.add_component_by_name("CameraComponent")
        camera_entity.add_component_by_name("OrbitCameraController")
        camera = camera_entity.get_component(CameraComponent)

        # Add ViewportHintComponent for pipeline and layer mask control
        #hint = ViewportHintComponent()
        # All layers enabled by default (inherited from ViewportHintComponent.__init__)
        camera_entity.add_component_by_name("ViewportHintComponent")
        hint = camera_entity.get_component(ViewportHintComponent)
        hint.pipeline_name = "(Editor)"
        
        # Create child entity for editor UI with layer=1
        ui_entity = Entity(name="editor_ui")
        ui_entity.serializable = False
        ui_entity.layer = 1  # Editor UI layer
        #ui_comp = UIComponent()
        ui_entity.add_component_by_name("UIComponent")
        ui_comp = ui_entity.get_component(UIComponent)
        ui_comp.active_in_editor = True
        ui_comp.set_ui_layout_by_name("editor_camera_ui")

        # Add EditorCameraUIController if available (loaded from stdlib)
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        #controller_cls = rm.get_component("EditorCameraUIController")
        #if controller_cls is not None:
        #    ui_entity.add_component(controller_cls())
        ui_entity.add_component_by_name("EditorCameraUIController")

        # Link UI entity as child of camera
        camera_entity.transform.link(ui_entity.transform)

        # Link camera to EditorEntities
        if self.editor_entities is not None:
            self.editor_entities.transform.link(camera_entity.transform)

        self.camera = camera

    @property
    def orbit_controller(self) -> OrbitCameraController | None:
        """Get OrbitCameraController for the editor camera."""
        if self.camera is None or self.camera.entity is None:
            return None
        return self.camera.entity.get_component(OrbitCameraController)

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
            # Temporarily enable serializable
            old_serializable = ent.serializable
            ent.serializable = True
            try:
                # Serialize only components (not the entity itself)
                components_data = []
                for ref in ent.tc_components:
                    comp_data = ref.serialize()
                    if comp_data:
                        components_data.append(comp_data)
                if components_data:
                    result[ent.name] = components_data
            finally:
                ent.serializable = old_serializable

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

        # Get scene ref for handle resolution during deserialization
        scene_ref = self._scene._tc_scene.scene_ref() if self._scene else None

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

