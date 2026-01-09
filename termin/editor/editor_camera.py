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
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.core.viewport_hint import ViewportHintComponent
from termin.visualization.ui.widgets.component import UIComponent

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class EditorCameraManager:
    """
    Manages the editor camera and editor entities root.

    Handles:
    - Creation of EditorEntities root entity
    - Creation of editor camera with OrbitCameraController
    - Serialization/deserialization of camera state
    """

    def __init__(self, scene: "Scene"):
        self._scene = scene
        self.editor_entities: Entity | None = None
        self.camera: PerspectiveCameraComponent | None = None

        self._ensure_editor_entities_root()
        self._ensure_editor_camera()

    def _ensure_editor_entities_root(self) -> None:
        """Find or create root entity for editor objects (camera, gizmo, etc.)."""
        for ent in self._scene.entities:
            if ent.name == "EditorEntities":
                self.editor_entities = ent
                return

        editor_entities = self._scene.create_entity("EditorEntities")
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

        # Create new camera in scene's pool
        camera_entity = self._scene.create_entity("camera")
        camera_entity.serializable = False
        camera = PerspectiveCameraComponent()
        camera_entity.add_component(camera)
        camera_entity.add_component(OrbitCameraController())

        # Add ViewportHintComponent for layer mask control
        hint = ViewportHintComponent()
        hint.pipeline_name = "(Editor)"
        # Layer mask: only layer 1 (editor UI layer)
        hint.layer_mask = 1 << 1  # Layer 1
        camera_entity.add_component(hint)

        # Create child entity for editor UI with layer=1
        ui_entity = self._scene.create_entity("editor_ui")
        ui_entity.serializable = False
        ui_entity.layer = 1  # Editor UI layer
        ui_comp = UIComponent()
        ui_comp.active_in_editor = True
        ui_comp.set_ui_layout_by_name("editor_camera_ui")
        ui_entity.add_component(ui_comp)

        # Add EditorCameraUIController if available (loaded from stdlib)
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        controller_cls = rm.get_component("EditorCameraUIController")
        if controller_cls is not None:
            ui_entity.add_component(controller_cls())

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
                for comp in ent.components:
                    comp_data = comp.serialize()
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

        for ent in entities:
            components_data = data.get(ent.name)
            if not components_data:
                continue

            for comp_data in components_data:
                comp_type = comp_data.get("type")
                comp_data_inner = comp_data.get("data", {})

                # Find matching component by type
                for comp in ent.components:
                    if comp.type_name() == comp_type:
                        comp.deserialize_data(comp_data_inner)
                        break

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
        """Remove EditorEntities from scene."""
        if self._scene is None or self._scene._tc_scene is None:
            return
        if self.editor_entities is None:
            return

        entities = []
        self._collect_hierarchy(self.editor_entities, entities)

        # Remove entities from scene (children first, then parent)
        for ent in reversed(entities):
            self._scene.remove(ent)

        self.editor_entities = None
        self.camera = None

    def _collect_hierarchy(self, entity: Entity, result: list) -> None:
        """Recursively collect entity and all descendants."""
        result.append(entity)
        for child_tf in entity.transform.children:
            if child_tf.entity is not None:
                self._collect_hierarchy(child_tf.entity, result)

