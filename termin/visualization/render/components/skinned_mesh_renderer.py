"""SkinnedMeshRenderer - Renderer component for skinned meshes with skeletal animation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.editor.inspect_field import InspectField
from termin.mesh.skinned_mesh import SkinnedMesh3
from termin.visualization.core.entity import RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.resources import ResourceManager
from termin.visualization.render.components.mesh_renderer import MeshRenderer

if TYPE_CHECKING:
    from termin.skeleton.skeleton import SkeletonInstance


class SkinnedMeshRenderer(MeshRenderer):
    """
    Renderer component for skinned meshes with skeletal animation.

    Extends MeshRenderer with:
    - skeleton_instance: Runtime skeleton state for bone matrices
    - Automatic upload of u_bone_matrices uniform before drawing
    """

    inspect_fields = {
        **MeshRenderer.inspect_fields,
        # skeleton_instance is typically set programmatically, not in inspector
    }

    _DEBUG_INIT = True

    def __init__(
        self,
        mesh: MeshDrawable | SkinnedMesh3 | None = None,
        material: Material | None = None,
        skeleton_instance: "SkeletonInstance | None" = None,
        cast_shadow: bool = True,
    ):
        """
        Initialize SkinnedMeshRenderer.

        Args:
            mesh: Skinned mesh (MeshDrawable or SkinnedMesh3)
            material: Material to use for rendering
            skeleton_instance: Runtime skeleton for bone animation
            cast_shadow: Whether this object casts shadows
        """
        if self._DEBUG_INIT:
            print(f"[SkinnedMeshRenderer.__init__] mesh={mesh}, material={material}")
            if material:
                print(f"  material type: {type(material).__name__}")
                print(f"  material phases: {len(material.phases) if hasattr(material, 'phases') else 'N/A'}")
        super().__init__(mesh=mesh, material=material, cast_shadow=cast_shadow)
        self._skeleton_instance: "SkeletonInstance | None" = skeleton_instance
        if self._DEBUG_INIT:
            print(f"  After super().__init__: _material_handle._direct={self._material_handle._direct}")

    @property
    def skeleton_instance(self) -> "SkeletonInstance | None":
        """Get the skeleton instance for animation."""
        return self._skeleton_instance

    @skeleton_instance.setter
    def skeleton_instance(self, value: "SkeletonInstance | None"):
        """Set the skeleton instance for animation."""
        self._skeleton_instance = value

    _DEBUG_SKINNING = True  # Temporary debug flag

    def draw_geometry(self, context: RenderContext, geometry_id: str = "") -> None:
        """
        Draw skinned geometry with bone matrices.

        Uploads u_bone_matrices uniform to the currently bound shader
        before drawing the mesh.
        """
        if self.mesh is None:
            return

        # Upload bone matrices if we have a skeleton
        if self._skeleton_instance is not None:
            bone_matrices = self._skeleton_instance.get_bone_matrices()
            bone_count = len(bone_matrices)

            # Get current shader from context and upload bone matrices
            shader = context.current_shader
            if self._DEBUG_SKINNING:
                print(f"[SkinnedMeshRenderer] bone_count={bone_count}, shader={shader}")
                if bone_count > 0:
                    print(f"  bone_matrix[0] diagonal: {bone_matrices[0].diagonal()}")

            if shader is not None:
                shader.set_uniform_matrix4_array("u_bone_matrices", bone_matrices, bone_count)
                shader.set_uniform_int("u_bone_count", bone_count)
            elif self._DEBUG_SKINNING:
                print("  WARNING: context.current_shader is None!")

        # Draw the mesh
        self.mesh.draw(context)

    def serialize_data(self) -> dict:
        """Serialize SkinnedMeshRenderer."""
        data = super().serialize_data()
        # skeleton_instance is runtime state, not serialized
        # It's linked via SkeletonAsset UUID in the scene
        return data
