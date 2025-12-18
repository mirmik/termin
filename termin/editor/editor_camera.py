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

import numpy as np

from termin.visualization.core.entity import Entity
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.geombase.pose3 import Pose3

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

        editor_entities = Entity(name="EditorEntities", serializable=False)
        self._scene.add(editor_entities)
        self.editor_entities = editor_entities

    def _ensure_editor_camera(self) -> None:
        """Create editor camera entity with OrbitCameraController."""
        camera_entity = Entity(name="camera", pose=Pose3.identity(), serializable=False)
        camera = PerspectiveCameraComponent()
        camera_entity.add_component(camera)
        camera_entity.add_component(OrbitCameraController())

        if self.editor_entities is not None:
            self.editor_entities.transform.link(camera_entity.transform)
        self._scene.add(camera_entity)
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

        Returns:
            Dict with target, radius, azimuth, elevation or None if camera not available.
        """
        orbit_ctrl = self.orbit_controller
        if orbit_ctrl is None:
            return None

        return {
            "target": list(orbit_ctrl.target),
            "radius": float(orbit_ctrl.radius),
            "azimuth": float(orbit_ctrl.azimuth),
            "elevation": float(orbit_ctrl.elevation),
        }

    def set_camera_data(self, data: dict) -> None:
        """
        Apply saved camera state.

        Args:
            data: Dict with target, radius, azimuth, elevation.
        """
        orbit_ctrl = self.orbit_controller
        if orbit_ctrl is None:
            return

        if "target" in data:
            orbit_ctrl.target = np.array(data["target"], dtype=np.float32)
        if "radius" in data:
            orbit_ctrl.radius = float(data["radius"])
        if "azimuth" in data:
            orbit_ctrl.azimuth = float(data["azimuth"])
        if "elevation" in data:
            orbit_ctrl.elevation = float(data["elevation"])

        orbit_ctrl._update_pose()

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
