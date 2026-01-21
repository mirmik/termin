"""Skybox configuration and management for Scene."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from termin.mesh import TcMesh
    from termin.visualization.core.material import Material
    from termin._native import log


class SkyboxManager:
    """
    Manages skybox mesh and material for a scene.

    Supports three skybox types:
    - "gradient": Two-color vertical gradient
    - "solid": Single solid color
    - "none": No skybox (transparent background)
    """

    def __init__(self):
        self._skybox_mesh: Optional["TcMesh"] = None
        self._skybox_material: Optional["Material"] = None
        self.skybox_type: str = "gradient"
        self.skybox_color = np.array([0.5, 0.7, 0.9], dtype=np.float32)
        self.skybox_top_color = np.array([0.4, 0.6, 0.9], dtype=np.float32)
        self.skybox_bottom_color = np.array([0.6, 0.5, 0.4], dtype=np.float32)

    def _ensure_skybox_mesh(self) -> "TcMesh":
        """Lazily create skybox cube mesh."""
        if self._skybox_mesh is None:
            from termin.voxels.voxel_mesh import create_voxel_mesh
            from termin.visualization.render.skybox import _skybox_cube
            vertices, triangles = _skybox_cube()
            self._skybox_mesh = create_voxel_mesh(
                vertices=vertices,
                triangles=triangles,
                name="skybox_cube",
            )
        return self._skybox_mesh

    def _create_gradient_skybox_material(self) -> "Material":
        """Create gradient skybox material."""
        from termin.visualization.core.material import Material
        from termin._native.render import TcShader
        from termin.visualization.render.skybox import SKYBOX_VERTEX_SHADER, SKYBOX_FRAGMENT_SHADER
        shader = TcShader.from_sources(
            SKYBOX_VERTEX_SHADER,
            SKYBOX_FRAGMENT_SHADER,
            "",
            "SkyboxGradient",
        )
        material = Material(name="SkyboxGradient", shader=shader)
        # Note: color is already None/unset by default
        return material

    def _create_solid_skybox_material(self) -> "Material":
        """Create solid color skybox material."""
        from termin.visualization.core.material import Material
        from termin._native.render import TcShader
        from termin.visualization.render.skybox import SKYBOX_VERTEX_SHADER, SKYBOX_SOLID_FRAGMENT_SHADER
        shader = TcShader.from_sources(
            SKYBOX_VERTEX_SHADER,
            SKYBOX_SOLID_FRAGMENT_SHADER,
            "",
            "SkyboxSolid",
        )
        material = Material(name="SkyboxSolid", shader=shader)
        # Note: color is already None/unset by default
        return material

    @property
    def mesh(self) -> "TcMesh":
        """Get skybox cube mesh."""
        try:
            return self._ensure_skybox_mesh()
        except Exception as e:
            from termin._native import log
            log.error(f"[SkyboxManager] Error ensuring skybox mesh: {e}")
            raise

    @property
    def material(self) -> "Material | None":
        """Get skybox material based on current skybox_type."""
        if self.skybox_type == "none":
            return None
        if self._skybox_material is None:
            if self.skybox_type == "solid":
                self._skybox_material = self._create_solid_skybox_material()
            else:
                self._skybox_material = self._create_gradient_skybox_material()
        return self._skybox_material

    def set_type(self, skybox_type: str) -> None:
        """Set skybox type and reset material if type changed."""
        if self.skybox_type != skybox_type:
            self.skybox_type = skybox_type
            self._skybox_material = None

    def serialize(self) -> dict:
        """Serialize skybox settings."""
        return {
            "skybox_type": self.skybox_type,
            "skybox_color": list(self.skybox_color),
            "skybox_top_color": list(self.skybox_top_color),
            "skybox_bottom_color": list(self.skybox_bottom_color),
        }

    def load_from_data(self, data: dict) -> None:
        """Load skybox settings from serialized data."""
        self.set_type(data.get("skybox_type", "gradient"))
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

    def destroy(self) -> None:
        """Release all resources."""
        self._skybox_mesh = None
        self._skybox_material = None
