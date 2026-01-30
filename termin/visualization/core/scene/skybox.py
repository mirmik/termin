"""Skybox mesh and material factory for Scene."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.mesh import TcMesh
    from termin.visualization.core.material import Material


class SkyboxManager:
    """
    Creates skybox mesh and material for a scene.

    Actual skybox settings (type, colors) are stored in tc_scene.
    This class only handles lazy creation of GPU resources.

    Supports three skybox types:
    - "gradient": Two-color vertical gradient
    - "solid": Single solid color
    - "none": No skybox (transparent background)
    """

    def __init__(self):
        self._skybox_mesh: Optional["TcMesh"] = None
        self._gradient_material: Optional["Material"] = None
        self._solid_material: Optional["Material"] = None

    def ensure_mesh(self) -> "TcMesh":
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

    def get_material(self, skybox_type: str) -> "Material | None":
        """Get skybox material for given type. Creates lazily if needed."""
        if skybox_type == "none":
            return None
        if skybox_type == "solid":
            if self._solid_material is None:
                self._solid_material = self._create_solid_material()
            return self._solid_material
        # Default: gradient
        if self._gradient_material is None:
            self._gradient_material = self._create_gradient_material()
        return self._gradient_material

    def _create_gradient_material(self) -> "Material":
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
        return Material(name="SkyboxGradient", shader=shader)

    def _create_solid_material(self) -> "Material":
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
        return Material(name="SkyboxSolid", shader=shader)

    def destroy(self) -> None:
        """Release all resources."""
        self._skybox_mesh = None
        self._gradient_material = None
        self._solid_material = None
